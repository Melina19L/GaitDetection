import pickle
import numpy as np

with open("try4.pkl", "rb") as f:
    d = pickle.load(f)

for sensor in ["thigh", "shank", "foot"]:
    ts = np.asarray(d[f"raw_right_{sensor}_timestamps"], dtype=np.float64)
    print(f"--- {sensor} ---")
    print(f"Length: {len(ts)}")
    print(f"First 5: {ts[:5]}")
    print(f"Last 5: {ts[-5:]}")
    diffs = np.diff(ts)
    print(f"Min diff: {diffs.min()}")
    print(f"Max diff: {diffs.max()}")
    
    # Check for negative jumps
    jumps = np.where(diffs < 0)[0]
    if len(jumps) > 0:
        print(f"NEGATIVE JUMPS FOUND at indices: {jumps[:5]}")
        for j in jumps[:5]:
            print(f"  Jump at {j}: {ts[j]} -> {ts[j+1]} (diff: {diffs[j]})")

ts = np.asarray(d["raw_pelvis_timestamps"], dtype=np.float64)
print(f"--- pelvis ---")
print(f"Length: {len(ts)}")
diffs = np.diff(ts)
jumps = np.where(diffs < 0)[0]
if len(jumps) > 0:
    print(f"NEGATIVE JUMPS FOUND at indices: {jumps[:5]}")
    for j in jumps[:5]:
        print(f"  Jump at {j}: {ts[j]} -> {ts[j+1]} (diff: {diffs[j]})")

