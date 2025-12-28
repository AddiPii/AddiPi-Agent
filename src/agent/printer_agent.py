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
            storage_connection_string: str,
            octoprint_url: str,
            octoprint_api_key: str
    ):
        self.iot_client = IoTHubDeviceClient.create_from_connection_string(
            device_connection_string
        )

        self.blob_service = BlobServiceClient.from_connection_string(
            storage_connection_string
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

            self.iot_client.send_message(message)
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
                    'reason': 'download_failed'
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

    def handle_cancel_print_method(self, request) -> MethodResponse:
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
            logger.error(f'Error handling cancelPrint: {e}')
            return MethodResponse.create_from_method_request(
                request,
                500,
                {'error': str(e)}
            )

    def monitor_print_progress(self):
        if not self.is_printing:
            return

        job_info = self.octoprint.get_job_info()
        progress = job_info.get('progress', {})
        state = job_info.get('state', 'Unknown')

        completion = progress.get('completion', 0)
        print_time = progress.get('printTime', 0)
        print_time_left = progress.get('printTimeLeft', 0)

        logger.info(
            f'Print status: {state}, Progress: {completion:.1f}%, '
            f'Time: {print_time}s, Left: {print_time_left}s'
        )

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

        if state.lower() in ['operational', 'ready'] and self.is_printing:
            print_duration = time.time() - self.print_start_time if self.print_start_time else 0

            self.send_telemetry('print_completed', {
                'jobId': self.current_job_id,
                'fileId': self.current_file_id,
                'printDuration':  print_duration,
                'success': True
            })

            logger.info(
                f'Printing job {self.current_job_id} successfully finished'
                )

            self.is_printing = False
            self.current_job_id = None
            self.current_file_id = None
            self.print_start_time = None

        elif state.lower() in ['error', 'offline'] and self.is_printing:
            self.send_telemetry('print_failed', {
                'jobId': self.current_job_id,
                'fileId': self.current_file_id,
                'reason': f'printer error: {state}',
                'success': False
            })

            logger.error(
                f'Printing job {self.current_job_id} finished with error: {state}'
            )

            self.is_printing = False
            self.current_job_id = None
            self.current_file_id = None
            self.print_start_time = None

    def start(self):
        try:
            self.iot_client.connect()
            logger.info('Connected with IoT Hub')

            self.iot_client.on_method_request_received = self.handle_method_request

            logger.info('Agent ready for receiving commands')

            self.send_telemetry('agent_started', {
                'version': '1.0.0'
            })

            while True:
                self.monitor_print_progress()
                time.sleep(10)

        except KeyboardInterrupt:
            logger.info('Agent stopped...')
            self.send_telemetry('agent_stopped', {})
        except Exception as e:
            logger.error(f'Error in the main loop: {e}')
            self.send_telemetry('agent_error', {'error': str(e)})
        finally:
            self.iot_client.disconnect()
            logger.info('Agent stopped')

    def handle_method_request(self, request):
        logger.info(f'Method received: {request.name}')

        if request.name == "startPrint":
            return self.handle_start_print_method(request)
        elif request.name == "cancelPrint":
            return self.handle_cancel_print_method(request)
        elif request.name == "getStatus":
            return self.handle_get_status_method(request)
        else:
            return MethodResponse.create_from_method_request(
                request,
                404,
                {'error': f'Method {request.name} not found'}
            )

    def handle_get_status_method(self, request) -> MethodResponse:
        try:
            printer_state = self.octoprint.get_printer_state()
            job_info = self.octoprint.get_job_info()

            status = {
                'isPrinting': self.is_printing,
                'currentJobId': self.current_job_id,
                'currentFileId': self.current_file_id,
                'printerState': printer_state.get('state', {}).get('text'),
                'progress': job_info.get('progress', {}).get('completion', 0),
                'timestamp': datetime.now().isoformat()
            }

            return MethodResponse.create_from_method_request(
                request,
                200,
                status
            )
        except Exception as e:
            return MethodResponse.create_from_method_request(
                request,
                500,
                {'error': str(e)}
            )
