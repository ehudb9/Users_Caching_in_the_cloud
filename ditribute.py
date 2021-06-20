import time
# import flask
from flask import Flask, session, redirect, url_for, escape, request
import boto3
import botocore
from botocore import exceptions
import sys
import random
import xxhash
#import Exception

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
    pass


def get_val(key):
    nodes = get_live_node_list()
    key_v_node_id = xxhash.xxh64_digest(key) % HASH

    node = nodes[key_v_node_id % len(nodes)]
    alt_node = node[(key_v_node_id + 1) % len(nodes)]

    try:
        return get(node, key)

    except:
        return get(alt_node, key)


def put_val(key, val):

    nodes = get_live_node_list()
    key_v_node_id = xxhash.xxh64_digest(key) % HASH

    node = nodes[key_v_node_id % len(nodes)]
    alt_node = node[(key_v_node_id + 1) % len(nodes)]

    error = None
    try:
        return put(node, key , val)
    except Exception as e:
        error = e

    put(alt_node , key , val)

    if error is not None:
        raise error