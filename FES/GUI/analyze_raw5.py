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
Q_START, Q_END = 7, 11
ts_s, ts_f = rs[:, 0], rf[:, 0]

TOLERANCE = 0.05
matched = []
j = 0
for i in range(len(ts_s)):
    while j < len(ts_f) and ts_f[j] < ts_s[i] - TOLERANCE:
        j += 1
    if j < len(ts_f) and abs(ts_f[j] - ts_s[i]) <= TOLERANCE:
        matched.append((i, j))

refs_s = [normalize(rs[i, Q_START:Q_END]) for i, _ in matched[:50]]
refs_f = [normalize(rf[j, Q_START:Q_END]) for _, j in matched[:50]]
qs_ref = np.mean(refs_s, axis=0); qs_ref /= np.linalg.norm(qs_ref)
qf_ref = np.mean(refs_f, axis=0); qf_ref /= np.linalg.norm(qf_ref)

gravity = np.array([0.0, 0.0, 1.0])

def ankle_angle_v2(qs, qf):
    """
    Ankle angle = angle between shank and foot projected onto a 
    gravity-constrained sagittal plane.
    
    Strategy: use the FOOT's ML axis (Y) projected onto the horizontal 
    plane as the sagittal plane normal. This follows the body's heading 
    (handles turns) but removes the vertical component (immune to knee tilt).
    """
    # Foot's medio-lateral axis (Y) in global frame
    foot_ml = rotate_vector_by_quaternion(AXIS_VECTORS['Y'], qf)
    # Keep only horizontal component (remove gravity contamination)
    foot_ml_horiz = foot_ml.copy()
    foot_ml_horiz[2] = 0
    n = np.linalg.norm(foot_ml_horiz)
    if n < 1e-6:
        return 0.0
    ml_dir = foot_ml_horiz / n
    
    # Shank longitudinal axis
    shank_long = rotate_vector_by_quaternion(AXIS_VECTORS['X'], qs)
    # Foot forward axis
    foot_fwd = rotate_vector_by_quaternion(AXIS_VECTORS['X'], qf)
    
    # Project both onto sagittal plane (perpendicular to ml_dir)
    shank_proj = shank_long - np.dot(shank_long, ml_dir) * ml_dir
    foot_proj = foot_fwd - np.dot(foot_fwd, ml_dir) * ml_dir
    
    ns = np.linalg.norm(shank_proj)
    nf = np.linalg.norm(foot_proj)
    if ns < 1e-6 or nf < 1e-6:
        return 0.0
    shank_proj /= ns
    foot_proj /= nf
    
    dot = np.clip(np.dot(shank_proj, foot_proj), -1, 1)
    angle = np.degrees(np.arccos(dot))
    
    cross = np.cross(foot_proj, shank_proj)
    if np.dot(cross, ml_dir) < 0:
        angle = -angle
    
    return angle

def ankle_angle_v3(qs, qf):
    """
    V3: Use shank's ML axis (Y) projected onto horizontal as sagittal normal.
    The shank's Y axis stays horizontal even during knee flexion because
    knee flexion is around Y itself.
    """
    shank_ml = rotate_vector_by_quaternion(AXIS_VECTORS['Y'], qs)
    shank_ml_horiz = shank_ml.copy()
    shank_ml_horiz[2] = 0
    n = np.linalg.norm(shank_ml_horiz)
    if n < 1e-6:
        return 0.0
    ml_dir = shank_ml_horiz / n
    
    shank_long = rotate_vector_by_quaternion(AXIS_VECTORS['X'], qs)
    foot_fwd = rotate_vector_by_quaternion(AXIS_VECTORS['X'], qf)
    
    shank_proj = shank_long - np.dot(shank_long, ml_dir) * ml_dir
    foot_proj = foot_fwd - np.dot(foot_fwd, ml_dir) * ml_dir
    
    ns = np.linalg.norm(shank_proj)
    nf = np.linalg.norm(foot_proj)
    if ns < 1e-6 or nf < 1e-6:
        return 0.0
    shank_proj /= ns
    foot_proj /= nf
    
    dot = np.clip(np.dot(shank_proj, foot_proj), -1, 1)
    angle = np.degrees(np.arccos(dot))
    
    cross = np.cross(foot_proj, shank_proj)
    if np.dot(cross, ml_dir) < 0:
        angle = -angle
    
    return angle

# Calibration offsets
cal_v2 = ankle_angle_v2(qs_ref, qf_ref)
cal_v3 = ankle_angle_v3(qs_ref, qf_ref)
print(f"Cal offset V2 (foot ML horiz): {cal_v2:.1f}°")
print(f"Cal offset V3 (shank ML horiz): {cal_v3:.1f}°")

angles_v2 = []
angles_v3 = []
knee_proxy = []

for idx_s, idx_f in matched:
    qs = normalize(rs[idx_s, Q_START:Q_END])
    qf = normalize(rf[idx_f, Q_START:Q_END])
    angles_v2.append(ankle_angle_v2(qs, qf) - cal_v2)
    angles_v3.append(ankle_angle_v3(qs, qf) - cal_v3)
    
    shank_x = rotate_vector_by_quaternion(AXIS_VECTORS['X'], qs)
    knee_proxy.append(np.degrees(np.arccos(np.clip(abs(shank_x[2]), 0, 1))))

angles_v2 = np.array(angles_v2)
angles_v3 = np.array(angles_v3)
knee_proxy = np.array(knee_proxy)

match_times = np.array([ts_s[m[0]] for m in matched]) - ts_s[matched[0][0]]
total_time = match_times[-1]

phases = [
    ("STAND STILL",     0, total_time*0.1),
    ("FLEX (straight)", total_time*0.1, total_time*0.3),
    ("KNEE BEND",       total_time*0.3, total_time*0.5),
    ("FLEX (bent)",      total_time*0.5, total_time*0.7),
    ("WALK",             total_time*0.7, total_time),
]

print(f"\n{'Phase':<22} {'V2 min':>8} {'V2 max':>8} {'V2 std':>8} | {'V3 min':>8} {'V3 max':>8} {'V3 std':>8}")
for name, t0, t1 in phases:
    mask = (match_times >= t0) & (match_times < t1)
    if mask.sum() < 5:
        continue
    a2 = angles_v2[mask]
    a3 = angles_v3[mask]
    print(f"{name:<22} {a2.min():>8.1f} {a2.max():>8.1f} {a2.std():>8.1f} | {a3.min():>8.1f} {a3.max():>8.1f} {a3.std():>8.1f}")

print(f"\n{'FULL':<22} {angles_v2.min():>8.1f} {angles_v2.max():>8.1f} {angles_v2.std():>8.1f} | {angles_v3.min():>8.1f} {angles_v3.max():>8.1f} {angles_v3.std():>8.1f}")

corr_v2 = np.corrcoef(angles_v2, knee_proxy)[0, 1]
corr_v3 = np.corrcoef(angles_v3, knee_proxy)[0, 1]
print(f"\nCorrelation with knee:")
print(f"  V2 (foot ML horiz):   r = {corr_v2:.3f}  {'⚠ HIGH' if abs(corr_v2) > 0.5 else '✓ LOW'}")
print(f"  V3 (shank ML horiz):  r = {corr_v3:.3f}  {'⚠ HIGH' if abs(corr_v3) > 0.5 else '✓ LOW'}")

