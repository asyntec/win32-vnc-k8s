import os
import logging
import psutil
import time

logger = logging.getLogger(__name__)

def reap_zombies():
    """
    Reaps zombie processes (<defunct>) using non-blocking waitpid.
    Essential when container runs without tini or systemd.
    """
    reaped = 0
    try:
        for proc in psutil.process_iter(['pid', 'status', 'name']):
            try:
                if proc.info['status'] == psutil.STATUS_ZOMBIE:
                    try:
                        os.waitpid(proc.info['pid'], os.WNOHANG)
                        reaped += 1
                    except (ChildProcessError, ProcessLookupError):
                        pass
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception as e:
        logger.debug(f"Error in reap_zombies: {e}")
    return reaped

def cleanup_orphans(active_displays=None, active_ports=None):
    """
    Finds and terminates orphaned processes (Xvnc, autocutsel, wine)
    not associated with any active session.
    """
    active_displays = set(active_displays or [])
    active_ports = set(active_ports or [])
    cleaned = 0
    target_names = {'xvnc', 'xtigervnc', 'x11vnc', 'autocutsel', 'wineserver', 'wine'}
    current_uid = os.getuid()

    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'uids']):
            try:
                if proc.info['pid'] <= 1 or proc.info['pid'] == os.getpid():
                    continue
                uids = proc.info.get('uids')
                if uids and uids.real != current_uid:
                    continue
                pname = (proc.info['name'] or '').lower()
                cmdline = ' '.join(proc.info.get('cmdline') or []).lower()

                if not any(t in pname or t in cmdline for t in target_names):
                    continue

                # Check if matches any active display
                is_active = False
                for disp in active_displays:
                    if f":{disp}" in cmdline:
                        is_active = True
                        break
                if not is_active:
                    for port in active_ports:
                        if str(port) in cmdline:
                            is_active = True
                            break

                if not is_active:
                    proc.terminate()
                    cleaned += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception as e:
        logger.debug(f"Error in cleanup_orphans: {e}")
    return cleaned
