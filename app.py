import requests
import boto3
from cache_manager import CacheManager
from datanode import Data_node
from hash_ring import HashRing
import load_balancer
import os
import boto3
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, request

app = Flask(__name__)


def check_and_update():
    target_groups = load_balancer.get_targets_status()

    healthy = target_groups[0]
    for healthy_instance in healthy:
        private_dns = load_balancer.get_private_dns(healthy_instance)
        ins_onfig = {
            'hostname': healthy_instance,
            'instance': Data_node(instance_id=healthy_instance, private_dns=private_dns)
        }
        hash_ring.add_node(healthy_instance, ins_onfig)

    sick = list(target_groups[1].keys())
    for sick_instance in sick:
        if hash_ring.get_node(sick_instance):
            hash_ring.remove_node(sick_instance)


@app.route('/')
def index():
    return "Hello to Cache server!"


@app.route('/put', methods=['POST'])
##put (str_key, data, expiration_date)
def put_data():
    data = request.json
    key = data['key']
    value = data['value']
    expiration_date = data['expiration_date']
    cache_manager.put(key, value, expiration_date)
    return ""


@app.route('/put-replica', methods=['POST'])
def put_replica():
    data = request.json
    key = data['key']
    value = data['value']
    expiration_date = data['expiration_date']
    cache_manager.put_replica(key, value, expiration_date)
    return ""


@app.route('/get/<key>', methods=['GET'])
def get_data(key):
    return cache_manager.get_value_from_datanode(key)


@app.route('/get-content', methods=['GET'])
def get_content():
    return cache_manager.get_dn_content()


@app.route('/healthcheck', methods=['GET'])
def health():
    return "OK-I_AM-HEALTHY", 200


if __name__ == '__main__':
    instance_id = os.environ.get("INSTANCE_ID")
    hash_ring = HashRing()
    cache_manager = CacheManager(hash_ring, instance_id)

    scheduler = BackgroundScheduler()
    scheduler.add_job(func=check_and_update, trigger="interval", seconds=5)
    scheduler.start()
    app.run(port=80, host="0.0.0.0/0")
