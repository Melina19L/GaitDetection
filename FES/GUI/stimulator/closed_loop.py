import numpy as np
from .gait_phases import Phase

from scipy.spatial.transform import Rotation as R
import math


# NOTE: Assume the quaternions are in the format [w, x, y, z] where w is the scalar part and (x, y, z) is the vector part.

DEG_TO_CURRENT = 0.1  # Example conversion factor from degrees to current
FLEXION_ANGLE = 60.0  # Example target knee bend angle in degrees
EXTENSION_ANGLE = 10.0  # Example target knee extension angle in degrees

# Ankle angle constants (typical gait cycle values)
PLANTARFLEXION_ANGLE = 20.0  # Target ankle plantarflexion angle in degrees (toe-off)
DORSIFLEXION_ANGLE = -10.0   # Target ankle dorsiflexion angle in degrees (mid-stance)

TIME_TOLERANCE = 0.10  # Time tolerance in seconds for matching timestamps (100 ms)


    
# Luka's Method - Relative Quqaternion Angle (RQA method)
#   - Assumption 1: Knee joint (and ankle) = Hinge joint (1 DOF)
#   - Assumption 2: which is a direct consequence of Assumption 1 => thigh ML axis is alligned with joint axis

# ---- quaternion helpers ----
def quat_conjugate(q): return np.array([q[0], -q[1], -q[2], -q[3]])
def quat_mul(q1, q2):
    w1,x1,y1,z1 = q1; w2,x2,y2,z2 = q2
    return np.array([
        w1*w2 - x1*x2 - y1*y2 - z1*z2,
        w1*x2 + x1*w2 + y1*z2 - z1*y2,
        w1*y2 - x1*z2 + y1*w2 + z1*x2,
        w1*z2 + x1*y2 - y1*x2 + z1*w2
    ])
def normalize(q): return q / np.linalg.norm(q)

def angle_between_quaternions_algo2(q_thigh, q_shank): #, joint_axis=None):
    # if joint_axis is None:
    #     joint_axis = np.array([0.0, 1.0, 0.0])  # y = ML (right)
    q_t = normalize(np.array(q_thigh))
    q_s = normalize(np.array(q_shank))
    # relative quaternion: thigh^{-1} * shank
    q_rel = quat_mul(quat_conjugate(q_t), q_s)
    q_rel = normalize(q_rel)
    w = np.clip(q_rel[0], -1.0, 1.0)
    angle = 2.0 * np.arccos(w)   # radians

    return np.degrees(angle)



# Dominks Method - Segment Axis Angle (SAA Method) - Main  Method, this is the one that acctually runs
def angle_between_quaternions(q1: np.ndarray, q2: np.ndarray) -> float:
    xAxis = np.array([1.0, 0.0, 0.0])
    x1 = rotate_vector_by_quaternion(xAxis, q1)
    x2 = rotate_vector_by_quaternion(xAxis, q2)
    angleRad = angle_between_vectors(x1, x2)
    angleDeg = np.degrees(angleRad)
    return angleDeg


def ankle_angle_between_quaternions(q_shank: np.ndarray, q_foot: np.ndarray) -> float:
    """Compute raw signed ankle angle using empirically confirmed sensor axes.

    Axes confirmed by sensor_axes_diagnostic on 2026-04-21:
      - Shank-X: most vertical axis (along tibia, global ≈ [0, 0, +1])
      - Foot-Y:  most horizontal axis (along foot toward toes, global ≈ [+0.98, +0.15, -0.11])

    Returns the SIGNED angle between these two axes in the global frame.
    The neutral-pose zeroing is handled externally by subtracting the calibration
    offset stored in ROM.offset (populated by ankle_functional_calibration).

    Sign convention:
      - foot_y_global[2] < 0 → toes DOWN → plantarflexion → positive sign
      - foot_y_global[2] > 0 → toes UP   → dorsiflexion   → negative sign

    Do NOT subtract any fixed constant here — the actual neutral angle between
    Shank-X and Foot-Y depends on sensor mounting and is measured at calibration.
    """
    xAxis = np.array([1.0, 0.0, 0.0])
    yAxis = np.array([0.0, 1.0, 0.0])

    # Longitudinal axes in global frame
    shank_x_global = rotate_vector_by_quaternion(xAxis, q_shank)
    foot_y_global  = rotate_vector_by_quaternion(yAxis, q_foot)

    # Unsigned angle between the two axes
    angle_rad = angle_between_vectors(shank_x_global, foot_y_global)
    angle_deg = np.degrees(angle_rad)

    # Signed based on vertical component of Foot-Y:
    #   toes DOWN (plantarflexion) → foot_y[2] < 0 → positive output
    #   toes UP   (dorsiflexion)   → foot_y[2] > 0 → negative output
    sign = -np.sign(foot_y_global[2]) if abs(foot_y_global[2]) > 0.01 else 1.0

    return sign * angle_deg   # raw signed angle; offset subtracted in ROM.get_ankle_angle



