import sys
import argparse
import h5py
import numpy as np
import matplotlib.pyplot as plt
import imufusion

# 1. Parse input file path
parser = argparse.ArgumentParser(description="Plot offline knee joint angles from an H5 recording.")
parser.add_argument("file_path", type=str, help="Path to the .h5 recording file")
args = parser.parse_args()
file_path = args.file_path
print(f"Loading H5 file: {file_path}")

with h5py.File(file_path, "r") as f:
    timestamps = f["Cometa/WaveX_IMU/timestamps"][:]
    imu_data = f["Cometa/WaveX_IMU/data"][:]
    events = f["logs/events"][:]

# Estimate sampling rate from timestamps (median of diffs is robust to outliers)
dt_samples = np.diff(timestamps)
dt = float(np.median(dt_samples))
sample_rate = 1.0 / dt
t0 = timestamps[0]

print(f"Estimated sampling rate: {sample_rate:.2f} Hz (dt = {dt*1000:.3f} ms)")
print(f"Data loaded successfully! Total samples: {len(timestamps)} ({len(timestamps)/sample_rate:.1f} seconds)")

# 2. Extract raw data for Right and Left Knee segments
# Right Knee: Thigh = Sensor 1 (Cols 0-8), Shin = Sensor 5 (Cols 36-44)
acc_r_thigh = imu_data[:, 0:3]
gyro_r_thigh = imu_data[:, 3:6]
acc_r_shin = imu_data[:, 36:39]
gyro_r_shin = imu_data[:, 39:42]

# Left Knee: Thigh = Sensor 2 (Cols 9-17), Shin = Sensor 6 (Cols 45-53)
acc_l_thigh = imu_data[:, 9:12]
gyro_l_thigh = imu_data[:, 12:15]
acc_l_shin = imu_data[:, 45:48]
gyro_l_shin = imu_data[:, 48:51]

# 3. Perform Sensor Fusion to obtain Quaternions for all four segments
print("Running Sensor Fusion (Madgwick AHRS) for all sensors...")
ahrs_r_thigh = imufusion.Ahrs()
ahrs_r_shin = imufusion.Ahrs()
ahrs_l_thigh = imufusion.Ahrs()
ahrs_l_shin = imufusion.Ahrs()

# Set standard AHRS parameters
settings = imufusion.Settings(imufusion.CONVENTION_NWU, 0.5, 10.0, 10.0, 5.0, 2000)
ahrs_r_thigh.settings = settings
ahrs_r_shin.settings = settings
ahrs_l_thigh.settings = settings
ahrs_l_shin.settings = settings

q_r_thigh = np.zeros((len(timestamps), 4))
q_r_shin = np.zeros((len(timestamps), 4))
q_l_thigh = np.zeros((len(timestamps), 4))
q_l_shin = np.zeros((len(timestamps), 4))

for i in range(len(timestamps)):
    # Right side
    ahrs_r_thigh.update_no_magnetometer(gyro_r_thigh[i], acc_r_thigh[i], dt)
    ahrs_r_shin.update_no_magnetometer(gyro_r_shin[i], acc_r_shin[i], dt)
    q_r_thigh[i] = ahrs_r_thigh.quaternion.wxyz
    q_r_shin[i] = ahrs_r_shin.quaternion.wxyz
    
    # Left side
    ahrs_l_thigh.update_no_magnetometer(gyro_l_thigh[i], acc_l_thigh[i], dt)
    ahrs_l_shin.update_no_magnetometer(gyro_l_shin[i], acc_l_shin[i], dt)
    q_l_thigh[i] = ahrs_l_thigh.quaternion.wxyz
    q_l_shin[i] = ahrs_l_shin.quaternion.wxyz

# 4. Calculate relative Joint Angles (3D angular difference)
print("Calculating relative joint angles...")
r_knee_angles = []
l_knee_angles = []

for i in range(len(timestamps)):
    # --- Right Knee Angle ---
    q_rt_conj = np.array([q_r_thigh[i,0], -q_r_thigh[i,1], -q_r_thigh[i,2], -q_r_thigh[i,3]])
    w1, x1, y1, z1 = q_rt_conj
    w2, x2, y2, z2 = q_r_shin[i]
    qw_r = w1*w2 - x1*x2 - y1*y2 - z1*z2
    
    angle_rad_r = 2 * np.arccos(np.clip(qw_r, -1.0, 1.0))
    r_knee_angles.append(np.degrees(angle_rad_r))
    
    # --- Left Knee Angle ---
    q_lt_conj = np.array([q_l_thigh[i,0], -q_l_thigh[i,1], -q_l_thigh[i,2], -q_l_thigh[i,3]])
    w1_l, x1_l, y1_l, z1_l = q_lt_conj
    w2_l, x2_l, y2_l, z2_l = q_l_shin[i]
    qw_l = w1_l*w2_l - x1_l*x2_l - y1_l*y2_l - z1_l*z2_l
    
    angle_rad_l = 2 * np.arccos(np.clip(qw_l, -1.0, 1.0))
    l_knee_angles.append(np.degrees(angle_rad_l))

r_knee_angles = np.array(r_knee_angles)
l_knee_angles = np.array(l_knee_angles)

# Calculate sitting calibration offsets at t = 2.0 seconds (post-AHRS convergence)
convergence_index = int(2.0 * sample_rate)
offset_r = r_knee_angles[convergence_index]
offset_l = l_knee_angles[convergence_index]

r_knee_norm = r_knee_angles - offset_r
l_knee_norm = l_knee_angles - offset_l

# 5. Plotting both knees in a single figure (2 subplots, English labels)
print("Generating synchronized subplots...")
fig, (ax_r, ax_l) = plt.subplots(2, 1, figsize=(15, 10), sharex=True)
time_s = timestamps - t0  # t=0 corresponds to the first recorded timestamp

# --- Subplot 1: Right Knee ---
ax_r.plot(time_s, r_knee_norm,
          label="Right Knee Angle", color="#ff5555", linewidth=2)
ax_r.set_title("Right Knee Joint Angle - Offline Analysis", fontsize=14, fontweight='bold')
ax_r.set_ylabel("Knee Angle (deg) - Sitting = 0°", fontsize=12)
ax_r.grid(True, linestyle="--", alpha=0.6)
ax_r.axhline(0, color="black", linestyle="-", alpha=0.5)

# --- Subplot 2: Left Knee ---
ax_l.plot(time_s, l_knee_norm,
          label="Left Knee Angle", color="#50fa7b", linewidth=2)
ax_l.set_title("Left Knee Joint Angle - Offline Analysis", fontsize=14, fontweight='bold')
ax_l.set_ylabel("Knee Angle (deg) - Sitting = 0°", fontsize=12)
ax_l.set_xlabel("Time (seconds)", fontsize=12)
ax_l.grid(True, linestyle="--", alpha=0.6)
ax_l.axhline(0, color="black", linestyle="-", alpha=0.5)

# Anchor x-axis to the recording start (t=0 = first timestamp)
ax_r.set_xlim(left=0, right=time_s[-1])
ax_l.set_xlim(left=0, right=time_s[-1])

ax_r.legend(loc="upper right")
ax_l.legend(loc="upper right")

plt.tight_layout()
plt.show()
