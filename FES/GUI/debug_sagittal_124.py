import pickle
import numpy as np
from scipy.spatial.transform import Rotation as R

with open("try6.pkl", "rb") as f:
    d = pickle.load(f)

def qnorm(q): return q / (np.linalg.norm(q, axis=-1, keepdims=True) + 1e-12)

def unwrap(ts):
    ts = ts.copy()
    diffs = np.diff(ts)
    for j in np.where(diffs < -1000.0)[0]: ts[j+1:] += 4294.967296
    return ts

t_sh = unwrap(d["raw_right_shank_timestamps"])
t_master = t_sh.copy()
t_rel = t_master - t_master[0]

def resample(q, ts, ts_target):
    idx = np.searchsorted(ts, ts_target)
    idx = np.clip(idx, 0, len(q)-1)
    return q[idx]

q_th_r = resample(qnorm(d["raw_right_thigh_quat"]), unwrap(d["raw_right_thigh_timestamps"]), t_master)
q_sh_r = qnorm(d["raw_right_shank_quat"])

# t=257 is the N-pose
idx_ref = np.argmin(np.abs(t_rel - 257))
q_th_ref = q_th_r[idx_ref:idx_ref+1]
q_sh_ref = q_sh_r[idx_ref:idx_ref+1]

def qconj(q): 
    o = q.copy(); o[..., 1:] = -o[..., 1:]; return o
def qmul(a, b):
    w1, x1, y1, z1 = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    w2, x2, y2, z2 = b[..., 0], b[..., 1], b[..., 2], b[..., 3]
    return np.stack([
        w1*w2 - x1*x2 - y1*y2 - z1*z2,
        w1*x2 + x1*w2 + y1*z2 - z1*y2,
        w1*y2 - x1*z2 + y1*w2 + z1*x2,
        w1*z2 + x1*y2 - y1*x2 + z1*w2
    ], axis=-1)

def signed_sagittal_series(q_prox, q_dist, q_prox_ref, q_dist_ref, ml_axis_prox):
    q_rel_now = qmul(qconj(q_prox), q_dist)
    q_rel_ref = qmul(qconj(q_prox_ref), q_dist_ref)
    q_delta   = qmul(q_rel_now, qconj(q_rel_ref))
    flip = q_delta[..., 0] < 0
    q_delta[flip] = -q_delta[flip]
    r = R.from_quat(np.stack([q_delta[..., 1], q_delta[..., 2], q_delta[..., 3], q_delta[..., 0]], axis=-1))
    eulers = r.as_euler('ZXY', degrees=True)
    return eulers[..., 0]

knee = signed_sagittal_series(q_th_r, q_sh_r, q_th_ref, q_sh_ref, 'Z')
# invert knee
knee = -knee

idx_start = np.argmin(np.abs(t_rel - 124.22))
idx_end = np.argmin(np.abs(t_rel - 125.32))

print(f"Knee range 124.2-125.3s: {np.min(knee[idx_start:idx_end]):.2f} to {np.max(knee[idx_start:idx_end]):.2f}")

# And what about 60s?
idx_start2 = np.argmin(np.abs(t_rel - 60))
idx_end2 = np.argmin(np.abs(t_rel - 61))
print(f"Knee range 60-61s: {np.min(knee[idx_start2:idx_end2]):.2f} to {np.max(knee[idx_start2:idx_end2]):.2f}")

