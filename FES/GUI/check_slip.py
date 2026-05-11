import pickle
import numpy as np

with open("try6.pkl", "rb") as f:
    d = pickle.load(f)

def qnorm(q): return q / (np.linalg.norm(q, axis=-1, keepdims=True) + 1e-12)
def qconj(q): 
    o = q.copy()
    o[..., 1:] = -o[..., 1:]
    return o
def qmul(a, b):
    w1, x1, y1, z1 = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    w2, x2, y2, z2 = b[..., 0], b[..., 1], b[..., 2], b[..., 3]
    return np.stack([
        w1*w2 - x1*x2 - y1*y2 - z1*z2,
        w1*x2 + x1*w2 + y1*z2 - z1*y2,
        w1*y2 - x1*z2 + y1*w2 + z1*x2,
        w1*z2 + x1*y2 - y1*x2 + z1*w2
    ], axis=-1)

def unwrap(ts):
    ts = ts.copy()
    diffs = np.diff(ts)
    for j in np.where(diffs < -1000.0)[0]: ts[j+1:] += 4294.967296
    return ts

t_th = unwrap(d["raw_right_thigh_timestamps"])
t_sh = unwrap(d["raw_right_shank_timestamps"])

q_th = qnorm(d["raw_right_thigh_quat"])
q_sh = qnorm(d["raw_right_shank_quat"])

# Let's resample
def resample(q, ts, ts_target):
    idx = np.searchsorted(ts, ts_target)
    idx = np.clip(idx, 0, len(q)-1)
    return q[idx]

t_master = t_sh.copy()
t_rel = t_master - t_master[0]
q_th_r = resample(q_th, t_th, t_master)
q_sh_r = q_sh

def get_angle(t_start):
    idx = np.searchsorted(t_rel, t_start)
    # average 1 second
    qt = qnorm(np.mean(q_th_r[idx:idx+60], axis=0, keepdims=True))
    qs = qnorm(np.mean(q_sh_r[idx:idx+60], axis=0, keepdims=True))
    return qmul(qconj(qt), qs)

# Angle at t=0 (standing still before walking)
# Angle at t=210 (standing still after walking)
q_rel_0 = get_angle(0)
q_rel_210 = get_angle(210)

diff = qmul(q_rel_0, qconj(q_rel_210))
flip = diff[..., 0] < 0
diff[flip] = -diff[flip]

import scipy.spatial.transform as transform
r = transform.Rotation.from_quat(np.roll(diff[0], -1))
print("Euler diff (XYZ):", r.as_euler('XYZ', degrees=True))

