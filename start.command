#!/bin/bash
# DigiBuddy for macOS / Linux. Double-click in Finder, or run ./start.command
cd "$(dirname "$0")" || exit 1

fail() {
  echo
  echo "Something went wrong. Is Docker Desktop open and running?"
  echo "For details run: docker compose logs api"
  read -r -p "Press Enter to close."
  exit 1
}

echo "Starting DigiBuddy. The first run builds everything and takes 5-10 minutes..."
docker compose up --build -d || fail

echo "Waiting for the API to be ready..."
until docker compose exec -T api python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')" >/dev/null 2>&1; do
  sleep 3
done

if [ ! -f .seeded ]; then
  echo "Creating the demo account, about a minute..."
  docker compose exec -T api python -m scripts.seed || fail
  echo done > .seeded
fi

echo
echo "DigiBuddy is running at http://localhost:3000"
echo "Demo login: demo@digibuddy.app / demo1234"
open http://localhost:3000 2>/dev/null || xdg-open http://localhost:3000 2>/dev/null
read -r -p "Press Enter to close this window (DigiBuddy keeps running)."
