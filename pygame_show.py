#!python3

import pygame
import os
from enum import Enum, unique

@unique
class CarStateEnum(Enum):
    ON_LANE = 0x01
    ON_WAITING_INTERSECTION = 0x02
    ON_INTERSECTION = 0x03


class CarState(object):
    def __init__(self, type=None):
        self.type = type  # type: CarStateEnum

    def do_action(self):
        pass

    def check_station(self):
        pass

    def enter_state(self):
        pass

    def exit_state(self):
        pass


class OnLaneState(CarState):
    def __init__(self, car):
        super().__init__()
        self.type = CarStateEnum.ON_LANE
        self.car = car

    def do_action(self):
        pass

    def check_station(self):
        pass

    def enter_state(self):
        pass

    def exit_state(self):
        pass


class OnWaitingState(CarState):
    def __init__(self, car):
        super().__init__()
        self.type = CarStateEnum.ON_WAITING_INTERSECTION
        self.car = car

    def do_action(self):
        pass

    def check_station(self):
        pass

    def enter_state(self):
        pass

    def exit_state(self):
        pass


class OnIntersectionState(CarState):
    def __init__(self, car):
        super().__init__()
        self.type = CarStateEnum.ON_INTERSECTION
        self.car = car

    def do_action(self):
        pass

    def check_station(self):
        pass

    def enter_state(self):
        pass

    def exit_state(self):
        pass


class StateMachine(object):
    def __init__(self):
        self.states = {}          # type: dict[CarStateEnum,CarState]
        self.active_state = None  # type: CarState

    def add_state(self, state):
        self.states[state.type] = state

    def think(self):
        if self.active_state is None:
            return
        self.active_state.do_action()
        new_state_type = self.active_state.check_station()
        if new_state_type is not None:
            self.set_state(new_state_type)

    def set_state(self, state_type):
        if self.active_state is not None:
            self.active_state.exit_state()
        self.active_state = self.states[state_type]
        self.active_state.enter_state()


class Car(pygame.sprite.Sprite):
    def __init__(self, id=None, world=None, image_surface=None):
        super().__init__(self)
        self.id = id
        self.world = world
        self.image = image_surface
        self.speed = (0, 0)  # 带方向的speed
        self.rect = self.image.get_rect()
        self.state_machine = StateMachine()
        self._init_state_machine()

    def _init_state_machine(self):
        on_lane_state = OnLaneState(self)
        on_waiting_state = OnWaitingState(self)
        on_intersection_state = OnIntersectionState(self)
        self.state_machine.add_state(on_lane_state)
        self.state_machine.add_state(on_waiting_state)
        self.state_machine.add_state(on_intersection_state)

    def rotate(self, turn_type: str, radius: float):
        pass

    def update(self, *args):
        self.state_machine.think()



