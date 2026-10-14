@echo off
cd /d "%~dp0"
echo Starting DigiBuddy. The first run builds everything and takes 5-10 minutes...
docker compose up --build -d || goto :fail

echo Waiting for the API to be ready...
:wait
timeout /t 3 /nobreak >nul
docker compose exec -T api python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')" >nul 2>&1 || goto :wait

if not exist ".seeded" (
  echo Creating the demo account, about a minute...
  docker compose exec -T api python -m scripts.seed || goto :fail
  echo done> .seeded
)

echo.
echo DigiBuddy is running at http://localhost:3000
echo Demo login: demo@digibuddy.app / demo1234
start "" http://localhost:3000
pause
exit /b 0

:fail
echo.
echo Something went wrong. Is Docker Desktop open and showing "Engine running"?
echo For details run: docker compose logs api
pause
exit /b 1
