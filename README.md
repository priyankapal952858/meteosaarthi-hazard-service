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
POST /alerts/test-sms?phone_number=+919876543210&message=Prototype%20SMS%20test
```

`/maps/radar` currently returns Open-Meteo rainfall as a clearly disclosed
substitute. Genuine IMD radar imagery requires an approved IMD provider
endpoint and access details.

## Prototype SMS testing

The service includes a prototype SMS flow for testing delivery to one trusted
team member before connecting a farmer contact list. It uses Fast2SMS when a
valid API key is configured. The API key is read from the environment and
must never be committed to GitHub.

In PowerShell, set the key in the same terminal that starts the service:

```powershell
$env:FAST2SMS_API_KEY = "<your-fast2sms-api-key>"
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/docs`, choose `POST /alerts/test-sms`, enter a
trusted team member's phone number and test message, then select **Execute**.
The number may be entered as `9876543210` or `+919876543210`.

The response reports whether delivery was successful, disabled because the
API key is missing, or rejected by the provider. A successful provider
response means the gateway accepted the request; confirm final delivery on
the recipient's phone. This endpoint is for internal testing only, not for
broadcasting to farmers.

### MOSDAC radar configuration

After MOSDAC provides the approved radar-image endpoint and token, configure
the service before starting it:

```powershell
$env:MOSDAC_RADAR_URL = "https://<approved-mosdac-endpoint>"
$env:MOSDAC_RADAR_TOKEN = "<approved-token>"
.\start_staging.ps1
```

The adapter sends `lat` and `lon` query parameters and expects an `image/*`
response. A successful response is returned as base64 image data with
`source: "MOSDAC"` and `data_type: "radar_imagery"`. If the endpoint is
missing, fails, or returns a non-image response, the service uses the
clearly labeled Open-Meteo rainfall fallback. Do not commit the token.

## Flood and live-signal coverage

The service uses two different kinds of flood-related information. They must
not be interpreted as the same measurement.

### Live detection used by the service

The service is not limited to the historical 1998-2022 atlas. Its current
hazard detection can use:

- **Current rainfall:** fetched from Open-Meteo when the request does not
  include a manual rainfall value.
- **Current river-discharge anomaly:** fetched from the Open-Meteo Flood API
  for locations where the primary atlas has no state-level data. The latest
  discharge is compared with the previous 30-day mean.
- **Real radar imagery:** fetched from MOSDAC when the approved live or
  standing-request radar endpoint is configured with `MOSDAC_RADAR_URL` and
  `MOSDAC_RADAR_TOKEN`.

If MOSDAC live radar access is not configured or temporarily fails, the radar
endpoint uses the clearly labeled Open-Meteo rainfall fallback. It never
claims that rainfall data is radar imagery.

### Primary historical atlas coverage

The NRSC/ISRO Flood Affected Area Atlas provides historical cumulative flood
affected-area data for these 25 states/UTs:

```text
Andhra Pradesh, Arunachal Pradesh, Assam, Bihar, Chhattisgarh, Delhi,
Gujarat, Haryana, Jammu & Kashmir, Jharkhand, Karnataka, Kerala,
Madhya Pradesh, Maharashtra, Manipur, Meghalaya, Odisha, Punjab,
Rajasthan, Tamil Nadu, Telangana, Tripura, Uttar Pradesh, Uttarakhand,
West Bengal
```

This atlas covers the period 1998-2022. It is historical context used to
strengthen risk assessment; it is not live flood detection, a current flood
observation, or a forecast.

### Backup coverage for other states/UTs

When the detected location is outside the primary list, the service calls the
Open-Meteo Flood API using the latitude and longitude. It compares the latest
river discharge with the previous 30-day mean and returns a
`river_discharge_anomaly` signal when data is available.

The backup can be used for locations such as Goa, Himachal Pradesh, Mizoram,
Nagaland, Sikkim, Puducherry, Ladakh, Chandigarh, Andaman & Nicobar Islands,
Lakshadweep, and Dadra & Nagar Haveli and Daman & Diu. Coverage depends on
the backup API having river-discharge data for the requested coordinates.

The backup signal is current/near-real-time context, not historical
flood-affected hectares. If the state cannot be detected or the backup API
fails, the response remains honest and reports flood data as unavailable.

### What “live” means in this service

- Rainfall is fetched from Open-Meteo when the client does not provide it.
- The backup provider supplies a current river-discharge comparison where
  primary atlas data is unavailable.
- Primary atlas values are never presented as live measurements.
- MOSDAC radar imagery is used only when its approved endpoint and token are
  configured; otherwise `/maps/radar` uses a clearly labeled rainfall
  fallback.

### Part 3 live-detection summary

For the GIS/Radar/Hazard responsibility, the service provides:

- **Live rainfall detection:** current hourly rainfall and intensity from
  Open-Meteo.
- **Live risk calculation:** current rainfall combined with available flood
  context.
- **Live hazard detection:** heavy-rainfall detection and elevated
  river-discharge anomaly detection.
- **Live alerts:** user-facing alerts generated from the detected hazards.
- **Live backup flood signal:** latest river discharge compared with the
  previous 30-day mean for locations outside primary atlas coverage.
- **Live radar imagery:** available only after the approved MOSDAC
  live/standing-request endpoint and token are configured.

The following are not live measurements:

- NRSC/ISRO flood atlas data from 1998-2022.
- GIS state boundaries used to identify the location's state.
- Historical flood-affected hectare and district statistics.

Therefore, the service currently supports live rainfall-based hazard
detection. Genuine live radar detection is implemented through a MOSDAC
adapter, but remains inactive until the approved MOSDAC endpoint and access
credentials are configured.

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