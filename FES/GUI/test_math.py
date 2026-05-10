import numpy as np
from scipy.spatial.transform import Rotation as R

def quat_conjugate(q):
    return np.array([q[0], -q[1], -q[2], -q[3]])

def quat_mul(q1, q2):
    w1, x1, y1, z1 = q1
    w2, x2, y2, z2 = q2
    return np.array([
        w1*w2 - x1*x2 - y1*y2 - z1*z2,
        w1*x2 + x1*w2 + y1*z2 - z1*y2,
        w1*y2 - x1*z2 + y1*w2 + z1*x2,
        w1*z2 + x1*y2 - y1*x2 + z1*w2
    ])

def twist_angle_around_axis(q: np.ndarray, axis: np.ndarray) -> float:
    axis = np.asarray(axis, dtype=float)
    axis = axis / np.linalg.norm(axis)
    proj = float(np.dot(q[1:], axis))
    twist_v = proj * axis
    tw = np.array([q[0], twist_v[0], twist_v[1], twist_v[2]], dtype=float)
    tw = tw / np.linalg.norm(tw)
    angle = 2.0 * float(np.arctan2(np.linalg.norm(tw[1:]), tw[0]))
    if proj < 0:
        angle = -angle
    return angle

def extract_joint_angle_with_axis(q_prox, q_dist, q_prox_ref, q_dist_ref, hinge_axis):
    q_rel_ref = quat_mul(quat_conjugate(q_prox_ref), q_dist_ref)
    q_rel     = quat_mul(quat_conjugate(q_prox), q_dist)
    q_delta   = quat_mul(quat_conjugate(q_rel_ref), q_rel)
    if q_delta[0] < 0:
        q_delta = -q_delta
    angle_rad = twist_angle_around_axis(q_delta, hinge_axis)
    return float(np.degrees(angle_rad))

# Simulate a static ankle while the knee bends.
# Frame definitions:
# Thigh: identity
# Shank: identity at ref
# Foot: identity at ref

q_thigh_ref = np.array([1, 0, 0, 0])
q_shank_ref = np.array([1, 0, 0, 0])
q_foot_ref = np.array([1, 0, 0, 0])

# Hinge axis for ankle (say, Y axis)
ankle_hinge_axis = np.array([0, 1.0, 0])

# Move knee by 60 degrees around Y axis
knee_rot = R.from_euler('y', 60, degrees=True).as_quat() # x, y, z, w
knee_rot_w_first = np.array([knee_rot[3], knee_rot[0], knee_rot[1], knee_rot[2]])

# Ankle is RIGID. Therefore foot moves EXACTLY with the shank globally.
q_shank = knee_rot_w_first
q_foot = knee_rot_w_first

# Calculate ankle angle
angle = extract_joint_angle_with_axis(q_shank, q_foot, q_shank_ref, q_foot_ref, ankle_hinge_axis)
print("Ankle angle when knee bends 60 deg, ankle rigid:", angle)

# Now, let's say the user bent their ankle by 15 deg.
ankle_rot = R.from_euler('y', 15, degrees=True).as_quat()
ankle_rot_w_first = np.array([ankle_rot[3], ankle_rot[0], ankle_rot[1], ankle_rot[2]])

q_foot_flexed = quat_mul(q_shank, ankle_rot_w_first)
angle_flexed = extract_joint_angle_with_axis(q_shank, q_foot_flexed, q_shank_ref, q_foot_ref, ankle_hinge_axis)
print("Ankle angle when knee bends 60 deg, ankle flexed 15 deg:", angle_flexed)

# Is there any crosstalk from knee moving on a DIFFERENT axis?
knee_rot_x = R.from_euler('x', 60, degrees=True).as_quat()
knee_rot_x_w_first = np.array([knee_rot_x[3], knee_rot_x[0], knee_rot_x[1], knee_rot_x[2]])

q_shank_x = knee_rot_x_w_first
q_foot_x = quat_mul(q_shank_x, ankle_rot_w_first)
angle_x = extract_joint_angle_with_axis(q_shank_x, q_foot_x, q_shank_ref, q_foot_ref, ankle_hinge_axis)
print("Ankle angle when knee bends 60 deg on X, ankle flexed 15 deg on Y:", angle_x)
