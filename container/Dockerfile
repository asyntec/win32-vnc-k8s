FROM i386/debian:bookworm

ENV DEBIAN_FRONTEND=noninteractive

# Install core runtime dependencies
RUN apt-get update && apt-get install -y \
    wine \
    xvfb \
    fluxbox \
    x11vnc \
    novnc \
    websockify \
    python3 \
    python3-pip \
    python3-fastapi \
    python3-uvicorn \
    python3-psutil \
    python3-multipart \
    python3-aiofiles \
    python3-jinja2 \
    procps \
    cabextract \
    p7zip-full \
    wget \
    curl \
    unzip \
    libgnutls30 \
    gnutls-bin \
    socat \
    cups \
    printer-driver-cups-pdf \
    ghostscript \
    autocutsel \
    tigervnc-standalone-server \
    xdotool \
    && rm -rf /var/lib/apt/lists/*

# Global GnuTLS override for legacy Win32 cryptographic handshake compatibility
RUN mkdir -p /etc/gnutls && \
    echo "[overrides]" > /etc/gnutls/gnutls.conf && \
    echo "default-priority-string = NORMAL:%COMPAT" >> /etc/gnutls/gnutls.conf

# Install winetricks
RUN wget https://raw.githubusercontent.com/Winetricks/winetricks/master/src/winetricks -O /usr/local/bin/winetricks && \
    chmod +x /usr/local/bin/winetricks

# Create dedicated non-root wineuser
RUN useradd -m -s /usr/sbin/nologin wineuser
USER wineuser
WORKDIR /home/wineuser

# Wine base environment variables
ENV WINEPREFIX=/home/wineuser/.wine
ENV WINEARCH=win32
ENV DISPLAY=:0
ENV GNUTLS_CPUID_OVERRIDE=0x1
ENV GNUTLS_SYSTEM_PRIORITY_FILE=/etc/gnutls/gnutls.conf
ENV CUPS_SERVER=/home/wineuser/.cups/cups.sock

# Initialize base wine prefix with standard core libraries
RUN xvfb-run -a winetricks -q corefonts vcrun6 mfc42 win7

# Root setup for CUPS printing and directories
USER root
RUN mkdir -p /home/wineuser/.cups/spool /home/wineuser/.cups/interfaces /home/wineuser/.cups/cache \
             /home/wineuser/.cups/state /home/wineuser/.cups/tmp /home/wineuser/PDF /home/wineuser/sessions && \
    chown -R wineuser:wineuser /home/wineuser/.cups /home/wineuser/PDF /home/wineuser/sessions /etc/cups

COPY container/cupsd.conf /home/wineuser/.cups/cupsd.conf
COPY container/cups-pdf.conf /etc/cups/cups-pdf.conf
COPY container/cups-pdf-backend /usr/lib/cups/backend/cups-pdf
RUN chmod 755 /usr/lib/cups/backend/cups-pdf

# Inject transparent clipboard bridge into noVNC UI
COPY container/novnc_bridge.js /tmp/novnc_bridge.js
RUN cat /tmp/novnc_bridge.js >> /usr/share/novnc/app/ui.js && rm /tmp/novnc_bridge.js

# Copy entrypoint and application orchestrator
COPY container/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

COPY orchestrator /app/orchestrator
ENV PYTHONPATH=/app

# Expose HTTP API (8000) and WebSockets noVNC (6080)
EXPOSE 8000 6080

USER wineuser
WORKDIR /app
ENTRYPOINT ["/entrypoint.sh"]
