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
nInstances = 3

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
    response = None
    try:
        response = elb.describe_load_balancers(Names=["Elb-Python"])
    except exceptions.ClientError as e:
        if e.response['Error']['Code'] != 'LoadBalancerNotFound':
            raise e
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
        # TODO else if group found get the instances and return.
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
    res = ec2.describe_instances()
    instances = []
    for i in res["Reservations"]:
        for instance in i["Instances"]:
            # instances.append()
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
        instancesToCreate = nInstances - len(instance)
        # for i in range(instancesToCreate):
            #TODO create and add instances while extracting the instance id + adding the base script
        return instances # ++TODO list of new instances

def get_targets_status():
    target_group = elb.describe_target_groups(
        Names=["elb-tg"],
    )
    target_group_arn = target_group["TargetGroups"][0]["TargetGroupArn"]
    health = elb.describe_target_health(TargetGroupArn=target_group_arn)
    print(health)
    healthy = []
    sick = {}
    for target in health["TargetHealthDescriptions"]:
        if target["TargetHealth"]["State"] == "unhealthy":
            sick[target["Target"]["Id"]] = target["TargetHealth"]["Description"]
        else:
            healthy.append(target["Target"]["Id"])
    return healthy, sick


elb = boto3.client('elbv2', region_name='us-east-2', aws_access_key_id=AWS_ACCESS, aws_secret_access_key=AWS_SECRET)
ec2 = boto3.client('ec2', region_name='us-east-2', aws_access_key_id=AWS_ACCESS, aws_secret_access_key=AWS_SECRET)
instances_manager()
#TODO need to find a way to connect the instances
print(get_targets_status())
