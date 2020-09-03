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
GREEN_DELAY_TIME = 3  # 绿灯时间
YELLOW_DELAY_TIME = 0.3  # 黄灯时间
STRAIGHT_PASS_TIME = 0.3  # 单车直行通过路口所用时间
TRUN_LEFT_PASS_TIME = 0.3  # 单车转弯通过路口所用时间
APPEND_TIME = 0.2  # 多车通过路口时，多余车的用时的增量(也即队列中的车挪动一个车位所用的时间)
RATE = 0.1  # 路口为空时的循环监听delay

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)


class CarInfo:
    Id = -1
    LineFrom = -1
    LineTo = -1
    TimeStart = 0.0
    Weight = -1
    client_host = ""
    client_port = -1


class TrafficQueues:
    def __init__(self):
        self.q = [deque() for i in range(8)]
        """
        道路映射示意图见 https://s1.ax1x.com/2020/05/27/tAnZaF.jpg
        """
        self.lock = threading.Lock()
        self.hash = {"02": 0,
                     "03": 1,
                     "13": 2,
                     "10": 3,
                     "20": 4,
                     "21": 5,
                     "31": 6,
                     "32": 7}

    def insertCar(self, carInfo: CarInfo) -> bool:
        queueIndex = self._getQueueIndex(carInfo)
        if queueIndex == -1:
            # print("Car {}: no need to wait, passing".format(carInfo.Id))
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

    # # 返回4个路口等待队列的长度
    # def getWaittingQueueSize4(self):
    #     wait_0 = len(self.q[0])+len(self.q[1])
    #     wait_1 = len(self.q[4])+len(self.q[5])
    #     wait_2 = len(self.q[2])+len(self.q[3])
    #     wait_3 = len(self.q[6])+len(self.q[7])
    #     return[wait_0, wait_1, wait_2, wait_3]

    # 返回8个路口等待队列的长度
    def getWaittingQueueSize8(self):
        return [len(self.q[i]) for i in range(8)]

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


