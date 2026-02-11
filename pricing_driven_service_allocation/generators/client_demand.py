
import numpy as np

def calculate_resources(
    n_clients: int,
    service_type: str,
    concurrency: float = 1.0,
    random_state: int = None
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

    # 1. Define Service Profiles (The "Weights")
    # These values are examples; in production, you would calibrate these
    # based on your hardware benchmarks.
    profiles = {
        'ar_vr': {
            # High render needs, high downlink
            'bw_mbps_avg': 50,    'bw_std': 15,
            'gpu_tflops_avg': 0.5, 'gpu_std': 0.1,
            'energy_w_avg': 10,    # Energy cost at the edge node per user
            'desc': 'Ultra-low latency, render heavy'
        },
        'video_privacy': {
            # Privacy = Heavy local processing, low output bandwidth
            'bw_mbps_avg': 2,     'bw_std': 0.5, # Only metadata sent out
            'gpu_tflops_avg': 1.2, 'gpu_std': 0.2, # Heavy AI inference
            'energy_w_avg': 15,
            'desc': 'Local privacy preservation (Edge AI)'
        },
        'lidar': {
            # Massive data upload
            'bw_mbps_avg': 100,   'bw_std': 40,
            'gpu_tflops_avg': 0.8, 'gpu_std': 0.3,
            'energy_w_avg': 20,
            'desc': 'Volumetric data upload'
        },
        'robot_iot': {
            # Low individual resource, but energy critical
            'bw_mbps_avg': 0.1,   'bw_std': 0.05,
            'gpu_tflops_avg': 0.01,'gpu_std': 0.005,
            'energy_w_avg': 0.5,   # Low per unit, but high density adds up
            'desc': 'Latency sensitive, battery constraints'
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
        return {'active_users': 0, 'bandwidth_mbps': 0, 'compute_tflops': 0, 'energy_watts': 0}

    # 3. Calculate Resources (Stochastic Simulation)
    # We simulate individual demand variations for active users

    # Bandwidth Demand
    bw_demand = rng.normal(profile['bw_mbps_avg'], profile['bw_std'], n_active)
    # Ensure no negative values (clip at 0)
    bw_total = np.maximum(bw_demand, 0).sum()

    # Compute Demand (GPU)
    gpu_demand = rng.normal(profile['gpu_tflops_avg'], profile['gpu_std'], n_active)
    gpu_total = np.maximum(gpu_demand, 0).sum()

    # Energy Estimate (Linear for simplicity, or add variance if needed)
    energy_total = n_active * profile['energy_w_avg']

    return {
        'service_mode': service_type,
        'active_users': n_active,
        'bandwidth_total_mbps': round(bw_total, 2),
        'compute_total_tflops': round(gpu_total, 2),
        'energy_total_watts': round(energy_total, 2)
    }