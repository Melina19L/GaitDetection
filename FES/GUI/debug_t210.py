import pickle
import numpy as np

with open("try6.pkl", "rb") as f:
    d = pickle.load(f)

def unwrap(ts):
    ts = ts.copy()
    diffs = np.diff(ts)
    jumps = np.where(diffs < -1000.0)[0]
    for j in jumps:
        ts[j+1:] += 4294.967296
    return ts

t_sh = unwrap(np.asarray(d["raw_right_shank_timestamps"]))
t0 = t_sh[0]

knee_pkl = np.asarray(d["right_knee_angles"])
knee_tpkl = unwrap(np.asarray(d["right_knee_timestamps"]))

# Find GUI angle at t=210
target_t = t0 + 210
idx = np.argmin(np.abs(knee_tpkl - target_t))
print(f"GUI Knee angle near t=210 (actual t={knee_tpkl[idx] - t0}): {knee_pkl[idx]}")

# Find GUI angle at t=10
idx = np.argmin(np.abs(knee_tpkl - (t0 + 10)))
print(f"GUI Knee angle near t=10 (actual t={knee_tpkl[idx] - t0}): {knee_pkl[idx]}")

# Find GUI angle at t=120
idx = np.argmin(np.abs(knee_tpkl - (t0 + 120)))
print(f"GUI Knee angle near t=120 (actual t={knee_tpkl[idx] - t0}): {knee_pkl[idx]}")

