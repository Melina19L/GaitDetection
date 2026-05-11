import pickle
import numpy as np

with open("try4.pkl", "rb") as f:
    d = pickle.load(f)

knee_pkl = np.asarray(d["right_knee_angles"], dtype=np.float64)
ank_pkl = np.asarray(d["right_ankle_angles"], dtype=np.float64)
hip_pkl = np.asarray(d["right_hip_angles"], dtype=np.float64)

for i in range(len(knee_pkl)):
    if abs(knee_pkl[i]) < 5 and abs(ank_pkl[i]) < 5 and abs(hip_pkl[i]) < 7:
        print(f"Found match at index {i}")
        break

