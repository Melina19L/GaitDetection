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
t_ft = unwrap(d["raw_right_foot_timestamps"])
t_pv = unwrap(d["raw_pelvis_timestamps"])

def check_diff(name, ts1, ts2):
    min_len = min(len(ts1), len(ts2))
    diff = ts1[:min_len] - ts2[:min_len]
    print(f"{name}: Min: {np.min(diff):.2f}, Max: {np.max(diff):.2f}, Mean: {np.mean(diff):.2f}")

check_diff("Knee (Thigh-Shank)", t_th, t_sh)
check_diff("Ankle (Shank-Foot)", t_sh, t_ft)
check_diff("Hip (Pelvis-Thigh)", t_pv, t_th)

