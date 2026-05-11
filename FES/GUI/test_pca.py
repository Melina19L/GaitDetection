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

def get_ml_axis_from_qdelta(q_prox, q_dist, ref_slice):
    q_prox_ref = qnorm(np.expand_dims(q_prox[ref_slice].mean(axis=0), 0))
    q_dist_ref = qnorm(np.expand_dims(q_dist[ref_slice].mean(axis=0), 0))
    
    min_len = min(len(q_prox), len(q_dist))
    q_rel_now = qmul(qconj(q_prox[:min_len]), q_dist[:min_len])
    q_rel_ref = qmul(qconj(q_prox_ref), q_dist_ref)
    
    q_delta = qmul(q_rel_now, qconj(q_rel_ref))
    flip = q_delta[..., 0] < 0
    q_delta[flip] = -q_delta[flip]
    
    # Variance of x, y, z components
    var_xyz = np.var(q_delta[..., 1:], axis=0)
    print("Variance of x, y, z:", var_xyz)
    idx = np.argmax(var_xyz)
    return ['X', 'Y', 'Z'][idx]

ref = slice(1834, 1893)
print("Knee ML:", get_ml_axis_from_qdelta(q_th, q_sh, ref))
print("Ankle ML:", get_ml_axis_from_qdelta(q_sh, q_ft, ref))
print("Hip ML:", get_ml_axis_from_qdelta(q_pv, q_th, ref))

