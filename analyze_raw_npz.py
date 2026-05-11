import numpy as np
import quaternion
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'FES', 'GUI'))

from stimulator.lower_limb_kinematics import get_segment_orientation, calc_sagittal_angle

def analyze_raw():
    file_path = os.path.join(os.path.dirname(__file__), 'FES', 'GUI', 'raw_imu_data_from_gui.npz')
    data = np.load(file_path, allow_pickle=True)
    
    print("Available keys:", list(data.keys()))
    
    # Try right leg first
    if 'right_thigh' not in data or 'right_shank' not in data:
        print("Missing right leg data")
        return
        
    r_thigh = data['right_thigh']
    r_shank = data['right_shank']
    print(f"Right thigh shape: {r_thigh.shape}, Right shank shape: {r_shank.shape}")
    
    paper_cal_wrapper = data.get('paper_cal')
    if paper_cal_wrapper is None:
        print("No paper_cal found!")
        return
        
    paper_cal = paper_cal_wrapper.item()
    if 'right_thigh' not in paper_cal or 'right_shank' not in paper_cal:
        print("Missing right leg calibration")
        return
        
    cal_th = paper_cal['right_thigh']
    cal_sh = paper_cal['right_shank']
    
    # Let's align lengths
    n = min(len(r_thigh), len(r_shank))
    r_thigh = r_thigh[:n]
    r_shank = r_shank[:n]
    
    print("Running math on first 100 samples...")
    angles = []
    
    n = min(len(r_thigh), len(r_shank))
    
    # Recalculate calib using the new fixed math
    from stimulator.lower_limb_kinematics import calibrate_segment
    # assume first 500 samples are calibration (static then dynamic)
    cal_th = {}
    cal_th['q_g'], cal_th['q_PCA'], cal_th['q_0'] = calibrate_segment(
        r_thigh[:100, 1:4], r_thigh[100:500, 4:7], r_thigh[:100, 7:11]
    )
    cal_sh = {}
    cal_sh['q_g'], cal_sh['q_PCA'], cal_sh['q_0'] = calibrate_segment(
        r_shank[:100, 1:4], r_shank[100:500, 4:7], r_shank[:100, 7:11]
    )
    
    # Pre-calculate static to remove offset
    q_pv_static = cal_th['q_PCA'] * cal_th['q_g']
    q_dist_static = cal_sh['q_PCA'] * cal_sh['q_g']
    q_joint_static = q_dist_static.conjugate() * q_pv_static
    static_rebait = calc_sagittal_angle(q_joint_static)
    
    angles = []
    ws, xs, ys, zs = [], [], [], []
    for i in range(n):
        q_prox = np.array(r_thigh[i, 7:11], dtype=np.float64)
        q_dist = np.array(r_shank[i, 7:11], dtype=np.float64)
        
        q_pv = get_segment_orientation(q_prox, cal_th['q_g'], cal_th['q_PCA'], cal_th['q_0'])
        q_dist_seg = get_segment_orientation(q_dist, cal_sh['q_g'], cal_sh['q_PCA'], cal_sh['q_0'])
        
        q_joint = q_dist_seg.conjugate() * q_pv
        ws.append(q_joint.w)
        xs.append(q_joint.x)
        ys.append(q_joint.y)
        zs.append(q_joint.z)
        
        raw_rebait = calc_sagittal_angle(q_joint)
        
        angle = raw_rebait - static_rebait
        angle = (angle + 180) % 360 - 180
        angles.append(angle)
        
    import matplotlib.pyplot as plt
    plt.figure(figsize=(12, 10))
    plt.subplot(2, 1, 1)
    plt.plot(ws, label='w')
    plt.plot(xs, label='x')
    plt.plot(ys, label='y')
    plt.plot(zs, label='z')
    plt.title('q_joint Quaternion Components')
    plt.legend()
    plt.grid()
    
    plt.subplot(2, 1, 2)
    plt.plot(angles, label='Angle')
    plt.title('Knee Angle')
    plt.grid()
    plt.tight_layout()
    plt.savefig('q_components.png')

if __name__ == '__main__':
    analyze_raw()
