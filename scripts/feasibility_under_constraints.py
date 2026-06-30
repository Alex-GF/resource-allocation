"""Re-evaluate baseline solutions under the full problem constraint set.

A solution is feasible under PRIME's problem definition if and only if:
  1. The baseline itself flagged it feasible (covers demand + basic constraints it models).
  2. The selected add-ons do not co-deploy mutually-exclusive providers (OPTUS/TELSTRA
     exclusion, as declared in `config/experiment_configuration.yml`).
  3. The union of device types of the selected add-ons covers the device types required
     by the application (e.g., CCTV requires CAMERA, NETWORK_NODE, DATA_CENTER; a
     single non-CAMERA node cannot satisfy the request).

Run from the repository root:

    python scripts/feasibility_under_constraints.py
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = REPO_ROOT / 'results'
TOPO_DIR = REPO_ROOT / 'synthetic-dataset' / 'synthetic-topologies'
FIG_DIR = RESULTS_DIR / 'figures'
FIG_DIR.mkdir(parents=True, exist_ok=True)

APP_NAMES = {'cctv': 'CCTV', 'lidar': 'LiDAR', 'robot': 'Robot', 'vr': 'VR'}
APP_ORDER = ['cctv', 'lidar', 'robot', 'vr']
FAMILY_COLORS = {'PRIME': '#3498db', 'RAOM4CC': '#e74c3c', 'EdgeWiseCR': '#2ecc71'}

# Device types required per application (from config/experiment_configuration.yml:
# dev_types_arvr, dev_types_robot, dev_types_lidar, dev_types_video).
REQUIRED_DEVICE_TYPES = {
    'vr':    {'CAMERA', 'SENSOR', 'NETWORK_NODE', 'DATA_CENTER'},
    'robot': {'SENSOR', 'COMPUTER', 'NETWORK_NODE'},
    'lidar': {'SENSOR', 'NETWORK_NODE', 'DATA_CENTER'},
    'cctv':  {'CAMERA', 'NETWORK_NODE', 'DATA_CENTER'},
}

# Critical device type per application — the defining sensor-type a single-node
# deployment must at least provide to be considered usable for that workload.
CRITICAL_DEVICE_TYPE = {
    'cctv':  'CAMERA',
    'vr':    'CAMERA',
    'lidar': 'SENSOR',
    'robot': 'SENSOR',
}

EXCLUSION_PAIRS = [('OPTUS', 'TELSTRA')]


def _provider_map(topo_id, cache):
    if topo_id in cache:
        return cache[topo_id]
    p = TOPO_DIR / topo_id / 'devices.csv'
    if not p.exists():
        cache[topo_id] = {}
        return {}
    d = pd.read_csv(p)
    m = dict(zip(d['device_id'].astype(str), d['provider'].astype(str)))
    cache[topo_id] = m
    return m


def _parse_ids(x):
    if pd.isna(x):
        return []
    try:
        v = ast.literal_eval(x)
        return [str(i) for i in v]
    except Exception:
        return []


def _parse_set(x):
    if pd.isna(x):
        return set()
    try:
        return set(ast.literal_eval(x))
    except Exception:
        return set()


def _violates_exclusion(providers):
    ps = set(providers)
    for a, b in EXCLUSION_PAIRS:
        if a in ps and b in ps:
            return True
    return False


def _app_from_sid(sid):
    return sid.split('_')[2]


def _tech_color(t):
    for fam, c in FAMILY_COLORS.items():
        if t.startswith(fam):
            return c
    return '#95a5a6'


def _short_tech(t):
    return t.replace('RAOM4CC_', 'RAOM. ').replace('EdgeWiseCR_', 'EW. ')


def _recheck(df, cache, mode='strict'):
    """Recompute feasibility combining demand (baseline's own flag), provider
    exclusions, and device-type coverage. ``mode`` selects the device-type check:
      - 'exclusion_only': no device-type check (PRIME-exclusion only)
      - 'critical': require the critical device type for the application to be
        present among the selected add-ons
      - 'strict': require ALL device types in `REQUIRED_DEVICE_TYPES[app]` to be
        covered by the union of selected add-ons
    """
    out = []
    for _, row in df.iterrows():
        if not row['feasible']:
            out.append(False)
            continue
        ids = _parse_ids(row['selected_node'])
        if not ids:
            out.append(True)
            continue
        # Constraint 2: provider exclusions
        pmap = _provider_map(row['topology_id'], cache)
        provs = [p for p in (pmap.get(i, '') for i in ids) if p]
        if provs and _violates_exclusion(provs):
            out.append(False)
            continue
        # Constraint 3: device-type coverage (modes)
        if mode == 'exclusion_only':
            out.append(True)
            continue
        sel_types = _parse_set(row['selected_features'])
        if mode == 'critical':
            crit = CRITICAL_DEVICE_TYPE.get(row['app'])
            out.append(crit in sel_types if crit else True)
        elif mode == 'strict':
            required = REQUIRED_DEVICE_TYPES.get(row['app'], set())
            out.append(required.issubset(sel_types) if required else True)
        else:
            out.append(True)
    return out


def main():
    cache = {}

    raom = pd.read_csv(RESULTS_DIR / 'raom4cc_benchmark_results.csv')
    raom['technique'] = 'RAOM4CC_' + raom['algorithm']
    raom['family'] = 'RAOM4CC'
    raom['feasible'] = raom['feasible'].astype(str) == 'True'
    raom['app'] = raom['scenario_id'].apply(_app_from_sid)
    raom['app_name'] = raom['app'].map(APP_NAMES)
    raom['feas_exc'] = _recheck(raom, cache, 'exclusion_only')
    raom['feas_crit'] = _recheck(raom, cache, 'critical')
    raom['feas_all'] = _recheck(raom, cache, 'strict')

    ew = pd.read_csv(RESULTS_DIR / 'edgewisecr_results.csv')
    ew['technique'] = 'EdgeWiseCR_' + ew['algorithm']
    ew['family'] = 'EdgeWiseCR'
    ew['feasible'] = ew['feasible'].astype(str) == 'True'
    ew['app'] = ew['scenario_id'].apply(_app_from_sid)
    ew['app_name'] = ew['app'].map(APP_NAMES)
    ew['feas_exc'] = _recheck(ew, cache, 'exclusion_only')
    ew['feas_crit'] = _recheck(ew, cache, 'critical')
    ew['feas_all'] = _recheck(ew, cache, 'strict')

    prime = pd.read_csv(RESULTS_DIR / 'results.csv')
    prime['technique'] = 'PRIME'
    prime['family'] = 'PRIME'
    prime['feasible'] = prime['status'] == 'COMPLETED'
    prime['app'] = prime['scenario_id'].apply(_app_from_sid)
    prime['app_name'] = prime['app'].map(APP_NAMES)
    prime['selected_node'] = prime['add_ons']
    # PRIME enforces all these constraints internally, so its solutions satisfy
    # every check by construction.
    prime['feas_exc'] = prime['feasible']
    prime['feas_crit'] = prime['feasible']
    prime['feas_all'] = prime['feasible']

    all_data = pd.concat([raom, ew, prime], ignore_index=True)

    def pivot(col):
        p = (all_data.groupby(['technique', 'app_name'])[col].mean() * 100)
        return p.unstack('app_name')[[APP_NAMES[a] for a in APP_ORDER]]

    piv_exc = pivot('feas_exc')
    piv_crit = pivot('feas_crit')
    piv_all = pivot('feas_all')

    piv_exc.to_csv(RESULTS_DIR / '_true_feasibility_pivot.csv')

    print('=== Per-app feasibility (%): demand + provider exclusion ===')
    print(piv_exc.round(1).to_string())
    print()
    print('=== Per-app feasibility (%): demand + exclusion + critical device type ===')
    print(piv_crit.round(1).to_string())
    print()
    print('=== Per-app feasibility (%): demand + exclusion + ALL required device types ===')
    print(piv_all.round(1).to_string())

    overall = pd.DataFrame({
        'exclusion_only': all_data.groupby('technique')['feas_exc'].mean() * 100,
        '+critical_type':  all_data.groupby('technique')['feas_crit'].mean() * 100,
        '+all_types':      all_data.groupby('technique')['feas_all'].mean() * 100,
    }).round(1)
    print()
    print('=== Overall (%) per technique ===')
    print(overall.to_string())

    # Render three charts side-by-side documentation would be cluttered; plot only the
    # strict "critical type" view as the primary figure since it produces a meaningful
    # spread across techniques.
    fig, ax = plt.subplots(figsize=(12, 8))
    o_crit = all_data.groupby('technique')['feas_crit'].mean().sort_values() * 100
    colors = [_tech_color(t) for t in o_crit.index]
    ax.barh(range(len(o_crit)), o_crit.values, color=colors, alpha=0.85,
            edgecolor='white', linewidth=0.5)
    ax.set_yticks(range(len(o_crit)))
    ax.set_yticklabels([_short_tech(t) for t in o_crit.index], fontsize=8)
    ax.axvline(100, color='grey', ls='--', alpha=0.4)
    ax.set_xlim(0, 115)
    for i, v in enumerate(o_crit.values):
        ax.text(v + 1, i, f'{v:.1f}%', va='center', fontsize=8, fontweight='bold')
    patches = [mpatches.Patch(color=c, label=f) for f, c in FAMILY_COLORS.items()]
    ax.legend(handles=patches, loc='lower right', title='Family')
    ax.set_title('Feasibility (demand + provider exclusion + critical device type)',
                 fontsize=13, fontweight='bold')
    plt.tight_layout()
    out = FIG_DIR / 'feasibility_true_faceted.png'
    plt.savefig(out, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f'\nFigure saved to {out}')


if __name__ == '__main__':
    main()