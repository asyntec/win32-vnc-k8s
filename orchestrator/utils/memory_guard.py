import os
import logging
import psutil

logger = logging.getLogger(__name__)

def get_cgroup_memory():
    """
    Returns current memory metrics by inspecting Linux cgroups:
    - usage_bytes, limit_bytes, available_bytes
    - usage_mb, limit_mb, available_mb
    - percent_used
    Accurately subtracts kernel reclaimable page cache to avoid false OOM positives.
    """
    usage = None
    limit = None
    reclaimable = 0

    # 1. cgroup v2 (/sys/fs/cgroup/memory.current & memory.max & memory.stat)
    if os.path.exists("/sys/fs/cgroup/memory.current") and os.path.exists("/sys/fs/cgroup/memory.max"):
        try:
            with open("/sys/fs/cgroup/memory.current", "r") as f:
                raw_usage = int(f.read().strip())
            with open("/sys/fs/cgroup/memory.max", "r") as f:
                val = f.read().strip()
                if val != "max":
                    limit = int(val)

            if os.path.exists("/sys/fs/cgroup/memory.stat"):
                with open("/sys/fs/cgroup/memory.stat", "r") as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) == 2:
                            k, v = parts[0], int(parts[1])
                            if k in ["inactive_file", "slab_reclaimable"]:
                                reclaimable += v

            usage = max(0, raw_usage - reclaimable)
        except Exception as e:
            logger.debug(f"cgroup v2 read error: {e}")

    # 2. cgroup v1 (/sys/fs/cgroup/memory/...)
    if (usage is None or limit is None) and os.path.exists("/sys/fs/cgroup/memory/memory.usage_in_bytes"):
        try:
            if usage is None:
                with open("/sys/fs/cgroup/memory/memory.usage_in_bytes", "r") as f:
                    raw_usage = int(f.read().strip())
                reclaimable = 0
                if os.path.exists("/sys/fs/cgroup/memory/memory.stat"):
                    with open("/sys/fs/cgroup/memory/memory.stat", "r") as f:
                        for line in f:
                            parts = line.strip().split()
                            if len(parts) == 2:
                                k, v = parts[0], int(parts[1])
                                if k in ["total_inactive_file", "inactive_file", "total_slab_reclaimable", "slab_reclaimable"]:
                                    reclaimable += v
                usage = max(0, raw_usage - reclaimable)
            if limit is None and os.path.exists("/sys/fs/cgroup/memory/memory.limit_in_bytes"):
                with open("/sys/fs/cgroup/memory/memory.limit_in_bytes", "r") as f:
                    limit = int(f.read().strip())
        except Exception as e:
            logger.debug(f"cgroup v1 read error: {e}")

    # 3. Host / VM fallback via psutil
    vm = psutil.virtual_memory()
    if limit is None or limit > vm.total or limit > (1024**4):
        limit = vm.total

    if usage is None:
        usage = vm.used - getattr(vm, "cached", 0)

    available = max(0, limit - usage)
    percent = (usage / limit) * 100.0 if limit > 0 else 0.0

    return {
        "usage_bytes": usage,
        "limit_bytes": limit,
        "available_bytes": available,
        "usage_mb": round(usage / (1024 * 1024), 2),
        "limit_mb": round(limit / (1024 * 1024), 2),
        "available_mb": round(available / (1024 * 1024), 2),
        "percent_used": round(percent, 2)
    }

def can_admit_new_session(required_headroom_mb=200.0, max_utilization_pct=85.0):
    """
    Admission control: dynamically determines if a new Win32 session can be admitted.
    """
    mem = get_cgroup_memory()
    if mem["available_mb"] < required_headroom_mb:
        return False, f"Insufficient memory headroom: {mem['available_mb']} MB available, requires {required_headroom_mb} MB.", mem
    if mem["percent_used"] > max_utilization_pct:
        return False, f"Memory utilization too high: {mem['percent_used']}% > {max_utilization_pct}%.", mem
    return True, "Admission approved", mem
