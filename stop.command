#!/bin/bash
cd "$(dirname "$0")" || exit 1
docker compose stop
echo "DigiBuddy stopped. Your accounts and data are kept."
read -r -p "Press Enter to close."
