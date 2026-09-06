#!/bin/bash
set -e

# Initialize runtime directories
mkdir -p /home/wineuser/sessions
mkdir -p /home/wineuser/PDF
mkdir -p /tmp/.X11-unix
chmod 1777 /tmp/.X11-unix

echo "Starting win32-vnc-k8s orchestrator..."
exec python3 -m orchestrator.api.main
