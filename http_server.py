from flask import Flask, redirect, url_for, request
#app = Flask(__name__)
import webbrowser

###
from http.server import BaseHTTPRequestHandler, HTTPServer # python3
from datetime import datetime
from furl import furl
import jump
import xxhash
import elb
import requests
import threading
import time
import load_balancer
####


global current_live_node_count
current_live_node_count = 0
host = ''
port = 80
instance_cache = dict()

my_ip = (requests.get("http://169.254.169.254/latest/meta-data/public-ipv4").content).decode()


def get_live_nodes():
    healthy, _ = load_balancer.get_targets_status()
    return healthy

def check_for_update():
    global current_live_node_count
    global flag
    flag = True
    while flag:
        print('check')
        live_nodes = get_live_nodes()
        print(f"live={len(live_nodes)}, prev={current_live_node_count}")
        if current_live_node_count != len(live_nodes):
            current_live_node_count = len(live_nodes)
            update_all_instances()
        time.sleep(15)
        if not flag:
            print('killed')


def update_all_instances():
    for item in instance_cache.items():
        #         delete expired item from cache
        item_expiration_date = datetime.strptime(item[1][1], '%d-%m-%Y')
        if item_expiration_date < datetime.now():
            print('delete')
            instance_cache.pop(item[0])
        #         check if instance update required
        else:
            print('update')
            live_nodes = get_live_nodes()
            node_id1 = hash_func(item[0], len(live_nodes))
            node_id2 = (node_id1 + 1) % len(live_nodes)
            ip1 = elb.get_instance_public_ip(live_nodes[node_id1]['Id'])
            ip2 = elb.get_instance_public_ip(live_nodes[node_id2]['Id'])
            request_args = {
                'str_key': item[0],
                'data': item[1][0],
                'expiration_date': item[1][1]
            }
            redirect_request(ip1, request_args, 'write')
            redirect_request(ip2, request_args, 'write')


def hash_func(str_key, node_count):
    vnode_id = xxhash.xxh64(str_key).intdigest() % 1024
    return jump.hash(vnode_id, node_count)


def redirect_request(ip, request_args, request_path):
    response = None
    if ip != my_ip:
        request = f"http://{ip}/{request_path}"
        if request_path == 'write':
            response = requests.post(request, params=request_args)
            #             response = requests.post(request)
            if response != None:
                response = response.text.split(': ')[1]
        else:
            response = requests.get(request, params=request_args)

            if response is not None:
                response = response.text.split(': ')[1]

    else:
        if request_path == 'write':
            response = write_request_handler(request_args['str_key'], request_args['data'],
                                             request_args['expiration_date'])
        else:
            response = read_request_handler(request_args['str_key'])

    return response


def is_expirtion_date_invalid(request_args):
    date = request_args['expiration_date'].split('-')
    if (date[0].isnumeric() and len(date[0]) == 2) and (date[1].isnumeric() and len(date[1]) == 2) and (
            date[2].isnumeric() and len(date[2]) == 4):
        return False
    return True


def put_request_handler(ip1, ip2, request_args):
    if len(request_args) < 3:
        return "Invalid put request - Invalid number of arguments"
    elif is_expirtion_date_invalid(request_args):
        return "Invalid put request - Invalid expiration date"
    response1 = redirect_request(ip1, request_args, 'write')
    response2 = redirect_request(ip2, request_args, 'write')

    return response1 if response1 != None else response2


def get_request_handler(ip1, ip2, request_args):
    response1 = redirect_request(ip1, request_args, 'read')
    response2 = redirect_request(ip2, request_args, 'read')
    error_message = "Key not found - Please enter a valid key"
    return response1 if response1 != error_message else response2


def write_request_handler(str_key, data, expiration_date):
    instance_cache[str_key] = [data, expiration_date]
    return "succeeded"


