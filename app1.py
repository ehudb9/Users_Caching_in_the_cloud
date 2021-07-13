from flask import Flask
from flask import request as req
import requests
import load_balancer
import json
import time
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import xxhash
import jump
import random

app = Flask(__name__)


@app.route('/healthcheck', methods=['GET'])
def health():
    return "OK", 200


@app.route('/', methods=['GET'])
def land():
    return "YES", 200


@app.route('/test', methods=['GET'])
def land2():
    return "TEST", 202


@app.route('/get', methods=['GET', 'POST'])
def get():
    key = req.args.get('str_key')
    data = None
    res = None
    try:
        hashed_str_key = my_vars.hash_index(key)
        instance_index = jump.hash(int(hashed_str_key) % len(my_vars.live_nodes), len(my_vars.live_nodes))
        instance_to_get_from = load_balancer.get_ip(my_vars.live_nodes[instance_index])
        backup_instance_ip = load_balancer.get_ip(my_vars.live_nodes[instance_index - 1])
        try:
            if instance_to_get_from == my_vars.ip_address:
                res = json.dumps(cache.get_data(key)), 200
            else:
                res = requests.post(my_vars.url_generator(instance_to_get_from, "get_from_instance",
                                                          f'str_key={req.args.get("str_key")}')).json()
            return res
        except:
            try:
                if backup_instance_ip == my_vars.ip_address:
                    res = json.dumps(cache.get_data(key)), 200
                else:
                    res = requests.post(my_vars.url_generator(instance_to_get_from, "get_from_instance",
                                                              f'str_key={req.args.get("str_key")}')).json()
                return res
            except:
                return "ERR", 403
    except:
        return "data doesn't exist instance or expired", 404


@app.route('/put', methods=['POST', 'GET'])
def post():
    try:
        str_key = req.args.get('str_key')
        data = req.args.get('data')
        if str_key is None or data is None:
            raise Exception
    except:
        return None, 400
    try:
        date = req.args.get('expiration_date')
    except:
        date = None
    try:
        hashed_str_key = my_vars.hash_index(str_key)
        instance_index = jump.hash(int(hashed_str_key) % len(my_vars.live_nodes), len(my_vars.live_nodes))
        instance_to_put_in_ip = load_balancer.get_ip(my_vars.live_nodes[instance_index])
        backup_instance_ip = load_balancer.get_ip(my_vars.live_nodes[instance_index - 1])
        if instance_to_put_in_ip == my_vars.ip_address or backup_instance_ip == my_vars.ip_address:
            res = cache.put_data(str_key, data, expiration_date=date)
        if instance_to_put_in_ip != my_vars.ip_address:
            if date is None:
                res = requests.post(my_vars.url_generator(instance_to_put_in_ip, "put_from_instance",
                                                          f'str_key={req.args.get("str_key")}&data={req.args.get("data")}'))
            else:
                res = requests.post(my_vars.url_generator(instance_to_put_in_ip, "put_from_instance",
                                                          f'str_key={req.args.get("str_key")}&data={req.args.get("data")}&expiration_date={req.args.get("expiration_date")}'))
        if backup_instance_ip != my_vars.ip_address:
            if date is None:
                res = requests.post(my_vars.url_generator(backup_instance_ip, "put_from_instance",
                                                          f'str_key={req.args.get("str_key")}&data={req.args.get("data")}'))
            else:
                res = requests.post(my_vars.url_generator(backup_instance_ip, "put_from_instance",
                                                          f'str_key={req.args.get("str_key")}&data={req.args.get("data")}&expiration_date={req.args.get("expiration_date")}'))
    except:
        res = None, 401
    return res


@app.route('/get_all', methods=['GET'])
def get_all():
    return cache.get_cache(), 200


@app.route('/id', methods=['GET'])
def get_id():
    return my_vars.instance_id, 200


@app.route('/clear', methods=['POST'])
def clear():
    cache.clear_cache()
    return "cache is clear", 200


@app.route('/get_all_and_clear', methods=['POST'])
def get_all_clear():
    cache_cpy = cache.get_cache()
    cache.clear_cache()
    return cache_cpy, 200


@app.route('/put_from_instance', methods=['POST', 'GET'])
def post_from_instance():
    try:
        str_key = req.args.get('str_key')
        data = req.args.get('data')
        if str_key is None or data is None:
            raise Exception
    except:
        return None, 400
    try:
        date = req.args.get('expiration_date')
    except:
        date = None
    return cache.put_data(str_key, data, expiration_date=date)

@app.route('/repost_from_instance', methods=['POST', 'GET'])
def repost():
    try:
        str_key = req.args.get('str_key')
        data = req.args.get('data')
        if str_key is None or data is None:
            raise Exception
    except:
        return None, 400

    return cache.reput_data(str_key, data)

@app.route('/get_from_instance', methods=['POST', 'GET'])
def get_from_instance():
    print("HERE")
    try:
        str_key = req.args.get('str_key')
        if str_key is None:
            raise Exception
    except:
        return None, 400
    print("DONE")
    return json.dumps(cache.get_data(str_key)), 200


