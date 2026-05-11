import pickle
import numpy as np

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
def qrotate_vec(q, v):
    qv = np.array([0.0, v[0], v[1], v[2]])
    return qmul(qmul(q, qv), qconj(q))[1:]

AXIS_VEC = {'X': np.array([1.0, 0.0, 0.0]),
            'Y': np.array([0.0, 1.0, 0.0]),
            'Z': np.array([0.0, 0.0, 1.0])}

def print_axis_alignment(q_static, name):
    print(f"--- {name} ---")
    for axis, v in AXIS_VEC.items():
        gv = qrotate_vec(q_static, v)
        print(f"Axis {axis} -> World {gv}")

with open("try3.pkl", "rb") as f:
    d = pickle.load(f)

q_th = qnorm(np.asarray(d["raw_right_thigh_quat"], dtype=np.float64))
q_sh = qnorm(np.asarray(d["raw_right_shank_quat"], dtype=np.float64))
q_ft = qnorm(np.asarray(d["raw_right_foot_quat"], dtype=np.float64))

q_th_ref = qnorm(np.expand_dims(q_th[1834:1893].mean(axis=0), 0))[0]
q_sh_ref = qnorm(np.expand_dims(q_sh[1834:1893].mean(axis=0), 0))[0]
q_ft_ref = qnorm(np.expand_dims(q_ft[1834:1893].mean(axis=0), 0))[0]

print_axis_alignment(q_th_ref, "Thigh")
print_axis_alignment(q_sh_ref, "Shank")
print_axis_alignment(q_ft_ref, "Foot")

