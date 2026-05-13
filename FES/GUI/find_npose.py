import pickle
import numpy as np

with open("try4.pkl", "rb") as f:
    d = pickle.load(f)

knee_pkl = np.asarray(d["right_knee_angles"], dtype=np.float64)
ank_pkl = np.asarray(d["right_ankle_angles"], dtype=np.float64)
hip_pkl = np.asarray(d["right_hip_angles"], dtype=np.float64)

# Print min max
print("Knee min max:", np.nanmin(knee_pkl), np.nanmax(knee_pkl))
print("Ankle min max:", np.nanmin(ank_pkl), np.nanmax(ank_pkl))
print("Hip min max:", np.nanmin(hip_pkl), np.nanmax(hip_pkl))

