#!/usr/bin/env python3
# -*-coding:utf-8-*-

import requests
import pickle

test = []


class Data:
    def __init__(self):
        self.name = ""
        self.id = None


if __name__ == '__main__':
    data = {"name":"lito", "id":1}
    # data = Data()
    # data.name = "lito"
    # data.id = 11
    resp = requests.post('http://127.0.0.1:8888/register', data=data)
    print(resp.text)
    resp.close()

    resp = requests.post('http://127.0.0.1:8888/request_lock', data=data)
    print(resp.text)
    resp.close()