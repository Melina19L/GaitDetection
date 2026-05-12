import pickle
import numpy as np

with open("try7.pkl", "rb") as f:
    d = pickle.load(f)

def unwrap(ts):
    ts = ts.copy()
    diffs = np.diff(ts)
    for j in np.where(diffs < -1000.0)[0]: ts[j+1:] += 4294.967296
    return ts

t_th = unwrap(d["raw_right_thigh_timestamps"])
t_sh = unwrap(d["raw_right_shank_timestamps"])

# Let's align them by index and see the difference in timestamps
min_len = min(len(t_th), len(t_sh))

# Time difference between the first samples
t0_th = t_th[0]
t0_sh = t_sh[0]
print(f"Thigh starts at {t0_th}")
print(f"Shank starts at {t0_sh}")
print(f"Initial offset: {t0_th - t0_sh}")

diff = t_th[:min_len] - t_sh[:min_len]
print(f"Timestamp difference stats for matched indices:")
print(f"Min: {np.min(diff)}, Max: {np.max(diff)}, Mean: {np.mean(diff)}")

