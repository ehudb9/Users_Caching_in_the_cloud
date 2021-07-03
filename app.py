from flask import Flask

app = Flask(__name__)

@app.route('/healthcheck', methods=['GET'])
def health():
    return "OK" , 200


if __name__ == '__main__':
    app.run()