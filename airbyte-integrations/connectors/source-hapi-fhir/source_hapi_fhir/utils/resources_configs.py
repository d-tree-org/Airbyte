import json
from typing import Any, Dict
import os


class ResourceConfigs:
    def __init__(self, path: str) -> None:
        self.resources_config: Dict[str, Any] = self.load_resources_config(path)

    @staticmethod
    def load_resources_config(path: str) -> Dict[str, Any]:
        try:
            with open(path, 'r') as file:
                return json.load(file)
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError:
            return {}

path = os.path.join(os.path.dirname(__file__), 'resources.json')
resources_config = ResourceConfigs(path).resources_config

