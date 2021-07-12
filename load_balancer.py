import time
# import flask
import boto3 as boto3
from flask import Flask, session, redirect, url_for, escape, request
import boto3
import botocore
from botocore import exceptions
import random

# USER_NAME = input("User name\n")
sess = boto3.Session()
AWS_ACCESS = sess.get_credentials().access_key
AWS_SECRET = sess.get_credentials().secret_key
REGION = sess.region_name
script_ec2_at_launch = f"""#!/bin/bash
    cd home/ubuntu
    sudo apt update
    git clone https://github.com/ehudb9/Users_Caching_in_the_cloud
    cd Users_Caching_in_the_cloud
    chmod 777 *.sh
    ./setup2.sh
    sudo aws configure set aws_access_key_id {AWS_ACCESS}
    sudo aws configure set aws_secret_access_key {AWS_SECRET} 
    sudo aws configure set region {REGION} 
    sudo python3 app1.py 
"""


def get_n_instances(tgNone: bool):
    result = None
    temp = ""
    digits = "1234567890"
    while result is None:
        result = input("input at least 3 number of instances\n")
        for char in result:
            temp = ""
            if char not in digits:
                result = None
                break
            else:
                temp += char
        else:
            # if temp == "0" or ((temp == "1" or temp == "2") and tgNone):
            if temp == "0":
                result = None
            else:
                result = temp
    return int(result)


#
# echo ok > healthcheck
#     touch Hello.txt
#     echo {REGION} > Hello.txt
#     #sudo python3 -m http.server 80
# cloud-config

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
        CidrIp="0.0.0.0/0",
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
    # was_created = None
    response = None
    try:
        print("Searching for existing ELB-Python load balancer")
        response = elb.describe_load_balancers(Names=["Elb-Python"])
        print("ELB-Python load balancer was found")
    #   was_created = False
    except exceptions.ClientError as e:
        if e.response['Error']['Code'] != 'LoadBalancerNotFound':
            raise e
        print("Creating our ELB-Python load balancer")
        #  was_created = True
        subnets = get_default_subnets()
        response = elb.create_load_balancer(
            Name="Elb-Python",
            Scheme='internet-facing',
            IpAddressType='ipv4',
            Subnets=subnets,
        )
    elb_arn = response["LoadBalancers"][0]["LoadBalancerArn"]
    vpc_id = response["LoadBalancers"][0]["VpcId"]
    print("Setting Security Group for ELB")
    results = init_security_groups(vpc_id)
    elb.set_security_groups(
        LoadBalancerArn=elb_arn,
        SecurityGroups=[results["elb-access"]]
    )
    target_group = None
    try:
        print("Searching for existing elb-tg Target Group")
        target_group = elb.describe_target_groups(
            Names=["elb-tg"],
        )
        print("elb-tg Target group was found")
    except exceptions.ClientError as e:
        if e.response['Error']['Code'] != 'TargetGroupNotFound':
            raise e
        print("Creating elb-tg Target-Group")
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
    print("Creating listeners for ELB")
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
    print("Ensuring the ELB is running")
    results = ensure_elb_setup_created()
    print("Get target-group")
    target_group = elb.describe_target_groups(
        Names=["elb-tg"],
    )
    instance = boto3.resource('ec2').Instance(instance_id)
    print("Ensuring the instance is running ")
    instance.wait_until_running()
    print("Give instance the same SG")
    sgs = [sg["GroupId"] for sg in instance.security_groups]
    sgs.append(results["instance-access"])
    instance.modify_attribute(
        Groups=sgs
    )
    target_group_arn = target_group["TargetGroups"][0]["TargetGroupArn"]
    print("Register instance {} in Target Group".format(instance_id))
    print("This can take up to 120 seconds to be healthy and may start as unhealthy".format(instance_id))
    elb.register_targets(
        TargetGroupArn=target_group_arn,
        Targets=[{
            "Id": instance_id,
            "Port": 80
        }]
    )


