import numpy as np
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'FES', 'GUI'))

from stimulator.lower_limb_kinematics import calibrate_segment, calculate_kinematics, get_segment_orientation, calc_sagittal_angle

def test_integration():
    print("Testing calibrate_segment...")
    acc_static = np.random.rand(50, 3)
    gyro_dynamic = np.random.rand(100, 3)
    q_static = np.random.rand(50, 4)
    # normalize quaternions
    q_static /= np.linalg.norm(q_static, axis=1, keepdims=True)
    
    q_g, q_PCA, q_0_inv = calibrate_segment(acc_static, gyro_dynamic, q_static)
    print(f"q_g: {q_g}")
    print(f"q_PCA: {q_PCA}")
    print(f"q_0_inv: {q_0_inv}")
    
    print("Testing real-time angle computation...")
    # Simulate one sample
    q_prox = np.array([1.0, 0.0, 0.0, 0.0])
    q_dist = np.array([0.9659, 0.2588, 0.0, 0.0]) # ~30 deg around X
    
    q_pv = get_segment_orientation(q_prox, q_g, q_PCA, q_0_inv)
    q_dist_seg = get_segment_orientation(q_dist, q_g, q_PCA, q_0_inv)
    
    q_joint = q_pv.conjugate() * q_dist_seg
    angle = calc_sagittal_angle(q_joint)
    print(f"Computed angle: {angle:.2f} degrees")
    print("All tests passed successfully!")

if __name__ == '__main__':
    test_integration()
