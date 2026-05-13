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
q_pv = qnorm(d["raw_pelvis_quat"])

v_th = rotate_vector_by_quaternion([1,0,0], q_th)
v_sh = rotate_vector_by_quaternion([1,0,0], q_sh)
v_pv = rotate_vector_by_quaternion([1,0,0], q_pv)

# Make sure they are aligned in time before dot product!
# We can just interpolate them to the master clock.
def unwrap(ts):
    ts = ts.copy()
    diffs = np.diff(ts)
    for j in np.where(diffs < -1000.0)[0]: ts[j+1:] += 4294.967296
    return ts

t_th = unwrap(d["raw_right_thigh_timestamps"])
t_sh = unwrap(d["raw_right_shank_timestamps"])
t_pv = unwrap(d["raw_pelvis_timestamps"])

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

target_knee = d.get("right_knee_offset", 4.53)
target_hip = d.get("right_hip_offset", 22.87)

# We want the moment where BOTH are close to target
diff = np.abs(saa_knee - target_knee) + np.abs(saa_hip - target_hip)
best_idx = np.argmin(diff)

print(f"Calibrate moment is at idx {best_idx}, t={t_master[best_idx] - t_master[0]:.2f}s")
print(f"SAA Knee there: {saa_knee[best_idx]:.2f}")
print(f"SAA Hip there: {saa_hip[best_idx]:.2f}")

