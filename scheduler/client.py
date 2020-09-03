#!/usr/bin/env python3
# -*-coding:utf-8-*-

import requests
import time
import random


class CarInfo:
    Id = -1
    LineFrom = -1
    LineTo = -1
    TimeStart = 0.0
    Weight = -1


def NewCarInfo():
    return {"id":-1,
            "line_from": -1,
            "line_to": -1,
            "request_time": 0.0,
            "weight": -1}


class Client:
    def __init__(self):
        self.host = '127.0.0.1'
        self.port = 8989

    def start(self):
        while True:
            req = NewCarInfo()
            req['id'] = random.randint(0, 10000)
            req['line_from'] = random.randint(0, 3)
            req['line_to'] = random.randint(0, 3)
            if req['line_to'] == req['line_from']:
                req['line_to'] = (req['line_to']+1) % 8
            req['request_time'] = time.time()
            req['weight'] = random.randint(0,10)
            try:
                print("post: id:{}, line_from: {}, line_to: {}, request_time: {}, weight: {}".format(req['id'],
                                                                                                     req['line_from'],
                                                                                                     req['line_to'],
                                                                                                     req['request_time'],
                                                                                                     req['weight']))
                resp = requests.post('http://127.0.0.1:8989/register', data=req)
                print(resp.text)
                resp.close()
            except Exception as e:
                print(e)
            time.sleep(random.random()/5)

    def test_pygame_show(self):
        while True:
            queue_size_list4 = {"0":random.randint(0,4),
                                "1":random.randint(0,4),
                                "2":random.randint(0,5),
                                "3":random.randint(0,5)}
            try:
                # resp = requests.get('http://127.0.0.1:7878/test')
                # print(resp)
                resp = requests.post('http://127.0.0.1:7878/update_waiting_queue', data=queue_size_list4)
                print(resp)
            except Exception as e:
                print(e)
            time.sleep(1)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return


if __name__ == '__main__':
    with Client() as client:
        client.start()
        # client.test_pygame_show()
