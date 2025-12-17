# AddiPi Raspberry Pi Printer Agent
from config.config import init_config

(
    device_conn_string,
    storage_conn_string,
    octoprint_api_key,
    octoprint_url
) = init_config()


print(octoprint_api_key)
