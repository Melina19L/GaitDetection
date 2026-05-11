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

# Angle between X axes at t=0.5s (sample 30)
v_th = rotate_vector_by_quaternion([1,0,0], q_th[30])
v_sh = rotate_vector_by_quaternion([1,0,0], q_sh[30])
v_pv = rotate_vector_by_quaternion([1,0,0], q_pv[30])

dot_knee = np.dot(v_th, v_sh)
dot_hip = np.dot(v_pv, v_th)

print("SAA Knee at t=0.5s:", np.degrees(np.arccos(np.clip(dot_knee, -1, 1))))
print("SAA Hip at t=0.5s:", np.degrees(np.arccos(np.clip(dot_hip, -1, 1))))

