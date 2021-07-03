import boto3

from draft import http_server
import load_balancer

# hash ?
import xxhash

HASH = 2 ** 10


class CircularQueueCACHING:

    # constructor
    def __init__(self):  # initializing the class
        sess = boto3.Session()
        AWS_ACCESS = sess.get_credentials().access_key
        AWS_SECRET = sess.get_credentials().secret_key
        REGION = sess.region_name
        # ec2 = boto3.client('ec2', region_name=REGION, aws_access_key_id=AWS_ACCESS, aws_secret_access_key=AWS_SECRET)
        self.elb = boto3.client('elbv2', region_name=REGION, aws_access_key_id=AWS_ACCESS,
                                aws_secret_access_key=AWS_SECRET)
        # initializing queue with none
        self.nodes = load_balancer.get_registered_instances_in_target_group()
        self.size = len(self.nodes)
        self.queue = [None for i in range(self.size)]
        # self.front = self.rear = -1
        # loop -> Node for every instance (when next is determinded by hash

    # def get_next() :
    def health_check(self):
        healthy, sick = load_balancer.get_targets_status()
        if len(healthy) == self.size:
            return "OK"
        # case of unhealty
        else:
            pass
        return healthy

    def get_val(self, key):
        nodes = self.health_check()

        key_v_node_id = xxhash.xxh64_digest(key) % HASH

        node = nodes[key_v_node_id % len(nodes)]
        alt_node = node[(key_v_node_id + 1) % len(nodes)]
        alt_node2 = node[(key_v_node_id + 2) % len(nodes)]

        try:
            return http_server.get(node, key)

        except:
            try:
                return http_server.get(alt_node, key)
            except:
                return http_server.get(alt_node2, key)

    def put_val(self, key, val):

        nodes = self.health_check()
        key_v_node_id = xxhash.xxh64_digest(key) % HASH

        node = nodes[key_v_node_id % len(nodes)]
        alt_node = node[(key_v_node_id + 1) % len(nodes)]
        alt_node2 = node[(key_v_node_id + 1) % len(nodes)]

        error = None
        try:
            return http_server.put(node, key, val)
        except Exception as e:
            error = e

        http_server.put(alt_node, key, val)

        if error is not None:
            raise error

    # HTTP ACCESS POINTs
    def enqueue(self, data):
        # enter new Instance
        # verify that data is instance there is a function isinstance

        # condition if queue is full
        if ((self.rear + 1) % self.size == self.front):
            print(" Queue is Full\n")

        # condition for empty queue
        elif (self.front == -1):
            self.front = 0
            self.rear = 0
            self.queue[self.rear] = data
        else:
            # next position of rear
            self.rear = (self.rear + 1) % self.size
            self.queue[self.rear] = data

    def dequeue(self, values: list):
        # need to extract every unhealthy node and readjust the data
        if (self.front == -1):  # condition for empty queue
            print("Queue is Empty\n")

        # condition for only one element
        elif (self.front == self.rear):
            temp = self.queue[self.front]
            self.front = -1
            self.rear = -1
            return temp
        else:
            temp = self.queue[self.front]
            self.front = (self.front + 1) % self.size
            return temp

    def display(self):
        # condition for empty queue
        if (self.front == -1):
            print("Queue is Empty")

        elif (self.rear >= self.front):
            print("Elements in the circular queue are:",
                  end=" ")
            for i in range(self.front, self.rear + 1):
                print(self.queue[i], end=" ")
            print()

        else:
            print("Elements in Circular Queue are:",
                  end=" ")
            for i in range(self.front, self.size):
                print(self.queue[i], end=" ")
            for i in range(0, self.rear + 1):
                print(self.queue[i], end=" ")
            print()

        if ((self.rear + 1) % self.size == self.front):
            print("Queue is Full")


# Driver Code
ob = CircularQueueCACHING(5)
ob.enqueue(14)
ob.enqueue(22)
ob.enqueue(13)
ob.enqueue(-6)
ob.display()
print("Deleted value = ", ob.dequeue())
print("Deleted value = ", ob.dequeue())
ob.display()
ob.enqueue(9)
ob.enqueue(20)
ob.enqueue(5)
ob.display()
