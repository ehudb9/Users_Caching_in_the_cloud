from flask import Flask
import requests
import load_balancer
import json
import time
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import xxhash

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


@app.route('/get', methods=['GET'])
def get():
    key = requests.args.get('str_key')
    data = None
    res = None
    try:
        data = cache.get_data(key)
        res = data, 200
    except:
        res = "data does not exist in this instance", 404
    finally:
        return res


@app.route('/put', methods=['POST'])
def post():
    try:
        str_key = requests.args.get('str_key')
        data = requests.args.get('data')
    except:
        return None
    try:
        date = requests.args.get('expiration_date')
    except:
        date = None


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

@app.route('/put_repart', methods=['POST'])
def post1():
    url = f'http://{my_vars.ip_address}:80/put_repart?str_key={requests.args.get("str-key")}&data={requests.args.get("data")}'



class Vars:
    def __init__(self):
        self.ip_address = requests.get('https://api.ipify.org').text
        self.instance_id = requests.get('http://169.254.169.254/latest/meta-data/instance-id').text
        self.live_nodes = load_balancer.get_targets_status()[0]
        self.n_live_nodes = len(self.live_nodes)
        self.port = 80
        self.bs = BackgroundScheduler(daemon=True)

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

    @staticmethod
    def hash_key(key):
        return xxhash.xxh64_intdigest(key)

    def put_data(self, ip, str_data: str, data, expiration_date=None, is_backup=False):
        if my_vars.ip_address == ip or is_backup:
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
            # self.hash_cache[str_data] = xxhash
        pass

    def get_data(self, str_data):
        return self.cache.get(str_data)

    def get_cache(self):
        return self.cache

    def clear_cache(self):
        self.cache = {}


if __name__ == '__main__':
    my_vars = Vars()
    cache = Cache()
    my_vars.add_base_jobs()
    my_vars.start_bs()
    app.run(host="0.0.0.0", port=80)
