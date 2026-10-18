"""Inspect public evidence around the remaining omitted payload edge pixel."""

import hashlib
import json
import runpy
import sys
from pathlib import Path

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
setup = base/'scripts/cup8158_guided_runtime_pair_r12_CPU_20261018.py'
sys.argv = [str(setup), '--working-source', str(root/'source_bounded_276456d_20261018'),
    '--sam-report', str(base/'reports/cup8158_owned_query_combined_GPU_responses_20261018.json')]
context = runpy.run_path(str(setup))
import numpy as np
from scipy.spatial import cKDTree

a, load = context['a'], context['load_frame']
instance = a._instance_pixels('e6')
point = np.array([.0107914749532938, .08394207060337067, .7108669877052307])
world = a._self_filtered_world(load('wrist_world_high.npz'))
rgb = load('wrist_high.png')
owned = np.zeros(world.shape[:2], bool)
ids = np.flatnonzero(np.isfinite(world).all(2))
owned.flat[ids] = cKDTree(instance).query(world.reshape(-1, 3)[ids],
    distance_upper_bound=np.nextafter(1e-6, np.inf))[0] <= 1e-6
y, x = 853, 481
region = np.s_[y-4:y+5, x-4:x+5]
local = world[region]
distance = np.linalg.norm(local-point, axis=2)
colour = np.max(abs(rgb[region].astype(float)-rgb[y, x].astype(float)), axis=2)/255.
semantic_ref = context['row']['perception_evidence']['e6']['sam_mask_files']['wrist']
with np.load(semantic_ref['path']) as archive:
    semantic = archive[archive.files[0]].astype(bool)
static_distance = cKDTree(a.payload_reference['scene']).query(point)[0]
report = {'scope': 'current saved public RGB-D and retained legitimate SAM only; zero controls',
    'private_truth_used': False, 'training': False, 'gpu_used': False,
    'setup_sha256': hashlib.sha256(setup.read_bytes()).hexdigest(),
    'point_m': point.tolist(), 'point_rgb': rgb[y, x].tolist(),
    'prelift_static_nearest_m': float(static_distance),
    'inside_current_raw_extent': bool(((point >= instance.min(0)) & (point <= instance.max(0))).all()),
    'current_raw_extent': [instance.min(0).tolist(), instance.max(0).tolist()],
    'nearest_instance_m': float(cKDTree(instance).query(point)[0]),
    'patch_row_col_start': [y-4, x-4], 'owned': owned[region].astype(int).tolist(),
    'semantic': semantic[region].astype(int).tolist(),
    'rgb_max_channel_difference': colour.tolist(), 'distance_from_point_m': distance.tolist()}
output = base/'reports/cup8158_boundary_reason_CPU_20261018.json'
output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report))
