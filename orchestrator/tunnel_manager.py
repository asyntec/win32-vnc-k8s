import subprocess
import socket
import time
import logging
import os
import re

logger = logging.getLogger(__name__)

HOSTNAME_REGEX = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9\-\.]{0,253}[a-zA-Z0-9])?$")

class TunnelManager:
    """
    Generic local proxy helper using socat.
    Encapsulates TCP streams into TLS 1.2 with Server Name Indication (SNI)
    strictly binding to localhost (127.0.0.1) for isolation.
    """
    def __init__(self, target_host: str, target_port: int, sni_host: str = None):
        if not HOSTNAME_REGEX.match(target_host) or "," in target_host:
            raise ValueError(f"Invalid target_host: illegal characters or format ({target_host})")
        if not (1 <= int(target_port) <= 65535):
            raise ValueError(f"Invalid target_port: must be 1-65535 ({target_port})")

        self.target_host = target_host
        self.target_port = int(target_port)
        self.sni_host = sni_host or target_host

        if not HOSTNAME_REGEX.match(self.sni_host) or "," in self.sni_host:
            raise ValueError(f"Invalid sni_host: illegal characters or format ({self.sni_host})")

        self.process = None
        self.local_port = None

    def _get_free_port(self) -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('127.0.0.1', 0))
            return s.getsockname()[1]

    def start(self) -> int:
        self.local_port = self._get_free_port()
        cmd = [
            "socat",
            "-b", "4096",
            f"TCP-LISTEN:{self.local_port},bind=127.0.0.1,fork,reuseaddr,keepalive=1,nodelay=1",
            f"OPENSSL:{self.target_host}:{self.target_port},verify=1,snihost={self.sni_host},keepalive=1,nodelay=1"
        ]
        self.log_file = f"/tmp/tunnel_{self.local_port}.log"
        with open(self.log_file, "w") as f:
            self.process = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT)

        for _ in range(50):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(('127.0.0.1', self.local_port)) == 0:
                    logger.info(f"Tunnel active: 127.0.0.1:{self.local_port} -> {self.target_host}:{self.target_port}")
                    return self.local_port
            time.sleep(0.05)

        raise RuntimeError(f"Failed to establish tunnel for {self.target_host}")

    def stop(self):
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None
        if hasattr(self, "log_file") and self.log_file and os.path.exists(self.log_file):
            try:
                os.remove(self.log_file)
            except OSError:
                pass
