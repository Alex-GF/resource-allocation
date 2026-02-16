import numpy as np

from enum import Enum

class AppType(Enum):
    AR_VR = "ar_vr"
    VIDEO_PRIVACY = "video_privacy"
    LIDAR = "lidar"
    ROBOT_IOT = "robot_iot"

def calculate_resources(
    n_clients: int,
    service_type: AppType,
    concurrency: float = 1.0,
    random_state: int = 35
):
    """
    Calculates resource demand for specific Smart Environment services.

    Args:
        n_clients: Number of potential clients in the polygon.
        service_type: One of 'ar_vr', 'video_privacy', 'lidar', 'robot_iot'.
        concurrency: 0.0 to 1.0 (percent of clients active simultaneously).
        random_state: Seed for reproducibility (or None for random variation).

    Returns:
        dict: A Resource Vector (RAM, GPU, CPU, Storage, TPU)
    """

    # Initialize Random Generator
    rng = np.random.default_rng(random_state)

    # 1. Define Service Profiles
    # Resources required PER ACTIVE USER on the Edge Node.
    profiles = {
        AppType.AR_VR: {
            # Heavy rendering + assets streaming/caching
            'ram_gb_avg': 8.0,  'ram_std': 0.5,
            'gpu_tflops_avg': 4.0, 'gpu_std': 1.5,
            'cpu_cores_avg': 2.0, 'cpu_std': 0.5,

            # Storage: cached assets, textures, session state (moderate)
            'storage_gb_avg': 1.5, 'storage_std': 0.4,

            # TPU: typically low for AR/VR unless doing perception; keep near-zero
            'tpu_tops_avg': 0.2, 'tpu_std': 0.2,
        },
        AppType.VIDEO_PRIVACY: {
            # AI inference + buffering frames
            'ram_gb_avg': 2.0, 'ram_std': 0.1,
            'gpu_tflops_avg': 2.5, 'gpu_std': 0.5,
            'cpu_cores_avg': 1.0, 'cpu_std': 0.2,

            # Storage: short rolling buffers, audit logs (low to moderate)
            'storage_gb_avg': 3.0, 'storage_std': 1.0,

            # TPU: if inference is mapped to TPU (e.g., quantized vision models)
            'tpu_tops_avg': 8.0, 'tpu_std': 2.0,
        },
        AppType.LIDAR: {
            # Point clouds buffering + processing
            'ram_gb_avg': 4.0, 'ram_std': 0.2,
            'gpu_tflops_avg': 1.0, 'gpu_std': 0.4,
            'cpu_cores_avg': 1.5, 'cpu_std': 0.3,

            # Storage: point cloud chunks, intermediate maps (moderate to high)
            'storage_gb_avg': 8.0, 'storage_std': 3.0,

            # TPU: can be used for segmentation/classification; moderate
            'tpu_tops_avg': 4.0, 'tpu_std': 2.0,
        },
        AppType.ROBOT_IOT: {
            # Lightweight messaging + occasional compute
            'ram_gb_avg': 0.2, 'ram_std': 0.01,
            'gpu_tflops_avg': 0.05, 'gpu_std': 0.01,
            'cpu_cores_avg': 0.1, 'cpu_std': 0.05,

            # Storage: telemetry logs, small state (very low)
            'storage_gb_avg': 0.2, 'storage_std': 0.1,

            # TPU: normally unused
            'tpu_tops_avg': 0.0, 'tpu_std': 0.05,
        }
    }

    if service_type not in profiles:
        raise ValueError(f"Service type must be one of {list(profiles.keys())}")

    profile = profiles[service_type]

    # 2. Determine Active Users (Binomial)
    n_active = rng.binomial(n=n_clients, p=concurrency)

    if n_active == 0:
        return {
            'service_mode': service_type,
            'active_users': 0,
            'ram_total_gb': 0,
            'gpu_total_tflops': 0,
            'cpu_total_cores': 0,
            'storage_total_gb': 0,
            'tpu_total_tops': 0,
        }

    # 3. Calculate Resources (Stochastic per active user)

    # RAM (clip to ensure > 0)
    ram_demand = rng.normal(profile['ram_gb_avg'], profile['ram_std'], n_active)
    ram_total = np.maximum(ram_demand, 0.1).sum()

    # GPU (clip to >= 0)
    gpu_demand = rng.normal(profile['gpu_tflops_avg'], profile['gpu_std'], n_active)
    gpu_total = np.maximum(gpu_demand, 0.0).sum()

    # CPU (clip to ensure > 0)
    cpu_demand = rng.normal(profile['cpu_cores_avg'], profile['cpu_std'], n_active)
    cpu_total = np.maximum(cpu_demand, 0.1).sum()

    # Storage (clip to >= 0; allows "no local storage" cases)
    storage_demand = rng.normal(profile['storage_gb_avg'], profile['storage_std'], n_active)
    storage_total = np.maximum(storage_demand, 0.0).sum()

    # TPU (clip to >= 0)
    tpu_demand = rng.normal(profile['tpu_tops_avg'], profile['tpu_std'], n_active)
    tpu_total = np.maximum(tpu_demand, 0.0).sum()

    return {
        'service_mode': service_type,
        'active_users': n_active,
        'ram_total_gb': int(round(ram_total, 0)),
        'gpu_total_tflops': int(round(gpu_total, 0)),
        'cpu_total_cores': int(round(cpu_total, 0)),
        'storage_total_gb': int(round(storage_total, 0)),
        'tpu_total_tops': int(round(tpu_total, 0)),
    }

# if __name__ == '__main__':
#     import pandas as pd
#     import os
#     DATASET_RESULT_DIR = "synthetic-dataset/data"

#     c_locations_df = pd.read_csv(os.path.join(DATASET_RESULT_DIR, "client_locations_filtered.csv"), index_col=0)

#     # --- Example Usage ---

#     n_clients = len(c_locations_df)

#     # 1. 50 People doing AR (Gaming event)
#     ar_reqs = calculate_resources(n_clients=n_clients, service_type=AppType.AR_VR, concurrency=0.7)
#     print("AR Requirements:", ar_reqs, "\n")

#     # 2. 50 Security Cameras (Privacy Mode)
#     vid_reqs = calculate_resources(n_clients=n_clients, service_type=AppType.VIDEO_PRIVACY, concurrency=1.0)
#     print("Privacy Video Requirements:", vid_reqs, "\n")

#     vid_reqs = calculate_resources(n_clients=n_clients, service_type=AppType.LIDAR, concurrency=0.4)
#     print("Lidar Requirements:", vid_reqs, "\n")

#     vid_reqs = calculate_resources(n_clients=n_clients, service_type=AppType.ROBOT_IOT, concurrency=0.9)
#     print("Robot/IoT Requirements:", vid_reqs)