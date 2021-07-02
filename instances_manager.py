import load_balancer
import random


def instances_manager():
    # get all instances
    res = load_balancer.ec2.describe_instances()
    instances = []
    for i in res["Reservations"]:
        for instance in i["Instances"]:
            if instance["State"]["Name"] == "running":
                instances.append(instance["InstanceId"])
    if load_balancer.nInstances == len(instances):
        for instance in instances:
            load_balancer.register_instance_in_elb(instance)
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