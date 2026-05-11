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

def get_pca_angle(q_prox, q_dist, ref_slice, name):
    q_prox_ref = qnorm(np.expand_dims(q_prox[ref_slice].mean(axis=0), 0))
    q_dist_ref = qnorm(np.expand_dims(q_dist[ref_slice].mean(axis=0), 0))
    
    min_len = min(len(q_prox), len(q_dist))
    q_rel_now = qmul(qconj(q_prox[:min_len]), q_dist[:min_len])
    q_rel_ref = qmul(qconj(q_prox_ref), q_dist_ref)
    
    q_delta = qmul(q_rel_now, qconj(q_rel_ref))
    flip = q_delta[..., 0] < 0
    q_delta[flip] = -q_delta[flip]
    
    A = q_delta[..., 1:]
    u, s, vh = np.linalg.svd(A, full_matrices=False)
    v_ML = vh[0]  # principal component
    
    # Check if v_ML aligns with +Z or +Y or +X to define a standard positive sign
    # e.g., if v_ML has negative Z, flip it
    max_idx = np.argmax(np.abs(v_ML))
    if v_ML[max_idx] < 0:
        v_ML = -v_ML

    proj = np.dot(A, v_ML)
    angles = 2 * np.arctan2(proj, q_delta[..., 0]) * 180 / np.pi
    
    print(f"{name} PCA ML axis: {v_ML}")
    print(f"{name} Angle range: {angles.min():.1f} to {angles.max():.1f}")
    return angles

ref = slice(1834, 1893)
knee_angles = get_pca_angle(q_th, q_sh, ref, "Knee")
ankle_angles = get_pca_angle(q_sh, q_ft, ref, "Ankle")
hip_angles = get_pca_angle(q_pv, q_th, ref, "Hip")

