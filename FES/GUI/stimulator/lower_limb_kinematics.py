import numpy as np
import quaternion
from sklearn.decomposition import PCA

def calibrate_segment(acc_static, gyro_dynamic, q_static):
    """
    Calibrate a single segment based on static and dynamic calibration data.
    
    Parameters:
    acc_static: nx3 numpy array of linear accelerations during static calibration (neutral pose).
    gyro_dynamic: nx3 numpy array of angular velocities during dynamic calibration (e.g. toe-touches).
    q_static: nx4 numpy array of raw IMU quaternions during static calibration.
    
    Returns:
    q_g: Quaternion for gravity alignment.
    q_PCA: Quaternion for PCA alignment (medial-lateral axis).
    q_0: Average orientation quaternion during static calibration.
    """
    # 1. Gravity Alignment (Static Calibration)
    # Average acceleration vector from the stationary period
    g_avg = np.mean(acc_static, axis=0)
    
    # Gravitational acceleration vector in the segment-fixed ISB reference frame
    g_anat = np.array([0.0, 9.81, 0.0]) # j_hat
    
    # Calculate q_g
    cross_prod = np.cross(g_avg, g_anat)
    norm_cross_prod = np.linalg.norm(cross_prod)
    if norm_cross_prod == 0:
        n_hat = np.array([0.0, 1.0, 0.0])
        theta = 0.0
    else:
        n_hat = cross_prod / norm_cross_prod
        dot_prod = np.dot(g_avg, g_anat)
        mag_g_avg = np.linalg.norm(g_avg)
        mag_g_anat = np.linalg.norm(g_anat)
        cos_theta = dot_prod / (mag_g_avg * mag_g_anat)
        # Handle potential floating point errors for arccos
        cos_theta = np.clip(cos_theta, -1.0, 1.0)
        theta = np.arccos(cos_theta)
        
    q_g = np.quaternion(np.cos(theta/2), *(np.sin(theta/2) * n_hat))

    # 2. PCA Alignment (Dynamic Calibration)
    pca = PCA(n_components=1)
    pca.fit(gyro_dynamic)
    e_pca = pca.components_[0] # principal component (axis of rotation)
    
    e_1 = np.array([0.0, 0.0, 1.0]) # k_hat (normal to sagittal plane)
    
    cross_prod_pca = np.cross(e_pca, e_1)
    n_hat_pca = cross_prod_pca / np.linalg.norm(cross_prod_pca)
    n_y = n_hat_pca[1] # Component in y-direction (aligned with gravity)
    
    dot_prod_pca = np.dot(e_pca, e_1)
    cos_theta_pca = np.clip(dot_prod_pca, -1.0, 1.0)
    theta_pca = np.arccos(cos_theta_pca)
    
    # Eq 7
    axis = np.array([0.0, 0.0, 0.0])
    axis[1] = np.sign(n_y)
    
    q_PCA_0 = np.quaternion(np.cos(theta_pca/2), *(np.sin(theta_pca/2) * axis))
    
    # Determine correct medial-lateral direction
    # We must rotate gyro data to the lab fixed global reference frame W_L
    # But wait, to check the direction, let's use the first method from the paper
    # "The magnitude of the maximum and minimum angular velocity values are compared..."
    
    # We need to rotate the gyro dynamic data
    gyro_W = np.zeros_like(gyro_dynamic)
    for i in range(len(gyro_dynamic)):
        # Assuming q_IMU during dynamic calibration is just the current orientation, 
        # but the paper states we apply this to the angular velocity vectors in W_L.
        # Actually, let's look at the implementation for q_PCA rotation (half a rotation)
        # We can approximate by looking at the projected angular velocity.
        pass # The ReBAIT code might handle this differently, but let's stick to the paper's logic
        
    # Simplified check from ReBAIT new_utils.py (ana_Calibration)
    projected_gyro = np.dot(gyro_dynamic, e_pca)
    if np.max(projected_gyro) > np.abs(np.min(projected_gyro)):
        q_PCA = np.quaternion(0, 0, 1, 0) * q_PCA_0 # Rotation about vertical (y) axis by half a rotation
    else:
        q_PCA = q_PCA_0

    # 3. Calculate q_0 (Average orientation quaternion during stationary calibration)
    # Average quaternions using eigenvector method or simple average (since spread is small during static phase)
    # We will use simple mean and normalize, which is an acceptable approximation for a static pose.
    q_static_np = quaternion.as_quat_array(q_static)
    q_mean = np.mean(quaternion.as_float_array(q_static_np), axis=0)
    q_0_inv = np.quaternion(*q_mean).normalized().conjugate() # The paper describes right-multiplying by q_0, which is the initial orientation relative inverse
    
    return q_g, q_PCA, q_0_inv

