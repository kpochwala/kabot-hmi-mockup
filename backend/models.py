from dataclasses import dataclass

@dataclass
class Vector2:
    x: float
    y: float

@dataclass
class Vector3:
    x: float
    y: float
    z: float

@dataclass
class RobotState:
    distance: float
    effort: Vector2
    linear_acceleration: Vector3
    angular_velocity: Vector3
    magnetic_field: Vector3
    stamps: dict = None

@dataclass
class RobotControl:
    effort: Vector2
