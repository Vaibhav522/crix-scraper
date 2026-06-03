#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "🚀 Starting project setup..."

# 1. Update package lists (Optional, uncomment if needed)
sudo apt update && apt upgrade -y

# 2. Ensure Python3 and Virtual Environment tools are installed
echo "📦 Checking for Python and venv..."
sudo apt install -y python3 python3-venv python3-pip

# 3. Create a virtual environment named 'venv'
echo "🛠️ Creating virtual environment..."
python3 -m venv ~/venv

# 4. Activate the virtual environment
echo "🔄 Activating virtual environment..."
source ~/venv/bin/activate

# 5. Upgrade pip inside the environment
echo "⬆️ Upgrading pip..."
pip install --upgrade pip

# 6. Install dependencies from requirements.txt
if [ -f requirements.txt ]; then
    echo "📥 Installing Python packages..."
    pip install -r requirements.txt
else
    echo "❌ Error: requirements.txt not found!"
    exit 1
fi

# 7. Install system dependencies and browser binaries for Playwright
echo "🌐 Installing Playwright browsers and system dependencies..."
playwright install chromium

sudo apt install xvfb -y

echo "✅ Setup complete! Project is ready."
echo "💡 To start working, activate the environment manually by running: source venv/bin/activate"


echo "Installing postgres"
sudo apt install -y postgresql postgresql-contrib

echo "Installing tmux"
sudo apt install tmux

