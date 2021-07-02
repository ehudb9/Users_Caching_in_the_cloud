import time
# import flask
import boto3 as boto3
from flask import Flask, session, redirect, url_for, escape, request
import boto3
import botocore
from botocore import exceptions
import sys
import random
import json


def run():
    # USER_NAME = input("User name\n")
    sess = boto3.Session()
    AWS_ACCESS = sess.get_credentials().access_key
    AWS_SECRET = sess.get_credentials().secret_key
    REGION = sess.region_name
    nInstances = 2

    script_ec2_at_launch = f""" #EC2
    runcmd:
        cd home/ubuntu 
        git clone https://github.com/ehudb9/Users_Caching_in_the_cloud
        cd Users_Caching_in_the_cloud
        chmod 777 *.sh
        ./setup.sh
        sudo aws configure set aws_access_key_id {AWS_ACCESS}
        sudo aws configure set aws_secret_access_key {AWS_SECRET} 
        sudo aws configure set region {REGION}
        sudo python3 main.py
        # - sudo python3 ec2_server.py
    """

    def create_ec2_user_data(aws_access_key_id, aws_secret_access_key, aws_default_region):
        ec2_user_data = f"""#cloud-config
        
        """

        return ec2_user_data

    def get_n_instances():
        result = None
        temp = ""
        digits = "1234567890"
        while result is None:
            result = input("input a strictly positive number of instances\n")
            for char in result:
                if char not in digits:
                    temp = ""
                    result = None
                    break
                else:
                    temp += char
            else:
                if temp == "0":
                    result = None
                else:
                    result = temp
        return int(result)

    # path = "C:\\Temp\\" + str(USER_NAME) + "_AccessKeys.xltx"
    # nInstances = get_n_instances()

    # def start():
    #     book = xlrd.open_workbook(path)
    #     sheet = book.sheet_by_index(0)
    #     a = sheet.cell(1, 0).value
    #     b = sheet.cell(1, 1).value
    #     return a, b
    #
    #
    # AWS_ACCESS, AWS_SECRET = start()

    # print(AWS_SECRET)
    # print(AWS_ACCESS)

    def init_security_groups(vpc_id):
        try:
            response = ec2.describe_security_groups(GroupNames=["-elb-access1"])
            elb_access = response["SecurityGroups"][0]
            response = ec2.describe_security_groups(GroupNames=["cache-elb-instance-access-new"])
            instance_access = response["SecurityGroups"][0]
            return {
                "elb-access": elb_access["GroupId"],
                "instance-access": instance_access["GroupId"],
            }
        except exceptions.ClientError as e:
            if e.response['Error']['Code'] != 'InvalidGroup.NotFound':
                raise e

        vpc = ec2.describe_vpcs(VpcIds=[vpc_id])
        cidr_block = vpc["Vpcs"][0]["CidrBlock"]

        elb = ec2.create_security_group(
            Description="ELB External Access",
            GroupName="-elb-access1",
            VpcId=vpc_id
        )
        elb_sg = boto3.resource('ec2').SecurityGroup(elb["GroupId"])
        elb_sg.authorize_ingress(
            CidrIp="0.0.0.0/0",
            FromPort=80,
            ToPort=80,
            IpProtocol="TCP",
        )
        instances = ec2.create_security_group(
            Description="ELB Access to instances",
            GroupName="cache-elb-instance-access-new",
            VpcId=vpc_id
        )
        instance_sg = boto3.resource('ec2').SecurityGroup(instances["GroupId"])
        instance_sg.authorize_ingress(
            CidrIp=cidr_block,
            FromPort=80,
            ToPort=80,
            IpProtocol="TCP",
        )
        instance_sg.authorize_ingress(
            CidrIp="0.0.0.0/0",
            FromPort=22,
            ToPort=22,
            IpProtocol="TCP",
        )
        return {
            "elb-access": elb["GroupId"],
            "instance-access": instances["GroupId"]
        }

    def get_default_subnets():
        response = ec2.describe_subnets(
            Filters=[{"Name": "default-for-az", "Values": ["true"]}]
        )
        subnetIds = [s["SubnetId"] for s in response["Subnets"]]
        return subnetIds

    # creates the ELB as well as the target group
    # that it will distribute the requests to
    def ensure_elb_setup_created():
        was_created = None  # TODO on logger\app\server create handler
        response = None
        try:
            response = elb.describe_load_balancers(Names=["Elb-Python"])
            was_created = False
        except exceptions.ClientError as e:
            if e.response['Error']['Code'] != 'LoadBalancerNotFound':
                raise e
            was_created = True
            subnets = get_default_subnets()
            response = elb.create_load_balancer(
                Name="Elb-Python",
                Scheme='internet-facing',
                IpAddressType='ipv4',
                Subnets=subnets,
            )
        elb_arn = response["LoadBalancers"][0]["LoadBalancerArn"]
        vpc_id = response["LoadBalancers"][0]["VpcId"]
        results = init_security_groups(vpc_id)
        elb.set_security_groups(
            LoadBalancerArn=elb_arn,
            SecurityGroups=[results["elb-access"]]
        )
        target_group = None
        try:
            target_group = elb.describe_target_groups(
                Names=["elb-tg"],
            )
        except exceptions.ClientError as e:
            if e.response['Error']['Code'] != 'TargetGroupNotFound':
                raise e

            target_group = elb.create_target_group(
                Name="elb-tg",
                Protocol="HTTP",
                Port=80,
                VpcId=vpc_id,
                HealthCheckProtocol="HTTP",
                HealthCheckPort="80",
                HealthCheckEnabled=True,
                HealthCheckPath="/healthcheck",
                HealthCheckIntervalSeconds=5,
                HealthCheckTimeoutSeconds=2,
                HealthyThresholdCount=2,
                UnhealthyThresholdCount=2,
                TargetType="instance",
                Matcher={
                    'HttpCode': '200',
                }
            )
        target_group_arn = target_group["TargetGroups"][0]["TargetGroupArn"]
        listeners = elb.describe_listeners(LoadBalancerArn=elb_arn)
        if len(listeners["Listeners"]) == 0:
            elb.create_listener(
                LoadBalancerArn=elb_arn,
                Protocol="HTTP",
                Port=80,
                DefaultActions=[
                    {
                        "Type": "forward",
                        "TargetGroupArn": target_group_arn,
                        "Order": 100
                    }
                ]
            )
        return results

    def register_instance_in_elb(instance_id):
        results = ensure_elb_setup_created()
        target_group = elb.describe_target_groups(
            Names=["elb-tg"],
        )
        instance = boto3.resource('ec2').Instance(instance_id)
        instance.wait_until_running()
        sgs = [sg["GroupId"] for sg in instance.security_groups]
        sgs.append(results["instance-access"])
        instance.modify_attribute(
            Groups=sgs
        )
        target_group_arn = target_group["TargetGroups"][0]["TargetGroupArn"]
        elb.register_targets(
            TargetGroupArn=target_group_arn,
            Targets=[{
                "Id": instance_id,
                "Port": 80
            }]
        )

    def instances_manager():
        # get all instances
        res = ec2.describe_instances()
        instances = []
        for i in res["Reservations"]:
            for instance in i["Instances"]:
                if instance["State"]["Name"] == "running":
                    instances.append(instance["InstanceId"])
        if nInstances == len(instances):
            for instance in instances:
                register_instance_in_elb(instance)
            return instances
        # elif nInstances < len(instances):
        if nInstances < len(instances):
            instances1 = random.sample(instances, nInstances)
            for instance in instances1:
                register_instance_in_elb(instance)
            return instances1
        else:
            # nInstances > instances
            for instance in instances:
                register_instance_in_elb(instance)
            # create more and register
            instancesToCreate = nInstances - len(instances)
            new = create_ec2_instances(instancesToCreate)
            instances.extend(new)
            return instances

    def get_targets_status():
        target_group = elb.describe_target_groups(
            Names=["elb-tg"],
        )
        target_group_arn = target_group["TargetGroups"][0]["TargetGroupArn"]
        health = elb.describe_target_health(TargetGroupArn=target_group_arn)
        healthy = []
        sick = {}
        for target in health["TargetHealthDescriptions"]:
            if target["TargetHealth"]["State"] != "healthy":
                sick[target["Target"]["Id"]] = target["TargetHealth"]["Description"]
            else:
                healthy.append(target["Target"]["Id"])
        return healthy, sick

    def create_ec2_instances(num_instances):
        print(2)
        instances = ec2.run_instances(
            ImageId='ami-00399ec92321828f5',
            MinCount=int(num_instances),
            MaxCount=int(num_instances),
            InstanceType="t2.micro",
            SecurityGroups=["cache-elb-instance-access-new"],
            UserData=script_ec2_at_launch
        )
        ins = []
        for i in instances["Instances"]:
            ins.append(i["InstanceId"])
        return ins

    ##TODO : Check Correctness
    def start_stopped_instances(instances: list):
        if instances == []:
            return
        response = ec2.start_instances(InstanceIds=instances)
        # for instance in instances:
        #     instance.wait_until_running()
        return response

    ##TODO : Check Correctness
    def stop_running_instances(instances: list):
        if instances == []:
            return
        response = ec2.stop_instances(InstanceIds=instances)
        # Hibernate=True | False,
        # DryRun=True | False,
        # Force=True | False
        # )
        # for instance in instances:
        #     instance.wait_until_running()
        return response

    ##TODO : Check Correctness
    def get_registered_instances_in_target_group():
        target_group = elb.describe_target_groups(
            Names=["elb-tg"],
        )
        target_group_arn = target_group["TargetGroups"][0]["TargetGroupArn"]
        health = elb.describe_target_health(TargetGroupArn=target_group_arn)
        instances = []
        for target in health["TargetHealthDescriptions"]:
            instances.append(target["Target"]["Id"])
        return instances

    elb = boto3.client('elbv2', region_name=REGION, aws_access_key_id=AWS_ACCESS, aws_secret_access_key=AWS_SECRET)
    ec2 = boto3.client('ec2', region_name=REGION, aws_access_key_id=AWS_ACCESS, aws_secret_access_key=AWS_SECRET)
    instances_manager()
    return elb


# app = Flask(__name__)
#
#
# @app.route("/healthcheck")
# def index():
#     return get_targets_status()
#

# TODO need to find a way to connect the instances
if __name__ == '__main__':
    elb = run()
    while True:
        def get_targets_status():
            target_group = elb.describe_target_groups(
                Names=["elb-tg"],
            )
            target_group_arn = target_group["TargetGroups"][0]["TargetGroupArn"]
            health = elb.describe_target_health(TargetGroupArn=target_group_arn)
            healthy = []
            sick = {}
            for target in health["TargetHealthDescriptions"]:
                if target["TargetHealth"]["State"] != "healthy":
                    sick[target["Target"]["Id"]] = target["TargetHealth"]["Description"]
                else:
                    healthy.append(target["Target"]["Id"])
            return healthy, sick


        print(get_targets_status())
        time.sleep(5)
