# schemas/enums.py
from enum import Enum

class Status(str, Enum):
    active = "active"
    inactive = "inactive"
    suspended = "suspended"
    draft = "draft"
