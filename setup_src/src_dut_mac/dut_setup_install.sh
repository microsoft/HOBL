#!/bin/sh
# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

# Set BIN_DIR to /Users/Shared/hobl_bin
BIN_DIR="/Users/Shared/hobl_bin"

# Helper function for error checking
check_status() {
    if [ $? -ne 0 ]; then
        log " ERROR - $1 failed"
        exit 1
    fi
    log "$1 successful"
}

# Create assets folder if it does not exist
if [ ! -d $BIN_DIR ]; then
    mkdir $BIN_DIR
fi

# Install SimpleRemote
echo "Installing SimpleRemoteConsole..."
cp ./SimpleRemoteConsole_osx-arm64.zip $BIN_DIR
unzip -o $BIN_DIR/SimpleRemoteConsole_osx-arm64.zip -d $BIN_DIR/SimpleRemote
# Remove the zip file after extraction
rm $BIN_DIR/SimpleRemoteConsole_osx-arm64.zip

# Copy launch script to BIN_DIR
echo "Copying launch script..."
cp ./launch_simple_remote.sh $BIN_DIR/SimpleRemote

# Install InputInject
echo "Installing InputInject..."
cp ./InputInject_osx-arm64.zip $BIN_DIR
unzip -o $BIN_DIR/InputInject_osx-arm64.zip -d $BIN_DIR/InputInject
# Remove the zip file after extraction
rm $BIN_DIR/InputInject_osx-arm64.zip

# Install ScreenServer
echo "Installing ScreenServer..."
cp ./ScreenServer_osx-arm64.zip $BIN_DIR
unzip -o $BIN_DIR/ScreenServer_osx-arm64.zip -d $BIN_DIR/ScreenServer
# Remove the zip file after extraction
rm $BIN_DIR/ScreenServer_osx-arm64.zip

# Install brightness utility
echo "Installing brightness utility..."
cp ./brightness $BIN_DIR/brightness
chmod +x $BIN_DIR/brightness

# Install certificates
echo "Installing certificates..."
sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain ./root_cert.pem
sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain ./int_cert.pem

# Stop any curent instance of SimpleRemote
echo "Stopping any current instance of SimpleRemote..."
killall SimpleRemoteConsole 2>&1 >/dev/null
sleep 1s

# Install Launch Agent
echo "Installing Launch Agent..."
mkdir -p ~/Library/LaunchAgents
chmod 700 ~/Library/LaunchAgents
cp ./simple_remote.plist ~/Library/LaunchAgents/
chmod 700 ~/Library/LaunchAgents/simple_remote.plist

# Start SimpleRemtote
echo "Starting SimpleRemote..."
launchctl enable gui/$(id -u)/SimpleRemote
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/simple_remote.plist
sleep 1s
launchctl kickstart gui/$(id -u)/SimpleRemote

# Set dock size to 60 pixels
echo "Setting Dock size to 60 pixels..."
defaults write com.apple.dock tilesize -int 60

# Disable tiled winoow margins
echo "Disabling tiled window margins..."
defaults write com.apple.WindowManager EnableTiledWindowMargins -bool false

# Restart the Dock to apply changes
echo "Restarting the Dock to apply changes..."
killall Dock

# Install desktop images
echo "Installing desktop images..."
rm -rf $BIN_DIR/DesktopImages
cp -R ./DesktopImages $BIN_DIR
osascript -e 'tell application "System Events" to tell every desktop to set picture to POSIX file "/Users/Shared/hobl_bin/DesktopImages/ColorChecker3000x2000_bar.png"'

# Trigger the security & privacy notification for screen & audio recording and documents.
HOST="localhost"
PORT="8000"

# Function to send RPC request using netcat with persistent connection
send_rpc() {
    local payload="$1"
    local name="$2"

    echo "Sending $name..."
    local response=$(echo "$payload" | nc -w 10 $HOST $PORT)

    echo "Response for $name: $response"
    return 0
}
# === PAYLOAD 1 ===
PAYLOAD1='{"method": "PluginLoad","params":["InputInject", "InputInject.Application", "/Users/Shared/hobl_bin/InputInject/InputInject.dll"], "jsonrpc": "2.0", "id": "1"}'
# === PAYLOAD 2 ===
PAYLOAD2='{"method": "StartJobWithNotification", "params": [null, null, "bash", "High", "-c \"ls ~/Documents\""], "jsonrpc": "2.0", "id": "1"}'
# === PAYLOAD 3 ===
PAYLOAD3='{"method": "PluginCallMethod", "params": ["InputInject", "MoveBy", 10, 10], "jsonrpc": "2.0", "id": "1"}'
# === PAYLOAD 4 ===
PAYLOAD4='{"method": "StartJobWithNotification", "params": [null, null, "bash", "High", "-c \"ls ~/Downloads\""], "jsonrpc": "2.0", "id": "1"}'


send_rpc "$PAYLOAD1" "Plugin Load"
send_rpc "$PAYLOAD2" "Documents Access Trigger"
send_rpc "$PAYLOAD3" "Accessibility Trigger"
send_rpc "$PAYLOAD4" "Downloads Access Trigger"

echo ""
echo "======================================================"
echo "  ACTION REQUIRED:"
echo "  Enable the permissions for SimpleRemoteConsole by going through screen & system audio recording pop up."
echo "  If popup disappeared the setting is under:"
echo "  System Settings → Privacy & Security → Screen & System Audio Recording -> Allow SimpleRemoteConsole"
echo "======================================================"
read -rp "Press Enter to continue once permissions are enabled..."
echo ""
# Kill simpleremote and start it again after user sets permission for screen recording
echo "Killing SimpleRemoteConsole"
pkill -x "SimpleRemoteConsole"
sleep 5
# Start SimpleRemtote
echo "Starting SimpleRemote..."
launchctl enable gui/$(id -u)/SimpleRemote
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/simple_remote.plist
sleep 1s
launchctl kickstart gui/$(id -u)/SimpleRemote

send_rpc "$PAYLOAD1" "Plugin Load"
send_rpc "$PAYLOAD3" "Accessibility Trigger"
send_rpc "$PAYLOAD3" "Accessibility Trigger"



# Install Brew (or verify it exists at default location)
echo "Installing Brew"
if [ -x /opt/homebrew/bin/brew ]; then
    echo "Brew already installed at /opt/homebrew/bin/brew"
else
    export NONINTERACTIVE=1
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    check_status "Brew installation"
fi

# Verify brew is installed at expected location
if [ ! -x /opt/homebrew/bin/brew ]; then
    echo " ERROR - Homebrew not found at /opt/homebrew/bin/brew"
    exit 1
fi
echo "Homebrew verified at /opt/homebrew/bin/brew"
eval "$(/opt/homebrew/bin/brew shellenv)"

# Install ffmpeg
echo "Installing ffmpeg"
brew install ffmpeg
check_status "ffmpeg installation"
