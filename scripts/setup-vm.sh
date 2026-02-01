#!/bin/bash
# Tooeybot VM Setup Script
# Run this inside the Ubuntu VM after initial OS installation

set -e

echo "=== Tooeybot VM Setup ==="

# Update system
echo "Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install base dependencies
echo "Installing base dependencies..."
sudo apt install -y \
    build-essential \
    git \
    curl \
    wget \
    jq \
    tree \
    htop \
    python3.12 \
    python3.12-venv \
    python3-pip

# Set Python 3.12 as default
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1

# Create agent directory structure
echo "Creating agent directory structure..."
sudo mkdir -p /agent
sudo chown $USER:$USER /agent

# Clone or copy the tooeybot files (assumes you've SCPd them)
echo "Setting up agent filesystem..."
if [ -d "$HOME/tooeybot/agent" ]; then
    cp -r $HOME/tooeybot/agent/* /agent/
else
    echo "Note: Copy tooeybot/agent directory to /agent/"
fi

# Setup runtime
echo "Setting up Python runtime..."
if [ -d "$HOME/tooeybot/runtime" ]; then
    cd $HOME/tooeybot/runtime
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
else
    echo "Note: Copy tooeybot/runtime directory to ~/tooeybot/runtime"
fi

# Install Ollama (optional - can run on host instead)
read -p "Install Ollama locally in VM? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
    
    # Pull a default model
    echo "Pulling llama3.2 model..."
    ollama pull llama3.2
fi

# Create systemd service (optional)
read -p "Create systemd service for agent? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    sudo tee /etc/systemd/system/tooeybot.service > /dev/null <<EOF
[Unit]
Description=Tooeybot Autonomous Agent
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$HOME/tooeybot/runtime
ExecStart=$HOME/tooeybot/runtime/venv/bin/python -m tooeybot run
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    echo "Service created. Enable with: sudo systemctl enable --now tooeybot"
fi

# Initialize git repo for agent state
echo "Initializing git repository for agent state..."
cd /agent
git init
git add .
git commit -m "Initial agent state"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "1. Copy config.example.yaml to config.yaml and configure LLM settings"
echo "2. If using Ollama on host, update base_url in config.yaml"
echo "3. Test with: cd ~/tooeybot/runtime && source venv/bin/activate && python -m tooeybot health"
echo "4. Add a task to /agent/tasks/inbox.md"
echo "5. Run a tick: python -m tooeybot tick"
