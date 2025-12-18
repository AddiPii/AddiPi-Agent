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

    def is_printer_ready(self) -> bool:
        state = self.get_printer_state()
        state_text = state.get('state', {}).get('text', '').lower()
        return state_text in ['operational', 'ready']

    def upload_and_select_file(self, file_path: str, filename: str) -> bool:
        try:
            with open(file_path, 'rb') as f:
                files = {'file': (filename, f, 'application/octet-stream')}
                data = {'select': 'true', 'print': 'false'}

                response = requests.post(
                    f'{self.base_url}/api/files/local',
                    headers={'X-Api-Key': self.api_key},
                    files=files,
                    data=data,
                    timeout=300
                )
                response.raise_for_status()
                logger.info(f'File {filename} uploading to OctoPrint')
                return True
        except Exception as e:
            logger.error(f'Error uploading file to Octoprint: {e}')
            return False

    def start_print(self) -> bool:
        try:
            response = requests.post(
                f'{self.base_url}/api/job',
                headers=self.headers,
                json={'command': 'start'},
                timeout=5
            )
            response.raise_for_status()
            logger.info('Printing started in OctoPrint')
            return True
        except Exception as e:
            logger.error(f'Error starting a print: {e}')
            return False

    def get_job_info(self) -> Dict[str, Any]:
        try:
            response = requests.get(
                f'{self.base_url}/api/job',
                headers=self.headers,
                timeout=5
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f'Error getting info about the job: {e}')
            return {}
