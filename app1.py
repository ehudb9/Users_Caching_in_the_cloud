from flask import Flask

app = Flask(__name__)
@app.route('/healthcheck', methods=['GET'])
def health():
    return "OK",200

@app.route('/',methods=['GET'])
def land():
    return "YES",200

if __name__ == '__main__':
    app.run(host="0.0.0.0",port=80)
