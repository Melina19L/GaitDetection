import pickle
import numpy as np

with open("try6.pkl", "rb") as f:
    d = pickle.load(f)

def qnorm(q): return q / (np.linalg.norm(q, axis=-1, keepdims=True) + 1e-12)
def rotate_vector_by_quaternion(v, q):
    u = q[..., 1:4]
    s = q[..., 0:1]
    uv = np.cross(u, v)
    uuv = np.cross(u, uv)
    return v + 2.0 * (s * uv + uuv)

q_th = qnorm(d["raw_right_thigh_quat"])
q_sh = qnorm(d["raw_right_shank_quat"])

def unwrap(ts):
    ts = ts.copy()
    diffs = np.diff(ts)
    for j in np.where(diffs < -1000.0)[0]: ts[j+1:] += 4294.967296
    return ts

t_th = unwrap(d["raw_right_thigh_timestamps"])
t_sh = unwrap(d["raw_right_shank_timestamps"])

def resample(q, ts, ts_target):
    idx = np.searchsorted(ts, ts_target)
    idx = np.clip(idx, 0, len(q)-1)
    return q[idx]

t_master = t_sh.copy()
t_rel = t_master - t_master[0]

q_th_r = resample(q_th, t_th, t_master)
q_sh_r = q_sh

v_th_r = rotate_vector_by_quaternion([1,0,0], q_th_r)
v_sh_r = rotate_vector_by_quaternion([1,0,0], q_sh_r)

dot_knee = np.sum(v_th_r * v_sh_r, axis=-1)
saa_knee = np.degrees(np.arccos(np.clip(dot_knee, -1, 1)))

idx_start = np.argmin(np.abs(t_rel - 123.7))
idx_end = np.argmin(np.abs(t_rel - 124.8))

print(f"Cycle 123.7-124.8s SAA MAX: {np.max(saa_knee[idx_start:idx_end]):.2f}")

