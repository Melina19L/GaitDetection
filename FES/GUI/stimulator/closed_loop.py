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


def ankle_angle_between_quaternions(
    q_shank: np.ndarray,
    q_foot: np.ndarray,
    foot_axis: str = 'X',
    shank_axis: str = 'X',
) -> float:
    """Unsigned angle between the chosen shank and foot longitudinal axes, in degrees.

    The choice of which sensor-local axis represents "along the segment" depends
    on how the strap orients the Movella DOT on the body:
      - Shank: the axis most aligned with gravity in standing pose (vertical = along tibia).
      - Foot: the axis most parallel to the floor in standing pose (horizontal = along toes).

    These are determined per-side at calibration via ``detect_most_vertical_axis``
    / ``detect_most_horizontal_axis`` and stored on ``ROM`` (or passed explicitly).

    Default ``shank_axis='X'`` and ``foot_axis='X'`` preserve the historic
    behaviour for the legacy mounting where both X-axes were already correct.

    Measurement principle:
      angle(Shank<axis>_global, Foot<axis>_global) at neutral is recorded as the
      calibration offset.  Subtracting it from each runtime measurement centres
      the output on 0° at neutral.  Larger angle = plantarflexion (+°), smaller
      angle = dorsiflexion (−°).  Picking the truly-longitudinal axes prevents
      the output from being contaminated by inversion/eversion or vertical-axis
      rotation when the sensor is mounted in a non-canonical orientation.
    """
    sax = AXIS_VECTORS[shank_axis]
    fax = AXIS_VECTORS[foot_axis]

    shank_global = rotate_vector_by_quaternion(sax, q_shank)
    foot_global  = rotate_vector_by_quaternion(fax, q_foot)

    angle_rad = angle_between_vectors(shank_global, foot_global)
    return float(np.degrees(angle_rad))


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

    def axis_info(q, label, fwd_axis=None):
        rows = []
        best_grav  = ('?', 0.0)
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
            
        floor_label = fwd_axis if fwd_axis else '?'
        rows.append(
            f'<tr style="color:#f39c12"><td><b>{label} summary</b></td>'
            f'<td colspan="2">↕ Vertical axis: <b>{label}-{best_grav[0]}</b></td>'
            f'<td>↔ Forward axis: <b>{label}-{floor_label}</b></td></tr>'
        )
        return rows

    # ── Pre-detect axes for accurate summary labels ──
    det_shank_fwd = '?'
    det_foot_fwd  = '?'
    if q_shank is not None and q_foot is not None:
        det_shank_fwd = detect_most_horizontal_axis(q_shank)
        det_foot_fwd  = detect_most_horizontal_axis(q_foot, q_shank)

    html = (
        '<p style="color:#3498db; font-weight:bold; font-size:12px;">📐 Sensor Axis Diagnostic</p>'
        '<table style="color:#ecf0f1; font-family:monospace; font-size:11px; border-collapse:collapse;">'
        '<tr style="color:#95a5a6">'
        '<th>Axis</th><th>Global direction [Gx,Gy,Gz]</th>'
        '<th>Vertical ↕</th><th>Horizontal ↔</th></tr>'
    )
    if q_shank is not None:
        html += ''.join(axis_info(q_shank, 'Shank', det_shank_fwd))
    if q_foot is not None:
        html += ''.join(axis_info(q_foot, 'Foot', det_foot_fwd))
    html += '</table>'

    # ── Auto-detected axis summary ──
    if q_shank is not None and q_foot is not None:
        det_shank_vert  = detect_most_vertical_axis(q_shank)
        det_foot_fwd    = detect_most_horizontal_axis(q_foot, q_shank)
        det_foot_ml     = detect_foot_medio_lateral_axis(q_foot, q_shank)
        det_foot_grav   = detect_most_vertical_axis(q_foot)
        html += (
            '<p style="color:#2ecc71; font-weight:bold; font-size:11px; margin-top:6px;">'
            '🎯 Auto-detected axes (used for ankle calculation):</p>'
            '<table style="color:#ecf0f1; font-family:monospace; font-size:11px; border-collapse:collapse;">'
            f'<tr><td>Shank longitudinal (vertical) axis:</td>'
            f'<td style="color:#50fa7b;"><b>{det_shank_vert}</b></td></tr>'
            f'<tr><td>Foot gravity axis (vertical):</td>'
            f'<td style="color:#50fa7b;"><b>{det_foot_grav}</b></td></tr>'
            f'<tr><td>Foot forward axis (toward toes):</td>'
            f'<td style="color:#50fa7b;"><b>{det_foot_fwd}</b></td></tr>'
            f'<tr><td>Foot medio-lateral axis (ankle twist):</td>'
            f'<td style="color:#ff79c6;"><b>{det_foot_ml}</b></td></tr>'
            '</table>'
        )

    html += (
        '<p style="color:#95a5a6; font-size:10px;">'
        'Vertical ↕ = aligned with gravity | Horizontal ↔ = parallel to floor<br/>'
        'Forward = X when Z is gravity (Xsens DOT convention)<br/>'
        'Medio-lateral = ankle rotation axis (perpendicular to both vertical and forward)</p>'
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


# ── Swing-twist decomposition ────────────────────────────────────────────────
def twist_angle_around_axis(q: np.ndarray, axis: np.ndarray) -> float:
    """Return the signed twist angle (radians) of quaternion ``q`` around ``axis``.

    Implements the standard swing-twist decomposition: projects ``q``'s vector
    part onto ``axis``, builds the twist quaternion, extracts its angle.
    Sign follows the sign of the projection along the axis.
    """
    axis = np.asarray(axis, dtype=float)
    n = float(np.linalg.norm(axis))
    if n < 1e-9:
        return 0.0
    axis = axis / n
    proj = float(np.dot(q[1:], axis))
    twist_v = proj * axis
    tw = np.array([q[0], twist_v[0], twist_v[1], twist_v[2]], dtype=float)
    tw_norm = float(np.linalg.norm(tw))
    if tw_norm < 1e-9:
        return 0.0
    tw = tw / tw_norm
    angle = 2.0 * float(np.arctan2(np.linalg.norm(tw[1:]), tw[0]))
    if proj < 0:
        angle = -angle
    return angle


def signed_ankle_angle(
    q_shank: np.ndarray,
    q_foot: np.ndarray,
    q_shank_ref: np.ndarray,
    q_foot_ref: np.ndarray,
    foot_axis: str = 'Y',
    shank_long_axis: str = 'X',
    foot_fwd_axis: str = 'X',
    shank_ml_axis: str = 'Y',
) -> float:
    """Return signed ankle dorsi-/plantar-flexion in degrees.

    Uses a **gravity-constrained sagittal-plane projection** that is
    geometrically decoupled from knee flexion:

      1. Compute the shank's medio-lateral (ML) axis in the global frame.
      2. Project it onto the horizontal plane (zero-out vertical component).
         Knee flexion rotates the shank *around* the ML axis, so the ML axis
         itself does NOT change direction — this is the key insight.
      3. Define the sagittal plane as perpendicular to this horizontal ML.
      4. Project the shank's longitudinal axis and the foot's forward axis
         onto this sagittal plane.
      5. The angle between these two projections IS the ankle flex/extension.

    The calibration-pose quaternions are used only to compute a static
    offset so that neutral standing reads 0°.

    Why the old twist-decomposition failed:
      Both knee flexion and ankle dorsiflexion are rotations around the
      same medio-lateral axis.  The relative quaternion q_delta picks up
      both indistinguishably.  The sagittal projection avoids this because
      it measures the *geometric angle between two body segments*, not the
      relative rotation.
    """
    qs     = normalize(np.asarray(q_shank,     dtype=float))
    qf     = normalize(np.asarray(q_foot,      dtype=float))
    qs_ref = normalize(np.asarray(q_shank_ref, dtype=float))
    qf_ref = normalize(np.asarray(q_foot_ref,  dtype=float))

    def _sagittal_angle(qs_cur, qf_cur):
        # Shank ML axis in global frame — stays horizontal during knee flexion
        shank_ml = rotate_vector_by_quaternion(
            AXIS_VECTORS.get(shank_ml_axis, AXIS_VECTORS['Y']), qs_cur,
        )
        # Keep only the horizontal component (remove gravity contamination)
        shank_ml[2] = 0.0
        n = float(np.linalg.norm(shank_ml))
        if n < 1e-6:
            return 0.0
        ml_dir = shank_ml / n

        # Shank longitudinal axis (along the tibia) and foot forward axis
        shank_long = rotate_vector_by_quaternion(
            AXIS_VECTORS.get(shank_long_axis, AXIS_VECTORS['X']), qs_cur,
        )
        foot_fwd = rotate_vector_by_quaternion(
            AXIS_VECTORS.get(foot_fwd_axis, AXIS_VECTORS['X']), qf_cur,
        )

        # Project both onto the sagittal plane (⊥ to ml_dir)
        shank_proj = shank_long - np.dot(shank_long, ml_dir) * ml_dir
        foot_proj  = foot_fwd  - np.dot(foot_fwd,  ml_dir) * ml_dir

        ns = float(np.linalg.norm(shank_proj))
        nf = float(np.linalg.norm(foot_proj))
        if ns < 1e-6 or nf < 1e-6:
            return 0.0
        shank_proj /= ns
        foot_proj  /= nf

        dot   = float(np.clip(np.dot(shank_proj, foot_proj), -1.0, 1.0))
        angle = float(np.degrees(np.arccos(dot)))

        # Sign convention: positive = dorsiflexion
        cross = np.cross(foot_proj, shank_proj)
        if float(np.dot(cross, ml_dir)) < 0:
            angle = -angle
        return angle

    # Calibration offset (angle at neutral standing pose)
    offset = _sagittal_angle(qs_ref, qf_ref)
    return _sagittal_angle(qs, qf) - offset


# ── Sensor-axis detection ────────────────────────────────────────────────────
# At calibration time we look at the world projection of each sensor's local
# axes (X / Y / Z) and pick the one most aligned with gravity (= longitudinal
# for vertical segments like shank/thigh/pelvis) or most parallel to the floor
# (= longitudinal for the foot, pointing toward toes).
# This makes the algorithm robust to operator-chosen strap orientation.
AXIS_VECTORS = {
    'X': np.array([1.0, 0.0, 0.0]),
    'Y': np.array([0.0, 1.0, 0.0]),
    'Z': np.array([0.0, 0.0, 1.0]),
}


def detect_most_vertical_axis(q: np.ndarray) -> str:
    """Return the local axis name ('X' | 'Y' | 'Z') of a sensor whose world
    projection is most aligned with gravity at the current pose.
    Used for shank / thigh / pelvis (segments that stand vertically at neutral).
    """
    best_name = 'X'
    best_score = -1.0
    for name, v in AXIS_VECTORS.items():
        gv = rotate_vector_by_quaternion(v, q)
        gv_norm = gv / (np.linalg.norm(gv) + 1e-9)
        score = abs(float(gv_norm[2]))   # |z component| → vertical alignment in [0,1]
        if score > best_score:
            best_score = score
            best_name = name
    return best_name


def detect_most_horizontal_axis(q: np.ndarray, q_shank: np.ndarray = None) -> str:
    """Return the local axis name ('X' | 'Y' | 'Z') of the foot sensor that
    points "forward" (toward the toes).

    This dynamically finds the axis that is most parallel to the shank's
    forward direction (the sagittal plane). This is completely robust to how
    the sensor is mounted on the foot (whether Y is forward or X is forward).
    """
    if q_shank is None:
        # Fallback if no shank reference: pick highest horizontal score
        best_name = 'X'
        best_horiz = -1.0
        for name, v in AXIS_VECTORS.items():
            gv = rotate_vector_by_quaternion(v, q)
            horiz = 1.0 - abs(float(gv[2]))
            if horiz > best_horiz:
                best_horiz = horiz
                best_name = name
        return best_name

    # Find shank's vertical axis to determine its forward plane
    shank_grav = detect_most_vertical_axis(q_shank)
    
    # The shank's forward direction is its most horizontal axis
    shank_fwd = 'Y'
    best_shank_horiz = -1.0
    for name, v in AXIS_VECTORS.items():
        if name == shank_grav:
            continue
        gv = rotate_vector_by_quaternion(v, q_shank)
        horiz = 1.0 - abs(float(gv[2]))
        if horiz > best_shank_horiz:
            best_shank_horiz = horiz
            shank_fwd = name
            
    shank_fwd_vec = rotate_vector_by_quaternion(AXIS_VECTORS[shank_fwd], q_shank)
    # Project shank forward vector perfectly onto horizontal plane
    shank_fwd_horiz = np.array([shank_fwd_vec[0], shank_fwd_vec[1], 0.0])
    n = np.linalg.norm(shank_fwd_horiz)
    if n > 1e-6:
        shank_fwd_horiz = shank_fwd_horiz / n

    # The foot forward axis is the one most aligned with the shank's horizontal forward
    foot_grav = detect_most_vertical_axis(q)
    best_foot_fwd = 'X'
    best_align = -1.0
    for name, v in AXIS_VECTORS.items():
        if name == foot_grav:
            continue
        gv = rotate_vector_by_quaternion(v, q)
        gv_horiz = np.array([gv[0], gv[1], 0.0])
        gn = np.linalg.norm(gv_horiz)
        if gn > 1e-6:
            gv_horiz = gv_horiz / gn
            
        align = abs(float(np.dot(gv_horiz, shank_fwd_horiz)))
        if align > best_align:
            best_align = align
            best_foot_fwd = name
            
    return best_foot_fwd


def detect_foot_medio_lateral_axis(q_foot: np.ndarray, q_shank: np.ndarray = None) -> str:
    """Return the foot's local axis that is the ankle's medio-lateral (rotation) axis.

    This is the axis perpendicular to both:
      - the gravity axis (most vertical foot axis)
      - the forward axis (most horizontal foot axis, pointing toward toes)

    The medio-lateral axis is used as the twist decomposition axis in
    ``signed_ankle_angle`` to extract pure dorsiflexion/plantarflexion.

    If only one horizontal axis remains after removing the gravity axis and
    the forward axis, it is returned directly (process of elimination).
    """
    gravity_axis = detect_most_vertical_axis(q_foot)
    forward_axis = detect_most_horizontal_axis(q_foot, q_shank)
    all_axes = {'X', 'Y', 'Z'}
    remaining = all_axes - {gravity_axis, forward_axis}
    if len(remaining) == 1:
        return remaining.pop()
    # Fallback: if gravity and forward accidentally map to the same axis
    # (degenerate case), pick the axis most perpendicular to forward in the
    # horizontal plane.
    fwd_global = rotate_vector_by_quaternion(AXIS_VECTORS[forward_axis], q_foot)
    fwd_horiz = np.array([fwd_global[0], fwd_global[1], 0.0])
    fwd_horiz_norm = np.linalg.norm(fwd_horiz)
    if fwd_horiz_norm < 1e-6:
        return 'X'  # last-resort fallback
    fwd_horiz = fwd_horiz / fwd_horiz_norm
    best_name = 'X'
    best_perp = -1.0
    for name in (all_axes - {gravity_axis}):
        gv = rotate_vector_by_quaternion(AXIS_VECTORS[name], q_foot)
        gv_horiz = np.array([gv[0], gv[1], 0.0])
        n = np.linalg.norm(gv_horiz)
        if n < 1e-6:
            continue
        gv_horiz = gv_horiz / n
        perp = 1.0 - abs(float(np.dot(gv_horiz, fwd_horiz)))
        if perp > best_perp:
            best_perp = perp
            best_name = name
    return best_name


def identify_hinge_axis(q_prox_array: np.ndarray, q_dist_array: np.ndarray) -> np.ndarray:
    """
    Identifies the hinge axis for a joint given synchronized arrays of quaternions.
    Based on the SVD of the relative rotation vectors.
    """
    def quat_mul(q1, q2):
        w1,x1,y1,z1 = q1; w2,x2,y2,z2 = q2
        return np.array([
            w1*w2 - x1*x2 - y1*y2 - z1*z2,
            w1*x2 + x1*w2 + y1*z2 - z1*y2,
            w1*y2 - x1*z2 + y1*w2 + z1*x2,
            w1*z2 + x1*y2 - y1*x2 + z1*w2
        ])
    def quat_conj(q):
        return np.array([q[0], -q[1], -q[2], -q[3]])
        
    diff_rotvecs = []
    q_rel_ref = quat_mul(quat_conj(q_prox_array[0]), q_dist_array[0])
    
    for i in range(len(q_prox_array)):
        q_rel = quat_mul(quat_conj(q_prox_array[i]), q_dist_array[i])
        q_diff = quat_mul(quat_conj(q_rel_ref), q_rel)
        if q_diff[0] < 0:
            q_diff *= -1
            
        norm_v = np.linalg.norm(q_diff[1:])
        if norm_v > 1e-8:
            angle_rad = 2 * np.arctan2(norm_v, q_diff[0])
            rotvec = (q_diff[1:] / norm_v) * angle_rad
            diff_rotvecs.append(rotvec)
            
    diff_rotvecs = np.array(diff_rotvecs)
    if len(diff_rotvecs) == 0:
        return np.array([0, 1.0, 0])
        
    magnitudes = np.linalg.norm(diff_rotvecs, axis=1, keepdims=True)
    weighted_rotvecs = diff_rotvecs * magnitudes
    
    U, S, Vt = np.linalg.svd(weighted_rotvecs, full_matrices=False)
    hinge_axis = Vt[0]
    return hinge_axis

def extract_functional_angle(qs: np.ndarray, qf: np.ndarray, qs_ref: np.ndarray, qf_ref: np.ndarray, hinge_axis: np.ndarray) -> float:
    """Extract the ankle hinge angle using swing-twist decomposition.

    Instead of a simple dot-product projection of the rotation vector
    (which is only accurate for small angles), this uses the proper
    swing-twist decomposition to isolate the rotation component around
    the functional hinge axis identified during calibration.

    This correctly decouples the ankle angle from knee flexion even
    for large relative rotations.
    """
    q_rel_ref = quat_mul(quat_conjugate(qs_ref), qf_ref)
    q_rel     = quat_mul(quat_conjugate(qs), qf)
    q_diff    = quat_mul(quat_conjugate(q_rel_ref), q_rel)
    if q_diff[0] < 0:
        q_diff = -q_diff

    # Swing-twist decomposition: extract ONLY the twist around hinge_axis
    angle_rad = twist_angle_around_axis(q_diff, hinge_axis)
    return float(np.degrees(angle_rad))


class ROM:
    def __init__(self, offset: float = 0.0, scale: float = 1.0):
        self.timestamp: float = 0.0
        self.offset: float = offset
        self.scale: float = scale
        self.angles = np.empty((0, 2))
        self.angles_algo2 = np.empty((0, 2))
        # Sensor-local longitudinal axes used for the ankle algorithm.
        # Defaults preserve historic behaviour (X for both); set via
        # ``set_ankle_axes`` after auto-detection at calibration time.
        self.shank_axis: str = 'X'
        self.foot_axis:  str = 'X'
        self.hinge_axis: np.ndarray = None

    def set_ankle_axes(self, shank_axis: str, foot_axis: str) -> None:
        """Configure which sensor-local axes represent "along the segment" for the
        ankle calculation.  Auto-detected at calibration via
        ``detect_most_vertical_axis`` (shank) and ``detect_most_horizontal_axis``
        (foot).  Pass 'X', 'Y', or 'Z'.
        """
        if shank_axis in AXIS_VECTORS:
            self.shank_axis = shank_axis
        if foot_axis in AXIS_VECTORS:
            self.foot_axis = foot_axis

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

    # ── Knee / Hip functional (sagittal hinge projection) ────────────────────
    # Mirror del pattern ankle: dopo calibrazione funzionale (5s flex/extend),
    # angolo calcolato via swing-twist su asse hinge identificato per SVD.
    # Elimina la contaminazione da rotazione/adduzione presente in
    # angle_between_quaternions (che e' la geodesica 3D cardinale).
    def set_knee_reference(self, q_thigh_ref: np.ndarray, q_shank_ref: np.ndarray,
                           hinge_axis: np.ndarray = None) -> None:
        self.q_thigh_ref_knee = normalize(np.asarray(q_thigh_ref, dtype=float))
        self.q_shank_ref_knee = normalize(np.asarray(q_shank_ref, dtype=float))
        self.knee_hinge_axis  = hinge_axis if hinge_axis is not None else None
        self.offset = 0.0

    def set_hip_reference(self, q_pelvis_ref: np.ndarray, q_thigh_ref: np.ndarray,
                          hinge_axis: np.ndarray = None) -> None:
        self.q_pelvis_ref_hip = normalize(np.asarray(q_pelvis_ref, dtype=float))
        self.q_thigh_ref_hip  = normalize(np.asarray(q_thigh_ref,  dtype=float))
        self.hip_hinge_axis   = hinge_axis if hinge_axis is not None else None
        self.offset = 0.0

    @staticmethod
    def calculate_knee_angle_functional(
        q_thigh: np.ndarray, q_shank: np.ndarray,
        q_thigh_ref: np.ndarray, q_shank_ref: np.ndarray,
        hinge_axis: np.ndarray,
    ) -> float:
        return extract_functional_angle(q_thigh, q_shank, q_thigh_ref, q_shank_ref, hinge_axis)

    @staticmethod
    def calculate_hip_angle_functional(
        q_pelvis: np.ndarray, q_thigh: np.ndarray,
        q_pelvis_ref: np.ndarray, q_thigh_ref: np.ndarray,
        hinge_axis: np.ndarray,
    ) -> float:
        return extract_functional_angle(q_pelvis, q_thigh, q_pelvis_ref, q_thigh_ref, hinge_axis)

    # ── Ankle methods (relative-quaternion approach) ──────────────────────────
    def set_ankle_reference(self, q_shank_ref: np.ndarray, q_foot_ref: np.ndarray, hinge_axis: np.ndarray = None) -> None:
        """Store calibration-pose quaternions for the stable relative-quaternion path.

        Call this immediately after `ankle_functional_calibration` with the same
        quaternions used during calibration.  From this point onwards,
        `get_ankle_angle` computes the *change* in relative orientation between
        shank and foot since the neutral pose, giving 0° in standing and correct
        dorsi/plantarflexion values during gait — free from global-frame sign ambiguity.
        """
        self.q_shank_ref = normalize(np.asarray(q_shank_ref, dtype=float))
        self.q_foot_ref  = normalize(np.asarray(q_foot_ref,  dtype=float))
        self.hinge_axis  = hinge_axis if hinge_axis is not None else None
        self.offset      = 0.0  # zeroing is handled by the relative-quat formula

    @staticmethod
    def ankle_functional_calibration(
        q_shank: np.ndarray,
        q_foot: np.ndarray,
        foot_axis: str = 'X',
        shank_axis: str = 'X',
    ) -> float:
        """Return the ankle angle at neutral pose (used as calibration offset).

        Subtracting this offset from every subsequent measurement centres the
        signal on 0° at neutral.  The two ``*_axis`` arguments must match the
        ones used at runtime (typically auto-detected at calibration time).
        """
        return ankle_angle_between_quaternions(q_shank, q_foot, foot_axis, shank_axis)

    @staticmethod
    def calculate_ankle_angle(
        q_shank: np.ndarray,
        q_foot: np.ndarray,
        offset: float,
        foot_axis: str = 'X',
        shank_axis: str = 'X',
        q_shank_ref: np.ndarray = None,
        q_foot_ref:  np.ndarray = None,
        hinge_axis: np.ndarray = None,
    ) -> float:
        """Return the calibrated ankle angle in degrees.
        
        If ``hinge_axis`` is provided (from functional calibration), uses the 
        SVD-based projection algorithm for complete decoupling from the knee.
        Otherwise falls back to the legacy algorithm.
        """
        if q_shank_ref is not None and q_foot_ref is not None and hinge_axis is not None:
            return extract_functional_angle(q_shank, q_foot, q_shank_ref, q_foot_ref, hinge_axis)

        # Fallback if no functional calibration was done
        if q_shank_ref is not None and q_foot_ref is not None:
            shank_vert = detect_most_vertical_axis(q_shank_ref)
            all_axes = {'X', 'Y', 'Z'}
            remaining = all_axes - {shank_vert, shank_axis}
            shank_ml = remaining.pop() if len(remaining) == 1 else 'Y'
            
            return signed_ankle_angle(
                q_shank, q_foot, q_shank_ref, q_foot_ref,
                foot_axis=foot_axis,
                shank_long_axis=shank_axis,
                foot_fwd_axis=foot_axis,
                shank_ml_axis=shank_ml,
            )
        return ankle_angle_between_quaternions(q_shank, q_foot, foot_axis, shank_axis) - offset

    def get_ankle_angle(self, q_shank: np.ndarray, q_foot: np.ndarray) -> float:
        """Compute, store and return the calibrated ankle angle, using the
        per-instance ``shank_axis`` / ``foot_axis`` configured via ``set_ankle_axes``.

        Robustness: clamp to physiological ±50° and reject magnetometer-induced
        spikes (Δ > 30° vs previous sample at ~60-100Hz is non-physiological).
        Without this, a yaw flip on the foot IMU's onboard 9-DOF Kalman can push
        the angle to ±100°/±300° for a few samples and corrupt the saved trace.
        """
        if hasattr(self, 'q_shank_ref') and hasattr(self, 'q_foot_ref'):
            angle = ROM.calculate_ankle_angle(
                q_shank, q_foot, self.offset,
                foot_axis=self.foot_axis, shank_axis=self.shank_axis,
                q_shank_ref=self.q_shank_ref, q_foot_ref=self.q_foot_ref,
                hinge_axis=self.hinge_axis
            )
        else:
            angle = ankle_angle_between_quaternions(
                q_shank, q_foot, self.foot_axis, self.shank_axis,
            ) - self.offset

        angle *= self.scale
        ANKLE_MIN, ANKLE_MAX, SPIKE_DELTA = -50.0, 50.0, 30.0
        angle = max(ANKLE_MIN, min(ANKLE_MAX, angle))
        if self.angles.shape[0] > 0:
            prev = float(self.angles[-1, 1])
            if abs(angle - prev) > SPIKE_DELTA:
                angle = prev
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
