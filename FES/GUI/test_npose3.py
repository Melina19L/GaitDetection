import pickle
import numpy as np

with open("try4.pkl", "rb") as f:
    d = pickle.load(f)

def unwrap_timestamps(ts):
    ts = ts.copy()
    diffs = np.diff(ts)
    jumps = np.where(diffs < -1000.0)[0]
    for j in jumps:
        ts[j+1:] += 4294.967296
    return ts

t_sh = unwrap_timestamps(np.asarray(d["raw_right_shank_timestamps"], dtype=np.float64))

knee_pkl = np.asarray(d["right_knee_angles"], dtype=np.float64)
knee_tpkl = unwrap_timestamps(np.asarray(d["right_knee_timestamps"], dtype=np.float64))

print("t_sh min/max:", t_sh.min(), t_sh.max())
print("knee_tpkl min/max:", knee_tpkl.min(), knee_tpkl.max())

