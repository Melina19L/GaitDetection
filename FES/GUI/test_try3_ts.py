import pickle
import numpy as np

with open("try3.pkl", "rb") as f:
    d = pickle.load(f)

t_sh = np.asarray(d["raw_right_shank_timestamps"], dtype=np.float64)
knee_tpkl = np.asarray(d["right_knee_timestamps"], dtype=np.float64)

print("try3 t_sh min/max:", t_sh.min(), t_sh.max())
print("try3 knee_tpkl min/max:", knee_tpkl.min(), knee_tpkl.max())

