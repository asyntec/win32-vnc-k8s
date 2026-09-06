import os
import threading
import logging

logger = logging.getLogger(__name__)

class TokenManager:
    """
    Thread-safe manager for websockify token mapping file.
    Enforces strict 0600 file permissions to prevent token sniffing.
    """
    _lock = threading.Lock()

    def __init__(self, token_file="/tmp/websockify_tokens"):
        self.token_file = token_file
        with self._lock:
            if not os.path.exists(self.token_file):
                with open(self.token_file, "w") as f:
                    f.write("")
                # Enforce private read/write permissions (owner only)
                os.chmod(self.token_file, 0o600)

    def add_token(self, token: str, host: str, port: int):
        with self._lock:
            lines = []
            if os.path.exists(self.token_file):
                with open(self.token_file, "r") as f:
                    lines = [l.strip() for l in f if l.strip() and not l.strip().startswith(f"{token}:")]
            lines.append(f"{token}: {host}:{port}")
            with open(self.token_file, "w") as f:
                f.write("\n".join(lines) + "\n")
            logger.info(f"Registered token {token} -> {host}:{port}")

    def remove_token(self, token: str):
        with self._lock:
            if not os.path.exists(self.token_file):
                return
            with open(self.token_file, "r") as f:
                lines = [l.strip() for l in f if l.strip() and not l.strip().startswith(f"{token}:")]
            with open(self.token_file, "w") as f:
                f.write("\n".join(lines) + "\n")
            logger.info(f"Removed token {token}")
