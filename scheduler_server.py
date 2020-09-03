#!/usr/bin/env python3
# -*-coding:utf-8-*-

from flask import Flask, request
from collections import deque
import time
import threading
from typing import List
import random
import logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

"""
常规红绿灯时间比例关系为
绿灯：30s  ？？？
黄灯：3s
单车通行时间：3s
"""

# 所有时间均采用s
GREEN_DELAY_TIME = 3     # 绿灯时间
YELLOW_DELAY_TIME = 0.3  # 黄灯时间
STRAIGHT_TIME = 0.3      # 单车直行通过路口所用时间
TRUN_LEFT_TIME = 0.3     # 单车转弯通过路口所用时间
APPEND_TIME = 0.2        # 多车通过路口时，多余车的用时的增量(也即队列中的车挪动一个车位所用的时间)
RATE = 0.1               # 路口为空时的循环监听delay


class CarInfo:
    Id = -1
    LineFrom = -1
    LineTo = -1
    TimeStart = 0.0
    Weight = -1
    client_host = ""
    client_port = -1


# 道路映射示意图见 https://s1.ax1x.com/2020/05/26/tiztUS.jpg
class TrafficQueues:
    def __init__(self):
        self.q = [deque() for i in range(8)]
        """
        0: 南->北   直行
        1: 南->西   左转
        2: 北->南   直行
        3: 北->东   左转  
        4: 东->西   直行  
        5: 东->南   左转
        6: 西->东   直行
        7: 西->北   左转
        """
        self.lock = threading.Lock()
        self.hash = {"02": 0,
                     "03": 1,
                     "20": 2,
                     "21": 3,
                     "13": 4,
                     "10": 5,
                     "31": 6,
                     "32": 7}

    def insertCar(self, carInfo: CarInfo) -> bool:
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
        # print("insert car: [id:{}, from:{}, to:{}] to queue {}".format(carInfo.Id, carInfo.LineFrom, carInfo.LineTo, queueIndex))
        return True

    # 返回4个路口等待队列的长度
    def getWaittingQueueSize4(self):
        wait_0 = len(self.q[0])+len(self.q[1])
        wait_1 = len(self.q[4])+len(self.q[5])
        wait_2 = len(self.q[2])+len(self.q[3])
        wait_3 = len(self.q[6])+len(self.q[7])
        return[wait_0, wait_1, wait_2, wait_3]

    # 返回8个路口等待队列的长度
    def getWaittingQueueSize8(self):
        pass


    def getCopy(self, choice=None):
        if choice is None:
            return self._getFullCopy()
        return self._getSelectedCopy(choice=choice)

    def _getFullCopy(self) -> list:
        try:
            self.lock.acquire()
            res = [x.copy() for x in self.q]
        except Exception as e:
            print("Cannot copy traffic queues: ", e)
            exit(1)
        finally:
            self.lock.release()
        return res

    def _getSelectedCopy(self, choice: dict) -> list:
        try:
            self.lock.acquire()
            res = [self.q[i].copy() for i in choice]
        except Exception as e:
            print("Cannot copy traffic queues: ", e)
            exit(1)
        finally:
            self.lock.release()
        return res

    def getSizesStr(self) -> str:
        s = "new traffic queues size: 0:{}, 1:{}, 2:{}, 3:{}, 4:{}, 5:{}, 6:{}, 7:{}"
        return s.format(len(self.q[0]),
                        len(self.q[1]),
                        len(self.q[2]),
                        len(self.q[3]),
                        len(self.q[4]),
                        len(self.q[5]),
                        len(self.q[6]),
                        len(self.q[7]), )

    def shrinkQueue(self, queueIndex: int, length: int):
        if length <= 0:
            return
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


