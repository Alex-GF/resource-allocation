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
        dict: A Resource Vector (Bandwidth, Compute, Storage, Energy)
    """

    # Initialize Random Generator
    rng = np.random.default_rng(random_state)

    # 1. Define Service Profiles
    # These represent the resources required PER ACTIVE USER on the Edge Node.
    profiles = {
        AppType.AR_VR: {
            # Heavy Rendering: Needs VRAM and huge GPU compute.
            'ram_gb_avg': 8.0, 'ram_std': 0.5,  # Low deviation (assets are fixed size)
            'gpu_tflops_avg': 4.0, 'gpu_std': 1.5,  # High variance (scene complexity varies)
            'cpu_cores_avg': 2.0, 'cpu_std': 0.5,  # Draw calls / physics
        },
        AppType.VIDEO_PRIVACY: {
            # AI Inference: High GPU Tensor usage, low CPU/RAM relative to AR.
            'ram_gb_avg': 2.0, 'ram_std': 0.1,  # Model weights are fixed size
            'gpu_tflops_avg': 2.5, 'gpu_std': 0.5,  # Steady stream inference
            'cpu_cores_avg': 1.0, 'cpu_std': 0.2,  # Pre-processing frames
        },
        AppType.LIDAR: {
            # Data Intensive: High RAM to buffer point clouds, Moderate CPU for I/O.
            'ram_gb_avg': 4.0, 'ram_std': 0.2,  # Buffering frames
            'gpu_tflops_avg': 1.0, 'gpu_std': 0.4,  # Filtering/Alignment
            'cpu_cores_avg': 1.5, 'cpu_std': 0.3,  # Spatial indexing
        },
        AppType.ROBOT_IOT: {
            # Lightweight: Minimal resources, mostly message passing.
            'ram_gb_avg': 0.2, 'ram_std': 0.01,  # Very stable tiny footprint
            'gpu_tflops_avg': 0.05, 'gpu_std': 0.01,  # Occasional path planning
            'cpu_cores_avg': 0.1, 'cpu_std': 0.05,  # Background threads
        }
    }

    if service_type not in profiles:
        raise ValueError(f"Service type must be one of {list(profiles.keys())}")

    profile = profiles[service_type]

    # 2. Determine Active Users
    # We use a Binomial distribution to simulate how many are actually active
    # (More accurate than just n * concurrency)
    n_active = rng.binomial(n=n_clients, p=concurrency)

    if n_active == 0:
        return {'active_users': 0, 'ram_total_gb': 0, 'gpu_total_tflops': 0, 'cpu_total_cores': 0}

    # 3. Calculate Resources (Stochastic)

    # RAM (Low Deviation)
    # We clip at 0.1 to ensure no user takes 0 RAM (impossible)
    ram_demand = rng.normal(profile['ram_gb_avg'], profile['ram_std'], n_active)
    ram_total = np.maximum(ram_demand, 0.1).sum()

    # GPU (High Variance usually)
    gpu_demand = rng.normal(profile['gpu_tflops_avg'], profile['gpu_std'], n_active)
    gpu_total = np.maximum(gpu_demand, 0.0).sum()

    # CPU
    cpu_demand = rng.normal(profile['cpu_cores_avg'], profile['cpu_std'], n_active)
    cpu_total = np.maximum(cpu_demand, 0.1).sum()

    return {
        'service_mode': service_type,
        'active_users': n_active,
        'ram_total_gb': int(round(ram_total, 0)),
        'gpu_total_tflops': int(round(gpu_total, 0)),
        'cpu_total_cores': int(round(cpu_total, 0))  # Cores usually counted in 0.5s or 1s
    }

if __name__ == '__main__':
    import pandas as pd
    import os
    DATASET_RESULT_DIR = "synthetic-dataset/data"

    c_locations_df = pd.read_csv(os.path.join(DATASET_RESULT_DIR, "client_locations_filtered.csv"), index_col=0)

    # --- Example Usage ---

    n_clients = len(c_locations_df)

    # 1. 50 People doing AR (Gaming event)
    ar_reqs = calculate_resources(n_clients=n_clients, service_type=AppType.AR_VR, concurrency=0.7)
    print("AR Requirements:", ar_reqs, "\n")

    # 2. 50 Security Cameras (Privacy Mode)
    vid_reqs = calculate_resources(n_clients=n_clients, service_type=AppType.VIDEO_PRIVACY, concurrency=1.0)
    print("Privacy Video Requirements:", vid_reqs, "\n")

    vid_reqs = calculate_resources(n_clients=n_clients, service_type=AppType.LIDAR, concurrency=0.4)
    print("Lidar Requirements:", vid_reqs, "\n")

    vid_reqs = calculate_resources(n_clients=n_clients, service_type=AppType.ROBOT_IOT, concurrency=0.9)
    print("Robot/IoT Requirements:", vid_reqs)