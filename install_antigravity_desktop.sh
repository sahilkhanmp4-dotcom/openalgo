#!/usr/bin/env bash
set -e

echo "========================================================"
echo "🚀 Installing Google Antigravity Desktop on Lubuntu..."
echo "========================================================"

# Step 1: Add official Google repository signing key
echo "1. Adding repository signing key..."
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://us-central1-apt.pkg.dev/doc/repo-signing-key.gpg | sudo gpg --dearmor --yes -o /etc/apt/keyrings/antigravity-repo-key.gpg

# Step 2: Add repository source list
echo "2. Adding Antigravity repository..."
echo "deb [signed-by=/etc/apt/keyrings/antigravity-repo-key.gpg] https://us-central1-apt.pkg.dev/projects/antigravity-auto-updater-dev/ antigravity-debian main" | sudo tee /etc/apt/sources.list.d/antigravity.list > /dev/null

# Step 3: Update package list
echo "3. Updating apt package list..."
sudo apt update

# Step 4: Install Antigravity desktop application
echo "4. Installing Antigravity Desktop application..."
sudo apt install -y antigravity

echo "========================================================"
echo "🎉 Installation Complete!"
echo "You can now launch Antigravity from your Application Menu"
echo "or by typing 'antigravity' in terminal."
echo "========================================================"