class TrafficManager(object):
    def __init__(self, controller):
        self.controller = controller  # type: Controller
        self.traffic_queues = self.controller.traffic_queues  # type: TrafficQueues
        self.total_counter = 0

    def run(self):
        pass

    def _on_queue_changed(self):
        self.controller.on_traffic_queue_changed()

    def _on_traffic_light_changed(self, *args):
        self.controller.on_traffic_light_changed(*args)

    def _on_shutdown(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return


class SmartTrafficManager(threading.Thread, TrafficManager):
    def __init__(self, controller):
        threading.Thread.__init__(self)
        TrafficManager.__init__(self, controller)
        self.total_counter = 0
        self.pass_time = STRAIGHT_PASS_TIME
        self.append_time = APPEND_TIME
        self.rate = RATE
        self.yellow_delay_time = YELLOW_DELAY_TIME

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
            print("[SMART TRAFFIC MANAGER] let traffic queue {} pass {} cars".format(priQueueIndex, carNumbers))
            self._on_traffic_light_changed(priQueueIndex)
            self.traffic_queues.shrinkQueue(priQueueIndex, carNumbers)  # 通知priQueueIndex队列中的前carNumber辆车通过路口
            self._on_queue_changed()
            print(self.traffic_queues.getSizesStr())
            time.sleep(self.pass_time + carNumbers * self.append_time)  # 等待车辆通过路口

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


class NormalTrafficManager(threading.Thread, TrafficManager):
    def __init__(self, controller):
        threading.Thread.__init__(self)
        TrafficManager.__init__(self, controller)
        self.traffic_lights = [(0, 4), (1, 5), (2, 6), (3, 7)]
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
            print("[NORMAL TRAFFIC MANAGER] queue {} and {} is passing.".format(line0, line1))
            self._on_traffic_light_changed(line0, line1)

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
                self._on_queue_changed()
                time.sleep(min(max(end_time - time.time(), 0), self.append_time))  # 等待车辆通过或者绿灯时间到达

            # 绿灯停止，黄灯亮起
            self._on_traffic_light_changed(None)
            print("waiting time >> total_cars: {}".format(self.total_counter))
            print(self.traffic_queues.getSizesStr())
            print("--" * 10)
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


class WebServer(threading.Thread):
    def __init__(self, traffic_queues):
        super().__init__()
        self.traffic_queues = traffic_queues  # type: TrafficQueues
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
        self.app.run(host=self.host, port=self.port, debug=False, use_reloader=False)

    def _on_shutdown(self):
        print("exit success")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._on_shutdown()


import pygame
from pygame.locals import *

pygame.init()

SCREEN_SIZE = (800, 800)
WIDTH, HEIGHT = SCREEN_SIZE
SCREEN = pygame.display.set_mode(SCREEN_SIZE, 0, 32)

INTERSECTION_IMAGE = "asset/image/intersection1.jpg"
BACKGROUND_IMAGE = pygame.image.load(INTERSECTION_IMAGE).convert()
BACKGROUND_IMAGE = pygame.transform.scale(BACKGROUND_IMAGE, SCREEN_SIZE)

CAR_IMAGE_SIZE = (50, 25)
image_names = ["asset/image/car0.png",
               "asset/image/car2.png"]
CAR_IMAGE_LIST = []
for name in image_names:
    image = pygame.image.load(name).convert_alpha()
    image = pygame.transform.scale(image, CAR_IMAGE_SIZE)
    CAR_IMAGE_LIST.append(image)

WAIT_LINE_INIT = [[WIDTH / 2 + WIDTH / 20, HEIGHT / 2 + HEIGHT / 10],  # 0
                  [WIDTH / 2 + WIDTH / 50, HEIGHT / 2 + HEIGHT / 10],  # 1
                  [WIDTH / 2 + 105, HEIGHT / 2 - 48],  # 2
                  [WIDTH / 2 + 105, HEIGHT / 2 - 25],  # 3
                  [WIDTH / 2 - 40, HEIGHT / 2 - 128],  # 4
                  [WIDTH / 2 - 13, HEIGHT / 2 - 128],  # 5
                  [WIDTH / 2 - 105, HEIGHT / 2 + 30],  # 6
                  [WIDTH / 2 - 105, HEIGHT / 2 + 8]]  # 7


class PygameCar(pygame.sprite.Sprite):
    def __init__(self, road_id):
        super().__init__()
        self.road_id = road_id
        self.image = random.choice(CAR_IMAGE_LIST)
        self.car_id = 0
        self.rect = None  # type: pygame.Rect
        self.increment = [0, 0]
        self.inter = 5
        self._rotate_image()

    def _rotate_image(self):
        road_directioin = int(self.road_id / 2)
        self.image = pygame.transform.rotate(self.image, (road_directioin + 1) * 90)
        self.rect = self.image.get_rect()
        if road_directioin == 0:
            self.increment = [0, self.rect.height + self.inter]
        elif road_directioin == 1:
            self.increment = [self.rect.width + self.inter, 0]
        elif road_directioin == 2:
            self.increment = [0, -(self.rect.height + self.inter)]
        elif road_directioin == 3:
            self.increment = [-(self.rect.width + self.inter), 0]

    def update(self, pos):
        self.rect.midtop = (WAIT_LINE_INIT[self.road_id][0] + self.increment[0] * pos,
                            WAIT_LINE_INIT[self.road_id][1] + self.increment[1] * pos)


lock = threading.Lock()


class MyGroup(pygame.sprite.Group):
    def __init__(self):
        super().__init__()

    def draw(self, surface):
        lock.acquire()
        super().draw(surface)
        lock.release()


class Scheduler(object):
    def __init__(self, active_ui=True):
        super().__init__()
        self.active_ui = active_ui
        self.screen = SCREEN
        self.all_sprite_group = MyGroup()
        self.clock = pygame.time.Clock()
        self.road_queue = [[] for i in range(8)]
        self.controller = Controller(self)
        self.road_id_texts = dict()
        self._init()

    def _init(self):
        fontObj = pygame.font.Font(None, 30)
        for id, pos in enumerate(WAIT_LINE_INIT):
            textSurfaceObj = fontObj.render(str(id), True, RED)  # type: pygame.Surface
            rect = textSurfaceObj.get_rect()  # type: pygame.Rect
            if id == 0 or id == 1:
                rect.midbottom = pos
            elif id == 2 or id == 3:
                rect.midleft = (pos[0]-40, pos[1]+15)
            elif id == 4 or id == 5:
                rect.center = (pos[0], pos[1]+65)
            else:
                rect.midleft = (pos[0]+35, pos[1]+10)
            self.road_id_texts[id] = [textSurfaceObj, rect]

    def _draw_road_id(self, screen):
        for id, obj in self.road_id_texts.items():
            screen.blit(obj[0], obj[1])

    def run(self):
        self.controller.run()
        self.clock.tick(30)
        running = True
        while True:
            for event in pygame.event.get():
                if event.type == QUIT:
                    running = False
            if not running:
                break
            self.screen.blit(BACKGROUND_IMAGE, (0, 0))
            self._draw_road_id(self.screen)

            # self.all_sprite_group.update()
            self.all_sprite_group.draw(self.screen)
            pygame.display.update()
        pygame.quit()

    def update_traffic_queue(self, queue_size_list):
        delete_list = []
        add_list = []
        for road_id, length in enumerate(queue_size_list):
            dec = len(self.road_queue[road_id]) - length
            if dec == 0:
                continue
            # 更新等待队列长度
            if dec > 0:
                for k in range(dec):
                    car = self.road_queue[road_id][0]
                    delete_list.append(car)
                    self.road_queue[road_id].remove(car)

            if dec < 0:
                for k in range(-dec):
                    new_car = PygameCar(road_id)
                    self.road_queue[road_id].append(new_car)
                    add_list.append(new_car)

        lock.acquire()
        for car in delete_list:
            car.kill()
        for car in add_list:
            self.all_sprite_group.add(car)
        for road_id, length in enumerate(queue_size_list):
            for pos in range(length):
                self.road_queue[road_id][pos].update(pos)
        lock.release()

    def update_traffic_light(self, *args):
        fontObj = pygame.font.Font(None, 30)
        if len(args) == 0 or args[0] is None:
            for id, obj in self.road_id_texts.items():
                # obj[0].set_colorkey(YELLOW)
                obj[0] = fontObj.render(str(id), True, YELLOW)
        else:
            for id, obj in self.road_id_texts.items():
                # obj[0].set_colorkey(RED)
                obj[0] = fontObj.render(str(id), True, RED)
            for id in args:
                print("set green: {}".format(id))
                self.road_id_texts[id][0] = fontObj.render(str(id), True, GREEN)

    def _on_shutdown(self):
        return

    def test_initial_car_postion(self):
        self.clock.tick(30)
        running = True
        for i in range(8):
            car = PygameCar(road_id=i)
            car.rect.midtop = WAIT_LINE_INIT[i]
            self.all_sprite_group.add(car)
        # car = PygameCar(5)
        # car.rect.midtop = WAIT_LINE_INIT[5]
        # self.all_sprite_group.add(car)

        while True:
            for event in pygame.event.get():
                if event.type == QUIT:
                    running = False
            if not running:
                break
            self.screen.blit(BACKGROUND_IMAGE, (0, 0))

            # self.all_sprite_group.update()
            self.all_sprite_group.draw(self.screen)
            pygame.display.update()
        pygame.quit()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._on_shutdown()


class Controller():
    def __init__(self, ui):
        super().__init__()
        self.ui = ui  # type: Scheduler
        self.traffic_queues = TrafficQueues()
        self.traffic_manager = NormalTrafficManager(self)
        self.web_server = WebServer(self.traffic_queues)

    def run(self):
        self.traffic_manager.start()
        self.web_server.start()

    def on_traffic_queue_changed(self):
        self.ui.update_traffic_queue(self.traffic_queues.getWaittingQueueSize8())

    def on_traffic_light_changed(self, *args):
        self.ui.update_traffic_light(*args)

    def _on_shutdown(self):
        if self.traffic_manager:
            self.traffic_manager.join()
        if self.web_server:
            self.web_server.join()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._on_shutdown()


if __name__ == '__main__':
    with Scheduler(active_ui=True) as app:
        app.run()
        # app.test_initial_car_postion()
