# AddiPi Raspberry Pi Printer Agent
from config.config import init_config


def main():
    (
        device_conn_string,
        storage_conn_string,
        octoprint_api_key,
        octoprint_url
    ) = init_config()

    print(octoprint_api_key)


if __name__ == '__main__':
    main()