def sensor_axes_diagnostic(q_shank: np.ndarray, q_foot: np.ndarray) -> str:
    """Return an HTML table showing how shank and foot sensor axes project in the global frame.

    Called at calibration time so the user can identify which sensor axis
    aligns with anatomical directions:
      - Gravity = global Z-down  → the axis with the largest |z| component
        when standing is the sensor's "vertical" axis.
      - Along-foot direction = parallel to floor, pointing toward toes
        → the axis with the smallest |z| value AND the largest |x| or |y|.

    The table is formatted for display in the GUI status box (HTML).
    """
    axes = {
        'X': np.array([1.0, 0.0, 0.0]),
        'Y': np.array([0.0, 1.0, 0.0]),
        'Z': np.array([0.0, 0.0, 1.0]),
    }
    gravity = np.array([0.0, 0.0, -1.0])   # global frame: Z points up, gravity is −Z

    def axis_info(q, label):
        rows = []
        best_grav  = ('?', 0.0)
        best_floor = ('?', 0.0)
        for name, v in axes.items():
            gv = rotate_vector_by_quaternion(v, q)
            gv_norm = gv / (np.linalg.norm(gv) + 1e-9)
            alignment_grav  = abs(float(np.dot(gv_norm, gravity)))   # 1 = vertical
            alignment_floor = float(1.0 - alignment_grav)             # 1 = horizontal
            bar_g = '█' * int(alignment_grav  * 10)
            bar_f = '█' * int(alignment_floor * 10)
            rows.append(
                f'<tr><td>{label}-{name}</td>'
                f'<td>[{gv[0]:+.2f}, {gv[1]:+.2f}, {gv[2]:+.2f}]</td>'
                f'<td title="vertical">{bar_g} {alignment_grav:.2f}</td>'
                f'<td title="horizontal">{bar_f} {alignment_floor:.2f}</td></tr>'
            )
            if alignment_grav  > best_grav[1]:  best_grav  = (name, alignment_grav)
            if alignment_floor > best_floor[1]: best_floor = (name, alignment_floor)
        rows.append(
            f'<tr style="color:#f39c12"><td><b>{label} summary</b></td>'
            f'<td colspan="2">↕ Vertical axis: <b>{label}-{best_grav[0]}</b></td>'
            f'<td>↔ Floor axis: <b>{label}-{best_floor[0]}</b></td></tr>'
        )
        return rows

    html = (
        '<p style="color:#3498db; font-weight:bold; font-size:12px;">📐 Sensor Axis Diagnostic</p>'
        '<table style="color:#ecf0f1; font-family:monospace; font-size:11px; border-collapse:collapse;">'
        '<tr style="color:#95a5a6">'
        '<th>Axis</th><th>Global direction [Gx,Gy,Gz]</th>'
        '<th>Vertical ↕</th><th>Horizontal ↔</th></tr>'
    )
    if q_shank is not None:
        html += ''.join(axis_info(q_shank, 'Shank'))
    if q_foot is not None:
        html += ''.join(axis_info(q_foot, 'Foot'))
    html += (
        '</table>'
        '<p style="color:#95a5a6; font-size:10px;">'
        'Vertical ↕ = aligned with gravity | Horizontal ↔ = parallel to floor<br/>'
        'The correct ankle axis is the Foot axis most HORIZONTAL (↔ close to 1.0).<br/>'
        'If Foot-X is the most horizontal → X-axis method is correct.<br/>'
        'If Foot-Z is the most horizontal → Z-axis method is correct.</p>'
    )
    return html


def rotate_vector_by_quaternion(v: np.ndarray, q: np.ndarray) -> np.ndarray:
    u = q[1:4]  # Extract the vector part of the quaternion
    s: float = q[0]  # Extract the scalar part of the quaternion
    v_rotated: np.ndarray = u * 2.0 * u.dot(v) + v * (s * s - u.dot(u)) + np.cross(u, v) * 2.0 * s
    return v_rotated



