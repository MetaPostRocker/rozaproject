#!/bin/bash
# Script to update the bot from GitHub

set -e

cd /opt/telegram-bot

echo "=== Stopping bot ==="
sudo systemctl stop telegram-bot

echo "=== Pulling updates ==="
git pull

echo "=== Activating venv ==="
source venv/bin/activate

echo "=== Updating dependencies ==="
pip install -r requirements.txt

echo "=== Starting bot ==="
sudo systemctl start telegram-bot

echo "=== Done! Checking status ==="
sudo systemctl status telegram-bot
