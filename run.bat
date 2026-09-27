@echo off
REM Start IP-SAKTI Sahayak on one port. Works with no API keys.
cd /d "%~dp0"
if "%PORT%"=="" set PORT=8000
python -c "import fastapi, uvicorn, yaml" 2>NUL || python -m pip install -q -r requirements.txt
if not exist web\dist (
  where npm >NUL 2>&1 && (pushd web && call npm ci --silent && call npm run --silent build & popd)
)
python -m uvicorn api.main:app --host 0.0.0.0 --port %PORT%
