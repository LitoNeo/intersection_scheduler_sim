#!/usr/bin/env python3
# -*-coding:utf-8-*-

from queue import Queue
import threading
from copy import deepcopy
from collections import deque
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from flask import Flask, request

class CarInfo:
    def __init__(self):
        self.Id = None
        self.LineFrom = None
        self.LineTo = None
        self.TimeStart = None
        self.Wright = None


class TrafficQueues:
    def __init__(self):
        self.q = [deque() for i in range(8)]
        self.lock = threading.Lock()
        self.hash = {"02": 0,
                     "20": 1,
                     "13": 2,
                     "31": 3,
                     "03": 4,
                     "21": 5,
                     "10": 6,
                     "32": 7}

    def insertCar(self, carInfo: CarInfo)->bool:
        queueIndex = self._getQueueIndex(carInfo)
        if queueIndex == -1:
            return True

        try:
            self.lock.acquire()
            self.q[queueIndex].append(carInfo)
        except Exception as e:
            print(e)
            return False
        finally:
            self.lock.release()

        return True

    def getCopy(self) -> list:
        try:
            self.lock.acquire()
            res = [x.copy() for x in self.q]
        except Exception as e:
            print("Cannot copy traffic queues: ", e)
            exit(1)
        finally:
            self.lock.release()
        return res

    def shrinkQueue(self, queueIndex: int, length: int):
        try:
            self.lock.acquire()
            for i in range(length):
                self.q[queueIndex].popleft()
        except Exception as e:
            print("shrink queue error: ", e)
            exit(1)
        finally:
            self.lock.release()

    def _getQueueIndex(self, carInfo: CarInfo) -> int:
        lineFrom = carInfo.LineFrom
        lineTo = carInfo.LineTo
        key = str(lineFrom) + str(lineTo)
        if not key in self.hash.keys():
            return -1
        return self.hash.get(key)


SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8888

app = Flask(__name__)


class TrafficQueueManager(threading.Thread):
    def __init__(self, trafficQueue: TrafficQueues):
        threading.Thread.__init__(self)
        self.trafficQeueue = trafficQueue
        self.host = SERVER_HOST
        self.port = SERVER_PORT
        self.app = Flask(__name__)
        self._add_url_handler()

    def _add_url_handler(self):
        self.app.add_url_rule('/register', 'register_task', self._api_register, methods=['POST'])

    def _api_register(self):
        print(request.form)
        return "success"

    def run(self):
        self.app.run(host=self.host, port=self.port, debug=False)


class IntersectionScheduler:
    def __init__(self):
        self.trafficQueues = TrafficQueues()
        self.trafficManager = TrafficQueueManager(self.trafficQueues)

    def start(self):
        self.trafficManager.start()

        while True:
            curQueueList = self.trafficQueues.getCopy()
            priQueueIndex, carNumbers = self._getPriorityQueue(curQueueList)

            # 所有队列均为空
            if priQueueIndex == -1:
                time.sleep(0.1)
                continue

            """
            # 有等待队列不为空，且获得了优先级最高的队列的index,及当前可以通过路口的车辆数
            # 通知该队列的前carNumbers辆车通过该路口
            # 车辆通过路口后需要从其原先队列中删除
            # --- 此处为根据车辆数目等待一定的时长
            """
            self.trafficQueues.shrinkQueue(priQueueIndex, carNumbers)
            time.sleep(5+carNumbers)

    # 主算法部分：通过路口等待队列(队列中的车辆数/车辆权重/各自初始如对时间)+当前时间
    # 获取优先级最高的队列，以及可以通过路口的车辆数
    def _getPriorityQueue(self, curQueueList):
        # if _all_empty(curQueueList):
            return -1,-1

    def _onShutdown(self):
        if self.trafficManager:
            self.trafficManager.join()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._onShutdown()


if __name__ == '__main__':
    try:
        with IntersectionScheduler() as app:
            app.start()
    except Exception as e:
        print(e)

