$ErrorActionPreference = "Stop"

$port = if ($env:PORT) { $env:PORT } else { "8000" }
$python = Join-Path $PSScriptRoot "venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Virtual environment not found at $python"
}

Write-Host "Starting MeteoSaarthi staging service on port $port"
Write-Host "Local URL: http://127.0.0.1:$port"
Write-Host "LAN URL:   http://$((Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.PrefixOrigin -ne 'WellKnown' } | Select-Object -First 1 -ExpandProperty IPAddress)):$port"

& $python -m uvicorn app.main:app --host 0.0.0.0 --port $port --workers 4