def angle_between_vectors(v1: np.ndarray, v2: np.ndarray) -> float:
    # Normalize the vectors
    v1_norm = v1 / np.linalg.norm(v1)
    v2_norm = v2 / np.linalg.norm(v2)

    # Calculate the dot product
    dot_product = np.clip(np.dot(v1_norm, v2_norm), -1.0, 1.0)  # Ensure the value is within the valid range for arccos
    return np.arccos(dot_product)


class ROM:
    def __init__(self, offset: float = 0.0, scale: float = 1.0):
        self.timestamp: float = 0.0
        self.offset: float = offset
        self.scale: float = scale
        self.angles = np.empty((0, 2))
        self.angles_algo2 = np.empty((0, 2))

    # ── Knee methods (unchanged) ──────────────────────────────────────────────
    @staticmethod
    def functional_calibration(q_thigh: np.ndarray, q_shank: np.ndarray) -> float:
        """Return the knee angle at current neutral pose (used as offset)."""
        return angle_between_quaternions(q_thigh, q_shank)

    @staticmethod
    def calculate_joint_angle(q_thigh: np.ndarray, q_shank: np.ndarray, offset: float) -> float:
        angle = angle_between_quaternions(q_thigh, q_shank)
        return angle - offset

    def get_joint_angle(self, q_thigh: np.ndarray, q_shank: np.ndarray) -> float:
        angle = angle_between_quaternions(q_thigh, q_shank) - self.offset
        angle *= self.scale
        self.angles = np.append(self.angles, [[self.timestamp, angle]], axis=0)
        return angle

    def set_offset(self, offset: float) -> None:
        self.offset = offset

    # ── Ankle methods (signed, Z-axis projection) ─────────────────────────────
    @staticmethod
    def ankle_functional_calibration(q_shank: np.ndarray, q_foot: np.ndarray) -> float:
        """Return the signed ankle angle at neutral pose (used as offset).

        This replaces the unsigned `functional_calibration` for the ankle.
        In quiet standing the returned value represents the geometric angle
        between shank and foot at the calibration instant; subtracting it
        from every subsequent measurement yields 0° at neutral and signed
        dorsiflexion (-) / plantarflexion (+) values during movement.
        """
        return ankle_angle_between_quaternions(q_shank, q_foot)

    @staticmethod
    def calculate_ankle_angle(q_shank: np.ndarray, q_foot: np.ndarray, offset: float) -> float:
        """Return the calibrated signed ankle angle in degrees."""
        return ankle_angle_between_quaternions(q_shank, q_foot) - offset

    def get_ankle_angle(self, q_shank: np.ndarray, q_foot: np.ndarray) -> float:
        """Compute, store and return the calibrated ankle angle."""
        angle = ankle_angle_between_quaternions(q_shank, q_foot) - self.offset
        angle *= self.scale
        self.angles = np.append(self.angles, [[self.timestamp, angle]], axis=0)
        return angle

    def ankle_compute_from_list(self, q_shank_array: np.ndarray, q_foot_array: np.ndarray,
                                 timestamp: float = None) -> float:
        """Compute ankle angle from synchronized quaternion arrays using the signed Z-axis method.

        Mirrors compute_from_list but uses get_ankle_angle (ankle-specific signed
        algorithm) instead of get_joint_angle (knee-specific unsigned X-axis algorithm).

        :param q_shank_array: Quaternions from the shank IMU [timestamp, w, x, y, z].
        :param q_foot_array:  Quaternions from the foot  IMU [timestamp, w, x, y, z].
        :param timestamp: Wall-clock time to log; if None uses shank timestamp.
        :return: Calibrated ankle angle in degrees, or 0.0 if no matching pair found.
        """
        if q_shank_array.size == 0 or q_foot_array.size == 0:
            return 0.0

        shank_ts = q_shank_array[:, 0]
        foot_ts  = q_foot_array[:, 0]

        # Iterate from the most-recent shank sample backwards
        for i in range(len(shank_ts) - 1, -1, -1):
            ts = shank_ts[i]
            closest_index = np.argmin(np.abs(foot_ts - ts))
            if np.abs(foot_ts[closest_index] - ts) < TIME_TOLERANCE:
                q_shank = q_shank_array[i, 1:5]
                q_foot  = q_foot_array[closest_index, 1:5]
                self.timestamp = timestamp if timestamp is not None else ts
                return self.get_ankle_angle(q_shank, q_foot)

        return 0.0

    def compute_from_list(self, q_thigh_array: np.ndarray, q_shank_array: np.ndarray, timestamp: float = None) -> float:
        """Compute joint angles from lists of quaternions for thigh and shank containing samples with timestamps.\n
        The required format is a 2D numpy array, with each row (first dimension) containing the following data [timestamp, w, x, y, z].\n
        This means that the quaternion can be extracted, while knowing the acquisition time of the sample.\n
        CAREFUL: This method requires the IMUs to be synchronized, otherwise the results will not be correct.\n

        :param q_thigh_array: Quaternions from the thigh IMU with timestamps.
        :type q_thigh_array: np.ndarray
        :param q_shank_array: Quaternions from the shank IMU with timestamps.
        :type q_shank_array: np.ndarray
        :param timestamp: If a certain timestamp should be logged (like time.time(), if None the selected ts in the shank array is used), defaults to None
        :type timestamp: float, optional
        :return: The calculated joint angle from the latest samples, which have near matching timestamps.
        :rtype: float
        """
        # Return if one of the arrays is empty (can happen at the beginning of the experiment)
        if q_thigh_array.size == 0 or q_shank_array.size == 0:
            return 0.0

        thigh_ts = q_thigh_array[:, 0]
        shank_ts = q_shank_array[:, 0]

        for i in range(len(thigh_ts) - 1, -1, -1):
            ts = thigh_ts[i]
            # Find the closest matching timestamp in the shank array
            closest_index = np.argmin(np.abs(shank_ts - ts))
            if np.abs(shank_ts[closest_index] - ts) < TIME_TOLERANCE:
                # If the timestamps are close enough, calculate the angle
                q_thigh = q_thigh_array[i, 1:5]
                q_shank = q_shank_array[closest_index, 1:5]
                self.timestamp = timestamp if timestamp is not None else shank_ts
                angle_primary = self.get_joint_angle(q_thigh, q_shank)
                # also compute and store algo2 (not used for closed-loop control but saved)
                try:
                    angle_algo2 = angle_between_quaternions_algo2(q_thigh, q_shank) - self.offset
                    self.angles_algo2 = np.append(self.angles_algo2, [[self.timestamp, angle_algo2]], axis=0)
                except Exception:
                    pass
                return angle_primary
    
    @staticmethod
    def static_compute_from_list(q_thigh_array: np.ndarray, q_shank_array: np.ndarray, offset: float) -> float:
        """Compute joint angles from lists of quaternions for thigh and shank containing samples with timestamps.\n
        The required format is a 2D numpy array, with each row (first dimension) containing the following data [timestamp, w, x, y, z].\n
        This means that the quaternion can be extracted, while knowing the acquisition time of the sample.\n
        CAREFUL: This method requires the IMUs to be synchronized, otherwise the results will not be correct.\n

        :param q_thigh_array: Quaternions from the thigh IMU with timestamps.
        :type q_thigh_array: np.ndarray
        :param q_shank_array: Quaternions from the shank IMU with timestamps.
        :type q_shank_array: np.ndarray
        :param offset: The offset to be applied to the angle calculation.
        :type offset: float
        :return: The calculated joint angle from the latest samples, which have near matching timestamps.
        :rtype: float
        """
        # Return if one of the arrays is empty (can happen at the beginning of the experiment)
        if q_thigh_array.size == 0 or q_shank_array.size == 0:
            return 0.0

        thigh_ts = q_thigh_array[:, 0]
        shank_ts = q_shank_array[:, 0]

        for i in range(len(thigh_ts) - 1, -1, -1):
            ts = thigh_ts[i]
            # Find the closest matching timestamp in the shank array
            closest_index = np.argmin(np.abs(shank_ts - ts))
            if np.abs(shank_ts[closest_index] - ts) < TIME_TOLERANCE:
                # If the timestamps are close enough, calculate the angle
                q_thigh = q_thigh_array[i, 1:5]
                q_shank = q_shank_array[closest_index, 1:5]
                return ROM.calculate_joint_angle(q_thigh, q_shank, offset)
        # No matching timestamp pair found within tolerance
        return None

    def get_pi_angle(self) -> float:
        """Get the last calculated joint angle from the angles array.

        :return: The last calculated joint angle.
        :rtype: float
        """
        if self.angles.size == 0:
            return 0.0
        return self.angles[-1, 1]
    
    def get_algo2_angle(self) -> float:
        """Return last saved algo2 angle (timestamp, angle saved in angles_algo2)."""
        if self.angles_algo2.size == 0:
            return 0.0
        return self.angles_algo2[-1, 1]


