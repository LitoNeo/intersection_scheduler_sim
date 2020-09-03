#!python3

import pygame
from pygame.locals import *
import random
import threading
from flask import Flask, request

import pygame
from pygame.locals import *

pygame.init()

SCREEN_SIZE = (800, 600)
WIDTH, HEIGHT = SCREEN_SIZE
SCREEN = pygame.display.set_mode(SCREEN_SIZE, 0, 32)

INTERSECTION_IMAGE = "intersection0.jpg"
BACKGROUND_IMAGE = pygame.image.load(INTERSECTION_IMAGE)

CAR_IMAGE_SIZE = (50,25)
image_names = ["car0.png",
               "car2.png"]
CAR_IMAGE_LIST = []
for name in image_names:
    image = pygame.image.load(name).convert_alpha()
    image = pygame.transform.scale(image, CAR_IMAGE_SIZE)
    CAR_IMAGE_LIST.append(image)

WAIT_LINE_INIT = [[WIDTH/2+WIDTH/30, HEIGHT/2+HEIGHT/5],   # 0
                  [WIDTH/2+WIDTH/8, HEIGHT/2-HEIGHT/25],   # 1
                  [WIDTH/2-WIDTH/25, HEIGHT/2-HEIGHT/5],   # 2
                  [WIDTH/2-WIDTH/5, HEIGHT/2+HEIGHT/20]]   # 3


class PygameCar(pygame.sprite.Sprite):
    def __init__(self, road_id):
        super().__init__()
        self.road_id = road_id
        self.image = random.choice(CAR_IMAGE_LIST)
        self.car_id = 0
        self.rect = None  # type: pygame.Rect
        self.increment = [0,0]
        self.inter = 5
        self._rotate_image()


    def _rotate_image(self):
        self.image = pygame.transform.rotate(self.image, (self.road_id+1)*90)
        self.rect = self.image.get_rect()
        if self.road_id == 0:
            self.increment = [0, self.rect.height+self.inter]
        elif self.road_id == 1:
            self.increment = [self.rect.width+self.inter, 0]
        elif self.road_id == 2:
            self.increment = [0, -(self.rect.height+self.inter)]
        elif self.road_id == 3:
            self.increment = [-(self.rect.width+self.inter), 0]

    def update(self, pos):
        self.rect.x = WAIT_LINE_INIT[self.road_id][0]+self.increment[0]*pos
        self.rect.y = WAIT_LINE_INIT[self.road_id][1]+self.increment[1]*pos

lock = threading.Lock()

class MyGroup(pygame.sprite.Group):
    def __init__(self):
        super().__init__()

    def draw(self, surface):
        lock.acquire()
        super().draw(surface)
        lock.release()


class PygameShower(object):
    def __init__(self):
        super().__init__()
        self.screen = SCREEN
        self.all_sprite_group = MyGroup()
        self.clock = pygame.time.Clock()
        self.road_queue = [[] for i in range(4)]

        self.flask_app = Flask(__name__)
        self._add_api_tasks()
        self.listen_thread = threading.Thread(target=self.listen)

    def _add_api_tasks(self):
        self.flask_app.add_url_rule('/update_waiting_queue', 'update_waiting_queue', self._update_waiting_queue, methods=['POST'])
        self.flask_app.add_url_rule('/test', 'test', self._test_listen, ['POST', 'GET'])

    def listen(self):
        self.flask_app.run(host='127.0.0.1', port=7878)

    def _test_listen(self):
        print("hello from client")
        return "hello from server"

    def _update_waiting_queue(self):
        line0 = int(request.form.get('0'))
        line1 = int(request.form.get('1'))
        line2 = int(request.form.get('2'))
        line3 = int(request.form.get('3'))
        queue_size_list = [line0, line1, line2, line3]
        lock.acquire()
        for road_id, length in enumerate(queue_size_list):
            dec = len(self.road_queue[road_id])-length
            if dec == 0:
                continue
            # 更新等待队列长度
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
        return "ok"

    def run(self):
        self.listen_thread.start()
        car = pygame.image.load("car0.png").convert_alpha()
        car = pygame.transform.scale(car, (30,15))
        self.clock.tick(30)
        running = True
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

    def _update_traffic_queue(self, queue_size_list):
        for road_id, length in enumerate(queue_size_list):
            dec = len(self.road_queue[road_id])-length
            if dec == 0:
                return
            # 更新等待队列长度
            if dec > 0:
                for k in range(dec):
                    car = self.road_queue[road_id][k]
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

    def _on_shutdown(self):
        if self.listen_thread:
            self.listen_thread.join()
        return

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._on_shutdown()


if __name__ == '__main__':
    with PygameShower() as app:
        app.run()