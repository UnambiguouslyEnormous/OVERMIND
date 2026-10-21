"""Bounded hardware diagnostics. Presence is never proof of a working training runtime."""
import importlib.util
import os
from pathlib import Path
import platform
import shutil
import subprocess
from .security import subprocess_environment


def _query(arguments):
    try:
        result = subprocess.run(arguments, capture_output=True, text=True, timeout=3,
                                env=subprocess_environment())
        return result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def inspect(storage_path=None):
    mem = {}
    try:
        with open('/proc/meminfo') as source:
            for line in source:
                k, v = line.split(':', 1)
                mem[k] = int(v.strip().split()[0]) // 1024
    except (OSError, ValueError):
        pass
    gpu = _query(['nvidia-smi', '--query-gpu=name,memory.total,memory.used,utilization.gpu',
                  '--format=csv,noheader,nounits'])
    details = _query(['nvidia-smi', '--query-gpu=name,driver_version,memory.total,memory.free,compute_cap',
                      '--format=csv,noheader,nounits']) if gpu else None
    devices = []
    for line in (details or '').splitlines():
        values = [v.strip() for v in line.split(',')]
        if len(values) != 5:continue
        name, driver, total, free, capability = values
        try:
            major, minor = (int(v) for v in capability.split('.'))
            devices.append({'name': name, 'driver': driver, 'vram_mb': int(total),
                            'free_vram_mb': int(free), 'compute_capability': capability,
                            'bf16_hardware_candidate': major >= 8,
                            'precision_guidance': 'FP32 safe default; FP16/BF16 require a verified runtime smoke test.' if major >= 8 else
                            'FP32 safe default; no BF16. FP16 kernels/performance must be verified.'})
        except ValueError:
            continue
    amd = []
    for device in Path('/sys/class/drm').glob('card[0-9]*/device'):
        try:
            if (device/'vendor').read_text().strip() == '0x1002':
                amd.append({'pci_device': (device/'device').read_text().strip(),
                            'driver': (device/'driver').resolve().name,
                            'rocm_training': 'unverified; PCI detection does not establish ROCm support'})
        except OSError:
            pass
    try:
        disk = shutil.disk_usage(storage_path or Path.cwd())
        storage = {'total_mb': disk.total // 2**20, 'free_mb': disk.free // 2**20}
    except OSError:
        storage = None
    dependencies = {name: importlib.util.find_spec(name) is not None for name in ('torch', 'transformers', 'peft', 'accelerate')}
    recommendations = ['CPU classifier: supported offline; real SGD weight updates.',
                       'Served Ollama/API models: inference only; access does not supply trainable weights.']
    if not all(dependencies.values()):
        recommendations.append('Generative LoRA unavailable: optional torch/transformers/peft/accelerate dependencies are incomplete. No automatic installation or model download.')
    else:
        recommendations.append('Optional training libraries detected; device, architecture, tokenizer, license and kernels still require verification.')
    if devices:
        recommendations.append('VRAM is a live free-memory snapshot, not a model-fit guarantee. GTX/Pascal: no BF16; do not assume QLoRA support.')
    return {'platform': platform.system(), 'cpu': platform.processor() or platform.machine(),
            'cpu_count': os.cpu_count(), 'ram_mb': mem.get('MemTotal'), 'available_mb': mem.get('MemAvailable'),
            'gpu': gpu, 'nvidia_devices': devices, 'amd_devices': amd, 'disk': storage,
            'optional_dependencies': dependencies, 'cuda_runtime': 'unverified', 'rocm_runtime': 'unverified',
            'load': list(os.getloadavg()) if hasattr(os, 'getloadavg') else None,
            'training_device': 'CPU', 'gpu_status': 'NVIDIA driver responds; training runtime unverified' if gpu else 'No working NVIDIA driver detected',
            'recommendations': recommendations}
