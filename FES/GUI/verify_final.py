"""Verify the new sagittal-plane ankle algorithm using live raw data."""
import numpy as np
import sys
sys.path.insert(0, '.')
from stimulator.closed_loop import (
    normalize, signed_ankle_angle, detect_most_vertical_axis,
    rotate_vector_by_quaternion, AXIS_VECTORS
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

# Detect axes like the calibration code does
shank_vert = detect_most_vertical_axis(qs_ref)
print(f"Shank vertical (longitudinal) axis: {shank_vert}")
print(f"Foot forward axis: X (from user calibration)")

# Test the ACTUAL signed_ankle_angle function from closed_loop.py
angles = []
knee_proxy = []
for idx_s, idx_f in matched:
    qs = normalize(rs[idx_s, Q_START:Q_END])
    qf = normalize(rf[idx_f, Q_START:Q_END])
    a = signed_ankle_angle(
        qs, qf, qs_ref, qf_ref,
        foot_axis='X',        # not used by new algo but kept for compat
        shank_long_axis=shank_vert,  # X for this user
        foot_fwd_axis='X',
        shank_ml_axis='Y',    # Y is ML for this user's shank
    )
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

corr = np.corrcoef(angles, knee_proxy)[0, 1]
print(f"\nKnee correlation: r = {corr:.3f}  {'⚠ HIGH' if abs(corr) > 0.5 else '✓ LOW — INDEPENDENT!'}")
print(f"Overall range: {angles.min():.1f}° to {angles.max():.1f}°")

