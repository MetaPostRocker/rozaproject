#!/bin/bash
# Installation script for Telegram bot on Ubuntu 22.04

set -e

echo "=== Updating system ==="
sudo apt update && sudo apt upgrade -y

echo "=== Installing Python 3.11 ==="
sudo apt install -y python3.11 python3.11-venv python3-pip git

echo "=== Creating bot directory ==="
sudo mkdir -p /opt/telegram-bot
sudo chown $USER:$USER /opt/telegram-bot

echo "=== Cloning repository ==="
cd /opt/telegram-bot
if [ -d ".git" ]; then
    git pull
else
    git clone https://github.com/MetaPostRocker/rozaproject.git .
fi

echo "=== Creating virtual environment ==="
python3.11 -m venv venv
source venv/bin/activate

echo "=== Installing dependencies ==="
pip install --upgrade pip
pip install -r requirements.txt

echo "=== Creating .env file template ==="
if [ ! -f .env ]; then
    cat > .env << 'EOF'
# Telegram Bot Token
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Google Sheets
GOOGLE_SHEETS_CREDENTIALS_FILE=credentials.json
SPREADSHEET_ID=your_spreadsheet_id_here

# Owner Telegram ID
OWNER_TELEGRAM_ID=your_telegram_id_here
EOF
    echo "!!! IMPORTANT: Edit /opt/telegram-bot/.env with your credentials !!!"
fi

echo "=== Setting up systemd service ==="
sudo cp deploy/telegram-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable telegram-bot

echo ""
echo "=== Installation complete ==="
echo ""
echo "Next steps:"
echo "1. Edit /opt/telegram-bot/.env with your credentials"
echo "2. Copy credentials.json to /opt/telegram-bot/"
echo "3. Start the bot: sudo systemctl start telegram-bot"
echo "4. Check status: sudo systemctl status telegram-bot"
echo "5. View logs: sudo journalctl -u telegram-bot -f"
