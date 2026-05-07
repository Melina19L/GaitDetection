import numpy as np
import sys
sys.path.insert(0, '.')
from stimulator.closed_loop import (
    normalize, quat_mul, quat_conjugate, rotate_vector_by_quaternion,
    AXIS_VECTORS
)

data = np.load("raw_imu_data_from_gui.npz")
rs = data['right_shank']
rf = data['right_foot']

Q_START = 7
Q_END = 11
ts_s = rs[:, 0]
ts_f = rf[:, 0]

# Match by timestamp
TOLERANCE = 0.05
matched = []
j = 0
for i in range(len(ts_s)):
    while j < len(ts_f) and ts_f[j] < ts_s[i] - TOLERANCE:
        j += 1
    if j < len(ts_f) and abs(ts_f[j] - ts_s[i]) <= TOLERANCE:
        matched.append((i, j))

# Reference (first 50 matched = standing still)
refs_s = [normalize(rs[i, Q_START:Q_END]) for i, _ in matched[:50]]
refs_f = [normalize(rf[j, Q_START:Q_END]) for _, j in matched[:50]]
qs_ref = np.mean(refs_s, axis=0); qs_ref /= np.linalg.norm(qs_ref)
qf_ref = np.mean(refs_f, axis=0); qf_ref /= np.linalg.norm(qf_ref)

# Get the reference sagittal plane from the shank at calibration
# Shank vertical axis = X, shank forward = Z (from user's latest calibration)
shank_long_ref = rotate_vector_by_quaternion(AXIS_VECTORS['X'], qs_ref)  # Points down along tibia
foot_fwd_ref = rotate_vector_by_quaternion(AXIS_VECTORS['X'], qf_ref)   # Points along foot

# The sagittal plane is defined by the shank longitudinal and vertical directions
# Its normal is the medio-lateral direction at calibration
# We use the GLOBAL Y-projection of the shank's local Z to get the sagittal normal
shank_ml_ref = rotate_vector_by_quaternion(AXIS_VECTORS['Y'], qs_ref)  # Shank ML axis in global
sag_normal = shank_ml_ref / np.linalg.norm(shank_ml_ref)

# Compute calibration angle
def project_to_plane(v, normal):
    return v - np.dot(v, normal) * normal

def sagittal_ankle_angle(qs, qf, sag_normal, offset):
    """Compute ankle angle by projecting shank and foot axes onto the sagittal plane."""
    # Shank longitudinal axis in global (points along the tibia, mostly downward when standing)
    shank_long = rotate_vector_by_quaternion(AXIS_VECTORS['X'], qs)
    # Foot forward axis in global (points along the foot toward toes)
    foot_fwd = rotate_vector_by_quaternion(AXIS_VECTORS['X'], qf)
    
    # Project both onto the sagittal plane
    shank_proj = project_to_plane(shank_long, sag_normal)
    foot_proj = project_to_plane(foot_fwd, sag_normal)
    
    ns = np.linalg.norm(shank_proj)
    nf = np.linalg.norm(foot_proj)
    if ns < 1e-6 or nf < 1e-6:
        return 0.0
    shank_proj /= ns
    foot_proj /= nf
    
    # Angle between the two projections
    dot = np.clip(np.dot(shank_proj, foot_proj), -1, 1)
    angle = np.degrees(np.arccos(dot))
    
    # Sign: cross product determines direction
    cross = np.cross(foot_proj, shank_proj)
    if np.dot(cross, sag_normal) < 0:
        angle = -angle
    
    return angle - offset

# Compute calibration offset
cal_angle = sagittal_ankle_angle(qs_ref, qf_ref, sag_normal, 0.0)
print(f"Calibration angle (offset): {cal_angle:.1f}°")

# Now test different approaches:
# A) Fixed sagittal plane (from calibration - doesn't rotate with the body)
# B) Dynamic sagittal plane (from current shank ML axis - rotates with the body)
# C) Dynamic sagittal from foot's ML axis

angles_fixed = []
angles_dyn_shank = []
angles_dyn_foot = []
knee_proxy = []

for idx_s, idx_f in matched:
    qs = normalize(rs[idx_s, Q_START:Q_END])
    qf = normalize(rf[idx_f, Q_START:Q_END])
    
    # A) Fixed sagittal plane
    a_fixed = sagittal_ankle_angle(qs, qf, sag_normal, cal_angle)
    angles_fixed.append(a_fixed)
    
    # B) Dynamic sagittal from shank
    shank_ml_now = rotate_vector_by_quaternion(AXIS_VECTORS['Y'], qs)
    sag_dyn_s = shank_ml_now / np.linalg.norm(shank_ml_now)
    a_dyn_s = sagittal_ankle_angle(qs, qf, sag_dyn_s, cal_angle)
    angles_dyn_shank.append(a_dyn_s)
    
    # C) Dynamic sagittal from foot
    foot_ml_now = rotate_vector_by_quaternion(AXIS_VECTORS['Y'], qf)
    sag_dyn_f = foot_ml_now / np.linalg.norm(foot_ml_now)
    a_dyn_f = sagittal_ankle_angle(qs, qf, sag_dyn_f, cal_angle)
    angles_dyn_foot.append(a_dyn_f)
    
    # Knee proxy
    shank_x = rotate_vector_by_quaternion(AXIS_VECTORS['X'], qs)
    knee_proxy.append(np.degrees(np.arccos(np.clip(abs(shank_x[2]), 0, 1))))

angles_fixed = np.array(angles_fixed)
angles_dyn_shank = np.array(angles_dyn_shank)
angles_dyn_foot = np.array(angles_dyn_foot)
knee_proxy = np.array(knee_proxy)

match_times = np.array([ts_s[m[0]] for m in matched]) - ts_s[matched[0][0]]
total_time = match_times[-1]

phases = [
    ("STAND STILL",    0, total_time*0.1),
    ("FLEX (straight)", total_time*0.1, total_time*0.3),
    ("KNEE BEND",      total_time*0.3, total_time*0.5),
    ("FLEX (bent)",     total_time*0.5, total_time*0.7),
    ("WALK",            total_time*0.7, total_time),
]

print(f"\n{'Phase':<22} {'Fixed min':>8} {'Fixed max':>8} | {'DynShank min':>10} {'DynShank max':>10} | {'DynFoot min':>10} {'DynFoot max':>10}")
for name, t0, t1 in phases:
    mask = (match_times >= t0) & (match_times < t1)
    if mask.sum() < 5:
        continue
    af = angles_fixed[mask]
    ads = angles_dyn_shank[mask]
    adf = angles_dyn_foot[mask]
    print(f"{name:<22} {af.min():>8.1f} {af.max():>8.1f} | {ads.min():>10.1f} {ads.max():>10.1f} | {adf.min():>10.1f} {adf.max():>10.1f}")

corr_f = np.corrcoef(angles_fixed, knee_proxy)[0, 1]
corr_ds = np.corrcoef(angles_dyn_shank, knee_proxy)[0, 1]
corr_df = np.corrcoef(angles_dyn_foot, knee_proxy)[0, 1]

print(f"\nCorrelation with knee proxy:")
print(f"  Fixed sagittal:      r = {corr_f:.3f}  {'⚠ HIGH' if abs(corr_f) > 0.5 else '✓ LOW'}")
print(f"  Dynamic (shank ML):  r = {corr_ds:.3f}  {'⚠ HIGH' if abs(corr_ds) > 0.5 else '✓ LOW'}")
print(f"  Dynamic (foot ML):   r = {corr_df:.3f}  {'⚠ HIGH' if abs(corr_df) > 0.5 else '✓ LOW'}")

