import pickle
import numpy as np

with open("try4.pkl", "rb") as f:
    d = pickle.load(f)

# Find the global maximum timestamp before any unwrapping
max_ts = 0
for k, v in d.items():
    if "timestamps" in k and len(v) > 0:
        max_ts = max(max_ts, np.max(v))
print("Global max ts:", max_ts)

def unwrap_timestamps_v2(ts, global_max):
    ts = ts.copy()
    # If the stream starts low but the session had high timestamps,
    # it means this entire stream started after the wrap-around.
    if len(ts) > 0 and ts[0] < 1000 and global_max > 4000:
        ts += 4294.967296
        
    diffs = np.diff(ts)
    jumps = np.where(diffs < -1000.0)[0]
    for j in jumps:
        ts[j+1:] += 4294.967296
    return ts

t_sh = unwrap_timestamps_v2(np.asarray(d["raw_right_shank_timestamps"], dtype=np.float64), max_ts)
knee_tpkl = unwrap_timestamps_v2(np.asarray(d["right_knee_timestamps"], dtype=np.float64), max_ts)

print("t_sh:", t_sh.min(), t_sh.max())
print("knee_tpkl:", knee_tpkl.min(), knee_tpkl.max())