@app.route('/repost_data', methods=['POST'])
def repost_data():
    try:
        str_key = req.args.get('str_key')
        data = req.args.get('data')
        if str_key is None or data is None:
            raise Exception
    except:
        return None, 400

    try:
        hashed_str_key = my_vars.hash_index(str_key)
        instance_index = jump.hash(int(hashed_str_key) % len(my_vars.live_nodes), len(my_vars.live_nodes))
        instance_to_put_in_ip = load_balancer.get_ip(my_vars.live_nodes[instance_index])
        backup_instance_ip = load_balancer.get_ip(my_vars.live_nodes[instance_index - 1])
        if instance_to_put_in_ip == my_vars.ip_address or backup_instance_ip == my_vars.ip_address:
            res = cache.reput_data(str_key, data)
        if instance_to_put_in_ip != my_vars.ip_address:
            res = requests.post(my_vars.url_generator(instance_to_put_in_ip, "repost_from_instance",
                                                      f'str_key={req.args.get("str_key")}&data={req.args.get("data")}'))

        if backup_instance_ip != my_vars.ip_address:
            res = requests.post(my_vars.url_generator(backup_instance_ip, "repost_from_instance",
                                                          f'str_key={req.args.get("str_key")}&data={req.args.get("data")}'))
    except:
        res = None, 401
    return res


class Vars:
    def __init__(self):
        self.ip_address = requests.get('https://api.ipify.org').text
        self.instance_id = requests.get('http://169.254.169.254/latest/meta-data/instance-id').text
        self.live_nodes = load_balancer.get_targets_status()[0]
        self.n_live_nodes = len(self.live_nodes)
        self.my_index = self.get_my_index()
        self.port = 80
        self.bs = BackgroundScheduler(daemon=True)

    def get_my_index(self):
        return self.live_nodes.index

    def check_status(self):
        current_live_nodes = load_balancer.get_targets_status()[0]
        if current_live_nodes == self.live_nodes:
            return
        self.live_nodes = load_balancer.get_targets_status()[0]
        self.n_live_nodes = len(self.live_nodes)
        #if self.live_nodes[0] == self.instance_id:
        repartition()

    def add_base_jobs(self):
        self.bs.add_job(self.check_status, 'interval', seconds=5)
        print("base status")
        self.bs.add_job(cache.expire_check, 'interval', seconds=5)
        print("expire check")

    def start_bs(self):
        self.bs.start()

    @staticmethod
    def hash_index(key):
        return xxhash.xxh64_intdigest(key) % (2 ** 10)

    def url_generator(self, ip: str, op, params):
        return "http://ec2-{}.{}.compute.amazonaws.com:{}/{}?{}".format(ip.replace(".", "-"), load_balancer.REGION,
                                                                        my_vars.port, op,
                                                                        params)

class Cache:
    def __init__(self):
        self.cache = {}
        self.hash_cache = {}

    def expire_check(self):
        for key in self.cache.keys():
            val = json.loads(self.cache.get(key))
            if val["expiration_date"] < self.get_millis(datetime.now()):
                self.cache.pop(key)

    @staticmethod
    def millis():
        return round(time.time() * 1000)

    @staticmethod
    def get_millis(dt):
        return int(round(dt.timestamp() * 1000))

    def put_data(self, str_data: str, data, expiration_date=None):
        if expiration_date is None:
            self.cache[str_data] = json.dumps({
                "data": data,
                "expiration_date": self.get_millis(datetime.now() + timedelta(days=90)),
            })
        else:
            self.cache[str_data] = json.dumps({
                "data": data,
                "expiration_date": self.get_millis(expiration_date),
            })
        return "OKOKOK", 200
        # self.hash_cache[str_data] = xxhash

    def reput_data(self, str_data: str, data: dict):

        self.cache[str_data] = json.dumps(data)
        return "OKOKOK", 200


    def get_data(self, str_data):
        return self.cache.get(str_data)

    def get_cache(self):
        return self.cache

    def clear_cache(self):
        self.cache = {}

def repartition():
    live_instances = load_balancer.get_targets_status()[0]
    all_data = {}
    # url = f'http://{load_balancer.get_ip(my_vars.live_nodes[hashed_index])}:{my_vars.port}/put?str_key={}&data={}&expiration_date={}'
    for instance_id in live_instances:
        curr_ip = load_balancer.get_ip(instance_id)
        # get and clear data
        url_req = "http://ec2-{}.{}.compute.amazonaws.com:{}/{}".format(curr_ip.replace(".", "-"), load_balancer.REGION,
                                                                 my_vars.port, "get_all_and_clear")
        # url_req = f'http://{curr_ip}:{80}/get_all_and_clear'
        res = requests.post(url_req).json()
        # fetch data
        print(res)
        print(type(res))
        all_data.extend(res)

    #resave-repartition:
    for key in all_data.keys() :
    #   key, put1 (put with data) include hash with index
        ip = my_vars.live_nodes[random.sample(1, len(my_vars.live_nodes))[0]]
        url_req = my_vars.url_generator(ip, "repost_data", f"str_key={key}&data={all_data.get(key)}")
        res = requests.post(url_req)

    return "OK - done"
cache = Cache()
if __name__ == '__main__':
    my_vars = Vars()
    my_vars.add_base_jobs()
    my_vars.start_bs()
    app.run(host="0.0.0.0", port=80)
