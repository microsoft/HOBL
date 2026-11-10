#!/bin/sh
# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

if [ "$(id -u)" -eq 0 ]; then
    echo "ERROR - This needs to be run without sudo." >&2
    exit 1
fi

ARCH="arm64"
if [ "$(uname -m)" = "x86_64" ]; then
    ARCH="x64"
fi

sudo apt update

# Set BIN_DIR to /home/shared/hobl_bin
BIN_DIR="/home/shared/hobl_bin"

# Helper function for error checking
check_status() {
    if [ $? -ne 0 ]; then
        echo " ERROR - $1 failed"
        exit 1
    fi
    echo "$1 successful"
}

# Create shared user folder if it does not exist
if [ ! -d /home/shared ]; then
    sudo mkdir /home/shared
fi
sudo chmod 777 /home/shared

# Create assets folder if it does not exist
if [ ! -d $BIN_DIR ]; then
    mkdir -p $BIN_DIR
fi
chmod 777 $BIN_DIR

# Install SimpleRemote
echo "Installing $ARCH SimpleRemoteConsole..."
cp ./SimpleRemoteServer_linux-$ARCH.zip $BIN_DIR
unzip -o $BIN_DIR/SimpleRemoteServer_linux-$ARCH.zip -d $BIN_DIR/SimpleRemote
# Remove the zip file after extraction
rm $BIN_DIR/SimpleRemoteServer_linux-$ARCH.zip

# Copy launch script to BIN_DIR
echo "Copying launch script..."
cp ./launch_simple_remote.sh $BIN_DIR/SimpleRemote

# Install brightness utility
echo "Installing brightness utility..."
echo "Y" | sudo apt install brightnessctl

# Install remote
echo "Installing remote..."
mkdir -p $BIN_DIR/remote
cp ./remote_linux-$ARCH $BIN_DIR/remote/remote
chmod -R 755 $BIN_DIR/remote/remote

# Stop any curent instance of SimpleRemote
echo "Stopping any current instance of SimpleRemote..."
sudo killall -9 SimpleRemoteConsole 2>&1 >/dev/null
sleep 1s

# Setup SimpleRemote service
SERVICE_NAME="SimpleRemote"
SCRIPT_PATH="/home/shared/hobl_bin/SimpleRemote/launch_simple_remote.sh"
# Create systemd user directory if it does not exist
mkdir -p ~/.config/systemd/user
# Write the service file
# tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null <<EOF
tee ~/.config/systemd/user/${SERVICE_NAME}.service > /dev/null <<EOF
[Unit]
Description=SimpleRemoteConsole
After=network.target

[Service]
Type=simple
ExecStart=${SCRIPT_PATH}
RemainAfterExit=true

[Install]
WantedBy=default.target
EOF
chmod +x "${SCRIPT_PATH}"

# Reload systemd, enable and start the service
systemctl --user daemon-reload
systemctl --user enable "${SERVICE_NAME}.service"
systemctl --user start "${SERVICE_NAME}.service"
sudo loginctl enable-linger $USER

# Show status
systemctl --user status "${SERVICE_NAME}.service" --no-pager

# Install ifconfig
echo "Installing ifconfig..."
sudo apt install net-tools
check_status "ifconfig installation"

# Install curl
echo "Installing curl..."
sudo apt install curl
check_status "curl installation"

# Install desktop images
echo "Installing desktop images..."
rm -rf $BIN_DIR/DesktopImages
cp -R ./DesktopImages $BIN_DIR
chmod 777 $BIN_DIR/DesktopImages
chmod 666 $BIN_DIR/DesktopImages/*
gsettings set org.gnome.desktop.background picture-uri "file:///home/shared/hobl_bin/DesktopImages/ColorChecker3000x2000.png"
gsettings set org.gnome.desktop.background picture-uri-dark "file:///home/shared/hobl_bin/DesktopImages/ColorChecker3000x2000.png"

# Prevent screen from turning off and disable lock screen delay
gsettings set org.gnome.desktop.session idle-delay 0
gsettings set org.gnome.desktop.screensaver lock-enabled false

# Install ffmpeg
echo "Installing ffmpeg"
sudo apt install ffmpeg
check_status "ffmpeg installation"

echo "Installing remote dependencies"
sudo apt install libxcb-xtest0 libxcb-keysyms1
check_status "remote dependencies installation"
