from utils.logger import get_logger
from azure.iot.device import IoTHubDeviceClient, Message
from azure.storage.blob import BlobServiceClient
from octoprint_client import OctoPrintClient
import os
from typing import Optional, Dict, Any
from datetime import datetime
import json


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
