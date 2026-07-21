"""Base class for controllers.

Controllers orchestrate one or more services inside a single database
session/transaction and expose plain-Python-object results to the UI layer.
Views call controllers; controllers never import CustomTkinter, and views
never import services or the database session directly.
"""
from __future__ import annotations

from utils.logger import get_logger


class BaseController:
    def __init__(self) -> None:
        self.logger = get_logger(self.__class__.__module__)
