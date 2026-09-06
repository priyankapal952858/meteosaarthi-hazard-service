# MeteoSaarthi Hazard Service

FastAPI service for GIS risk maps, rainfall signals, flood-hazard baselines,
and alert generation.

## Setup on a new computer

PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Linux or macOS:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Run locally

Windows:

```powershell
.\start_staging.ps1
```

Any platform:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open the API documentation at:

```text
http://127.0.0.1:8000/docs
```

## Main endpoints

```text
GET /health
GET /capabilities
GET /maps/risk?lat=19.076&lon=72.8777&rainfall=10
GET /maps/radar?lat=19.076&lon=72.8777
GET /alerts?lat=19.076&lon=72.8777&rainfall=10
```

`/maps/radar` currently returns Open-Meteo rainfall as a clearly disclosed
substitute. Genuine IMD radar imagery requires an approved IMD provider
endpoint and access details.

## Run tests

```powershell
python -m pytest -q
```

## Important data

The `data/` directory is required. Do not remove the state boundary GeoJSON
or the flood-hazard statistics JSON file.

## Handover notes

- The service uses historical NRSC/ISRO flood data where available.
- Uncovered states can use the separate Open-Meteo river-discharge backup
  signal when coordinates are provided.
- Errors include request and trace IDs where applicable.
- The LAN URL printed by `start_staging.ps1` works only on the same network.
- Do not share the local `venv/`, cache folders, or Python bytecode files.