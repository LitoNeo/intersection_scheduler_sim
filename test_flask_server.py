#!/usr/bin/env python3
# -*-coding:utf-8-*-

from flask import Flask, request
import pickle

class WebServer:
    def __init__(self):
        self.host = "127.0.0.1"
        self.port = 8888
        self.app = Flask(__name__)
        self._add_api_tasks()

    def _add_api_tasks(self):
        self.app.add_url_rule('/register', 'register_task', self._api_register, methods=['POST'])
        self.app.add_url_rule('/request_lock', 'request_cross_lock', self._api_request_lock, methods=['POST'])

    def _api_register(self):
        name = request.form.get('name', default='NULL')
        id = request.form.get('id', default=-1)
        args = request.form.getlist('args')
        print("name={}\nid={}\nargs={}\n".format(name, id, args))
        return "success"

    def _api_request_lock(self):
        print("name ({}) is requesting lock, forbid.".format(request.form.get('name')))
        return "fail"

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return exc_type, exc_val, exc_tb

    def run(self):
        self.app.run(host=self.host, port=self.port, debug=True)


if __name__ == '__main__':
    with WebServer() as server:
        server.run()
