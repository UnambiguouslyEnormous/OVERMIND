import os
import platform
import subprocess
from .security import subprocess_environment

def inspect():
    mem = {}
    try:
        with open('/proc/meminfo') as source:
            for line in source:
                k,v = line.split(':',1)
                mem[k] = int(v.strip().split()[0]) // 1024
    except OSError: pass
    gpu = None
    try:
        r = subprocess.run(['nvidia-smi','--query-gpu=name,memory.total,memory.used,utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=3,env=subprocess_environment())
        if r.returncode == 0: gpu = r.stdout.strip()
    except (OSError,subprocess.TimeoutExpired): pass
    return {'platform':platform.system(),'cpu_count':os.cpu_count(),'ram_mb':mem.get('MemTotal'), 'available_mb':mem.get('MemAvailable'),
        'gpu':gpu,'load':list(os.getloadavg()) if hasattr(os,'getloadavg') else None,
        'training_device':'CPU', 'gpu_status':'available' if gpu else 'No working NVIDIA driver detected'}