class SmartTrafficManager(threading.Thread):
    def __init__(self, traffic_queues: TrafficQueues):
        threading.Thread.__init__(self)
        self.traffic_queues = traffic_queues
        self.total_counter = 0
        self.pass_time = STRAIGHT_TIME
        self.append_time = APPEND_TIME
        self.rate = RATE

    def run(self):
        print("Smart Traffic Manager Run.")
        while True:
            curQueueList = self.traffic_queues.getCopy()
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
            print(">> let traffic queue {} pass {} cars".format(priQueueIndex, carNumbers))
            self.traffic_queues.shrinkQueue(priQueueIndex, carNumbers)  # 通知priQueueIndex队列中的前carNumber辆车通过路口
            print(self.traffic_queues.getSizesStr())
            time.sleep(self.pass_time + carNumbers*self.append_time)  # 等待车辆通过路口

    # TODO:: 主算法部分：通过路口等待队列(队列中的车辆数/车辆权重/各自初始如对时间)+当前时间
    # 获取优先级最高的队列，以及可以通过路口的车辆数
    def _getPriorityQueue(self, curQueueList: List[deque]):
        queue_index, car_nums = -1, 0
        for i in range(len(curQueueList)):
            if len(curQueueList[i]) > car_nums:
                queue_index = i
                car_nums = len(curQueueList[i])
        if queue_index == -1:
            return -1, -1
        return queue_index, random.randint(1, car_nums)

    def _onShutdown(self):
        return


class NormalTrafficManager(threading.Thread):
    def __init__(self, traffic_queues: TrafficQueues):
        threading.Thread.__init__(self)
        self.traffic_queues = traffic_queues
        self.traffic_lights = [(0, 2), (1, 3), (4, 6), (5, 7)]
        self.cur_traffic_index = 0
        self.last_time = 0  # 上一次变化的时间
        self.total_counter = 0
        self.cur_counter = 0
        self.green_delay_time = GREEN_DELAY_TIME
        self.yellow_delay_time = YELLOW_DELAY_TIME
        self.rate = RATE  # 频率，ms
        self.append_time = APPEND_TIME

    def run(self):
        print("Normal Traffic Manager Run.")
        while True:
            self.cur_traffic_index = (self.cur_traffic_index + 1) % len(self.traffic_lights)
            line0, line1 = self.traffic_lights[self.cur_traffic_index]
            end_time = time.time() + self.green_delay_time
            print("queue {} and {} is passing.".format(line0, line1))
            while time.time() < end_time:
                queues = self.traffic_queues.getCopy((line0, line1))
                # 队列没有车辆时，循环检测
                if len(queues[0]) == 0 and len(queues[1]) == 0:
                    time.sleep(self.rate)
                    continue
                # 任意一条队列有车时，弹出队首车辆通行，时间为下一辆车进入到停止线位置，即
                if len(queues[0]) > 0:
                    self.traffic_queues.shrinkQueue(line0, 1)
                    self.total_counter += 1
                if len(queues[1]) > 0:
                    self.traffic_queues.shrinkQueue(line1, 1)
                    self.total_counter += 1
                time.sleep(min(end_time - time.time(), self.append_time))  # 等待车辆通过或者绿灯时间到达

            # 绿灯停止，黄灯亮起
            print("yellow light >> total_cars: {}".format(self.total_counter))
            print(self.traffic_queues.getSizesStr())
            print("--"*10)
            time.sleep(self.yellow_delay_time)

    # TODO::获取优先级最高的队列（两条），
    def _getPriorityQueue(self, curQueueList: List[deque]):
        queue_index, car_nums = -1, 0
        for i in range(len(curQueueList)):
            if len(curQueueList[i]) > car_nums:
                queue_index = i
                car_nums = len(curQueueList[i])
        if queue_index == -1:
            return -1, -1
        return queue_index, random.randint(1, car_nums)

    def _onShutdown(self):
        return


class WebServer:
    def __init__(self):
        self.traffic_queues = TrafficQueues()
        self.traffic_managers = {'SMART': SmartTrafficManager(self.traffic_queues),
                                 'NORMAL': NormalTrafficManager(self.traffic_queues)}
        self.active_traffic_manager = None
        self.shower = IntersectionShower(self.traffic_queues)
        self.host = '127.0.0.1'
        self.port = 8989
        self.app = Flask(__name__)
        self._add_api_tasks()

    def _add_api_tasks(self):
        self.app.add_url_rule('/register', 'register_task', self._api_register, methods=['POST'])

    def _api_register(self):
        car = CarInfo()
        car.Id = request.form.get('id')
        car.LineFrom = request.form.get('line_from')
        car.LineTo = request.form.get('line_to')
        car.TimeStart = time.time()
        car.Weight = request.form.get('weight')
        # print(request.remote_addr)
        if self.traffic_queues.insertCar(car):
            return "success"
        return "fail"

    def run(self):
        self.active_traffic_manager = self.traffic_managers["NORMAL"]  # 选择哪一个通行控制算法
        self.active_traffic_manager.start()
        self.shower.start()
        self.app.run(host=self.host, port=self.port, debug=False, use_reloader=False)

    def _on_shutdown(self):
        if self.active_traffic_manager:
            self.active_traffic_manager.join()
        if self.shower:
            self.shower.join()
        print("exit success")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._on_shutdown()