def read_request_handler(str_key):
    tup = instance_cache.get(str_key, None)
    tup_expiration_date = datetime.strptime(tup[1], '%d-%m-%Y')
    if tup != None:
        if tup_expiration_date >= datetime.now():
            return tup[0]
        else:
            instance_cache.pop(str_key)

    return "Key not found - Please enter a valid key"


class HandleRequests(BaseHTTPRequestHandler):
    def _set_headers(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        self._set_headers()
        f = furl(self.path)

        if f.path == "/update":
            update_all_instances()
        if f.path == "/read":
            response = read_request_handler(f.args['str_key'])
            self.wfile.write("read request response: {}".format(response).encode('utf-8'))

        elif f.path == "/get":
            #             send read request to 2 ec2 by getting ip from hash func
            live_nodes, sick = get_live_nodes()
            node_id1 = hash_func(f.args['str_key'], len(live_nodes))
            node_id2 = (node_id1 + 1) % len(live_nodes)
            ip1 = elb.get_instance_public_ip(live_nodes[node_id1]['Id'])
            ip2 = elb.get_instance_public_ip(live_nodes[node_id2]['Id'])
            response = get_request_handler(ip1, ip2, f.args)

            self.wfile.write("get request response: {} ".format(response).encode('utf-8'))

        elif self.path == "/healthcheck":
            self.wfile.write("Ok".format().encode('utf-8'))

    def do_POST(self):
        self._set_headers()
        f = furl(self.path)

        if f.path == "/write":
            response = write_request_handler(f.args['str_key'], f.args['data'], f.args['expiration_date'])
            self.wfile.write("write request response: {}".format(response).encode('utf-8'))

        elif f.path == "/put":
            #           send write request to 2 ec2 by getting ip from hash func
            live_nodes, sick = get_live_nodes()
            node_id1 = hash_func(f.args['str_key'], len(live_nodes))
            node_id2 = (node_id1 + 1) % len(live_nodes)
            ip1 = elb.get_instance_public_ip(live_nodes[node_id1]['Id'])
            ip2 = elb.get_instance_public_ip(live_nodes[node_id2]['Id'])
            response = put_request_handler(ip1, ip2, f.args)
            self.wfile.write("put request response: {}".format(response).encode('utf-8'))


try:
    current_live_node_count = len(get_live_nodes()[0])
    update_thread = threading.Thread(target=check_for_update, args=[])
    update_thread.start()
    HTTPServer((host, port), HandleRequests).serve_forever()
finally:
    exit()



#
#
#
#
# new = 2 # open in a new tab, if possible
#
#
#
# html = f"""
# <html>
#    <body>
#       <form action = "http://localhost:5000/login" method = "post">
#          <p>Enter Name:</p>
#          <p><input type = "text" name = "nm" /></p>
#          <p><input type = "submit" value = "submit" /></p>
#       </form>
#    </body>
# </html>
# """
#
# # GET|PUT|healthcheck
#
#
#
# @app.route('/success/<name>')
# def success(name):
#    return 'welcome %s' % name
#
# @app.route('/login',methods = ['POST', 'GET'])
# def login():
#    if request.method == 'POST':
#       user = request.form['nm']
#       return redirect(url_for('success',name = user))
#    else:
#       user = request.args.get('nm')
#       return redirect(url_for('success',name = user))
#
# def main():
#     file = open("sample.html", "w")
#     file.write(html)
#     file.close()
#     webbrowser.open("sample.html", new=new)
#     app.run(debug=True)
#
# def get(str_key: str):
#     # None or data:
#     """
#     Get the user from the relevant EC2 instance
#     :param str_key:
#     :return:None or data
#     """
#     pass
#
#
# def put(str_key: str, data: str, expiration_date: int):
#     """
#     Manage the distribute: which user goes where
#     :param str_key:
#     :param data:
#     :param expiration_date:
#     :return:
#     """
#     pass
#
# #################################

#
# if __name__ == '__main__':
#     main()

