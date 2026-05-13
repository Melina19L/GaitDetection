import pickle
import numpy as np

with open("try6.pkl", "rb") as f:
    d = pickle.load(f)

knee_gui = np.asarray(d["right_knee_angles"])
print(f"GUI Knee stats: min={np.nanmin(knee_gui)}, max={np.nanmax(knee_gui)}, mean={np.nanmean(knee_gui)}")

