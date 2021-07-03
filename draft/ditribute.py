import time
# import flask
from flask import Flask, session, redirect, url_for, escape, request
import boto3
import botocore
from botocore import exceptions
import sys
import random
import xxhash
# import Exception

##################################################################
from http.server import BaseHTTPRequestHandler, HTTPServer  # python3
from datetime import datetime
from furl import furl
# import jump
import xxhash
import load_balancer
import requests
import threading
import time

HASH = 2 ** 10


def get(str_key: str):
    # None or data:
    """
    Get the user from the relevant EC2 instance
    :param str_key:
    :return:None or data
    """
    pass


def put(str_key: str, data: str, expiration_date: int):
    """
    Manage the distribute: which user goes where
    :param str_key:
    :param data:
    :param expiration_date:
    :return:
    """
    pass


def get_live_node_list() -> []:
    return load_balancer.get_targets_status()


def get_val(key):
    nodes = get_live_node_list()[0]
    key_v_node_id = xxhash.xxh64_digest(key) % HASH

    node = nodes[key_v_node_id % len(nodes)]
    alt_node = node[(key_v_node_id + 1) % len(nodes)]

    try:
        return get(node, key)

    except:
        return get(alt_node, key)


def put_val(key, val):
    nodes = get_live_node_list()[0]
    key_v_node_id = xxhash.xxh64_digest(key) % HASH

    node = nodes[key_v_node_id % len(nodes)]
    alt_node = node[(key_v_node_id + 1) % len(nodes)]

    error = None
    try:
        return put(node, key, val)
    except Exception as e:
        error = e

    put(alt_node, key, val)

    if error is not None:
        raise error


def is_expirtion_date_invalid(request_args):
    date = request_args['expiration_date'].split('-')
    if (date[0].isnumeric() and len(date[0]) == 2) and (date[1].isnumeric() and len(date[1]) == 2) and (
            date[2].isnumeric() and len(date[2]) == 4):
        return False
    return True


class HandleRequests(BaseHTTPRequestHandler):
    def _set_headers(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        self._set_headers()
        f = furl(self.path)

        if f.path == "/update":
            pass
            # update_all_instances()
        if f.path == "/read":
            pass
            # response = read_request_handler(f.args['str_key'])
            # self.wfile.write("read request response: {}".format(response).encode('utf-8'))

        elif f.path == "/get":
            #             send read request to 2 ec2 by getting ip from hash func
            live_nodes, sick = get_live_node_list()
            node_id1 = get_val(f.args['str_key'])
            # node_id2 = (node_id1 + 1) % len(live_nodes)
            # ip1 = load_balancer.get_instance_public_ip(live_nodes[node_id1]['Id'])
            # ip2 = load_balancer.get_instance_public_ip(live_nodes[node_id2]['Id'])
            # response = get_request_handler(ip1, ip2, f.args)

            # self.wfile.write("get request response: {} ".format(response).encode('utf-8'))

        elif self.path == "/healthcheck":
            self.wfile.write("Ok".format().encode('utf-8'))

    def do_POST(self):
        self._set_headers()
        f = furl(self.path)

        if f.path == "/write":
            pass
            # response = write_request_handler(f.args['str_key'], f.args['data'], f.args['expiration_date'])
            # self.wfile.write("write request response: {}".format(response).encode('utf-8'))

        elif f.path == "/put":
            #           send write request to 2 ec2 by getting ip from hash func
            live_nodes, sick = get_live_node_list()
            node_id1 = put_val(f.args['str_key'], len(live_nodes))
            node_id2 = (node_id1 + 1) % len(live_nodes)
            ip1 = load_balancer.get_instance_public_ip(live_nodes[node_id1]['Id'])
            ip2 = load_balancer.get_instance_public_ip(live_nodes[node_id2]['Id'])
            # response = put_request_handler(ip1, ip2, f.args)
            # self.wfile.write("put request response: {}".format(response).encode('utf-8'))


# run the listener
host = ''
port = 80
instance_cache = dict()

my_ip = requests.get("http://169.254.169.254/latest/meta-data/public-ipv4").content.decode()

# try:
#     current_live_node_count = len(get_live_nodes()[0])
#     update_thread = threading.Thread(target=check_for_update, args=[])
#     update_thread.start()
#     HTTPServer((host, port), HandleRequests).serve_forever()
# finally:
#     exit()
##################################################
