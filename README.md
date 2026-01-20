# AddiPi-Agent

An intelligent agent for managing 3D printers on Raspberry Pi, integrating OctoPrint with Azure IoT Hub and Azure Blob Storage.

## 📋 Table of Contents

- [Project Overview](#project-overview)
- [System Requirements](#system-requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running](#running)
- [Architecture](#architecture)
- [API Interface](#api-interface)
- [Telemetry](#telemetry)
- [Docker](#docker)
- [Troubleshooting](#troubleshooting)

## 🎯 Project Overview

**AddiPi-Agent** is an intelligent agent for Raspberry Pi that:

- 🖨️ Manages 3D printers through **OctoPrint**
- ☁️ Communicates with Azure cloud via **IoT Hub**
- 📦 Downloads G-code files from **Azure Blob Storage**
- 📊 Sends telemetry about print progress and device status
- 🎛️ Supports remote printer control via Direct Methods

### Key Features

1. **Print Job Management**
   - Download G-code files from the cloud
   - Automatic file upload and selection in OctoPrint
   - Real-time print progress monitoring

2. **IoT Hub Communication**
   - Device-to-Cloud (D2C) telemetry transmission
   - Direct Methods support
   - Method support: `startPrint`, `cancelPrint`, `getStatus`

3. **Printer Status Monitoring**
   - Print progress tracking
   - Nozzle and bed temperature retrieval
   - Error detection and job completion

## 🔧 System Requirements

### Hardware
- **Raspberry Pi** (3B+ or newer recommended)
- **3D Printer** with OctoPrint support
- **Network connectivity** to Azure cloud

### Software
- **Python 3.10+**
- **pip** (package manager)
- **OctoPrint** (installed and running on the same network)

## 📦 Installation

### 1. Clone the Repository

```bash
git clone <repository-URL>
cd AddiPi-Agent
```

### 2. Create Virtual Environment (optional but recommended)

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### Project Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `azure-iot-device` | ≥2.14.0 | Communication with Azure IoT Hub |
| `azure-storage-blob` | ≥12.19.1 | Access to Azure Blob Storage |
| `requests` | - | HTTP communication with OctoPrint |
| `dotenv` | - | Environment variable management |

## ⚙️ Configuration

The agent is configured through environment variables. Create a `.env` file in the project root directory:

```env
# Azure IoT Hub
DEVICE_CONNECTION_STRING=HostName=<iothub-name>.azure-devices.net;DeviceId=<device-id>;SharedAccessKey=<key>

# Azure Blob Storage
STORAGE_CONN=DefaultEndpointsProtocol=https;AccountName=<account>;AccountKey=<key>;EndpointSuffix=core.windows.net

# OctoPrint
OCTOPRINT_URL=http://prusai3mk3.local  # OctoPrint URL (default shown)
OCTOPRINT_API_KEY=<api-key-from-octoprint>
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DEVICE_CONNECTION_STRING` | ✅ | Azure IoT Hub connection parameters |
| `STORAGE_CONN` | ✅ | Azure Blob Storage connection parameters |
| `OCTOPRINT_URL` | ❌ | OctoPrint URL (default: http://prusai3mk3.local) |
| `OCTOPRINT_API_KEY` | ✅ | API key from OctoPrint |

### Getting Azure Parameters

1. **IoT Hub Connection String:**
   - Azure Portal → IoT Hub → Devices → Your device → Connection strings

2. **Storage Connection String:**
   - Azure Portal → Storage Account → Access keys → Connection string

### Getting OctoPrint API Key

1. Log in to OctoPrint
2. Settings → API → Generate new API key
3. Copy the key to the `.env` file

## 🚀 Running

### Running as Python Script

```bash
python src/app.py
```

### Running in Background (Linux/Mac)

```bash
nohup python src/app.py > agent.log 2>&1 &
```

### Running with systemd (Linux)

Create file `/etc/systemd/system/addipi-agent.service`:

```ini
[Unit]
Description=AddiPi Printer Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/path/to/AddiPi-Agent
ExecStart=/usr/bin/python3 src/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Activation:
```bash
sudo systemctl daemon-reload
sudo systemctl enable addipi-agent
sudo systemctl start addipi-agent
sudo systemctl status addipi-agent
```

## 🏗️ Architecture

### Directory Structure

```
AddiPi-Agent/
├── src/
│   ├── app.py                    # Application entry point
│   ├── agent/
│   │   ├── printer_agent.py      # Main agent logic
│   │   └── octoprint_client.py   # OctoPrint client
│   ├── config/
│   │   └── config.py             # Configuration management
│   └── utils/
│       └── logger.py             # Logging
├── requirements.txt              # Python dependencies
├── Dockerfile                    # Docker configuration
└── README.md                     # Documentation
```

### Components

#### [app.py](src/app.py)
Application entry point. Initializes configuration and launches the agent.

#### [printer_agent.py](src/agent/printer_agent.py)
Main system component responsible for:
- Managing IoT Hub connection
- Fetching and sending telemetry
- Handling Direct Methods
- Monitoring print progress
- Communicating with Blob Storage

**Class: `PrinterAgent`**

Key methods:
- `start_print_job()` - Starts a print job
- `send_telemetry()` - Sends data to IoT Hub
- `monitor_print_progress()` - Monitors progress
- `handle_method_request()` - Handles method requests

#### [octoprint_client.py](src/agent/octoprint_client.py)
HTTP wrapper for OctoPrint API. Handles:
- Printer status retrieval
- File upload and selection
- Print control (start, cancel)
- Job information retrieval

**Class: `OctoPrintClient`**

#### [config.py](src/config/config.py)
Loads and validates environment variables from `.env` file.

#### [logger.py](src/utils/logger.py)
Configures logging system for the entire application.

### Data Flow

```
Azure IoT Hub
      ↓
[Direct Method Request]
      ↓
PrinterAgent.handle_method_request()
      ↓
OctoPrintClient.upload_and_select_file()
      ↓
OctoPrintClient.start_print()
      ↓
[Monitoring Loop]
      ↓
PrinterAgent.monitor_print_progress()
      ↓
Azure IoT Hub (Telemetry)
```

## 🔌 API Interface

The agent supports three main Direct Methods in Azure IoT Hub:

### 1. **startPrint**

Starts printing a file downloaded from Azure Blob Storage.

**Request:**
```json
{
  "jobId": "job-123",
  "fileId": "model.gcode"
}
```

**Response (success):**
```json
{
  "status": "printing_started",
  "jobId": "job-123"
}
```

**Response (error):**
```json
{
  "error": "Failed to start printing"
}
```

**Status codes:**
- `200` - Print started
- `400` - Missing parameters
- `500` - Print error

### 2. **cancelPrint**

Cancels the current print job.

**Request:**
```json
{}
```

**Response (success):**
```json
{
  "status": "print_cancelled",
  "jobId": "job-123"
}
```

**Status codes:**
- `200` - Print cancelled
- `400` - No active job
- `500` - Cancel error

### 3. **getStatus**

Retrieves current printer and job status.

**Request:**
```json
{}
```

**Response:**
```json
{
  "isPrinting": true,
  "currentJobId": "job-123",
  "currentFileId": "model.gcode",
  "printerState": "Printing",
  "progress": 45.5,
  "temperature": {
    "nozzle": 210.5,
    "bed": 60.2
  },
  "timestamp": "2024-01-20T10:30:45.123456"
}
```

## 📊 Telemetry

The agent sends the following telemetry events to IoT Hub:

### Events

| Event | Sent | Data |
|-------|------|------|
| `agent_started` | At startup | `version` |
| `print_started` | Print start | `jobId`, `fileId` |
| `print_progress` | Every 30 seconds | `progress`, `printTime`, `printTimeLeft`, `state` |
| `print_completed` | Print end | `jobId`, `printDuration`, `success` |
| `print_failed` | Print error | `jobId`, `reason` |
| `print_cancelled` | Cancellation | `jobId` |
| `agent_stopped` | Shutdown | - |
| `agent_error` | Agent error | `error` |

### Telemetry Message Format

Each telemetry message has the structure:

```json
{
  "event": "print_progress",
  "timestamp": "2024-01-20T10:30:45.123456",
  "deviceId": "raspberry-pi-mkt-01",
  "progress": 45.5,
  "printTime": 1800,
  "printTimeLeft": 2200,
  "state": "Printing"
}
```

### IoT Hub Routing

Messages contain custom properties for easier routing:
- `eventType` - Event type
- `jobId` - Job ID (if available)

Routing rule example:
```
SELECT * FROM devices WHERE properties.system.connection_auth_method = 'sas' 
  AND eventType = 'print_completed'
```

## 🐳 Docker

The project includes Docker configuration for running the agent in a container.

### Building the Image

```bash
docker build -t addipi-agent:latest .
```

### Running the Container

```bash
docker run -d \
  --name addipi-agent \
  --env-file .env \
  --restart unless-stopped \
  addipi-agent:latest
```

### Docker Compose (optional)

Create file `docker-compose.yml`:

```yaml
version: '3.8'
services:
  addipi-agent:
    build: .
    container_name: addipi-agent
    env_file: .env
    restart: unless-stopped
    volumes:
      - ./logs:/app/logs
```

Running:
```bash
docker-compose up -d
```

## ❓ Troubleshooting

### Problem: "DEVICE_CONNECTION_STRING is not set"

**Cause:** Missing environment variable.

**Solution:**
1. Check if `.env` file exists in the root directory
2. Ensure `DEVICE_CONNECTION_STRING` variable is set
3. Reload environment variables: `source .env`

### Problem: "Failed to connect to OctoPrint"

**Cause:** No connection to OctoPrint or incorrect URL.

**Solution:**
1. Check if OctoPrint is running: `curl http://prusai3mk3.local`
2. Verify URL in `OCTOPRINT_URL` variable
3. Check network connection between Raspberry Pi and printer

### Problem: "Unauthorized (401)" from OctoPrint API

**Cause:** Incorrect API key.

**Solution:**
1. Log in to OctoPrint
2. Generate a new API key
3. Update `OCTOPRINT_API_KEY` in `.env` file

### Problem: "Failed to download file from Blob Storage"

**Cause:** Incorrect connection string or file doesn't exist.

**Solution:**
1. Check if file exists in `gcode` container
2. Verify connection string in `STORAGE_CONN` variable
3. Check Azure Storage account permissions

### Enable Debug Logging

Edit [logger.py](src/utils/logger.py):

```python
logging.basicConfig(
    level=logging.DEBUG,  # Change to DEBUG
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### Viewing Logs

```bash
# For systemd
sudo journalctl -u addipi-agent -f

# For Docker containers
docker logs -f addipi-agent
```

## 📝 License

The project is available under the MIT License.

## 👨‍💻 Authors

@ovezthaking

## 🤝 Contributing

All suggestions and pull requests are welcome!



# AddiPi-Agent - Polish
Agent do zarządzania drukarkami 3D na Raspberry Pi, integrujący OctoPrint z Azure IoT Hub i Azure Blob Storage.

## 📋 Spis treści

- [Opis projektu](#opis-projektu)
- [Wymagania systemowe](#wymagania-systemowe)
- [Instalacja](#instalacja)
- [Konfiguracja](#konfiguracja)
- [Uruchomienie](#uruchomienie)
- [Architektura](#architektura)
- [Interfejs API](#interfejs-api)
- [Telemetria](#telemetria)
- [Docker](#docker)
- [Rozwiązywanie problemów](#rozwiązywanie-problemów)

## 🎯 Opis projektu

**AddiPi-Agent** to inteligentny agent dla Raspberry Pi, który:

- 🖨️ Zarządza drukarkami 3D za pośrednictwem **OctoPrint**
- ☁️ Komunikuje się z chmurą Azure za pośrednictwem **IoT Hub**
- 📦 Pobiera pliki G-code z **Azure Blob Storage**
- 📊 Wysyła telemetrię o postępie druku i stanie urządzenia
- 🎛️ Obsługuje sterowanie drukarką zdalne za pośrednictwem Direct Methods

### Główne funkcjonalności

1. **Zarządzanie zadaniami drukowania**
   - Pobieranie plików G-code z chmury
   - Automatyczne nagrywanie i wybieranie pliku w OctoPrint
   - Monitorowanie postępu drukowania w czasie rzeczywistym

2. **Komunikacja z IoT Hub**
   - Wysyłanie telemetrii Device-to-Cloud (D2C)
   - Obsługa metod bezpośrednich (Direct Methods)
   - Obsługa żądań metod: `startPrint`, `cancelPrint`, `getStatus`

3. **Monitorowanie stanu drukarki**
   - Śledzenie postępu drukowania
   - Pobieranie temperatury dysz i łóżka
   - Detekcja błędów i zakończeń zadań

## 🔧 Wymagania systemowe

### Sprzęt
- **Raspberry Pi** (3B+ lub nowsze zalecane)
- **Drukarka 3D** ze wsparcie OctoPrint
- **Połączenie sieciowe** do chmury Azure

### Oprogramowanie
- **Python 3.10+**
- **pip** (menedżer pakietów)
- **OctoPrint** (zainstalowany i uruchomiony na tej samej sieci)

## 📦 Instalacja

### 1. Klonowanie repozytorium

```bash
git clone <URL-repozytorium>
cd AddiPi-Agent
```

### 2. Tworzenie wirtualnego środowiska (opcjonalnie, ale zalecane)

```bash
python -m venv venv
source venv/bin/activate  # Na Windows: venv\Scripts\activate
```

### 3. Instalacja zależności

```bash
pip install -r requirements.txt
```

### Zależności projektu

| Pakiet | Wersja | Zastosowanie |
|--------|--------|--------------|
| `azure-iot-device` | ≥2.14.0 | Komunikacja z Azure IoT Hub |
| `azure-storage-blob` | ≥12.19.1 | Dostęp do Azure Blob Storage |
| `requests` | - | Komunikacja HTTP z OctoPrint |
| `dotenv` | - | Zarządzanie zmiennymi środowiska |

## ⚙️ Konfiguracja

Agent konfiguruje się poprzez zmienne środowiska. Utwórz plik `.env` w katalogu głównym projektu:

```env
# Azure IoT Hub
DEVICE_CONNECTION_STRING=HostName=<iothub-name>.azure-devices.net;DeviceId=<device-id>;SharedAccessKey=<key>

# Azure Blob Storage
STORAGE_CONN=DefaultEndpointsProtocol=https;AccountName=<account>;AccountKey=<key>;EndpointSuffix=core.windows.net

# OctoPrint
OCTOPRINT_URL=http://prusai3mk3.local  # URL do OctoPrint (domyślnie pokazana wartość)
OCTOPRINT_API_KEY=<api-key-z-octaprint>
```

### Zmienne środowiska

| Zmienna | Wymagana | Opis |
|---------|----------|------|
| `DEVICE_CONNECTION_STRING` | ✅ | Parametry połączenia Azure IoT Hub |
| `STORAGE_CONN` | ✅ | Parametry połączenia Azure Blob Storage |
| `OCTOPRINT_URL` | ❌ | URL do OctoPrint (domyślnie: http://prusai3mk3.local) |
| `OCTOPRINT_API_KEY` | ✅ | Klucz API z OctoPrint |

### Pobranie parametrów Azure

1. **IoT Hub Connection String:**
   - Azure Portal → IoT Hub → Devices → Twoje urządzenie → Connection strings

2. **Storage Connection String:**
   - Azure Portal → Storage Account → Access keys → Connection string

### Pobranie klucza OctoPrint

1. Zaloguj się do OctoPrint
2. Ustawienia → API → Wygeneruj nowy klucz API
3. Skopiuj klucz do pliku `.env`

## 🚀 Uruchomienie

### Uruchomienie jako skrypt Python

```bash
python src/app.py
```

### Uruchomienie w tle (Linux/Mac)

```bash
nohup python src/app.py > agent.log 2>&1 &
```

### Uruchomienie z systemd (Linux)

Utwórz plik `/etc/systemd/system/addipi-agent.service`:

```ini
[Unit]
Description=AddiPi Printer Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/path/to/AddiPi-Agent
ExecStart=/usr/bin/python3 src/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Aktywacja:
```bash
sudo systemctl daemon-reload
sudo systemctl enable addipi-agent
sudo systemctl start addipi-agent
sudo systemctl status addipi-agent
```

## 🏗️ Architektura

### Struktura katalogów

```
AddiPi-Agent/
├── src/
│   ├── app.py                    # Punkt wejścia aplikacji
│   ├── agent/
│   │   ├── printer_agent.py      # Główna logika agenta
│   │   └── octoprint_client.py   # Klient do OctoPrint
│   ├── config/
│   │   └── config.py             # Zarządzanie konfiguracją
│   └── utils/
│       └── logger.py             # Logowanie
├── requirements.txt              # Zależności Python
├── Dockerfile                    # Konfiguracja Docker
└── README.md                     # Niniejszy plik
```

### Komponenty

#### [app.py](src/app.py)
Punkt wejścia aplikacji. Inicjalizuje konfigurację i uruchamia agenta.

#### [printer_agent.py](src/agent/printer_agent.py)
Główny komponent systemu odpowiadający za:
- Zarządzanie połączeniem z IoT Hub
- Pobieranie i wysyłanie telemetrii
- Obsługę metod Direct Methods
- Monitorowanie postępu drukowania
- Komunikację z magazynem Blob Storage

**Klasa: `PrinterAgent`**

Kluczowe metody:
- `start_print_job()` - Uruchamia zadanie drukowania
- `send_telemetry()` - Wysyła dane do IoT Hub
- `monitor_print_progress()` - Monitoruje postęp
- `handle_method_request()` - Obsługuje żądania metod

#### [octoprint_client.py](src/agent/octoprint_client.py)
Wrapper HTTP dla API OctoPrint. Obsługuje:
- Pobieranie stanu drukarki
- Upload i wybieranie plików
- Kontrola drukowania (start, anulowanie)
- Pobieranie informacji o zadaniach

**Klasa: `OctoPrintClient`**

#### [config.py](src/config/config.py)
Ładuje i waliduje zmienne środowiska z pliku `.env`.

#### [logger.py](src/utils/logger.py)
Konfiguruje system logowania dla całej aplikacji.

### Przepływ danych

```
Azure IoT Hub
      ↓
[Direct Method Request]
      ↓
PrinterAgent.handle_method_request()
      ↓
OctoPrintClient.upload_and_select_file()
      ↓
OctoPrintClient.start_print()
      ↓
[Monitoring Loop]
      ↓
PrinterAgent.monitor_print_progress()
      ↓
Azure IoT Hub (Telemetria)
```

## 🔌 Interfejs API

Agent obsługuje trzy główne metody Direct Methods w Azure IoT Hub:

### 1. **startPrint**

Rozpoczyna drukowanie pliku pobranego z Azure Blob Storage.

**Żądanie:**
```json
{
  "jobId": "job-123",
  "fileId": "model.gcode"
}
```

**Odpowiedź (sukces):**
```json
{
  "status": "printing_started",
  "jobId": "job-123"
}
```

**Odpowiedź (błąd):**
```json
{
  "error": "Failed to start printing"
}
```

**Kody statusu:**
- `200` - Drukowanie rozpoczęte
- `400` - Brakuje parametrów
- `500` - Błąd podczas drukowania

### 2. **cancelPrint**

Anuluje bieżące zadanie drukowania.

**Żądanie:**
```json
{}
```

**Odpowiedź (sukces):**
```json
{
  "status": "print_cancelled",
  "jobId": "job-123"
}
```

**Kody statusu:**
- `200` - Drukowanie anulowane
- `400` - Brak aktywnego zadania
- `500` - Błąd anulowania

### 3. **getStatus**

Pobiera aktualny status drukarki i zadania.

**Żądanie:**
```json
{}
```

**Odpowiedź:**
```json
{
  "isPrinting": true,
  "currentJobId": "job-123",
  "currentFileId": "model.gcode",
  "printerState": "Printing",
  "progress": 45.5,
  "temperature": {
    "nozzle": 210.5,
    "bed": 60.2
  },
  "timestamp": "2024-01-20T10:30:45.123456"
}
```

## 📊 Telemetria

Agent wysyła następujące zdarzenia telemetryczne do IoT Hub:

### Zdarzenia

| Zdarzenie | Wysyłane | Dane |
|-----------|----------|------|
| `agent_started` | Przy starcie | `version` |
| `print_started` | Początek druku | `jobId`, `fileId` |
| `print_progress` | Co 30 sekund | `progress`, `printTime`, `printTimeLeft`, `state` |
| `print_completed` | Koniec druku | `jobId`, `printDuration`, `success` |
| `print_failed` | Błąd druku | `jobId`, `reason` |
| `print_cancelled` | Anulowanie | `jobId` |
| `agent_stopped` | Zatrzymanie | - |
| `agent_error` | Błąd agenta | `error` |

### Format wiadomości telemetrycznej

Każda wiadomość telemetryczna ma strukturę:

```json
{
  "event": "print_progress",
  "timestamp": "2024-01-20T10:30:45.123456",
  "deviceId": "raspberry-pi-mkt-01",
  "progress": 45.5,
  "printTime": 1800,
  "printTimeLeft": 2200,
  "state": "Printing"
}
```

### Routing w IoT Hub

Wiadomości zawierają custom properties ułatwiające routing:
- `eventType` - Typ zdarzenia
- `jobId` - ID zadania (jeśli dostępne)

Przykład reguły routingu:
```
SELECT * FROM devices WHERE properties.system.connection_auth_method = 'sas' 
  AND eventType = 'print_completed'
```

## 🐳 Docker

Projekt zawiera konfigurację Docker do uruchomienia agenta w kontenerze.

### Build obrazu

```bash
docker build -t addipi-agent:latest .
```

### Uruchomienie kontenera

```bash
docker run -d \
  --name addipi-agent \
  --env-file .env \
  --restart unless-stopped \
  addipi-agent:latest
```

### Docker Compose (opcjonalnie)

Utwórz plik `docker-compose.yml`:

```yaml
version: '3.8'
services:
  addipi-agent:
    build: .
    container_name: addipi-agent
    env_file: .env
    restart: unless-stopped
    volumes:
      - ./logs:/app/logs
```

Uruchomienie:
```bash
docker-compose up -d
```

## ❓ Rozwiązywanie problemów

### Problem: "DEVICE_CONNECTION_STRING is not set"

**Przyczyna:** Brakuje zmiennej środowiska.

**Rozwiązanie:**
1. Sprawdź czy plik `.env` istnieje w katalogu głównym
2. Upewnij się że zmienna `DEVICE_CONNECTION_STRING` jest ustawiona
3. Przeładuj zmienne środowiska: `source .env`

### Problem: "Failed to connect to OctoPrint"

**Przyczyna:** Brakuje połączenia z OctoPrint lub błędny URL.

**Rozwiązanie:**
1. Sprawdź czy OctoPrint jest uruchomiony: `curl http://prusai3mk3.local`
2. Zweryfikuj URL w zmiennej `OCTOPRINT_URL`
3. Sprawdź połączenie sieciowe między Raspberry Pi a drukarką

### Problem: "Unauthorized (401)" z OctoPrint API

**Przyczyna:** Błędny klucz API.

**Rozwiązanie:**
1. Zaloguj się do OctoPrint
2. Utwórz nowy klucz API
3. Zaktualizuj `OCTOPRINT_API_KEY` w pliku `.env`

### Problem: "Failed to download file from Blob Storage"

**Przyczyna:** Błędny connection string lub plik nie istnieje.

**Rozwiązanie:**
1. Sprawdź czy plik istnieje w kontenerze `gcode`
2. Zweryfikuj connection string w zmiennej `STORAGE_CONN`
3. Sprawdź uprawnienia konta Azure Storage

### Włączenie debug loggingu

Edytuj [logger.py](src/utils/logger.py):

```python
logging.basicConfig(
    level=logging.DEBUG,  # Zmień na DEBUG
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### Podgląd logów

```bash
# Dla systemd
sudo journalctl -u addipi-agent -f

# Dla kontenerów Docker
docker logs -f addipi-agent
```

## 📝 Licencja

Projekt jest dostępny na licencji MIT.

## 👨‍💻 Autorzy

@ovezthaking

## 🤝 Wkład

Wszelkie sugestie i pull requesty są mile widziane!