def instances_manager():
    # get all running_instances
    print("Ensuring elb is setup")
    ensure_elb_setup_created()
    print("Get all instances")
    res = ec2.describe_instances()
    # vars to assign the running and stopped
    print("Get all instances in TG")
    registered_instances = get_registered_instances_in_target_group()
    print("Get all instances which can be assigned")
    running_instances = []
    stopped_instances = []
    for i in res["Reservations"]:
        for instance in i["Instances"]:
            if instance["State"]["Name"] == "running" or instance["State"]["Name"] == "pending":
                if instance["State"]["Name"] == "pending":
                    ins = boto3.resource('ec2').Instance(instance["InstanceId"])
                    ins.wait_until_running()
                running_instances.append(instance["InstanceId"])
            if instance["State"]["Name"] == "stopped":
                stopped_instances.append(instance["InstanceId"])

    nInstances = get_n_instances(len(registered_instances) == 0)
    if len(registered_instances) == 0:
        print("Case 1 : Target group has no instances")
        if nInstances == len(running_instances):
            print("Case 1-1 : There are the same amount of existing running instances which just not assigned")
            for instance in running_instances:
                register_instance_in_elb(instance)
            return running_instances
        if nInstances < len(running_instances):
            print("Case 1-2 : There are more existing running instances which just not assigned")
            instances1 = random.sample(running_instances, nInstances)
            for instance in instances1:
                register_instance_in_elb(instance)
            return instances1
        else:
            # nInstances > running_instances
            print("Case 1-3 : There are less existing running instances which just not assigned")
            for instance in running_instances:
                register_instance_in_elb(instance)
            print("Case 1-3-1 : we need all stopped and running Instances and maybe more")
            if nInstances - len(running_instances) - len(stopped_instances) >= 0:
                # checking if the number of required instances
                # is greater or equal to the number of running and stopped instances

                # starting all stopped instances
                start_stopped_instances(stopped_instances)
                # create more and register
                instancesToCreate = nInstances - len(running_instances) - len(stopped_instances)
                if instancesToCreate > 0:
                    print("Creating {} Instances".format(instancesToCreate))
                    new = create_ec2_instances(instancesToCreate)
                    for instance in new:
                        register_instance_in_elb(instance)
                    running_instances.extend(new)
                return running_instances
            else:
                print("Case 1-3-2 : we need all running Instances and some of stopped")
                instances1 = random.sample(stopped_instances, nInstances - len(running_instances))
                start_stopped_instances(instances1)
                running_instances.extend(instances1)
                return running_instances

    if nInstances > len(registered_instances):
        print("Case 2 : The TG exists and have registered instances which we have to assign")
        print("See white space in code")
        # in this case we want to act the following
        # 1. run every single one of the registered instances
        print("Start all stopped instances in TG if there any")
        for ins in registered_instances:
            # if they are stopped we start them
            if ins in stopped_instances:
                start_stopped_instances([ins])
        # 2. find and isolate the rest of the instances (if they exist)
        print("Find other assignable Instances")
        unregistered_running = []
        unregistered_stopped = []
        for instance in running_instances:
            if instance not in registered_instances:
                unregistered_running.append(instance)
        for instance in stopped_instances:
            if instance not in registered_instances:
                unregistered_stopped.append(instance)
        # 3. find out the number of remaining instances to assign
        n1Instances = nInstances - len(registered_instances)
        # 4. prioritize the existing not registered running instances and add them
        if n1Instances < len(unregistered_running):
            running_instances_to_register = random.sample(unregistered_running, n1Instances)
            for instance_id in running_instances_to_register:
                register_instance_in_elb(instance_id)
        else:
            for instance_id in unregistered_running:
                register_instance_in_elb(instance_id)
            registered_instances.extend(unregistered_running)
            n2Instances = n1Instances - len(unregistered_running)
            if n2Instances == 0:
                return registered_instances.extend(unregistered_running)
            else:
                # 5. prioritize the existing and not registered stopped instances
                if n2Instances < len(unregistered_stopped):
                    stopped_instances_to_register_and_run = random.sample(unregistered_stopped, n2Instances)
                    start_stopped_instances(stopped_instances_to_register_and_run)
                    for instance_id in stopped_instances_to_register_and_run:
                        register_instance_in_elb(instance_id)
                    registered_instances.extend(stopped_instances_to_register_and_run)
                    return registered_instances
                else:
                    start_stopped_instances(unregistered_stopped)
                    for instance_id in unregistered_stopped:
                        register_instance_in_elb(instance_id)
                    registered_instances.extend(unregistered_stopped)
                    n3Instances = n2Instances - len(unregistered_stopped)
                    if n3Instances == 0:
                        return registered_instances
                    else:
                        # 6. create new instances
                        instances11 = create_ec2_instances(n3Instances)
                        for i in instances11:
                            register_instance_in_elb(i)


def get_targets_status():
    target_group = elb.describe_target_groups(
        Names=["elb-tg"],
    )
    target_group_arn = target_group["TargetGroups"][0]["TargetGroupArn"]
    health = elb.describe_target_health(TargetGroupArn=target_group_arn)
    healthy = []
    sick = {}
    for target in health["TargetHealthDescriptions"]:
        if target["TargetHealth"]["State"] == "unhealthy":
            sick[target["Target"]["Id"]] = target["TargetHealth"]["Description"]
        if target["TargetHealth"]["State"] == "healthy":
            healthy.append(target["Target"]["Id"])
    return healthy, sick


def create_ec2_instances(num_instances):
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


def start_stopped_instances(instances: list):
    if instances == []:
        return
    print("Start instances {}".format(instances))
    response = ec2.start_instances(InstanceIds=instances)
    return response


def stop_running_instances(instances: list):
    if instances == []:
        return
    print("Stop instances {}".format(instances))
    response = ec2.stop_instances(InstanceIds=instances)
    return response


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


def get_ip(instance_id: id):
    res = ec2.describe_instances()
    if instance_id not in get_registered_instances_in_target_group():
        return "Invalid ID"
    for i in res["Reservations"]:
        for instance in i["Instances"]:
            if instance["InstanceId"] == instance_id:
                return instance["PublicIpAddress"]
    return "Invalid ID"


def repartition():
    live_instances = get_targets_status()[0]
    all_data = {}
    for instance_id in live_instances:
        instance = boto3.resource('ec2').Instance(instance_id)
        # data =
        # fetch data
        # all_data.update(data)
        # clear data

    # for key in all_data :
    #   key, put1 (put with data) include hash with index
    #
    #
    #


elb = boto3.client('elbv2', region_name=REGION, aws_access_key_id=AWS_ACCESS, aws_secret_access_key=AWS_SECRET)
ec2 = boto3.client('ec2', region_name=REGION, aws_access_key_id=AWS_ACCESS, aws_secret_access_key=AWS_SECRET)
if __name__ == '__main__':
    instances_manager()
    while True:
        print(get_targets_status())
        time.sleep(5)
