import pickle
import numpy as np
from scipy.spatial.transform import Rotation as R

with open("try6.pkl", "rb") as f:
    d = pickle.load(f)

q_th = np.asarray(d["raw_right_thigh_quat"], dtype=np.float64)

def qrotate_vec(q, v):
    u = q[..., 1:4]
    s = q[..., 0:1]
    uv = np.cross(u, v)
    uuv = np.cross(u, uv)
    return v + 2.0 * (s * uv + uuv)

# Find the longitudinal axis of the thigh
# Assuming the user walked, the longitudinal axis is the one that stays most vertical during the whole session?
# Or we just check all X, Y, Z and see which one is most vertical during the low variance windows.

window_len = 60
variances = []
verticalities = []
for i in range(0, len(q_th) - window_len, 10):
    q_window = q_th[i:i+window_len]
    var = np.sum(np.var(q_window, axis=0))
    q_avg = q_window.mean(axis=0)
    q_avg /= np.linalg.norm(q_avg)
    
    # Test X, Y, Z verticality
    vx = abs(qrotate_vec(q_avg, [1,0,0])[2])
    vy = abs(qrotate_vec(q_avg, [0,1,0])[2])
    vz = abs(qrotate_vec(q_avg, [0,0,1])[2])
    max_vert = max(vx, vy, vz)
    
    variances.append(var)
    verticalities.append(max_vert)

variances = np.array(variances)
verticalities = np.array(verticalities)

# We want variance < threshold AND verticality near 1.0 (e.g. > 0.8)
standing_mask = verticalities > 0.8
if np.any(standing_mask):
    idx = np.argmin(variances[standing_mask])
    best_i = np.where(standing_mask)[0][idx] * 10
    print(f"Standing N-pose at {best_i} to {best_i+60}, variance = {variances[standing_mask][idx]}, verticality = {verticalities[standing_mask][idx]}")
else:
    print("No standing pose found!")

