import pickle
import numpy as np

with open("try4.pkl", "rb") as f:
    d = pickle.load(f)

for k in d.keys():
    if "timestamps" in k:
        arr = d[k]
        if len(arr) > 0:
            print(f"{k}: len={len(arr)}, min={np.min(arr):.2f}, max={np.max(arr):.2f}")
        else:
            print(f"{k}: len=0")

