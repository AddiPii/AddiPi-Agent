import requests
from typing import Dict, Any
from utils.logger import get_logger


logger = get_logger(__name__)


class OctoPrintClient:

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.headers = {
            'X-Api-Key': api_key,
            'Content-Type': 'application/json'
        }

    def get_printer_state(self) -> Dict[str, Any]:
        try:
            response = requests.get(
                f'{self.base_url}/api/printer',
                headers=self.headers,
                timeout=5
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f'Error get printer state: {e}')
            return {'state': {'text': 'Error'}}
