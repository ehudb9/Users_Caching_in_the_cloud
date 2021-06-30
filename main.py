import time
# import flask
import boto3 as boto3
from flask import Flask, session, redirect, url_for, escape, request
import boto3
import botocore
from botocore import exceptions
import sys
import random
import xlrd
import json

# USER_NAME = input("User name\n")
USER_NAME = "cc"


# TODO Config and add excel file to C:\Temp
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


path = "C:\\Temp\\" + str(USER_NAME) + "_AccessKeys.xltx"
# nInstances = get_n_instances()
nInstances = 5


# print(path)
def start():
    book = xlrd.open_workbook(path)
    sheet = book.sheet_by_index(0)
    a = sheet.cell(1, 0).value
    b = sheet.cell(1, 1).value
    return a, b


AWS_ACCESS, AWS_SECRET = start()


# print(AWS_SECRET)
# print(AWS_ACCESS)

def init_security_groups(vpc_id):
    try:
        response = ec2.describe_security_groups(GroupNames=["-elb-access"])
        elb_access = response["SecurityGroups"][0]
        response = ec2.describe_security_groups(GroupNames=["cache-elb-instance-access"])
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
        GroupName="-elb-access",
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
        GroupName="cache-elb-instance-access",
        VpcId=vpc_id
    )
    instance_sg = boto3.resource('ec2').SecurityGroup(instances["GroupId"])
    instance_sg.authorize_ingress(
        CidrIp=cidr_block,
        FromPort=80,
        ToPort=80,
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
        was_created = True
    except exceptions.ClientError as e:
        if e.response['Error']['Code'] != 'LoadBalancerNotFound':
            raise e
        was_created = False
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
    # vars to assign the running and stopped
    registered_instances = get_registered_instances_in_target_group()
    running_instances = []
    stopped_instances = []

    for i in res["Reservations"]:
        for instance in i["Instances"]:
            if instance["State"]["Name"] == "running":
                running_instances.append(instance["InstanceId"])
            if instance["State"]["Name"] == "stopped":
                stopped_instances.append(instance["InstanceId"])

    if len(registered_instances) == 0:
        # handling the init case
        if nInstances == len(running_instances):
            for instance in running_instances:
                register_instance_in_elb(instance)
            return running_instances
        if nInstances < len(running_instances):
            instances1 = random.sample(running_instances, nInstances)
            to_stop = []
            for instance in instances1:
                register_instance_in_elb(instance)
            for i in running_instances:
                if i not in instances1:
                    to_stop.append(i)
            stop_running_instances(to_stop)
            return instances1
        else:
            # nInstances > instances
            for instance in running_instances:
                register_instance_in_elb(instance)
            ##TODO : Check Correctness from this line untill the end of function lines(243 - 335)
            ## and try and simplify it maybe functions
            if nInstances - len(running_instances) - len(stopped_instances) >= 0:
                # checking if the number of required instances
                # is greater or equal to the number of running and stopped instances

                # starting all stopped instances
                start_stopped_instances(stopped_instances)
                # if strictly bigger that means we have to create new instances else we are good
                instancesToCreate = nInstances - len(running_instances) - len(stopped_instances)
                if instancesToCreate > 0:
                    # creating more and register in recursive call
                    create_ec2_instances(instancesToCreate)
                return instances_manager()
            else:
                # else we just need to select (n - m) instances to restart running
                instances_to_start = random.sample(stopped_instances, nInstances - len(running_instances))
                start_stopped_instances(instances_to_start)
                return instances_manager()

    if len(registered_instances) <= nInstances:
        # if there is the same number we want to run all
        if len(registered_instances) == nInstances:
            for ins in registered_instances:
                # if they are stopped we start them
                if ins in stopped_instances:
                    start_stopped_instances([ins])
            return registered_instances

        # otherwise we want to act in the following order :
        # 1. isolate the running and stopped registered targets
        registered_running_instances = []
        registered_stopped_instances = []
        for ins1 in registered_instances:
            if ins1 in stopped_instances:
                registered_stopped_instances.append(ins1)
            if ins1 in running_instances:
                registered_running_instances.append(ins1)
        # 2. pick a (n-m) of the stopped instances and start them
        registered_stopped_instances_to_start = random.sample(stopped_instances,
                                                              nInstances - len(registered_running_instances))
        start_stopped_instances(registered_stopped_instances_to_start)
        # 3. combine those lists and return them
        registered_running_instances.extend(registered_stopped_instances_to_start)
        return registered_running_instances

    if nInstances > len(registered_instances):
        # in this case we want to act the following
        # 1. run every single one of the registered instances
        for ins in registered_instances:
            # if they are stopped we start them
            if ins in stopped_instances:
                start_stopped_instances([ins])
        # 2. find and isolate the rest of the instances (if they exist)
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
                # 4. prioritize the existing and not registered stopped instances
                if n2Instances < len(unregistered_stopped):
                    stopped_instances_to_register_and_run = random.sample(unregistered_stopped, n2Instances)
                    start_stopped_instances(stopped_instances_to_register_and_run)
                    for instance_id in stopped_instances_to_register_and_run:
                        register_instance_in_elb(instance_id)
                    registered_instances.extend(stopped_instances_to_register_and_run)
                    return registered_instances
                else:
                    for instance_id in unregistered_stopped:
                        register_instance_in_elb(instance_id)
                    registered_instances.extend(unregistered_stopped)
                    n3Instances = n2Instances - len(unregistered_stopped)
                    if n3Instances == 0:
                        return registered_instances
                    else:
                        # 5. create new instances
                        create_ec2_instances(n3Instances)


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
    instances = ec2.run_instances(
        ImageId='ami-00399ec92321828f5',
        MinCount=int(num_instances),
        MaxCount=int(num_instances),
        InstanceType="t2.micro",
        SecurityGroups=["cache-elb-instance-access"]
    )
    return instances


##TODO : Check Correctness
def start_stopped_instances(instances: list):
    response = ec2.start_instances(InstanceIds=instances)
    # for instance in instances:
    #     instance.wait_until_running()
    return response


##TODO : Check Correctness
def stop_running_instances(instances: list):
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


elb = boto3.client('elbv2', region_name='us-east-2', aws_access_key_id=AWS_ACCESS, aws_secret_access_key=AWS_SECRET)
ec2 = boto3.client('ec2', region_name='us-east-2', aws_access_key_id=AWS_ACCESS, aws_secret_access_key=AWS_SECRET)

app = Flask(__name__)


@app.route("/healthcheck")
def index():
    return "Hello World!"


instances_manager()
# TODO need to find a way to connect the instances
# while True:
#     print(get_targets_status())
#     time.sleep(3)