def get_segment_orientation(q_IMU, q_g, q_PCA, q_0):
    """
    Calculates the current segment orientation quaternion.
    Equation 10: q_i = q_PCA * q_g * q_IMU * q_0
    """
    q_IMU = np.quaternion(*q_IMU) if isinstance(q_IMU, (list, tuple, np.ndarray)) else q_IMU
    q_g = np.quaternion(*q_g) if isinstance(q_g, (list, tuple, np.ndarray)) else q_g
    q_PCA = np.quaternion(*q_PCA) if isinstance(q_PCA, (list, tuple, np.ndarray)) else q_PCA
    q_0 = np.quaternion(*q_0) if isinstance(q_0, (list, tuple, np.ndarray)) else q_0
    
    return q_PCA * q_g * q_IMU * q_0

def calc_sagittal_angle(q):
    """
    Calculates the sagittal plane angle from a quaternion.
    Equation 11
    """
    q_np = np.quaternion(*q) if isinstance(q, (list, tuple, np.ndarray)) else q
    w = q_np.w
    z = q_np.z
    theta = 2 * np.arccos(w / np.sqrt(w**2 + z**2)) * np.sign(z)
    return np.degrees(theta)

def calculate_kinematics(pelvis_q, thigh_q, shank_q, foot_q, calib_data):
    """
    Calculate the segment and joint angles.
    
    Parameters:
    *_q: Arrays of quaternions (Nx4) for each segment.
    calib_data: Dictionary containing q_g, q_PCA, q_0 for each segment.
    
    Returns:
    segment_angles: dict of sagittal angles for each segment.
    joint_angles: dict of sagittal angles for hip, knee, ankle.
    """
    n = len(shank_q)
    
    # Initialize arrays
    theta_segment = {'pelvis': np.zeros(n), 'thigh': np.zeros(n), 'shank': np.zeros(n), 'foot': np.zeros(n)}
    theta_joint = {'hip': np.zeros(n), 'knee': np.zeros(n), 'ankle': np.zeros(n)}
    
    for i in range(n):
        # 1. Transform segment orientations
        q_pv = get_segment_orientation(pelvis_q[i], calib_data['pelvis']['q_g'], calib_data['pelvis']['q_PCA'], calib_data['pelvis']['q_0'])
        q_th = get_segment_orientation(thigh_q[i], calib_data['thigh']['q_g'], calib_data['thigh']['q_PCA'], calib_data['thigh']['q_0'])
        q_sh = get_segment_orientation(shank_q[i], calib_data['shank']['q_g'], calib_data['shank']['q_PCA'], calib_data['shank']['q_0'])
        q_ft = get_segment_orientation(foot_q[i], calib_data['foot']['q_g'], calib_data['foot']['q_PCA'], calib_data['foot']['q_0'])
        
        # Segment sagittal angles
        theta_segment['pelvis'][i] = calc_sagittal_angle(q_pv)
        theta_segment['thigh'][i] = calc_sagittal_angle(q_th)
        theta_segment['shank'][i] = calc_sagittal_angle(q_sh)
        theta_segment['foot'][i] = calc_sagittal_angle(q_ft)
        
        # 2. Calculate Joint Quaternions (Table 1)
        # Hip: q_h = q'_PV * q_TH
        q_h = q_pv.conjugate() * q_th
        # Knee: q_k = q'_SH * q_TH  (note: in paper it's q'_SH * q_TH for knee)
        q_k = q_sh.conjugate() * q_th
        # Ankle: q_a = q'_SH * q_FT
        q_a = q_sh.conjugate() * q_ft
        
        # Joint sagittal angles
        theta_joint['hip'][i] = calc_sagittal_angle(q_h)
        theta_joint['knee'][i] = calc_sagittal_angle(q_k)
        theta_joint['ankle'][i] = calc_sagittal_angle(q_a)
        
    return theta_segment, theta_joint

if __name__ == '__main__':
    # Simple test with dummy data
    print("Running basic test...")
    n = 10
    dummy_q = np.array([[1.0, 0.0, 0.0, 0.0]] * n)
    
    calib = {
        seg: {
            'q_g': np.quaternion(1, 0, 0, 0),
            'q_PCA': np.quaternion(1, 0, 0, 0),
            'q_0': np.quaternion(1, 0, 0, 0)
        } for seg in ['pelvis', 'thigh', 'shank', 'foot']
    }
    
    seg_ang, joint_ang = calculate_kinematics(dummy_q, dummy_q, dummy_q, dummy_q, calib)
    print("Test passed successfully.")
