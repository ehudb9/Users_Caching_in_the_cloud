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
                print("yes")
                res = json.dumps(cache.get_data(key)), 200
            else:
                print("request?")
                res = requests.post(my_vars.url_generator(instance_to_get_from, "get_from_instance",
                                                          f'str_key={req.args.get("str_key")}')).json()
                print("returned")
            return res
        except:
            print("EH")
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


@app.route('/put_repart', methods=['POST'])
def post1():
    hashed_index = my_vars.hash_index(requests.args.get("str_key"))
    url = f'http://{load_balancer.get_ip(my_vars.live_nodes[hashed_index])}:{my_vars.port}/put?str_key={requests.args.get("str_key")}&data={requests.args.get("data")}'
    # str_key={requests.args.get("str-key")}&data={requests.args.get("data")


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
        load_balancer.repartition()

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

    def get_data(self, str_data):
        return self.cache.get(str_data)

    def get_cache(self):
        return self.cache

    def clear_cache(self):
        self.cache = {}


cache = Cache()
if __name__ == '__main__':
    my_vars = Vars()
    my_vars.add_base_jobs()
    my_vars.start_bs()
    app.run(host="0.0.0.0", port=80)
