from enum import Enum

class EntityType(str, Enum):
    USER = "USER"
    DEVICE = "DEVICE"
    IP = "IP"
    DOMAIN = "DOMAIN"
    PROCESS = "PROCESS"
    FILE = "FILE"
    HASH = "HASH"