import pygame
from pygame.locals import *

pygame.init()

SCREEN_SIZE = (800, 600)
WIDTH, HEIGHT = SCREEN_SIZE
SCREEN = pygame.display.set_mode(SCREEN_SIZE, 0, 32)

INTERSECTION_IMAGE = "intersection0.jpg"
BACKGROUND_IMAGE = pygame.image.load(INTERSECTION_IMAGE)

CAR_IMAGE_SIZE = (30,15)
image_names = ["car0.png",
                  "car1.png"]
CAR_IMAGE_LIST = []
for name in image_names:
    image = pygame.image.load(name).convert_alpha()
    pygame.transform.scale(image, CAR_IMAGE_SIZE)
    CAR_IMAGE_LIST.append(image)

WAIT_LINE_INIT = [[WIDTH/2, HEIGHT/2+50],   # 0
                  [WIDTH/2+50, HEIGHT/2],   # 1
                  [WIDTH/2, HEIGHT/2-50],   # 2
                  [WIDTH/2-50, HEIGHT/2]]   # 3


class PygameCar(pygame.sprite.Sprite):
    def __init__(self, road_id):
        super().__init__()
        self.image = random.choice(CAR_IMAGE_LIST)
        self.road_id = road_id
        self.car_id = 0
        self.rect = self.image.get_rect()  # type: pygame.Rect
        self.increment = [0,0]
        self.inter = 5
        self._rotate_image()

    def _rotate_image(self):
        pygame.transform.rotate(self.image, (self.road_id+1)*90)
        if self.road_id == 0:
            self.increment = [0, self.rect.height+self.inter]
        elif self.road_id == 1:
            self.increment = [self.rect.width+self.inter, 0]
        elif self.road_id == 2:
            self.increment = [0, -(self.rect.height+self.inter)]
        elif self.road_id == 3:
            self.increment = [-(self.rect.width+self.inter), 0]

    def update(self, pos):
        self.rect.width = WAIT_LINE_INIT[self.road_id][0]+self.increment[0]*pos
        self.rect.height = WAIT_LINE_INIT[self.road_id][1]+self.increment[1]*pos

lock = threading.Lock()

class MyGroup(pygame.sprite.Group):
    def __init__(self):
        super().__init__()

    def draw(self, surface):
        lock.acquire()
        super().draw(surface)
        lock.release()


class IntersectionShower(threading.Thread):
    def __init__(self, traffic_queue):
        super().__init__()
        self.screen = SCREEN
        self.all_sprite_group = pygame.sprite.Group()
        self.clock = pygame.time.Clock()
        self.traffic_queue = traffic_queue  # type: TrafficQueues
        self.road_queue = [[] for i in range(4)]

    def run(self):
        self.screen.blit(BACKGROUND_IMAGE, (0, 0))
        self.clock.tick(30)
        running = True
        while True:
            for event in pygame.event.get():
                if event.type == QUIT:
                    running = False
            if not running:
                break
            queue_size_list = self.traffic_queue.getWaittingQueueSize4()
            self._update_traffic_queue(queue_size_list)
            # self.all_sprite_group.update()
            self.all_sprite_group.draw(self.screen)
            pygame.display.update()

    def _update_traffic_queue(self, queue_size_list):
        for road_id, length in enumerate(queue_size_list):
            dec = len(self.road_queue[road_id])-length
            if dec == 0:
                continue
            # 更新等待队列长度
            lock.acquire()
            if dec > 0:
                for k in range(dec):
                    car = self.road_queue[road_id][0]
                    self.road_queue[road_id].remove(car)
                    car.kill()

            if dec < 0:
                for k in range(-dec):
                    new_car = PygameCar(road_id)
                    self.road_queue[road_id].append(new_car)
                    self.all_sprite_group.add(new_car)
            # 更新等待车辆位置
            for pos in range(length):
                self.road_queue[road_id][pos].update(pos)
            lock.release()


def Test_pygame_shower():
    traffic_queue = TrafficQueues()
    IntersectionShower(traffic_queue).run()


if __name__ == '__main__':
    with WebServer() as server:
        server.run()
    # Test_pygame_shower()
