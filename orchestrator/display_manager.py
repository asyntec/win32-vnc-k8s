import subprocess
import socket
import time
import logging
import os
import threading
from typing import Optional
from .utils.token_manager import TokenManager

logger = logging.getLogger(__name__)
_ALLOCATION_LOCK = threading.Lock()

class DisplayManager:
    """
    Manages dynamic allocation of X11 displays and internal TigerVNC RFB ports.
    Applies 16-bit color depth optimization to reduce RAM and bandwidth by 50%.
    """
    def __init__(self, session_id: str, width: int = 1280, height: int = 720):
        self.session_id = session_id
        self.width = width
        self.height = height
        self.display = None
        self.vnc_port = None
        self.vnc_token = None
        self.vnc_proc = None
        self.autocutsel_proc1 = None
        self.autocutsel_proc2 = None
        self.token_mgr = TokenManager()

    def _get_free_display(self, start=100, end=1000) -> int:
        for d in range(start, end):
            socket_path = f"/tmp/.X11-unix/X{d}"
            lock_path = f"/tmp/.X{d}-lock"
            if not os.path.exists(socket_path) and not os.path.exists(lock_path):
                return d
        raise RuntimeError("No free X11 display available")

    def _get_free_port(self, start_port=5901, end_port=6000) -> int:
        for port in range(start_port, end_port + 1):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(('127.0.0.1', port))
                    return port
                except socket.error:
                    continue
        raise RuntimeError(f"No free port in range {start_port}-{end_port}")

    def start(self, vnc_token: Optional[str] = None):
        self.vnc_token = vnc_token or self.session_id
        with _ALLOCATION_LOCK:
            self.display = self._get_free_display()
            self.vnc_port = self._get_free_port()

            def run_proc(cmd, log_name):
                log_file = open(f"/tmp/{log_name}_{self.session_id}.log", "w")
                proc = subprocess.Popen(cmd, stdout=log_file, stderr=subprocess.STDOUT, start_new_session=True)
                log_file.close()
                return proc

            # 1. Start TigerVNC standalone server with 16-bit color depth optimization
            self.vnc_proc = run_proc([
                "Xvnc", f":{self.display}",
                "-geometry", f"{self.width}x{self.height}",
                "-depth", "16",
                "-rfbport", str(self.vnc_port),
                "-SecurityTypes", "None",
                "-localhost",
                "-desktop", f"win32-{self.session_id[:8]}",
                "-pn",
                "-FrameRate", "60"
            ], "Xvnc")

            # Wait for Xvnc socket creation
            socket_path = f"/tmp/.X11-unix/X{self.display}"
            ready = False
            for _ in range(50):
                if os.path.exists(socket_path):
                    ready = True
                    break
                time.sleep(0.05)

            if not ready:
                raise RuntimeError(f"Xvnc failed to initialize display :{self.display}")

        # 2. Start dual autocutsel for full CLIPBOARD and PRIMARY selection synchronization
        self.autocutsel_proc1 = run_proc([
            "autocutsel", "-display", f":{self.display}", "-s", "CLIPBOARD"
        ], "autocutsel_cb")
        self.autocutsel_proc2 = run_proc([
            "autocutsel", "-display", f":{self.display}", "-s", "PRIMARY"
        ], "autocutsel_pr")

        # 3. Register secure vnc_token for websockify single-port routing
        self.token_mgr.add_token(self.vnc_token, "127.0.0.1", self.vnc_port)
        return self.display, 6080

    def stop(self):
        if self.vnc_token:
            self.token_mgr.remove_token(self.vnc_token)
        for proc in [self.autocutsel_proc1, self.autocutsel_proc2, self.vnc_proc]:
            if proc:
                try:
                    proc.terminate()
                    proc.wait(timeout=2)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass

        lock_file = f"/tmp/.X{self.display}-lock"
        if os.path.exists(lock_file):
            try:
                os.remove(lock_file)
            except OSError:
                pass
