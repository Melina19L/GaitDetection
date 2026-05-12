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

print(f"Thigh duration: {t_th[-1] - t_th[0]:.2f}s (len={len(t_th)})")
print(f"Shank duration: {t_sh[-1] - t_sh[0]:.2f}s (len={len(t_sh)})")

