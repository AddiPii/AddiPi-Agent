from utils.logger import get_logger
from azure.iot.device import IoTHubDeviceClient, MethodResponse, Message
from azure.storage.blob import BlobServiceClient
from .octoprint_client import OctoPrintClient
import os
from typing import Optional, Dict, Any
from datetime import datetime
import json
import time


logger = get_logger(__name__)


class PrinterAgent:
    """Główny agent drukarki"""

    def __init__(
        self,
        device_connection_string: str,
        storage_connection_string: str,
        octoprint_url: str,
        octoprint_api_key: str
    ):
        # IoT Hub Client
        self.iot_client = IoTHubDeviceClient.create_from_connection_string(
            device_connection_string
        )

        # Azure Blob Storage Client
        self.blob_service = BlobServiceClient.from_connection_string(
            storage_connection_string
        )
        self.container_name = 'gcode'

        # OctoPrint Client
        self.octoprint = OctoPrintClient(octoprint_url, octoprint_api_key)

        # Lokalny katalog na pliki
        self.local_files_dir = '/tmp/addipi_files'
        os.makedirs(self.local_files_dir, exist_ok=True)

        # Status
        self.current_job_id: Optional[str] = None
        self.current_file_id: Optional[str] = None
        self.is_printing = False
        self.print_start_time: Optional[float] = None
        self.last_progress_report: float = 0

        logger.info('PrinterAgent zainicjalizowany')

    def download_file_from_blob(self, file_id: str) -> Optional[str]:
        """Pobiera plik z Azure Blob Storage"""
        try:
            container_client = self.blob_service.get_container_client(
                self.container_name
            )
            blob_client = container_client.get_blob_client(file_id)

            local_path = os.path.join(self.local_files_dir, file_id)

            logger.info(f'Pobieranie pliku {file_id} z Blob Storage...')
            with open(local_path, 'wb') as f:
                blob_data = blob_client.download_blob()
                blob_data.readinto(f)

            logger.info(f'Plik {file_id} pobrany do {local_path}')
            return local_path
        except Exception as e:
            logger.error(f'Błąd pobierania pliku z Blob Storage: {e}')
            return None

    def send_telemetry(self, event_type: str, data: Dict[str, Any]):
        """Wysyła telemetrię do IoT Hub (Device-to-Cloud message)"""
        try:
            message_data = {
                'event': event_type,
                'timestamp': datetime.utcnow().isoformat(),
                'deviceId': 'raspberry-pi-mkt-01',
                **data
            }

            message = Message(json.dumps(message_data))
            message.content_encoding = "utf-8"
            message.content_type = "application/json"

            # Dodaj properties dla łatwiejszego routingu w IoT Hub
            message.custom_properties["eventType"] = event_type
            if self.current_job_id:
                message.custom_properties["jobId"] = self.current_job_id

            self.iot_client.send_message(message)
            logger.info(f'Wysłano telemetrię: {event_type}')

        except Exception as e:
            logger.error(f'Błąd wysyłania telemetrii: {e}')

    def start_print_job(self, file_id: str, job_id: str) -> bool:
        """Rozpoczyna zadanie drukowania"""
        try:
            # Sprawdź stan drukarki
            if not self.octoprint.is_printer_ready():
                logger.error('Drukarka nie jest gotowa')
                self.send_telemetry('print_failed', {
                    'jobId': job_id,
                    'fileId': file_id,
                    'reason': 'printer_not_ready'
                })
                return False

            # Pobierz plik z Blob Storage
            local_path = self.download_file_from_blob(file_id)
            if not local_path:
                self.send_telemetry('print_failed', {
                    'jobId': job_id,
                    'fileId': file_id,
                    'reason': 'download_failed'
                })
                return False

            # Upload do OctoPrint
            if not self.octoprint.upload_and_select_file(local_path, file_id):
                self.send_telemetry('print_failed', {
                    'jobId': job_id,
                    'fileId': file_id,
                    'reason': 'upload_to_octoprint_failed'
                })
                return False

            # Rozpocznij druk
            if not self.octoprint.start_print():
                self.send_telemetry('print_failed', {
                    'jobId': job_id,
                    'fileId': file_id,
                    'reason': 'start_print_failed'
                })
                return False

            self.current_job_id = job_id
            self.current_file_id = file_id
            self.is_printing = True
            self.print_start_time = time.time()

            # Wyślij telemetrię o rozpoczęciu druku
            self.send_telemetry('print_started', {
                'jobId': job_id,
                'fileId': file_id
            })

            logger.info(f'Zadanie {job_id} rozpoczęte pomyślnie')
            return True

        except Exception as e:
            logger.error(f'Błąd w start_print_job: {e}')
            self.send_telemetry('print_failed', {
                'jobId': job_id,
                'fileId': file_id,
                'reason': str(e)
            })
            return False

    def handle_start_print_method(self, request) -> MethodResponse:
        """Obsługuje metodę startPrint z IoT Hub"""
        try:
            payload = json.loads(request.payload)
            file_id = payload.get('fileId')
            job_id = payload.get('jobId')

            logger.info(f'Otrzymano komendę startPrint: {payload}')

            if not file_id or not job_id:
                return MethodResponse.create_from_method_request(
                    request,
                    400,
                    json.dumps({'error': 'Missing fileId or jobId'})
                )

            # Rozpocznij drukowanie
            success = self.start_print_job(file_id, job_id)

            if success:
                return MethodResponse.create_from_method_request(
                    request,
                    200,
                    json.dumps({'status': 'printing_started', 'jobId': job_id})
                )
            else:
                return MethodResponse.create_from_method_request(
                    request,
                    500,
                    json.dumps({'error': 'Failed to start printing'})
                )

        except Exception as e:
            logger.error(f'Błąd obsługi startPrint: {e}')
            return MethodResponse.create_from_method_request(
                request,
                500,
                json.dumps({'error': str(e)})
            )

    def handle_cancel_print_method(self, request) -> MethodResponse:
        """Obsługuje metodę cancelPrint z IoT Hub"""
        try:
            if not self.is_printing:
                return MethodResponse.create_from_method_request(
                    request,
                    400,
                    json.dumps({'error': 'No active print job'})
                )

            if self.octoprint.cancel_print():
                self.send_telemetry('print_cancelled', {
                    'jobId': self.current_job_id,
                    'fileId': self.current_file_id
                })

                self.is_printing = False
                job_id = self.current_job_id
                self.current_job_id = None
                self.current_file_id = None

                return MethodResponse.create_from_method_request(
                    request,
                    200,
                    json.dumps({'status': 'print_cancelled', 'jobId': job_id})
                )
            else:
                return MethodResponse.create_from_method_request(
                    request,
                    500,
                    json.dumps({'error': 'Failed to cancel print'})
                )

        except Exception as e:
            logger.error(f'Błąd obsługi cancelPrint: {e}')
            return MethodResponse.create_from_method_request(
                request,
                500,
                json.dumps({'error': str(e)})
            )

    def monitor_print_progress(self):
        """Monitoruje postęp drukowania"""
        if not self.is_printing:
            return

        job_info = self.octoprint.get_job_info()
        progress = job_info.get('progress', {})
        state = job_info.get('state', 'Unknown')

        completion = progress.get('completion', 0)
        print_time = progress.get('printTime', 0)
        print_time_left = progress.get('printTimeLeft', 0)

        logger.info(
            f'Stan druku: {state}, Postęp: {completion:.1f}%, '
            f'Czas: {print_time}s, Pozostało: {print_time_left}s'
        )

        # Wysyłaj raport postępu co 30 sekund
        current_time = time.time()
        if current_time - self.last_progress_report > 30:
            self.send_telemetry('print_progress', {
                'jobId': self.current_job_id,
                'fileId': self.current_file_id,
                'progress': completion,
                'printTime': print_time,
                'printTimeLeft': print_time_left,
                'state': state
            })
            self.last_progress_report = current_time

        # Sprawdź czy druk się zakończył
        if state.lower() in ['operational', 'ready'] and self.is_printing:
            # Druk zakończony pomyślnie
            print_duration = time.time() - self.print_start_time if self.print_start_time else 0
            self.send_telemetry('print_completed', {
                'jobId': self.current_job_id,
                'fileId': self.current_file_id,
                'printDuration': print_duration,
                'success': True
            })

            logger.info(f'Druk zadania {self.current_job_id} zakończony pomyślnie')

            self.is_printing = False
            self.current_job_id = None
            self.current_file_id = None
            self.print_start_time = None

        elif state.lower() in ['error', 'offline'] and self.is_printing:
            # Druk zakończony błędem
            self.send_telemetry('print_failed', {
                'jobId': self.current_job_id,
                'fileId': self.current_file_id,
                'reason': f'printer_error: {state}',
                'success': False
            })

            logger.error(f'Druk zadania {self.current_job_id} zakończony błędem: {state}')

            self.is_printing = False
            self.current_job_id = None
            self.current_file_id = None
            self.print_start_time = None

    def start(self):
        """Uruchamia agenta"""
        try:
            # Połącz z IoT Hub
            self.iot_client.connect()
            logger.info('Połączono z IoT Hub')

            # Zarejestruj handler dla metod (MUSI BYĆ PO connect())
            self.iot_client.on_method_request_received = self.handle_method_request

            logger.info('Agent gotowy do odbierania komend')
            logger.info('Zarejestrowane metody: startPrint, cancelPrint, getStatus')

            # Wysłij wiadomość o starcie
            self.send_telemetry('agent_started', {
                'version': '1.0.0'
            })

            # Główna pętla monitorowania
            while True:
                self.monitor_print_progress()
                time.sleep(10)  # Sprawdzaj co 10 sekund

        except KeyboardInterrupt:
            logger.info('Zatrzymywanie agenta...')
            self.send_telemetry('agent_stopped', {})
        except Exception as e:
            logger.error(f'Błąd w głównej pętli: {e}')
            self.send_telemetry('agent_error', {'error': str(e)})
        finally:
            self.iot_client.disconnect()
            logger.info('Agent zatrzymany')

    def handle_method_request(self, request):
        """Główny router dla Direct Methods"""
        try:
            logger.info(f'📞 Otrzymano metodę: {request.name}')

            if request.name == "startPrint":
                response = self.handle_start_print_method(request)
            elif request.name == "cancelPrint":
                response = self.handle_cancel_print_method(request)
            elif request.name == "getStatus":
                response = self.handle_get_status_method(request)
            else:
                response = MethodResponse.create_from_method_request(
                    request,
                    404,
                    {'error': f'Method {request.name} not found'}
                )

            self.iot_client.send_method_response(response)
            logger.info(f'✅ Odpowiedź wysłana dla {request.name}: status {response.status}')
            return response

        except Exception as e:
            logger.error(f'❌ Błąd obsługi metody {request.name}: {e}')
            return MethodResponse.create_from_method_request(
                request,
                500,
                {'error': str(e)}
            )

    def handle_get_status_method(self, request) -> MethodResponse:
        """Zwraca aktualny status drukarki"""
        try:
            logger.info('🔍 Pobieranie statusu drukarki...')

            printer_state = self.octoprint.get_printer_state()
            job_info = self.octoprint.get_job_info()

            progress_data = job_info.get('progress', {})
            completion = progress_data.get('completion') if progress_data else None

            # Pobranie temperatur
            temperatures = printer_state.get('temperature', {})
            nozzle_temp = temperatures.get('tool0', {}).get('actual', 0.0)
            bed_temp = temperatures.get('bed', {}).get('actual', 0.0)

            status = {
                'isPrinting': self.is_printing,
                'currentJobId': self.current_job_id,
                'currentFileId': self.current_file_id,
                'printerState': printer_state.get('state', {}).get('text', 'Unknown'),
                'progress': completion if completion is not None else 0.0,  # <-- Zawsze liczba!
                'temperature': {
                    'nozzle': nozzle_temp,
                    'bed': bed_temp
                    },
                'timestamp': datetime.utcnow().isoformat()
            }

            logger.info(f'✅ Status: {status}')

            return MethodResponse.create_from_method_request(
                request,
                200,
                json.dumps(status)  # <-- To musi być string!
            )
        except Exception as e:
            logger.error(f'❌ Błąd pobierania statusu: {e}')
            return MethodResponse.create_from_method_request(
                request,
                500,
                json.dumps({'error': str(e)})
            )
