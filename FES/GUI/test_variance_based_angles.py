import pickle
import numpy as np
from scipy.spatial.transform import Rotation as R
import matplotlib.pyplot as plt

with open("try2.pkl", "rb") as f:
    d = pickle.load(f)

def qnorm(q):
    n = np.linalg.norm(q, axis=-1, keepdims=True)
    return q / (n + 1e-12)
def qconj(q):
    out = q.copy()
    out[..., 1:] = -out[..., 1:]
    return out
def qmul(a, b):
    w1, x1, y1, z1 = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    w2, x2, y2, z2 = b[..., 0], b[..., 1], b[..., 2], b[..., 3]
    return np.stack([
        w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
        w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
        w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
        w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
    ], axis=-1)
def to_scipy(q):
    return np.stack([q[..., 1], q[..., 2], q[..., 3], q[..., 0]], axis=-1)

q_th = qnorm(np.asarray(d["raw_right_thigh_quat"], dtype=np.float64))
q_sh = qnorm(np.asarray(d["raw_right_shank_quat"], dtype=np.float64))
q_ft = qnorm(np.asarray(d["raw_right_foot_quat"], dtype=np.float64))
q_pv = qnorm(np.asarray(d["raw_pelvis_quat"], dtype=np.float64))

t_th = np.asarray(d["raw_right_thigh_timestamps"], dtype=np.float64)
t_sh = np.asarray(d["raw_right_shank_timestamps"], dtype=np.float64)
t_ft = np.asarray(d["raw_right_foot_timestamps"], dtype=np.float64)
t_pv = np.asarray(d["raw_pelvis_timestamps"], dtype=np.float64)

def resample(q_in, ts_in, ts_target):
    if q_in.shape[0] == 0: return np.zeros((ts_target.size, 4))
    idx = np.searchsorted(ts_in, ts_target)
    idx = np.clip(idx, 0, q_in.shape[0] - 1)
    idx_prev = np.clip(idx - 1, 0, q_in.shape[0] - 1)
    use_prev = np.abs(ts_in[idx_prev] - ts_target) < np.abs(ts_in[idx] - ts_target)
    return q_in[np.where(use_prev, idx_prev, idx)]

t_master = t_sh.copy()
q_th_r = resample(q_th, t_th, t_master)
q_sh_r = resample(q_sh, t_sh, t_master)
q_ft_r = resample(q_ft, t_ft, t_master)
q_pv_r = resample(q_pv, t_pv, t_master)

def auto_ml_axis_variance(q_prox, q_dist, ref_slice):
    q_prox_ref = qnorm(np.expand_dims(q_prox[ref_slice].mean(axis=0), 0))
    q_dist_ref = qnorm(np.expand_dims(q_dist[ref_slice].mean(axis=0), 0))
    q_rel_now = qmul(qconj(q_prox), q_dist)
    q_rel_ref = qmul(qconj(q_prox_ref), q_dist_ref)
    q_delta = qmul(q_rel_now, qconj(q_rel_ref))
    flip = q_delta[..., 0] < 0
    q_delta[flip] = -q_delta[flip]
    var_xyz = np.var(q_delta[..., 1:], axis=0)
    return ['X', 'Y', 'Z'][np.argmax(var_xyz)]

def signed_sagittal_series(q_prox, q_dist, q_prox_ref, q_dist_ref, ml_axis_prox):
    q_rel_now = qmul(qconj(q_prox), q_dist)
    q_rel_ref = qmul(qconj(q_prox_ref), q_dist_ref)
    q_delta   = qmul(q_rel_now, qconj(q_rel_ref))
    flip = q_delta[..., 0] < 0
    q_delta[flip] = -q_delta[flip]
    r = R.from_quat(to_scipy(qnorm(q_delta)))
    order = {'X': 'XYZ', 'Y': 'YXZ', 'Z': 'ZXY'}[ml_axis_prox]
    eulers = r.as_euler(order, degrees=True)
    return eulers[..., 0]

ref = slice(1834, 1893)
ml_knee = auto_ml_axis_variance(q_th_r, q_sh_r, ref)
ml_ankle = auto_ml_axis_variance(q_sh_r, q_ft_r, ref)
ml_hip = auto_ml_axis_variance(q_pv_r, q_th_r, ref)

q_th_ref = qnorm(q_th_r[ref].mean(axis=0))
q_sh_ref = qnorm(q_sh_r[ref].mean(axis=0))
q_ft_ref = qnorm(q_ft_r[ref].mean(axis=0))
q_pv_ref = qnorm(q_pv_r[ref].mean(axis=0))

knee = signed_sagittal_series(q_th_r, q_sh_r, q_th_ref, q_sh_ref, ml_knee)
ankle = signed_sagittal_series(q_sh_r, q_ft_r, q_sh_ref, q_ft_ref, ml_ankle)
hip = signed_sagittal_series(q_pv_r, q_th_r, q_pv_ref, q_th_ref, ml_hip)

# Fix signs based on expected anatomy
if np.abs(np.min(knee)) > np.max(knee): knee = -knee
if np.abs(np.min(hip)) > np.max(hip): hip = -hip

print("Knee Range:", np.min(knee), np.max(knee))
print("Ankle Range:", np.min(ankle), np.max(ankle))
print("Hip Range:", np.min(hip), np.max(hip))

