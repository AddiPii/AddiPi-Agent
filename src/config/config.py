import os
from dotenv import load_dotenv


load_dotenv()


def init_config():
    device_conn_string = os.getenv('DEVICE_CONNECTION_STRING')

    if not device_conn_string:
        raise ValueError('DEVICE_CONNECTION_STRING is not set')

    storage_conn_string = os.getenv('STORAGE_CONN')

    if not storage_conn_string:
        raise ValueError('STORAGE_CONN is not set')

    octoprint_api_key = os.getenv('OCTOPRINT_API_KEY')

    if not octoprint_api_key:
        raise ValueError('OCTOPRINT_API_KEY is not set')

    octoprint_url = os.getenv('OCTOPRINT_URL', 'http://prusai3mk3.local')

    return (
        device_conn_string,
        storage_conn_string,
        octoprint_api_key,
        octoprint_url
        )
