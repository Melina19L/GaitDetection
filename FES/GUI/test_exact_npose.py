import pickle
import numpy as np
from scipy.spatial.transform import Rotation as R

with open("try6.pkl", "rb") as f:
    d = pickle.load(f)

def qnorm(q): return q / (np.linalg.norm(q, axis=-1, keepdims=True) + 1e-12)
def rotate_vector_by_quaternion(v, q):
    u = q[..., 1:4]
    s = q[..., 0:1]
    uv = np.cross(u, v)
    uuv = np.cross(u, uv)
    return v + 2.0 * (s * uv + uuv)

def unwrap(ts):
    ts = ts.copy()
    diffs = np.diff(ts)
    for j in np.where(diffs < -1000.0)[0]: ts[j+1:] += 4294.967296
    return ts

t_th = unwrap(d["raw_right_thigh_timestamps"])
t_sh = unwrap(d["raw_right_shank_timestamps"])
t_pv = unwrap(d["raw_pelvis_timestamps"])

q_th = qnorm(d["raw_right_thigh_quat"])
q_sh = qnorm(d["raw_right_shank_quat"])
q_pv = qnorm(d["raw_pelvis_quat"])

def resample(q, ts, ts_target):
    idx = np.searchsorted(ts, ts_target)
    idx = np.clip(idx, 0, len(q)-1)
    return q[idx]

t_master = t_sh.copy()
q_th_r = resample(q_th, t_th, t_master)
q_sh_r = q_sh
q_pv_r = resample(q_pv, t_pv, t_master)

v_th_r = rotate_vector_by_quaternion([1,0,0], q_th_r)
v_sh_r = rotate_vector_by_quaternion([1,0,0], q_sh_r)
v_pv_r = rotate_vector_by_quaternion([1,0,0], q_pv_r)

dot_knee = np.sum(v_th_r * v_sh_r, axis=-1)
dot_hip = np.sum(v_pv_r * v_th_r, axis=-1)

saa_knee = np.degrees(np.arccos(np.clip(dot_knee, -1, 1)))
saa_hip = np.degrees(np.arccos(np.clip(dot_hip, -1, 1)))

target_knee = d.get("right_knee_offset", 0.0)
target_hip = d.get("right_hip_offset", 0.0)

# We want the moment where BOTH are close to target
diff = np.abs(saa_knee - target_knee) + np.abs(saa_hip - target_hip)
best_idx = np.argmin(diff)
ref_start = best_idx
ref_end = best_idx + 1

q_th_ref = q_th_r[ref_start:ref_end]
q_sh_ref = q_sh_r[ref_start:ref_end]
q_pv_ref = q_pv_r[ref_start:ref_end]
q_ft_ref = resample(qnorm(d["raw_right_foot_quat"]), unwrap(d["raw_right_foot_timestamps"]), t_master)[ref_start:ref_end]

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
    order = {'X': 'XYZ', 'Y': 'YXZ', 'Z': 'ZXY'}[ml_axis_prox]
    eulers = r.as_euler(order, degrees=True)
    return eulers[..., 0]

knee = signed_sagittal_series(q_th_r, q_sh_r, q_th_ref, q_sh_ref, 'Z')
hip = signed_sagittal_series(q_pv_r, q_th_r, q_pv_ref, q_th_ref, 'Y')

print("Knee range:", np.min(knee), np.max(knee))
print("Hip range:", np.min(hip), np.max(hip))

