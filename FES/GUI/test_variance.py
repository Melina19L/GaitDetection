import pickle
import numpy as np
import sys
from scipy.spatial.transform import Rotation as R

with open("try3.pkl", "rb") as f:
    d = pickle.load(f)

# we just want to see the variances of the Euler angles for delta
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

q_th_ref = q_th[1834:1893].mean(axis=0)
q_sh_ref = q_sh[1834:1893].mean(axis=0)
q_ft_ref = q_ft[1834:1893].mean(axis=0)
q_th_ref = qnorm(np.expand_dims(q_th_ref, 0))
q_sh_ref = qnorm(np.expand_dims(q_sh_ref, 0))
q_ft_ref = qnorm(np.expand_dims(q_ft_ref, 0))

# knee
min_len = min(len(q_th), len(q_sh))
q_rel_now = qmul(qconj(q_th[:min_len]), q_sh[:min_len])
q_rel_ref = qmul(qconj(q_th_ref), q_sh_ref)
q_delta = qmul(q_rel_now, qconj(q_rel_ref))

flip = q_delta[..., 0] < 0
q_delta[flip] = -q_delta[flip]

r = R.from_quat(to_scipy(qnorm(q_delta)))
eulers = r.as_euler('XYZ', degrees=True)

print("Knee XYZ variances:", np.var(eulers, axis=0))
print("Knee XYZ ranges:", np.ptp(eulers, axis=0))

# ankle
min_len = min(len(q_sh), len(q_ft))
q_rel_now = qmul(qconj(q_sh[:min_len]), q_ft[:min_len])
q_rel_ref = qmul(qconj(q_sh_ref), q_ft_ref)
q_delta = qmul(q_rel_now, qconj(q_rel_ref))

flip = q_delta[..., 0] < 0
q_delta[flip] = -q_delta[flip]

r = R.from_quat(to_scipy(qnorm(q_delta)))
eulers = r.as_euler('XYZ', degrees=True)

print("Ankle XYZ variances:", np.var(eulers, axis=0))
print("Ankle XYZ ranges:", np.ptp(eulers, axis=0))

