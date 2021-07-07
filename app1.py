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


@app.route('/get', methods=['GET'])
def get():
    #    url = f'http://{v.ip_address}:{v.port}/get?str_key={requests.args.get("str-key")}'
    # get key from request
    key = requests.args.get('str_key')
    ans1 = requests.get("")



@app.route('/put', methods=['POST'])
def post():
    url = f'http://{v.ip_address}:{v.port}/get?str_key={requests.args.get("str-key")}'


@app.route('/get_all', methods=['GET'])
def get():
    url = f'http://{v.ip_address}:80/get_all'


@app.route('/put_repart', methods=['POST'])
def post():
    url = f'http://{v.ip_address}:80/put_repart?str_key={requests.args.get("str-key")}&data={requests.args.get("data")}'

@app.route('/put_repart', methods=['GET'])
def post():
    url = f'http://{v.ip_address}:80/put_repart?str_key={requests.args.get("str-key")}&data={requests.args.get("data")}'


class Vars():
    def __init__(self):
        self.ip_address = requests.get('https://api.ipify.org').text
        self.instance_id = requests.get('http://169.254.169.254/latest/meta-data/instance-id').text
        self.live_nodes = load_balancer.get_targets_status()[0]
        self.n_live_nodes = len(self.live_nodes)
        self.port = 80
        self.cache = {}
        self.hash_cache = {}
        self.bs = BackgroundScheduler(daemon=True)

    def expire_check(self):
        for key in self.cache.keys():
            val = json.loads(self.cache.get(key))
            if val["expiration_date"] < Vars.get_millis(datetime.now()):
                self.cache.pop(key)

    def check_status(self):
        current_live_nodes = load_balancer.get_targets_status()[0]
        if current_live_nodes == self.live_nodes:
            return
        self.live_nodes = load_balancer.get_targets_status()[0]
        self.n_live_nodes = len(self.live_nodes)
        load_balancer.repartition()

    @staticmethod
    def millis():
        return round(time.time() * 1000)

    @staticmethod
    def get_millis(dt):
        return int(round(dt.timestamp() * 1000))

    def put_data(self, ip, str_data: str, data, is_backup=False):
        if self.instance_id == ip or is_backup:
            self.cache[str_data] = json.dumps({
                "data": data,
                "expiration_date": Vars.get_millis(datetime.now() + timedelta(days=90)),
            })
            # self.hash_cache[str_data] = xxhash
        pass

    def put_data(self, ip, str_data: str, data: json, is_backup=False):
        if self.instance_id == ip or is_backup:
            self.cache[str_data] = data

        # self.hash_cache[str_data] = xxhash
        pass

    def get_data(self, ip):
        pass

    def get_cache(self):
        return self.cache

    def clear_cache(self):
        self.cache = {}

    def add_base_jobs(self):
        self.bs.add_job(self.check_status, 'interval', seconds=5)
        print("base status")
        self.bs.add_job(self.expire_check, 'interval', seconds=5)
        print("expire check")

    def start_bs(self):
        self.bs.start()


if __name__ == '__main__':
    v = Vars()
    v.add_base_jobs()
    v.start_bs()
    app.run(host="0.0.0.0", port=80)
