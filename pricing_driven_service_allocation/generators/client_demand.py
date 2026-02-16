import csv
import json
import os
import re
import sys
from enum import Enum
from typing import List

import numpy as np
import pandas as pd


class AppType(Enum):
    AR_VR = "ar/vr"
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


def draw_clients_on_map(
        topology_id: str,
        topologies_result_dir: str,
        client_polygon: List[List[float]],
        clients_file: str = "clients.csv",
        map_source_file: str = "map.html",
        map_target_file: str = "map.html"
):
    """
    Injects client coordinates and a boundary polygon into an existing map.
    """
    topology_dir = os.path.join(topologies_result_dir, topology_id)
    map_source_path = os.path.join(topology_dir, map_source_file)
    map_target_path = os.path.join(topology_dir, map_target_file)
    clients_path = os.path.join(topologies_result_dir, topology_id, clients_file)

    # 1. Process Polygon (Convert [lon, lat] -> [lat, lon] for Leaflet)
    leaflet_polygon = [[p[1], p[0]] for p in client_polygon]

    # 2. Read and parse CSV data
    clients = []
    try:
        with open(clients_path, mode='r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                clients.append({
                    "latitude": float(row['latitude']),
                    "longitude": float(row['longitude'])
                })
    except Exception as e:
        return f"Error reading CSV: {e}"

    # 3. Read the existing HTML file
    if not os.path.exists(map_source_path):
        return "Source HTML file not found."

    with open(map_source_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 4. Inject 'clients' and 'polygon' data into JavaScript
    data_injection = (
        f"const clients = {json.dumps(clients, indent=4)};\n        "
        f"const clientAreaCoords = {json.dumps(leaflet_polygon)};\n        "
    )
    content = content.replace("const devices =", f"{data_injection}const devices =")

    # 5. Update Legend (Added 'Client Area' with a fill style)
    client_legend = """
            <hr style="margin: 8px 0; border: 0; border-top: 1px solid #eee;">
            <div class="legend-item">
                <div class="legend-color" style="background-color: #FFD700; border: 1px solid #000; border-radius: 0;"></div>
                <span style="font-weight: bold;">CLIENTS</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background-color: rgba(255, 215, 0, 0.2); border: 2px solid #FFD700; border-radius: 2px;"></div>
                <span>Client Area</span>
            </div>
        </div>"""
    content = re.sub(r'</div>\s*</div>\s*<script>', f'{client_legend}\n    </div>\n    <script>', content)

    # 6. Inject Drawing Logic (Polygon + Markers)
    # We place the polygon drawing inside renderMarkers so it persists on filter changes
    drawing_logic = """
            let visible = 0;

            // Draw Client Polygon Area
            if (typeof clientAreaCoords !== 'undefined') {
                const poly = L.polygon(clientAreaCoords, {
                    color: '#FFD700',
                    weight: 2,
                    fillColor: '#FFD700',
                    fillOpacity: 0.15,
                    dashArray: '5, 5'
                }).addTo(markerLayer);
                markers.push(poly);
            }

            // Plot Clients
            // Plot Clients as Squares
            clients.forEach((c, idx) => {
                const squareIcon = L.divIcon({
                    className: 'custom-square-marker',
                    html: `<div style="width: 10px; height: 10px; background-color: #FFD700; border: 1px solid #000;"></div>`,
                    iconSize: [10, 10],
                    iconAnchor: [5, 5]
                });

                const m = L.marker([c.latitude, c.longitude], { icon: squareIcon })
                           .bindPopup(`<strong>Client #${idx + 1}</strong>`)
                           .addTo(markerLayer);
                markers.push(m);
                visible += 1;
            });
    """
    content = content.replace("let visible = 0;", drawing_logic)

    # 7. Update Header/Description
    content = content.replace("<h1>🗺️ Device Topology</h1>", "<h1>🗺️ Device & Client Topology</h1>")
    content = content.replace("Total: 1098", f"Total: {1098 + len(clients)}")

    # 8. Save updated map
    with open(map_target_path, 'w', encoding='utf-8') as f:
        f.write(content)

    return f"Successfully updated map with polygon saved to: {map_target_path}"


if __name__ == '__main__':

    DATASET_RESULT_DIR = "synthetic-dataset/data"
    TOPOLOGIES_RESULT_DIR = "synthetic-dataset/synthetic-topologies"
    topology_id = "c28ad123-e113-460c-8723-ea71a59cbafe"
    CLIENTS_FILE = "clients.csv"
    MAP_FILE = "map_with_clients.html"

    CLIENT_POLYGON = [[144.95128085314013, -37.81311379425756], [144.954906094624, -37.82109949971801],
                      [144.97481006469786, -37.81512407043976], [144.97090595848454, -37.807413124398344],
                      [144.95128085314013, -37.81311379425756]]

    c_locations_df = pd.read_csv(os.path.join(TOPOLOGIES_RESULT_DIR, topology_id, CLIENTS_FILE), index_col=0)
    draw_clients_on_map(topology_id, TOPOLOGIES_RESULT_DIR, CLIENT_POLYGON, map_target_file=MAP_FILE)

    sys.exit()

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
