import asyncio
import logging
import os
import secrets
import time
import uuid
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from orchestrator.session_manager import Session
from orchestrator.utils.memory_guard import can_admit_new_session, get_cgroup_memory
from orchestrator.utils.reaper import cleanup_orphans, reap_zombies

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("orchestrator")

app = FastAPI(
    title="win32-vnc-k8s Orchestrator",
    description="High-density x86 Windows application runtime with HTML5 VNC streaming for Kubernetes",
    version="1.0.0"
)

# 1. Balanced CORS configuration
cors_origins_env = os.getenv("CORS_ALLOWED_ORIGINS", "*")
cors_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]
allow_all = "*" in cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=not allow_all,  # Only allow credentials with explicit origins
    allow_methods=["*"],
    allow_headers=["*"],
)

sessions: Dict[str, Session] = {}
SESSION_IDLE_TIMEOUT = int(os.getenv("SESSION_IDLE_TIMEOUT", "1800"))
REQUIRED_HEADROOM_MB = float(os.getenv("REQUIRED_HEADROOM_MB", "200.0"))
MAX_UTILIZATION_PCT = float(os.getenv("MAX_UTILIZATION_PCT", "85.0"))

# 2. Whitelist for Allowed Binaries (Configurable via ALLOWED_APPS)
DEFAULT_ALLOWED_APPS = ["notepad.exe", "calc.exe", "winemine.exe"]
raw_allowed = os.getenv("ALLOWED_APPS", "")
ALLOWED_APPS = set([a.strip().lower() for a in raw_allowed.split(",") if a.strip()] or DEFAULT_ALLOWED_APPS)

# 3. Whitelist for Allowed Environment Variable Prefixes
ALLOWED_ENV_PREFIXES = ("APP_", "WIN32_")

def sanitize_extra_env(extra_env: Optional[Dict[str, str]]) -> Dict[str, str]:
    if not extra_env:
        return {}
    clean = {}
    for k, v in extra_env.items():
        key = k.strip().upper()
        if any(key.startswith(prefix) for prefix in ALLOWED_ENV_PREFIXES):
            clean[key] = str(v)
    return clean

# 4. Optional API Key Protection (Enforced only when ORCHESTRATOR_API_KEY is configured)
ORCHESTRATOR_API_KEY = os.getenv("ORCHESTRATOR_API_KEY", "")

def verify_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")):
    if ORCHESTRATOR_API_KEY:
        if not x_api_key or not secrets.compare_digest(x_api_key, ORCHESTRATOR_API_KEY):
            raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key header")
    return True

class SessionRequest(BaseModel):
    app_path: Optional[str] = "notepad.exe"
    extra_env: Optional[Dict[str, str]] = None

@app.on_event("startup")
async def startup_event():
    async def maintenance_loop():
        while True:
            try:
                reap_zombies()
                now = time.time()
                to_remove = []
                for sid, session in list(sessions.items()):
                    if now - getattr(session, "last_activity", now) > SESSION_IDLE_TIMEOUT:
                        to_remove.append(sid)

                for sid in to_remove:
                    logger.info(f"Reaping idle session {sid}")
                    s = sessions.pop(sid, None)
                    if s:
                        s.terminate()

                active_displays = [s.display for s in sessions.values() if s.display]
                cleanup_orphans(active_displays=active_displays)
            except Exception as e:
                logger.error(f"Maintenance loop error: {e}")
            await asyncio.sleep(30)

    asyncio.create_task(maintenance_loop())

@app.get("/health")
@app.get("/api/health")
async def health():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "active_sessions": len(sessions)
    }

@app.get("/api/metrics", dependencies=[Depends(verify_api_key)])
async def metrics():
    mem = get_cgroup_memory()
    return {
        "active_sessions": len(sessions),
        "memory": mem
    }

@app.post("/api/sessions", dependencies=[Depends(verify_api_key)])
async def create_session(req: SessionRequest):
    # Validate app against positive whitelist
    raw_app = req.app_path or "notepad.exe"
    app_filename = os.path.basename(raw_app.replace("\\", "/")).lower()
    if app_filename not in ALLOWED_APPS:
        raise HTTPException(
            status_code=400,
            detail=f"Application '{app_filename}' is not permitted. Allowed applications: {sorted(list(ALLOWED_APPS))}"
        )

    # Sanitize environment variables against positive whitelist prefix
    clean_env = sanitize_extra_env(req.extra_env)

    # Admission control: verify host/pod memory headroom
    admitted, msg, mem = can_admit_new_session(
        required_headroom_mb=REQUIRED_HEADROOM_MB,
        max_utilization_pct=MAX_UTILIZATION_PCT
    )
    if not admitted:
        raise HTTPException(status_code=503, detail=f"Capacity exceeded: {msg}")

    session_id = str(uuid.uuid4())
    session = Session(
        session_id=session_id,
        app_path=app_filename,
        extra_env=clean_env
    )

    try:
        meta = session.setup()
        sessions[session_id] = session
        return {
            "session_id": session_id,
            "display": meta["display"],
            "ws_port": meta["ws_port"],
            "vnc_url": meta["vnc_url"]
        }
    except Exception as e:
        session.terminate()
        logger.error(f"Failed to launch session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sessions", dependencies=[Depends(verify_api_key)])
async def list_sessions():
    return [
        {
            "session_id": sid,
            "display": s.display,
            "uptime_seconds": int(time.time() - getattr(s, "last_activity", time.time()))
        }
        for sid, s in sessions.items()
    ]

@app.delete("/api/sessions/{session_id}", dependencies=[Depends(verify_api_key)])
async def delete_session(session_id: str):
    session = sessions.pop(session_id, None)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.terminate()
    return {"status": "terminated", "session_id": session_id}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
