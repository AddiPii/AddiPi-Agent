# AddiPi Raspberry Pi Printer Agent
from config.config import init_config
from agent.printer_agent import PrinterAgent


def main():
    (
        device_conn_string,
        storage_conn_string,
        octoprint_api_key,
        octoprint_url
    ) = init_config()

    agent = PrinterAgent(
        device_connection_string=device_conn_string,
        storage_connection_string=storage_conn_string,
        octoprint_api_key=octoprint_api_key,
        octoprint_url=octoprint_url
    )

    agent.start()


if __name__ == '__main__':
    main()
