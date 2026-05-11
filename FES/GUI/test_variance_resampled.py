import pickle
import numpy as np

with open("try3.pkl", "rb") as f:
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

q_th = qnorm(np.asarray(d["raw_right_thigh_quat"], dtype=np.float64))
q_sh = qnorm(np.asarray(d["raw_right_shank_quat"], dtype=np.float64))
q_ft = qnorm(np.asarray(d["raw_right_foot_quat"], dtype=np.float64))
q_pv = qnorm(np.asarray(d["raw_pelvis_quat"], dtype=np.float64))

t_th = np.asarray(d["raw_right_thigh_timestamps"], dtype=np.float64)
t_sh = np.asarray(d["raw_right_shank_timestamps"], dtype=np.float64)
t_ft = np.asarray(d["raw_right_foot_timestamps"], dtype=np.float64)
t_pv = np.asarray(d["raw_pelvis_timestamps"], dtype=np.float64)

def resample(q_in, ts_in, ts_target):
    idx = np.searchsorted(ts_in, ts_target)
    idx = np.clip(idx, 0, q_in.shape[0] - 1)
    idx_prev = np.clip(idx - 1, 0, q_in.shape[0] - 1)
    use_prev = np.abs(ts_in[idx_prev] - ts_target) < np.abs(ts_in[idx] - ts_target)
    chosen = np.where(use_prev, idx_prev, idx)
    return q_in[chosen]

t_master = t_sh.copy()
q_th_r = resample(q_th, t_th, t_master)
q_sh_r = resample(q_sh, t_sh, t_master)
q_ft_r = resample(q_ft, t_ft, t_master)
q_pv_r = resample(q_pv, t_pv, t_master)

def get_ml_axis(q_prox, q_dist, ref_slice, name):
    q_prox_ref = qnorm(np.expand_dims(q_prox[ref_slice].mean(axis=0), 0))
    q_dist_ref = qnorm(np.expand_dims(q_dist[ref_slice].mean(axis=0), 0))
    
    q_rel_now = qmul(qconj(q_prox), q_dist)
    q_rel_ref = qmul(qconj(q_prox_ref), q_dist_ref)
    
    q_delta = qmul(q_rel_now, qconj(q_rel_ref))
    flip = q_delta[..., 0] < 0
    q_delta[flip] = -q_delta[flip]
    
    var_xyz = np.var(q_delta[..., 1:], axis=0)
    print(f"{name} XYZ variances:", var_xyz)
    idx = np.argmax(var_xyz)
    ml_axis = ['X', 'Y', 'Z'][idx]
    print(f" -> ML axis: {ml_axis}")
    return ml_axis

ref = slice(1834, 1893)
get_ml_axis(q_th_r, q_sh_r, ref, "Knee")
get_ml_axis(q_sh_r, q_ft_r, ref, "Ankle")
get_ml_axis(q_pv_r, q_th_r, ref, "Hip")