class PIController:
    def __init__(self, kp: float, ki: float, dt: float, target_extension: float = EXTENSION_ANGLE, target_flexion: float = FLEXION_ANGLE):
        self.kp = kp
        self.ki = ki
        self.dt = dt
        self.target_extension = target_extension  # Target angle for extension
        self.target_flexion = target_flexion
        self.integral = 0.0
        self.target = self.target_extension
        self.flexing: bool = True  # True for bending, False for extension
        self.inverse: bool = False  # True if the controller is in inverse mode (e.g., for extension outside swing phase)
        # Record the timestamps, errors and output
        self.timestamps = []
        self.errors = []
        self.outputs = []
        
        # Record the target changes
        self.target_changes = np.empty((0, 2))  # Each row will be [timestamp, target_angle]
        self.target_changes = np.append(self.target_changes, [[0.0, self.target_extension]], axis=0)  # Initialize with the extension target

    def compute(self, measured_value: float, timestamp: float = 0.0) -> float:
        """Compute the PI control output based on the target and measured value.

        :param measured_value: The measured value (e.g., knee angle).
        :type measured_value: float
        :param timestamp: The timestamp at what time the controller was updated. Used for recording, defaults to 0.0
        :type timestamp: float, optional
        :return: The control output in terms of current to be applied to the actuator.
        :rtype: float
        """
        # Calculate the error and update the integral term
        error = self.target - measured_value
        self.integral += error * self.dt
        # Calculate the output using the PI formula
        output = self.kp * error + self.ki * self.integral
        # Inverse the current if the controller is in inverse mode
        if self.inverse:
            output = -output
        
        # Record the data for analysis
        self.timestamps.append(timestamp)
        self.errors.append(error)
        self.outputs.append(output)
        
        return output  # *DEG_TO_CURRENT Convert output to current

    def set_target(self, target_value: float):
        """Set a new target value for the PI controller."""
        self.target = target_value
        self.target_changes = np.append(self.target_changes, [[self.timestamps[-1] if self.timestamps else 0.0, target_value]], axis=0)
        self.reset()  # Reset the integral when the target changes

    def set_gains(self, kp: float, ki: float):
        """Set new gains for the PI controller."""
        self.kp = kp
        self.ki = ki
        self.integral = 0.0

    def update_target(self, phase: Phase, measured_angle: float) -> bool:
        """Update the target based on the current phase and measured value.
        This method adjusts the target angle based on the phase of the gait cycle.

        :param phase: The current phase of the gait cycle.
        :type phase: Phase
        :param measured_angle: The measured knee angle value.
        :type measured_angle: float
        :return: True if the target was updated, False otherwise.
        :rtype: bool
        """
        if (phase == Phase.LOADING_RESPONSE or phase == Phase.MID_STANCE or phase == Phase.TERMINAL_SWING) and not self.inverse:
            # Setting flexing to True here allows the controller to start flexing the knee after transition to swing phase later on
            self.flexing = True
            self.inverse = True
            self.set_target(self.target_extension)
            return True
        elif phase == Phase.MID_SWING:
            if self.flexing and self.target != self.target_flexion:
                # This will be the case only after transitioning from mid stance to swing phase
                self.inverse = False
                self.set_target(self.target_flexion)
                return True
            elif self.flexing and measured_angle >= self.target:
                # After reaching the target angle, the knee should be extended
                self.inverse = False
                self.flexing = False
                self.set_target(self.target_extension)
                return True

        # If the target is already set correctly, do nothing
        return False

    def reset(self):
        """Reset the integral."""
        self.integral = 0.0


if __name__ == "__main__":
    # Example usage
    q_shank = np.array([0.7071, 0.0, 0.7071, 0.0])  # Example quaternion for shank
    q_thigh = np.array([0.7071, 0.0, 0.0, 0.7071])  # Example quaternion for thigh

    # knee_angle = calculate_knee_angle(q_shank, q_thigh)
    knee_angle = 40
    print(f"Knee Angle: {knee_angle:.2f} degrees")

    # Example PI controller usage
    pi_controller = PIController(kp=1.0, ki=0.1, dt=0.01)
    control_signal = pi_controller.compute(target_value=30.0, measured_value=knee_angle)
    print(f"Control Signal: {control_signal:.2f}")
