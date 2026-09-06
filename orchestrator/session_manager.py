import logging
import os
import secrets
import shutil
import subprocess
import time
import uuid
from typing import Dict, Optional

from .display_manager import DisplayManager
from .wine_manager import WineManager

logger = logging.getLogger(__name__)

class Session:
    """
    Represents an isolated, containerized Win32 execution session.
    """
    def __init__(self, session_id: str, app_path: str = "notepad.exe", extra_env: Optional[Dict] = None):
        self.session_id = session_id
        self.vnc_token = secrets.token_urlsafe(24)  # Isolated secret token for streaming
        self.app_path = app_path
        self.extra_env = extra_env or {}
        default_dir = "/home/wineuser/sessions" if os.path.exists("/home/wineuser") else os.path.expanduser("~/.wine_sessions")
        self.wine_sessions_dir = os.getenv("WINE_SESSIONS_DIR", default_dir)
        self.wine_prefix = os.path.join(self.wine_sessions_dir, session_id)
        os.makedirs(self.wine_sessions_dir, exist_ok=True)

        self.display_mgr = DisplayManager(session_id)
        self.wine = WineManager(self.wine_prefix)
        self.shared_dir = os.path.join(self.wine_prefix, "drive_c", "Documents")
        os.makedirs(self.shared_dir, exist_ok=True)

        self.display = None
        self.ws_port = None
        self.app_proc = None
        self.last_activity = time.time()
        self._spool_watcher_running = False

    def touch(self):
        self.last_activity = time.time()

    def setup(self):
        logger.info(f"Starting session {self.session_id} with app {self.app_path}")
        self.display, self.ws_port = self.display_mgr.start(vnc_token=self.vnc_token)

        self.wine.env["DISPLAY"] = f":{self.display}"
        self.wine.initialize_prefix()

        env = self.wine.env.copy()
        env["DISPLAY"] = f":{self.display}"
        env.update(self.extra_env)

        # Run application inside isolated virtual desktop
        wine_cmd = ["wine", "explorer", "/desktop=session,1280x720", self.app_path]
        wine_log = open(os.path.join(self.wine_prefix, "wine.log"), "w")
        self.app_proc = subprocess.Popen(
            wine_cmd,
            env=env,
            cwd=self.shared_dir,
            stdout=wine_log,
            stderr=subprocess.STDOUT,
            start_new_session=True
        )
        wine_log.close()

        self._start_spool_watcher()
        return {
            "session_id": self.session_id,
            "display": self.display,
            "ws_port": self.ws_port,
            "vnc_url": f"/vnc/vnc.html?path=vnc/?token={self.vnc_token}&autoconnect=true&resize=scale"
        }

    def _start_spool_watcher(self):
        """Background thread detecting PostScript .SPL print jobs and rendering to PDF via Ghostscript."""
        import threading
        self._spool_watcher_running = True

        def watcher_loop():
            spool_dir = os.path.join(self.wine_prefix, "drive_c", "windows", "system32", "spool", "printers")
            if not os.path.exists(spool_dir):
                return

            while getattr(self, "_spool_watcher_running", False):
                try:
                    for fname in os.listdir(spool_dir):
                        if not fname.lower().endswith(".spl"):
                            continue
                        spl_file = os.path.join(spool_dir, fname)
                        if os.path.islink(spl_file) or not os.path.isfile(spl_file):
                            continue

                        job_id = uuid.uuid4().hex[:8]
                        pdf_out = os.path.join(self.shared_dir, f"PrintJob_{int(time.time())}_{job_id}.pdf")
                        cmd = [
                            "gs", "-q", "-dNOPAUSE", "-dBATCH", "-dSAFER",
                            "-dCompatibilityLevel=1.4", "-sDEVICE=pdfwrite",
                            f"-sOutputFile={pdf_out}", spl_file
                        ]
                        subprocess.run(cmd, check=False, capture_output=True)
                        try:
                            os.remove(spl_file)
                        except OSError:
                            pass
                except Exception:
                    pass
                time.sleep(1.0)

        t = threading.Thread(target=watcher_loop, daemon=True)
        t.start()

    def terminate(self):
        self._spool_watcher_running = False
        if self.app_proc:
            try:
                self.app_proc.terminate()
                self.app_proc.wait(timeout=2)
            except Exception:
                try:
                    self.app_proc.kill()
                except Exception:
                    pass

        self.display_mgr.stop()

        # Clean session directory
        if os.path.exists(self.wine_prefix):
            try:
                shutil.rmtree(self.wine_prefix)
            except Exception as e:
                logger.warning(f"Error removing session directory {self.wine_prefix}: {e}")
