import numpy as np
import sys
sys.path.insert(0, '.')
from stimulator.closed_loop import (
    normalize, quat_mul, quat_conjugate, rotate_vector_by_quaternion,
    twist_angle_around_axis, AXIS_VECTORS
)

data = np.load("raw_imu_data_from_gui.npz")
rs = data['right_shank']
rf = data['right_foot']

print(f"Right Shank samples: {rs.shape}")
print(f"Right Foot samples:  {rf.shape}")
if rs.shape[0] == 0 or rf.shape[0] == 0:
    print("No data!")
    sys.exit(1)

# Column 0 = LSL timestamp, columns 1-10 = sample data
# sample[6:10] = quaternion [w, x, y, z] — but in raw_log we stored [ts] + list(sample)
# So: col 0 = LSL ts, col 1..N = sample values, quaternion at col 7:11
ts_s = rs[:, 0]
ts_f = rf[:, 0]
print(f"Shank time range: {ts_s[0]:.2f} to {ts_s[-1]:.2f} ({ts_s[-1]-ts_s[0]:.1f}s)")
print(f"Foot  time range: {ts_f[0]:.2f} to {ts_f[-1]:.2f} ({ts_f[-1]-ts_f[0]:.1f}s)")

# Check the sample structure
print(f"\nShank sample cols: {rs.shape[1]}")
print(f"First shank sample (first 12 vals): {rs[0, :12]}")
print(f"First foot  sample (first 12 vals): {rf[0, :12]}")

# The quaternion in Xsens DOT LSL is at indices 6:10 of the SAMPLE
# In our raw_log we stored [ts] + list(sample), so quat is at [7:11]
Q_START = 7
Q_END = 11

# Verify quaternion norm
q_test = rs[0, Q_START:Q_END]
print(f"\nShank quat[0] = {q_test}, norm = {np.linalg.norm(q_test):.4f}")
q_test_f = rf[0, Q_START:Q_END]
print(f"Foot  quat[0] = {q_test_f}, norm = {np.linalg.norm(q_test_f):.4f}")

# If norm is far from 1, quaternion indices are wrong — try finding them
if abs(np.linalg.norm(q_test) - 1.0) > 0.1:
    print("\nQuaternion at [7:11] has bad norm! Scanning for correct indices...")
    for start in range(1, rs.shape[1]-3):
        q_try = rs[0, start:start+4]
        n = np.linalg.norm(q_try)
        if abs(n - 1.0) < 0.05:
            print(f"  Found unit quaternion at [{start}:{start+4}]: {q_try}, norm={n:.4f}")

# Match by timestamp
TOLERANCE = 0.05
matched = []
j = 0
for i in range(len(ts_s)):
    while j < len(ts_f) and ts_f[j] < ts_s[i] - TOLERANCE:
        j += 1
    if j < len(ts_f) and abs(ts_f[j] - ts_s[i]) <= TOLERANCE:
        matched.append((i, j))

print(f"\nMatched pairs: {len(matched)} out of {min(len(ts_s), len(ts_f))}")

if len(matched) < 10:
    print("Too few matches, cannot analyze")
    sys.exit(1)

# Use first 50 matched pairs as reference
refs_s = []
refs_f = []
for idx_s, idx_f in matched[:50]:
    refs_s.append(rs[idx_s, Q_START:Q_END])
    refs_f.append(rf[idx_f, Q_START:Q_END])

qs_ref = np.mean(refs_s, axis=0)
qs_ref = qs_ref / np.linalg.norm(qs_ref)
qf_ref = np.mean(refs_f, axis=0)
qf_ref = qf_ref / np.linalg.norm(qf_ref)

print(f"\nReference shank quat: {qs_ref}")
print(f"Reference foot  quat: {qf_ref}")

# Compute angles with twist decomposition around Y (ML axis)
angles_twist_Y = []
# Also compute the simple 3D angle between axes for comparison
angles_3d = []
# Also try twist around X  
angles_twist_X = []

