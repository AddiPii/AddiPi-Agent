from utils.logger import get_logger
from azure.iot.device import IoTHubDeviceClient, MethodResponse, Message
from azure.storage.blob import BlobServiceClient
from octoprint_client import OctoPrintClient
import os
from typing import Optional, Dict, Any
from datetime import datetime
import json
import time


logger = get_logger(__name__)


class PrinterAgent:
    def __init__(
            self,
            device_connection_string: str,
            storage_connection_String: str,
            octoprint_url: str,
            octoprint_api_key: str
    ):
        self.iot_cliet = IoTHubDeviceClient.create_from_connection_string(
            device_connection_string
        )

        self.blob_service = BlobServiceClient.from_connection_string(
            storage_connection_String
        )

        self.container_name = '.gcode'

        self.octoprint = OctoPrintClient(octoprint_url, octoprint_api_key)

        self.local_files_dir = '/tmp/addipi_files'
        os.makedirs(self.local_files_dir, exist_ok=True)

        self.current_job_id: Optional[str] = None
        self.current_file_id: Optional[str] = None
        self.is_printing = False
        self.print_start_time: Optional[float] = None
        self.last_progress_report: float = 0

        logger.info('PrinterAgent successfully initialized')

    def download_file_from_blob(self, file_id: str) -> Optional[str]:
        try:
            container_client = self.blob_service.get_container_client(
                self.container_name
            )
            blob_client = container_client.get_blob_client(file_id)

            local_path = os.path.join(self.local_files_dir, file_id)

            logger.info(f'Downloading file {file_id} from Blob Storage...')
            with open(local_path, 'wb') as f:
                blob_data = blob_client.download_blob()
                blob_data.readinto(f)

            logger.info(f'File {file_id} downloaded to {local_path}')
            return local_path
        except Exception as e:
            logger.error(f'Error downloading file from Blob Storage: {e}')
            return None

    def send_telemetry(self, event_type: str, data: Dict[str, Any]):
        try:
            message_data = {
                'event': event_type,
                'timestamp': datetime.now().isoformat(),
                'deviceId': 'raspberry-pi-mkt-01',
                **data
            }

            message = Message(json.dumps(message_data))
            message.content_encoding = 'utf-8'
            message.content_type = 'application/json'

            message.custom_properties['eventType'] = event_type
            if self.current_job_id:
                message.custom_properties['jobId'] = self.current_job_id

            self.iot_cliet.send_message(message)
            logger.info(f'Telemetry sent: {event_type}')

        except Exception as e:
            logger.error(f'Error sending telemetry: {e}')

    def start_print_job(self, file_id: str, job_id: str) -> bool:
        try:
            if not self.octoprint.is_printer_ready():
                logger.error('Printer is not ready')
                self.send_telemetry('print_failed', {
                    'jobId': job_id,
                    'fileId': file_id,
                    'reason': 'printer_not_ready'
                })
                return False

            local_path = self.download_file_from_blob(file_id)
            if not local_path:
                self.send_telemetry('print_failed', {
                    'jobId': job_id,
                    'fileId': file_id,
                    'reason': 'downloaded_failed'
                })
                return False

            if not self.octoprint.upload_and_select_file(local_path, file_id):
                self.send_telemetry('print_failed', {
                    'jobId': job_id,
                    'fileId': file_id,
                    'reason': 'upload_to_octoprint_failed'
                })
                return False

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

            self.send_telemetry('print_started', {
                'jobId': job_id,
                'fileId': file_id
            })

            logger.info(f'Job {job_id} started successfully')
            return True

        except Exception as e:
            logger.error(f'Error in start_print_job: {e}')
            self.send_telemetry('print_failed', {
                'jobId': job_id,
                'fileId': file_id,
                'reason': str(e)
            })
            return False

    def handle_start_print_method(self, request) -> MethodResponse:
        try:
            payload = json.loads(request.payload)
            file_id = payload.get('fileId')
            job_id = payload.get('jobId')

            logger.info(f'Received command startPrint: {payload}')

            if not file_id or not job_id:
                return MethodResponse.create_from_method_request(
                    request,
                    400,
                    {'error': 'Missing fileId or jobId'}
                )

            success = self.start_print_job(file_id, job_id)

            if success:
                return MethodResponse.create_from_method_request(
                    request,
                    200,
                    {'status': 'printing_started', 'jobId': job_id}
                )
            else:
                return MethodResponse.create_from_method_request(
                    request,
                    500,
                    {'error': 'Failed to start printing'}
                )

        except Exception as e:
            logger.error(f'Error handling startPrint: {e}')
            return MethodResponse.create_from_method_request(
                request,
                500,
                {'error': str(e)}
            )

    def handle_control_print_method(self, request) -> MethodResponse:
        try:
            if not self.is_printing:
                return MethodResponse.create_from_method_request(
                    request,
                    400,
                    {'error': 'No active print job'}
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
                    {'status': 'print_cancelled', 'jobId': job_id}
                )
            else:
                return MethodResponse.create_from_method_request(
                    request,
                    500,
                    {'error': 'Failed to cancel print'}
                )
        except Exception as e:
            logger.error(f'Error handling cancelPrint; {e}')
            return MethodResponse.create_from_method_request(
                request,
                500,
                {'error': str(e)}
            )
