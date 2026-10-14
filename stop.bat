@echo off
cd /d "%~dp0"
docker compose stop
echo DigiBuddy stopped. Your accounts and data are kept.
pause
