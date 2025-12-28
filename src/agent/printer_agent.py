from utils.logger import get_logger
from azure.iot.device import IoTHubDeviceClient, MethodResponse, Message
from azure.storage.blob import BlobServiceClient
from octoprint_client import OctoPrintClient
import os
from typing import Optional


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
