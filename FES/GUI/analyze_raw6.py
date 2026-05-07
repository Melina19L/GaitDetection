import numpy as np
import sys
sys.path.insert(0, '.')
from stimulator.closed_loop import normalize, rotate_vector_by_quaternion, AXIS_VECTORS

data = np.load("raw_imu_data_from_gui.npz")
rs = data['right_shank']
rf = data['right_foot']
Q_START, Q_END = 7, 11
ts_s = rs[:, 0]
ts_f = rf[:, 0]

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

def ankle_v3(qs, qf):
    shank_ml = rotate_vector_by_quaternion(AXIS_VECTORS['Y'], qs)
    shank_ml_horiz = shank_ml.copy()
    shank_ml_horiz[2] = 0
    n = np.linalg.norm(shank_ml_horiz)
    if n < 1e-6: return 0.0
    ml_dir = shank_ml_horiz / n
    
    shank_long = rotate_vector_by_quaternion(AXIS_VECTORS['X'], qs)
    foot_fwd = rotate_vector_by_quaternion(AXIS_VECTORS['X'], qf)
    
    shank_proj = shank_long - np.dot(shank_long, ml_dir) * ml_dir
    foot_proj = foot_fwd - np.dot(foot_fwd, ml_dir) * ml_dir
    
    ns, nf = np.linalg.norm(shank_proj), np.linalg.norm(foot_proj)
    if ns < 1e-6 or nf < 1e-6: return 0.0
    shank_proj /= ns; foot_proj /= nf
    
    dot = np.clip(np.dot(shank_proj, foot_proj), -1, 1)
    angle = np.degrees(np.arccos(dot))
    cross = np.cross(foot_proj, shank_proj)
    if np.dot(cross, ml_dir) < 0: angle = -angle
    return angle

cal = ankle_v3(qs_ref, qf_ref)
angles = [ankle_v3(normalize(rs[i, Q_START:Q_END]), normalize(rf[j, Q_START:Q_END])) - cal for i, j in matched]
angles = np.array(angles)

# Detailed phase analysis with more granularity
match_times = np.array([ts_s[m[0]] for m in matched]) - ts_s[matched[0][0]]
total_time = match_times[-1]

print(f"Total recording: {total_time:.0f}s, {len(matched)} matched pairs")
print(f"\nOverall: P5={np.percentile(angles,5):.1f}  P25={np.percentile(angles,25):.1f}  "
      f"P50={np.percentile(angles,50):.1f}  P75={np.percentile(angles,75):.1f}  P95={np.percentile(angles,95):.1f}")

# Check for outliers vs real data
outlier_mask = (angles > 50) | (angles < -50)
print(f"Samples > 50° or < -50°: {outlier_mask.sum()} ({100*outlier_mask.sum()/len(angles):.1f}%)")

# Print in 30-second windows
window = 30
t = 0
print(f"\n{'Time window':<20} {'Min':>8} {'P5':>8} {'Median':>8} {'P95':>8} {'Max':>8}")
while t < total_time:
    mask = (match_times >= t) & (match_times < t + window)
    if mask.sum() > 10:
        a = angles[mask]
        print(f"{f'{t:.0f}-{t+window:.0f}s':<20} {a.min():>8.1f} {np.percentile(a,5):>8.1f} {np.median(a):>8.1f} {np.percentile(a,95):>8.1f} {a.max():>8.1f}")
    t += window

