import requests
from typing import Dict, Any
from utils.logger import get_logger


logger = get_logger(__name__)


class OctoPrintClient:
    """Klient do komunikacji z OctoPrint"""
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.headers = {
            'X-Api-Key': api_key,
            'Content-Type': 'application/json'
        }

    def get_printer_state(self) -> Dict[str, Any]:
        """Pobiera aktualny stan drukarki"""
        try:
            response = requests.get(
                f'{self.base_url}/api/printer',
                headers=self.headers,
                timeout=5
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f'Błąd pobierania stanu drukarki: {e}')
            return {'state': {'text': 'Error'}}

    def is_printer_ready(self) -> bool:
        """Sprawdza czy drukarka jest gotowa do druku"""
        state = self.get_printer_state()
        state_text = state.get('state', {}).get('text', '').lower()
        return state_text in ['operational', 'ready']

    def upload_and_select_file(self, file_path: str, filename: str) -> bool:
        """Uploaduje plik do OctoPrint i go wybiera"""
        try:
            with open(file_path, 'rb') as f:
                files = {'file': (filename, f, 'application/octet-stream')}
                data = {'select': 'true', 'print': 'false'}

                response = requests.post(
                    f'{self.base_url}/api/files/local',
                    headers={'X-Api-Key': self.api_key},
                    files=files,
                    data=data,
                    timeout=30
                )
                response.raise_for_status()
                logger.info(f'Plik {filename} uploadowany do OctoPrint')
                return True
        except Exception as e:
            logger.error(f'Błąd uploadowania pliku do OctoPrint: {e}')
            return False

    def start_print(self) -> bool:
        """Rozpoczyna drukowanie wybranego pliku"""
        try:
            response = requests.post(
                f'{self.base_url}/api/job',
                headers=self.headers,
                json={'command': 'start'},
                timeout=5
            )
            response.raise_for_status()
            logger.info('Drukowanie rozpoczęte w OctoPrint')
            return True
        except Exception as e:
            logger.error(f'Błąd rozpoczynania druku: {e}')
            return False

    def get_job_info(self) -> Dict[str, Any]:
        """Pobiera informacje o aktualnym zadaniu"""
        try:
            response = requests.get(
                f'{self.base_url}/api/job',
                headers=self.headers,
                timeout=5
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f'Błąd pobierania info o zadaniu: {e}')
            return {}

    def cancel_print(self) -> bool:
        """Anuluje bieżący wydruk"""
        try:
            response = requests.post(
                f'{self.base_url}/api/job',
                headers=self.headers,
                json={'command': 'cancel'},
                timeout=5
            )
            response.raise_for_status()
            logger.info('Drukowanie anulowane w OctoPrint')
            return True
        except Exception as e:
            logger.error(f'Błąd anulowania druku: {e}')
            return False
