"""
Topology Generator Module

This module provides functions for generating device topologies within geographic areas.
"""

import os
import json
import uuid
from typing import Optional, List, Tuple, Dict, Any

import pandas as pd

from pricing_driven_resource_allocation.utils.geometrical_utils import distance_3d


def topology(
    lat: float,
    long: float,
    rad: float,
    devices_df: pd.DataFrame,
    topologies_result_dir: str,
    resources_to_consider: List[str],
    number_of_providers: Optional[int] = None,
    allowed_groups: Optional[List[int]] = None,
    number_of_devices: Optional[int] = None,
    center_elevation: float = 0.0,
    options: Optional[dict] = None
) -> Tuple[pd.DataFrame, str]:
    """
    Generate a sub-dataset of devices within a circular area and an HTML map.

    This version builds the embedded device payload dynamically based on
    `resources_to_consider` (resource capacity columns) and their presence
    in the selected topology dataframe.

    Parameters
    ----------
    lat : float
        Center latitude.
    long : float
        Center longitude.
    rad : float
        Radius in meters (applied to 3D distance).
    devices_df : pd.DataFrame
        Full devices dataset.
    topologies_result_dir : str
        Directory where topology results will be saved.
    resources_to_consider : List[str]
        Resource capacity column names to include in:
          - the CSV (already included as part of df_work),
          - the devices payload embedded into the HTML map,
          - the metadata file (for traceability).
        Example:
          ["available_ram_gb", "available_storage_gb", "available_cpu_cores"]
    number_of_providers : int, optional
        Maximum number of providers. If None, unlimited.
    allowed_groups : List[int], optional
        Allowed global groups. Defaults to [1, 2, 3].
    number_of_devices : int, optional
        Number of devices to select. If None, select all within area.
    center_elevation : float, optional
        Elevation (meters) at center point. Defaults to 0.0.
    options : dict, optional
        - seed: int (default 1)
        - logs: bool (default True)
        - resource_label_map: Dict[str, str] optional mapping for display labels in the popup
        - resource_unit_map: Dict[str, str] optional mapping for display units in the popup

    Returns
    -------
    Tuple[pd.DataFrame, str]
        DataFrame with selected devices and topology UUID.
    """

    if options is None:
        options = {"seed": 1, "logs": True}
    else:
        options = {"seed": 1, "logs": True, **options}

    if allowed_groups is None:
        allowed_groups = [1, 2, 3]

    seed = options.get("seed", 1)
    logs = options.get("logs", True)

    df_work = devices_df.copy()

    # Filter by allowed groups
    df_work = df_work[df_work["global_group"].isin(allowed_groups)]

    # Calculate 3D distance from center for each device
    df_work["distance_to_center"] = df_work.apply(
        lambda row: distance_3d(
            long,
            lat,
            row["longitude"],
            row["latitude"],
            center_elevation,
            row.get("elevation", 0.0)
        ),
        axis=1
    )

    # Filter devices within radius (3D distance)
    df_work = df_work[df_work["distance_to_center"] <= rad]

    # Filter by provider constraint if specified
    if number_of_providers is not None:
        top_providers = df_work["provider"].value_counts().head(number_of_providers).index.tolist()
        df_work = df_work[df_work["provider"].isin(top_providers)]

    # Select number_of_devices random devices if specified
    if number_of_devices is not None and len(df_work) > number_of_devices:
        df_work = df_work.sample(n=number_of_devices, random_state=seed)
    elif number_of_devices is not None and len(df_work) < number_of_devices:
        if logs:
            print(f"Warning: Only {len(df_work)} devices found, but {number_of_devices} were requested.")

    # Remove the temporary distance column
    df_work = df_work.drop(columns=["distance_to_center"])

    # Validate resources_to_consider (only keep those present)
    missing_resources = [r for r in resources_to_consider if r not in df_work.columns]
    present_resources = [r for r in resources_to_consider if r in df_work.columns]
    if logs and missing_resources:
        print("Warning: Some resources_to_consider are not present in devices_df and will be omitted:")
        print("  - " + ", ".join(missing_resources))

    # Generate UUID for this topology
    topology_id = str(uuid.uuid4())

    # Create topology directory
    topology_dir = os.path.join(topologies_result_dir, topology_id)
    os.makedirs(topology_dir, exist_ok=True)

    # Save CSV
    csv_path = os.path.join(topology_dir, "devices.csv")
    df_work.to_csv(csv_path)

    # Provider colors
    base_colors = {
        "OPTUS": "#007AFF",
        "TELSTRA": "#34C759",
        "MACQUARIE": "#5856D6",
        "TELECOM": "#FF9500",
        "VODAFONE": "#ff3b30"
    }
    unique_providers = df_work["provider"].unique().tolist()
    provider_colors: Dict[str, str] = {}
    fallback_palette = ["#667eea", "#764ba2", "#48bb78", "#ed8936", "#e53e3e", "#3182ce"]
    for i, p in enumerate(unique_providers):
        provider_colors[p] = base_colors.get(p, fallback_palette[i % len(fallback_palette)])

    # Optional display label/unit maps for popup rendering
    resource_label_map: Dict[str, str] = options.get("resource_label_map", {})
    resource_unit_map: Dict[str, str] = options.get("resource_unit_map", {})

    def _label(res: str) -> str:
        return resource_label_map.get(res, res)

    def _unit(res: str) -> str:
        return resource_unit_map.get(res, "")

    # Build devices payload for embedding in HTML (dynamic resources)
    devices_payload: List[Dict[str, Any]] = []
    for idx, row in df_work.iterrows():
        payload = {
            "device_id": str(idx),
            "latitude": float(row["latitude"]),
            "longitude": float(row["longitude"]),
            "provider": str(row["provider"]),
            "global_group": int(row["global_group"]),
        }

        # Add dynamic resource fields (capacities)
        for res in present_resources:
            val = row[res]
            if pd.isna(val):
                val = 0
            # keep ints if effectively integer
            v = float(val)
            if abs(v - round(v)) < 1e-9:
                v = int(round(v))
            payload[res] = v

        devices_payload.append(payload)

    # Legend HTML for providers
    legend_items_html = "\n".join([
        f"            <div class=\"legend-item\">\n"
        f"                <div class=\"legend-color\" style=\"background-color: {provider_colors[p]};\"></div>\n"
        f"                <span>{p}</span>\n"
        f"            </div>"
        for p in unique_providers
    ])

    # Provider filter options
    provider_options_html = "\n".join(
        ["                    <option value=\"\">All</option>"] +
        [f"                    <option value=\"{p}\">{p}</option>" for p in unique_providers]
    )

    # Build popup rows dynamically for resources
    # (Rendered in JS, so we provide label/unit maps + resource list)
    resources_js = json.dumps(present_resources)
    label_map_js = json.dumps({r: _label(r) for r in present_resources})
    unit_map_js = json.dumps({r: _unit(r) for r in present_resources})

    # Construct HTML content
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Device Topology Map</title>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css" />
  <script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
  <style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color:#f5f5f5; }}
    .container {{ display:flex; flex-direction:column; height:100vh; }}
    .header {{
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: white; padding:20px; box-shadow:0 2px 10px rgba(0,0,0,0.1); z-index:10;
    }}
    .header h1 {{ font-size:24px; margin-bottom:8px; }}
    .header p {{ font-size:14px; opacity:0.9; }}
    .controls {{
      background:white; padding:15px 20px; border-bottom:1px solid #e0e0e0;
      display:flex; gap:15px; align-items:center; flex-wrap:wrap;
      box-shadow:0 1px 3px rgba(0,0,0,0.05); z-index:9;
    }}
    .control-group {{ display:flex; align-items:center; gap:8px; }}
    .control-group label {{ font-weight:500; font-size:14px; color:#333; }}
    .control-group select, .control-group input {{
      padding:8px 12px; border:1px solid #ddd; border-radius:4px; font-size:14px;
      background:white; cursor:pointer; transition:border-color 0.2s;
    }}
    .control-group select:hover, .control-group input:hover {{ border-color:#667eea; }}
    .control-group select:focus, .control-group input:focus {{
      outline:none; border-color:#667eea; box-shadow:0 0 5px rgba(102, 126, 234, 0.2);
    }}
    .stats {{ display:flex; gap:20px; font-size:14px; color:#666; margin-left:auto; }}
    .stats span {{ font-weight:500; }}
    #map {{ flex:1; position:relative; }}
    .legend {{
      background:white; padding:12px 16px; border-radius:4px; box-shadow:0 2px 6px rgba(0,0,0,0.1);
      position:absolute; bottom:20px; right:20px; z-index:1000; font-size:12px; max-width:200px;
    }}
    .legend h4 {{ margin-bottom:8px; font-size:13px; font-weight:600; }}
    .legend-item {{ display:flex; align-items:center; gap:8px; margin-bottom:6px; }}
    .legend-color {{
      width:12px; height:12px; border-radius:50%; border:1px solid white; box-shadow:0 0 3px rgba(0,0,0,0.2);
    }}
    .leaflet-popup-content {{ max-height:400px; overflow-y:auto; font-size:12px; }}
    .popup-table {{ width:100%; border-collapse:collapse; }}
    .popup-table tr {{ border-bottom:1px solid #eee; }}
    .popup-table td {{ padding:6px; }}
    .popup-table td:first-child {{
      font-weight:600; color:#667eea; width:45%; word-break:break-word;
    }}
    .popup-table td:last-child {{ text-align:right; word-break:break-word; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>🗺️ Device Topology</h1>
      <p>Geographic location of devices with dynamic rendering</p>
    </div>
    <div class="controls">
      <div class="control-group">
        <label for="providerFilter">Filter by provider:</label>
        <select id="providerFilter">
{provider_options_html}
        </select>
      </div>
      <div class="control-group">
        <label for="searchDevice">Search device:</label>
        <input type="text" id="searchDevice" placeholder="E.g: device id">
      </div>
      <div class="stats">
        <span id="deviceCount">Total: {len(devices_payload)}</span>
        <span id="visibleCount">Visible: 0</span>
      </div>
    </div>
    <div id="map"></div>
    <div class="legend">
      <h4>Providers</h4>
{legend_items_html}
    </div>
  </div>

  <script>
    const devices = {json.dumps(devices_payload)};
    const providerColors = {json.dumps(provider_colors)};
    const centerLat = {lat};
    const centerLong = {long};
    const radiusMeters = {rad};

    const resourcesToShow = {resources_js};
    const resourceLabelMap = {label_map_js};
    const resourceUnitMap = {unit_map_js};

    const map = L.map('map').setView([centerLat, centerLong], 12);
    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap contributors'
    }}).addTo(map);

    const radiusCircle = L.circle([centerLat, centerLong], {{
      radius: radiusMeters,
      color: 'blue',
      fillColor: 'blue',
      fillOpacity: 0.1
    }}).addTo(map);

    const centerMarker = L.marker([centerLat, centerLong]).addTo(map);
    centerMarker.bindPopup('Center');

    const markerLayer = L.layerGroup().addTo(map);

    function devicePopupHtml(d) {{
      let resourceRows = "";
      resourcesToShow.forEach(r => {{
        if (d[r] === undefined) return;
        const label = resourceLabelMap[r] || r;
        const unit = resourceUnitMap[r] || "";
        resourceRows += `<tr><td>${{label}}</td><td>${{d[r]}} ${{unit}}</td></tr>`;
      }});

      return `
      <table class="popup-table">
        <tr><td>Device ID</td><td>${{d.device_id}}</td></tr>
        <tr><td>Provider</td><td>${{d.provider}}</td></tr>
        <tr><td>Group</td><td>${{d.global_group}}</td></tr>
        ${{resourceRows}}
        <tr><td>Latitude</td><td>${{d.latitude.toFixed(6)}}</td></tr>
        <tr><td>Longitude</td><td>${{d.longitude.toFixed(6)}}</td></tr>
      </table>`;
    }}

    function renderMarkers(providerFilterValue) {{
      markerLayer.clearLayers();
      let visible = 0;

      devices.forEach(d => {{
        if (providerFilterValue && d.provider !== providerFilterValue) return;
        const color = providerColors[d.provider] || '#3182ce';
        const m = L.circleMarker([d.latitude, d.longitude], {{
          radius: 6,
          color: color,
          fillColor: color,
          fillOpacity: 0.9,
          weight: 1
        }});
        m.bindPopup(devicePopupHtml(d));
        m.addTo(markerLayer);
        visible += 1;
      }});

      document.getElementById('visibleCount').innerText = `Visible: ${{visible}}`;
    }}

    renderMarkers('');

    document.getElementById('providerFilter').addEventListener('change', (e) => {{
      renderMarkers(e.target.value);
    }});

    document.getElementById('searchDevice').addEventListener('keydown', (e) => {{
      if (e.key === 'Enter') {{
        const val = e.target.value.trim();
        const found = devices.find(d => d.device_id === val);
        if (found) {{
          map.setView([found.latitude, found.longitude], 15);
          const color = providerColors[found.provider] || '#3182ce';
          const tempMarker = L.circleMarker([found.latitude, found.longitude], {{
            radius: 8,
            color: color,
            fillColor: color,
            fillOpacity: 0.9,
            weight: 2
          }}).addTo(map);
          tempMarker.bindPopup(devicePopupHtml(found)).openPopup();
          setTimeout(() => map.removeLayer(tempMarker), 5000);
        }}
      }}
    }});
  </script>
</body>
</html>
"""

    # Save HTML
    html_path = os.path.join(topology_dir, "map.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    # Save topology metadata (include resources_to_consider for traceability)
    topo_metadata = {
        "topology_id": topology_id,
        "center_lat": lat,
        "center_long": long,
        "center_elevation": center_elevation,
        "radius_meters": rad,
        "num_devices": len(df_work),
        "allowed_groups": allowed_groups,
        "max_providers": number_of_providers,
        "requested_devices": number_of_devices,
        "providers_in_topology": unique_providers,
        "num_providers": len(unique_providers),
        "resources_to_consider": present_resources,
        "omitted_resources": missing_resources,
        "devices_csv": "devices.csv",
        "map_html": "map.html",
    }

    metadata_path = os.path.join(topology_dir, "metadata.json")
    with open(metadata_path, "w") as f:
        json.dump(topo_metadata, f, indent=2)

    if logs:
        print(f"Topology {topology_id} generated successfully!")
        print(f"  - Devices selected: {len(df_work)}")
        print(f"  - Providers: {len(unique_providers)} ({', '.join(unique_providers)})")
        print(f"  - Groups: {sorted(df_work['global_group'].unique().tolist())}")
        print(f"  - Resources considered: {present_resources}")
        if missing_resources:
            print(f"  - Resources omitted (missing in df): {missing_resources}")
        print(f"  - Files saved in: {topology_dir}")

    return df_work, topology_id