for idx_s, idx_f in matched:
    qs = normalize(rs[idx_s, Q_START:Q_END])
    qf = normalize(rf[idx_f, Q_START:Q_END])
    
    # === Twist decomposition (current algorithm) ===
    q_rel_now = quat_mul(quat_conjugate(qf), qs)
    q_rel_ref = quat_mul(quat_conjugate(qf_ref), qs_ref)
    q_delta = quat_mul(q_rel_now, quat_conjugate(q_rel_ref))
    q_delta = normalize(q_delta)
    if q_delta[0] < 0:
        q_delta = -q_delta
    
    rad_Y = twist_angle_around_axis(q_delta, AXIS_VECTORS['Y'])
    angles_twist_Y.append(np.degrees(rad_Y))
    
    rad_X = twist_angle_around_axis(q_delta, AXIS_VECTORS['X'])
    angles_twist_X.append(np.degrees(rad_X))
    
    # === Simple sagittal plane projection ===
    # Shank longitudinal axis (most vertical = X based on calibration)
    shank_long = rotate_vector_by_quaternion(AXIS_VECTORS['X'], qs)
    # Foot forward axis (X based on detection)
    foot_fwd = rotate_vector_by_quaternion(AXIS_VECTORS['X'], qf)
    
    # Project both into sagittal plane 
    # Use the foot's ML axis (Y) to define the sagittal plane normal
    foot_ml_global = rotate_vector_by_quaternion(AXIS_VECTORS['Y'], qf)
    foot_ml_global = foot_ml_global / np.linalg.norm(foot_ml_global)
    
    # Project shank_long and foot_fwd onto the plane perpendicular to ML
    shank_proj = shank_long - np.dot(shank_long, foot_ml_global) * foot_ml_global
    foot_proj = foot_fwd - np.dot(foot_fwd, foot_ml_global) * foot_ml_global
    
    n_s = np.linalg.norm(shank_proj)
    n_f = np.linalg.norm(foot_proj)
    if n_s > 1e-6 and n_f > 1e-6:
        shank_proj /= n_s
        foot_proj /= n_f
        dot = np.clip(np.dot(shank_proj, foot_proj), -1, 1)
        angle_3d = np.degrees(np.arccos(dot))
        # Sign: cross product check
        cross = np.cross(foot_proj, shank_proj)
        if np.dot(cross, foot_ml_global) < 0:
            angle_3d = -angle_3d
        angles_3d.append(angle_3d - 90)  # subtract 90 so standing = ~0
    else:
        angles_3d.append(0)

angles_twist_Y = np.array(angles_twist_Y)
angles_twist_X = np.array(angles_twist_X)
angles_3d = np.array(angles_3d)

# Identify the 5 phases based on time
total_time = ts_s[matched[-1][0]] - ts_s[matched[0][0]]
match_times = np.array([ts_s[m[0]] for m in matched]) - ts_s[matched[0][0]]

# Print statistics per phase
phases = [
    ("STAND STILL",  0, total_time*0.1),
    ("FLEX (straight)", total_time*0.1, total_time*0.3),
    ("KNEE BEND",   total_time*0.3, total_time*0.5),
    ("FLEX (bent)",  total_time*0.5, total_time*0.7),
    ("WALK",         total_time*0.7, total_time),
]

print("\n========== ANKLE ANGLE ANALYSIS ==========")
print(f"{'Phase':<22} {'Twist-Y min':>10} {'Twist-Y max':>10} {'Twist-Y std':>10} | {'Sagittal min':>10} {'Sagittal max':>10}")
for name, t0, t1 in phases:
    mask = (match_times >= t0) & (match_times < t1)
    if mask.sum() < 5:
        continue
    ty = angles_twist_Y[mask]
    s = angles_3d[mask]
    print(f"{name:<22} {ty.min():>10.1f} {ty.max():>10.1f} {ty.std():>10.1f} | {s.min():>10.1f} {s.max():>10.1f}")

print(f"\n{'FULL RECORDING':<22} {angles_twist_Y.min():>10.1f} {angles_twist_Y.max():>10.1f} {angles_twist_Y.std():>10.1f} | {angles_3d.min():>10.1f} {angles_3d.max():>10.1f}")

# Check knee dependency: correlate twist-Y with a proxy for knee angle
# Proxy: angle between shank vertical axis and gravity
knee_proxy = []
for idx_s, _ in matched:
    qs = normalize(rs[idx_s, Q_START:Q_END])
    shank_x = rotate_vector_by_quaternion(AXIS_VECTORS['X'], qs)
    # How much shank tilts from vertical (0 = standing straight)
    knee_proxy.append(np.degrees(np.arccos(np.clip(abs(shank_x[2]), 0, 1))))

knee_proxy = np.array(knee_proxy)
corr = np.corrcoef(angles_twist_Y, knee_proxy)[0, 1]
corr_sag = np.corrcoef(angles_3d, knee_proxy)[0, 1]
print(f"\nCorrelation with knee proxy (shank tilt):")
print(f"  Twist-Y:   r = {corr:.3f}  {'⚠ HIGH DEPENDENCY' if abs(corr) > 0.5 else '✓ low dependency'}")
print(f"  Sagittal:  r = {corr_sag:.3f}  {'⚠ HIGH DEPENDENCY' if abs(corr_sag) > 0.5 else '✓ low dependency'}")

