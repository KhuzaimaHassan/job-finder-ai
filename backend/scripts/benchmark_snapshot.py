"""Read-only startup/RAM probe. Never refreshes providers or writes cloud data."""
import argparse
import asyncio
import json
import logging
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def memory_mib():
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        *[(name, ctypes.c_size_t) for name in (
                            "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                            "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage",
                            "PagefileUsage", "PeakPagefileUsage")]]

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
            raise ctypes.WinError(ctypes.get_last_error())
        return {"resident_mib": round(counters.WorkingSetSize / 2**20, 1),
                "peak_resident_mib": round(counters.PeakWorkingSetSize / 2**20, 1)}
    import resource
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {"peak_resident_mib": round(peak / (2**20 if sys.platform == "darwin" else 1024), 1)}


async def benchmark(iterations):
    # Include all API imports in the process footprint, without starting its
    # lifespan/scheduler. The only cloud I/O below is SELECT against jobs.
    from app.main import app  # noqa: F401
    from app.services import job_fetcher as jf

    print(json.dumps({"phase": "api_imported", **memory_mib()}), flush=True)
    for iteration in range(iterations):
        started = time.monotonic()
        await jf.reload_snapshot(force=True)
        matches = jf.search_jobs(q="python")[1]
        print(json.dumps({"phase": "snapshot", "iteration": iteration + 1,
                          "seconds": round(time.monotonic() - started, 2),
                          "jobs": len(jf.get_all_jobs()), "python_matches": matches,
                          **memory_mib()}), flush=True)
    started = time.monotonic()
    for _ in range(20):
        await jf.reload_snapshot()
    print(json.dumps({"phase": "20_cached_ticks", "seconds": round(time.monotonic() - started, 3),
                      **memory_mib()}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, choices=range(1, 11), default=3)
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)  # Keep URLs/credentials out of probe output.
    asyncio.run(benchmark(args.iterations))
