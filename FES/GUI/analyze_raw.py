import numpy as np
from stimulator.closed_loop import twist_angle_around_axis, AXIS_VECTORS
import matplotlib.pyplot as plt

data = np.load("raw_imu_data_from_gui.npz")
rs = data['right_shank']
rf = data['right_foot']

print(f"Right Shank samples: {len(rs)}")
print(f"Right Foot samples: {len(rf)}")

# ts is at index 0, quat w,x,y,z at 1,2,3,4
ts_s = rs[:, 0]
ts_f = rf[:, 0]

# Calculate time difference
if len(ts_s) > 0 and len(ts_f) > 0:
    print(f"Shank duration: {ts_s[-1] - ts_s[0]:.2f} s")
    print(f"Foot duration: {ts_f[-1] - ts_f[0]:.2f} s")
    
    # Check alignment if we matched by index (the current bug)
    n_pairs = min(len(ts_s), len(ts_f))
    index_gaps = ts_s[:n_pairs] - ts_f[:n_pairs]
    print(f"Mean gap by index match: {np.mean(index_gaps):.4f} s (max: {np.max(np.abs(index_gaps)):.4f} s)")

    # Let's align them properly by timestamp and compute the twist angle
    from scipy.spatial.transform import Rotation
    def quat_mul(q1, q2):
        w1, x1, y1, z1 = q1
        w2, x2, y2, z2 = q2
        return np.array([
            w1*w2 - x1*x2 - y1*y2 - z1*z2,
            w1*x2 + x1*w2 + y1*z2 - z1*y2,
            w1*y2 - x1*z2 + y1*w2 + z1*x2,
            w1*z2 + x1*y2 - y1*x2 + z1*w2
        ])
    def quat_conjugate(q):
        return np.array([q[0], -q[1], -q[2], -q[3]])

    # Choose a reference frame (say, average of first 50 aligned samples)
    qs_aligned = []
    qf_aligned = []
    times = []
    
    for i in range(len(ts_s)):
        t = ts_s[i]
        idx_f = np.argmin(np.abs(ts_f - t))
        if np.abs(ts_f[idx_f] - t) < 0.05: # 50ms tolerance
            qs_aligned.append(rs[i, 1:5])
            qf_aligned.append(rf[idx_f, 1:5])
            times.append(t)
            
    qs_aligned = np.array(qs_aligned)
    qf_aligned = np.array(qf_aligned)
    
    qs_ref = np.mean(qs_aligned[:50], axis=0)
    qs_ref /= np.linalg.norm(qs_ref)
    qf_ref = np.mean(qf_aligned[:50], axis=0)
    qf_ref /= np.linalg.norm(qf_ref)
    
    # Twist decomposition
    q_rel_ref = quat_mul(quat_conjugate(qf_ref), qs_ref)
    axis = AXIS_VECTORS['Y'] # Foot ML axis is Y for this user's twist setting
    
    angles_proper = []
    for qs, qf in zip(qs_aligned, qf_aligned):
        q_rel_now = quat_mul(quat_conjugate(qf), qs)
        q_delta = quat_mul(q_rel_now, quat_conjugate(q_rel_ref))
        if q_delta[0] < 0: q_delta = -q_delta
        rad = twist_angle_around_axis(q_delta, axis)
        angles_proper.append(np.degrees(rad))
        
    print(f"\nProperly aligned Ankle Range: min {np.min(angles_proper):.1f}, max {np.max(angles_proper):.1f}")
    
    # Let's compute it with the INDEX mismatch (the bug)
    angles_buggy = []
    for qs, qf in zip(rs[:n_pairs, 1:5], rf[:n_pairs, 1:5]):
        q_rel_now = quat_mul(quat_conjugate(qf), qs)
        q_delta = quat_mul(q_rel_now, quat_conjugate(q_rel_ref))
        if q_delta[0] < 0: q_delta = -q_delta
        rad = twist_angle_around_axis(q_delta, axis)
        angles_buggy.append(np.degrees(rad))
        
    print(f"Buggy matched Ankle Range: min {np.min(angles_buggy):.1f}, max {np.max(angles_buggy):.1f}")

