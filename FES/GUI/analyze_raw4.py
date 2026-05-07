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

# Match
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

gravity = np.array([0, 0, 1.0])

def ankle_angle_gravity_sagittal(qs, qf, qs_ref, qf_ref):
    """
    Compute ankle angle using a gravity-defined sagittal plane.
    
    The sagittal plane normal is the cross product of gravity and the 
    shank's longitudinal axis at CALIBRATION time (fixed heading).
    Both shank-long and foot-fwd are projected onto this plane.
    The ankle angle = angle between them - calibration offset.
    """
    # Shank longitudinal (X axis) - this points along the tibia
    shank_long = rotate_vector_by_quaternion(AXIS_VECTORS['X'], qs)
    foot_fwd = rotate_vector_by_quaternion(AXIS_VECTORS['X'], qf)
    
    # Use the calibration-time shank to define the sagittal plane heading
    shank_long_cal = rotate_vector_by_quaternion(AXIS_VECTORS['X'], qs_ref)
    
    # The sagittal plane normal = cross(gravity, shank_at_cal_horizontal)
    # This gives us a fixed ML direction that doesn't change with knee flexion
    shank_horiz = shank_long_cal.copy()
    shank_horiz[2] = 0  # Remove vertical component
    n = np.linalg.norm(shank_horiz)
    if n < 1e-6:
        shank_horiz = np.array([1, 0, 0])
    else:
        shank_horiz /= n
    
    # ML direction = perpendicular to forward and gravity
    ml_dir = np.cross(shank_horiz, gravity)
    ml_norm = np.linalg.norm(ml_dir)
    if ml_norm < 1e-6:
        return 0.0
    ml_dir /= ml_norm
    
    # Project both vectors onto the sagittal plane
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

# Compute calibration offset
cal_offset = ankle_angle_gravity_sagittal(qs_ref, qf_ref, qs_ref, qf_ref)
print(f"Calibration offset: {cal_offset:.1f}°")

angles = []
knee_proxy = []
for idx_s, idx_f in matched:
    qs = normalize(rs[idx_s, Q_START:Q_END])
    qf = normalize(rf[idx_f, Q_START:Q_END])
    a = ankle_angle_gravity_sagittal(qs, qf, qs_ref, qf_ref) - cal_offset
    angles.append(a)
    
    shank_x = rotate_vector_by_quaternion(AXIS_VECTORS['X'], qs)
    knee_proxy.append(np.degrees(np.arccos(np.clip(abs(shank_x[2]), 0, 1))))

angles = np.array(angles)
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

print(f"\n{'Phase':<22} {'Min':>8} {'Max':>8} {'Mean':>8} {'Std':>8}")
for name, t0, t1 in phases:
    mask = (match_times >= t0) & (match_times < t1)
    if mask.sum() < 5:
        continue
    a = angles[mask]
    print(f"{name:<22} {a.min():>8.1f} {a.max():>8.1f} {a.mean():>8.1f} {a.std():>8.1f}")

print(f"\n{'FULL RECORDING':<22} {angles.min():>8.1f} {angles.max():>8.1f} {angles.mean():>8.1f} {angles.std():>8.1f}")

corr = np.corrcoef(angles, knee_proxy)[0, 1]
print(f"\nCorrelation with knee: r = {corr:.3f}  {'⚠ HIGH' if abs(corr) > 0.5 else '✓ LOW'}")

