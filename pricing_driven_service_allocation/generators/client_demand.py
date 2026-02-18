import numpy as np
import math
from typing import Dict, Any, Optional
from enum import Enum

import numpy as np
class AppType(Enum):
    AR_VR = "vr"
    VIDEO_PRIVACY = "cctv"
    LIDAR = "lidar"
    ROBOT_IOT = "robot"


def calculate_resources(
    n_clients: int,
    service_type,  # AppType
    *,
    concurrency: float,
    requests_per_second_per_active_client: float,
    resources_to_consider: list[str],
    requests_per_second_std: float = 0.15,
    random_state: Optional[int] = 35,
    resource_mapping: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:

    n_clients = int(n_clients)
    if n_clients < 0:
        raise ValueError("n_clients must be non-negative")
    if not (0.0 <= concurrency <= 1.0):
        raise ValueError("concurrency must be between 0.0 and 1.0")
    if requests_per_second_per_active_client < 0.0:
        raise ValueError("requests_per_second_per_active_client must be non-negative")
    if requests_per_second_std < 0.0:
        raise ValueError("requests_per_second_std must be non-negative")

    rng = np.random.default_rng(random_state)

    # Profiles (recalibrated)
    # Key changes:
    # - per-session RAM is tiny (or zero) unless your domain requires it
    # - shared RAM scales sub-linearly with active users
    # - GPU/TPU are used only by a fraction of requests
    profiles = {
        service_type.__class__.AR_VR: {
            "base_ram_gb": 1.5,
            "base_storage_gb": 2.0,

            # Small per-session resident state (do NOT assume linear heavy session RAM)
            "session_ram_gb_avg": 0.002, "session_ram_gb_std": 0.001,  # ~2 MB
            "session_storage_gb_avg": 0.005, "session_storage_gb_std": 0.003,

            # Shared memory component (cache, assets, pipelines) — sub-linear scaling
            "shared_ram_gb_at_100_active": 2.0,   # tuning knob
            "shared_ram_growth": "sqrt",          # "sqrt" or "log"

            # Per-request processing
            "cpu_ms_per_request_avg": 3.0, "cpu_ms_per_request_std": 1.0,
            "gpu_ms_per_request_avg": 6.0, "gpu_ms_per_request_std": 2.0,
            "tpu_ms_per_request_avg": 0.0, "tpu_ms_per_request_std": 0.2,

            # Fraction of requests that actually hit the accelerator
            "gpu_request_fraction": 0.25,
            "tpu_request_fraction": 0.0,

            "target_cpu_utilization": 0.65,
            "target_gpu_utilization": 0.75,
            "target_tpu_utilization": 0.75,
            "safety_factor": 1.15,

            "log_megabytes_per_request": 0.01,
            "retention_seconds": 1800,
            "network_megabytes_in_per_request": 0.10,
            "network_megabytes_out_per_request": 0.20,

            # Accelerator capacity (abstract throughput)
            "gpu_capacity_seconds_per_second": 120.0,
            "tpu_capacity_seconds_per_second": 200.0,
        },

        service_type.__class__.VIDEO_PRIVACY: {
            "base_ram_gb": 1.2,
            "base_storage_gb": 10.0,

            "session_ram_gb_avg": 0.001, "session_ram_gb_std": 0.001,  # ~1 MB
            "session_storage_gb_avg": 0.01, "session_storage_gb_std": 0.01,

            "shared_ram_gb_at_100_active": 1.5,
            "shared_ram_growth": "sqrt",

            "cpu_ms_per_request_avg": 2.0, "cpu_ms_per_request_std": 0.8,
            "gpu_ms_per_request_avg": 8.0, "gpu_ms_per_request_std": 3.0,
            "tpu_ms_per_request_avg": 4.0, "tpu_ms_per_request_std": 2.0,

            "gpu_request_fraction": 0.40,  # more inference-heavy
            "tpu_request_fraction": 0.15,  # only some routed to TPU

            "target_cpu_utilization": 0.65,
            "target_gpu_utilization": 0.75,
            "target_tpu_utilization": 0.75,
            "safety_factor": 1.20,

            "log_megabytes_per_request": 0.05,
            "retention_seconds": 7200,
            "network_megabytes_in_per_request": 0.30,
            "network_megabytes_out_per_request": 0.05,

            "gpu_capacity_seconds_per_second": 160.0,
            "tpu_capacity_seconds_per_second": 250.0,
        },

        service_type.__class__.LIDAR: {
            "base_ram_gb": 1.0,
            "base_storage_gb": 5.0,

            "session_ram_gb_avg": 0.002, "session_ram_gb_std": 0.001,
            "session_storage_gb_avg": 0.05, "session_storage_gb_std": 0.03,

            "shared_ram_gb_at_100_active": 1.2,
            "shared_ram_growth": "sqrt",

            "cpu_ms_per_request_avg": 5.0, "cpu_ms_per_request_std": 2.0,
            "gpu_ms_per_request_avg": 4.0, "gpu_ms_per_request_std": 2.0,
            "tpu_ms_per_request_avg": 2.0, "tpu_ms_per_request_std": 1.5,

            "gpu_request_fraction": 0.20,
            "tpu_request_fraction": 0.10,

            "target_cpu_utilization": 0.60,
            "target_gpu_utilization": 0.75,
            "target_tpu_utilization": 0.75,
            "safety_factor": 1.20,

            "log_megabytes_per_request": 0.02,
            "retention_seconds": 3600,
            "network_megabytes_in_per_request": 0.20,
            "network_megabytes_out_per_request": 0.10,

            "gpu_capacity_seconds_per_second": 140.0,
            "tpu_capacity_seconds_per_second": 220.0,
        },

        service_type.__class__.ROBOT_IOT: {
            "base_ram_gb": 0.3,
            "base_storage_gb": 1.0,

            "session_ram_gb_avg": 0.0002, "session_ram_gb_std": 0.0001,  # 0.2 MB
            "session_storage_gb_avg": 0.001, "session_storage_gb_std": 0.001,

            "shared_ram_gb_at_100_active": 0.3,
            "shared_ram_growth": "log",

            "cpu_ms_per_request_avg": 0.8, "cpu_ms_per_request_std": 0.4,
            "gpu_ms_per_request_avg": 0.0, "gpu_ms_per_request_std": 0.2,
            "tpu_ms_per_request_avg": 0.0, "tpu_ms_per_request_std": 0.2,

            "gpu_request_fraction": 0.0,
            "tpu_request_fraction": 0.0,

            "target_cpu_utilization": 0.70,
            "target_gpu_utilization": 0.80,
            "target_tpu_utilization": 0.80,
            "safety_factor": 1.10,

            "log_megabytes_per_request": 0.002,
            "retention_seconds": 86400,
            "network_megabytes_in_per_request": 0.01,
            "network_megabytes_out_per_request": 0.01,

            "gpu_capacity_seconds_per_second": 200.0,
            "tpu_capacity_seconds_per_second": 300.0,
        },
    }

    if service_type not in profiles:
        raise ValueError(f"Service type must be one of {list(profiles.keys())}")

    p = profiles[service_type]

    default_offer_to_internal = {
        "available_ram_gb": "ram_total_gb",
        "available_storage_gb": "storage_total_gb",
        "available_cpu_cores": "cpu_total_cores",
        "available_gpu_units": "gpu_equivalent_units",
        "available_tpu_units": "tpu_equivalent_units",
        "available_network_in_mbps": "network_megabits_in_per_second",
        "available_network_out_mbps": "network_megabits_out_per_second",
    }
    if resource_mapping is None:
        resource_mapping = default_offer_to_internal
    else:
        merged = dict(default_offer_to_internal)
        merged.update(resource_mapping)
        resource_mapping = merged

    # 1) Active users
    n_active = int(rng.binomial(n=n_clients, p=concurrency))

    if n_active == 0:
        internal = {
            "ram_total_gb": 0,
            "storage_total_gb": 0,
            "cpu_total_cores": 0,
            "gpu_equivalent_units": 0,
            "tpu_equivalent_units": 0,
            "network_megabits_in_per_second": 0.0,
            "network_megabits_out_per_second": 0.0,
        }
        resources = {res: internal.get(resource_mapping.get(res, ""), 0) for res in resources_to_consider}
        return {
            "service_mode": service_type,
            "active_users": 0,
            "total_requests_per_second": 0.0,
            **internal,
            "resources": resources,
        }

    # 2) Aggregate request rate
    rps_per_user = rng.normal(
        loc=requests_per_second_per_active_client,
        scale=requests_per_second_std * max(requests_per_second_per_active_client, 1e-9),
        size=n_active,
    )
    rps_per_user = np.maximum(rps_per_user, 0.0)
    total_rps = float(rps_per_user.sum()) * p["safety_factor"]

    # 3) RAM and storage
    session_ram = rng.normal(p["session_ram_gb_avg"], p["session_ram_gb_std"], n_active)
    session_ram = float(np.maximum(session_ram, 0.0).sum())

    session_storage = rng.normal(p["session_storage_gb_avg"], p["session_storage_gb_std"], n_active)
    session_storage = float(np.maximum(session_storage, 0.0).sum())

    # Shared RAM term
    shared_at_100 = float(p.get("shared_ram_gb_at_100_active", 0.0))
    growth = p.get("shared_ram_growth", "sqrt")

    if shared_at_100 <= 0.0:
        shared_ram = 0.0
    else:
        if growth == "log":
            # log1p(100) scaling anchor
            shared_ram = shared_at_100 * (math.log1p(n_active) / max(math.log1p(100), 1e-9))
        else:
            # sqrt scaling anchor
            shared_ram = shared_at_100 * (math.sqrt(n_active) / max(math.sqrt(100), 1e-9))

    ram_total_gb = (p["base_ram_gb"] + shared_ram + session_ram) * p["safety_factor"]
    storage_total_gb = (p["base_storage_gb"] + session_storage) * p["safety_factor"]

    # 4) Processing -> sizing
    def ms_to_s(ms: float) -> float:
        return float(ms) / 1000.0

    cpu_ms = max(0.0, float(rng.normal(p["cpu_ms_per_request_avg"], p["cpu_ms_per_request_std"])))
    gpu_ms = max(0.0, float(rng.normal(p["gpu_ms_per_request_avg"], p["gpu_ms_per_request_std"])))
    tpu_ms = max(0.0, float(rng.normal(p["tpu_ms_per_request_avg"], p["tpu_ms_per_request_std"])))

    # Fraction of requests that use accelerators
    gpu_frac = float(p.get("gpu_request_fraction", 0.0))
    tpu_frac = float(p.get("tpu_request_fraction", 0.0))
    gpu_frac = min(max(gpu_frac, 0.0), 1.0)
    tpu_frac = min(max(tpu_frac, 0.0), 1.0)

    cpu_seconds_per_second = total_rps * ms_to_s(cpu_ms)
    gpu_seconds_per_second = total_rps * gpu_frac * ms_to_s(gpu_ms)
    tpu_seconds_per_second = total_rps * tpu_frac * ms_to_s(tpu_ms)

    cpu_cores = cpu_seconds_per_second / p["target_cpu_utilization"]

    gpu_capacity = float(p.get("gpu_capacity_seconds_per_second", 1.0))
    tpu_capacity = float(p.get("tpu_capacity_seconds_per_second", 1.0))

    gpu_units = 0.0
    if gpu_seconds_per_second > 0.0 and gpu_capacity > 0.0:
        gpu_units = gpu_seconds_per_second / (gpu_capacity * p["target_gpu_utilization"])

    tpu_units = 0.0
    if tpu_seconds_per_second > 0.0 and tpu_capacity > 0.0:
        tpu_units = tpu_seconds_per_second / (tpu_capacity * p["target_tpu_utilization"])

    # 5) Logs with retention
    log_gb = 0.0
    if p["log_megabytes_per_request"] > 0.0 and p["retention_seconds"] > 0.0:
        log_megabytes = total_rps * p["log_megabytes_per_request"] * p["retention_seconds"]
        log_gb = (log_megabytes / 1024.0) * p["safety_factor"]
        storage_total_gb += log_gb

    # 6) Network
    net_in_mbps = float(total_rps * p["network_megabytes_in_per_request"] * 8.0) * p["safety_factor"]
    net_out_mbps = float(total_rps * p["network_megabytes_out_per_request"] * 8.0) * p["safety_factor"]

    internal = {
        "ram_total_gb": int(math.ceil(ram_total_gb)),
        "cpu_total_cores": int(math.ceil(cpu_cores)),
        "gpu_equivalent_units": int(math.ceil(gpu_units)),
        "tpu_equivalent_units": int(math.ceil(tpu_units)),
        "storage_total_gb": int(math.ceil(storage_total_gb)),
        "network_megabits_in_per_second": round(net_in_mbps, 3),
        "network_megabits_out_per_second": round(net_out_mbps, 3),
    }

    resources: Dict[str, Any] = {}
    for res in resources_to_consider:
        internal_key = resource_mapping.get(res)
        resources[res] = internal.get(internal_key, 0) if internal_key else 0

    return {
        "service_mode": service_type,
        "active_users": n_active,
        "total_requests_per_second": round(total_rps, 3),
        **internal,
        "resources": resources,

        # Diagnostics
        "cpu_seconds_per_second": round(cpu_seconds_per_second, 6),
        "gpu_seconds_per_second": round(gpu_seconds_per_second, 6),
        "tpu_seconds_per_second": round(tpu_seconds_per_second, 6),
        "gpu_request_fraction": gpu_frac,
        "tpu_request_fraction": tpu_frac,
        "gpu_capacity_seconds_per_second": gpu_capacity,
        "tpu_capacity_seconds_per_second": tpu_capacity,
        "shared_ram_component_gb": round(shared_ram, 3),
        "session_ram_component_gb": round(session_ram, 3),
    }
