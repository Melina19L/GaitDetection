"""FOG H5 offline kinematic reconstruction + gait detection + Freeze Index.

Input : a MAPP `recording_data.h5` (COMETA WaveX IMU + WIMU MK3).
Output: 3 PNGs for a chosen time window (here 800-860 s = 13:20-14:20):
  * bilateral knee / hip / ankle joint angles
  * Method-1 gait detection on both feet (HS/TO + stance/swing)
  * Freeze Index per sensor (8 COMETA blocks + 5 WIMU devices)

Calibration: first 10 s of the recording (subject standing still) gives the
neutral-pose reference for every segment.

Reuses the live thesis system maths (`stimulator.closed_loop`,
`stimulator.gait_detection_imu`) so offline numbers match the real-time pipeline.

Standalone: hardcoded paths/constants at the top, run directly.
"""
import os
import sys
import numpy as np
import h5py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ── reuse live-system maths ────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
# locate FES/GUI regardless of how deep this script sits under FES/
_GUI = next((os.path.join(p, "GUI") for p in
             (os.path.join(_HERE, *([".."] * n)) for n in range(1, 5))
             if os.path.isdir(os.path.join(p, "GUI", "stimulator"))), None)
if _GUI and _GUI not in sys.path:
    sys.path.insert(0, _GUI)
import imufusion
from stimulator.closed_loop import (
    angle_between_quaternions,
    rotate_vector_by_quaternion,
    detect_most_vertical_axis,
    detect_most_horizontal_axis,
    AXIS_VECTORS,
)
from stimulator.gait_detection_imu import identify_gait_phases, identify_valleys

# ── CONFIG ─────────────────────────────────────────────────────────────────
_ROOT = ("/Users/chiaracazzoli/Library/CloudStorage/OneDrive-epfl.ch/"
         "File di Daniel Leal - Recording sessions/Group_FOG/")
# Per-SUBJECT config. Sensor placement can differ per subject, so each carries
# its own WIMU device map and candidate leg blocks. `leg_blocks` gives the two
# COMETA blocks per side as an UNORDERED pair -- which is thigh vs shin is
# resolved automatically per session (resolve_leg_map, via physiological ankle
# ROM), so a mislabelled/inverted mounting is corrected without manual checking.
# Session times are seconds from video start (= first camera frame).
SUBJECTS = {
    "FOG002": {
        "base": _ROOT + "FOG002/MAPP/",
        "wimu_map": {"R_foot": "dev5", "L_foot": "dev2",
                     "wrist": "dev3", "cervical": "dev6", "pelvis": "dev7"},
        "leg_blocks": {"R": (0, 4), "L": (1, 5)},   # unordered; auto-resolved
        "calib": (0.0, 10.0),
        "sessions": [
            {"tag": "narrow", "folder": "Narrow Corridor_1",
             "win": (800.0, 860.0), "fog_events": [(831.0, 837.0)],
             "walk_ref": (810.0, 822.0),
             # clean turn (turn-R 12:13.2-12:24.21 + turn-L 12:24.75-12:34.0):
             # matched-activity negative (FOG occurred during a turn)
             "turn_ref": (733.2, 754.0)},
            {"tag": "eight", "folder": "8 Shape Circuit_1",
             "win": (125.0, 195.0), "fog_events": [(153.0, 158.0), (160.0, 163.0)],
             "walk_ref": (134.0, 143.0),
             # clean turn (turn-R 1:03.11-1:10.24 + turn-L 1:10.25-1:16.47), no FOG
             "turn_ref": (63.11, 76.47)},
        ],
    },
    "FOG004": {
        # COMETA muscle montage (from the placement sheet): RF=thigh, TA=shin,
        # BF=thigh(post), GAS=shin(post). Block index = sensor number - 1.
        # Explicit map (anterior muscles): R thigh=RF(blk0)/shin=TA(blk2);
        # L thigh=RF(blk1)/shin=TA(blk3). Bypasses auto-resolve.
        "base": _ROOT + "FOG004/MAPP/",
        "wimu_map": {"R_foot": "dev7", "L_foot": "dev2",
                     "pelvis": "dev5", "cervical": "dev3", "wrist": "dev6"},
        "cometa_map": {("R", "thigh"): 0, ("R", "shin"): 2,
                       ("L", "thigh"): 1, ("L", "shin"): 3},
        "calib": (0.0, 10.0),
        "sessions": [
            # Narrow Corridor 5:05-6:00 ; FOG 5:24-5:26 ; straight walk 5:08-5:15
            {"tag": "narrow", "folder": "Narrow Corridor_1",
             "win": (305.0, 360.0), "fog_events": [(324.0, 326.0)],
             "walk_ref": (308.0, 315.0)},
            # 8 Shape: R_foot enumerated as dev1 here (no dev7)
            # 1:30-3:00 ; FOG 1:57.7-2:05, 2:11.2-2:12 ; walk 1:41-1:49.4
            {"tag": "eight_a", "folder": "8 Shape Circuit_1",
             "wimu_map": {"R_foot": "dev1", "L_foot": "dev2",
                          "pelvis": "dev5", "cervical": "dev3", "wrist": "dev6"},
             "win": (90.0, 180.0), "fog_events": [(117.7, 125.0), (131.2, 132.0)],
             "walk_ref": (101.0, 109.4)},
            # 8 Shape 3:00-4:30 ; FOG 3:09.1-3:11.3, 3:17-3:19, 4:11-4:13 ; walk 3:54.3-4:04.3
            {"tag": "eight_b", "folder": "8 Shape Circuit_1",
             "wimu_map": {"R_foot": "dev1", "L_foot": "dev2",
                          "pelvis": "dev5", "cervical": "dev3", "wrist": "dev6"},
             "win": (180.0, 270.0),
             "fog_events": [(189.1, 191.3), (197.0, 199.0), (251.0, 253.0)],
             "walk_ref": (234.3, 244.3)},
        ],
    },
    "FOG006": {
        # COMETA same muscle montage as the placement sheet (RF=thigh, TA=shin).
        # Only 3 WIMU present (dev2,5,6): R_foot=dev6, L_foot=dev2, pelvis=dev5
        # (the given cervical=6 duplicated R_foot and wrist=dev3 is absent).
        "base": _ROOT + "FOG006/MAPP/",
        "wimu_map": {"R_foot": "dev6", "L_foot": "dev2", "pelvis": "dev5"},
        "cometa_map": {("R", "thigh"): 0, ("R", "shin"): 2,
                       ("L", "thigh"): 1, ("L", "shin"): 3},
        "calib": (0.0, 10.0),
        "sessions": [
            # Narrow Corridor: walk 7:02-7:12.5, turn-R 7:13.5-7:21.6,
            # turn-L 7:22.5-7:32.9, FOG 7:20-7:22.3
            {"tag": "narrow", "folder": "Narrow Corridor_1",
             "win": (420.0, 455.0), "fog_events": [(440.0, 442.3)],
             "walk_ref": (422.0, 432.5), "turn_ref": (442.5, 452.9)},
        ],
    },
}


def _build_sessions():
    out = []
    for sid, s in SUBJECTS.items():
        for ses in s["sessions"]:
            out.append({"tag": f"{sid.lower()}_{ses['tag']}",
                        "path": s["base"] + ses["folder"] + "/recording_data.h5",
                        "win": ses["win"], "calib": s["calib"],
                        "fog_events": ses["fog_events"], "walk_ref": ses["walk_ref"],
                        "turn_ref": ses.get("turn_ref"),
                        "wimu_map": ses.get("wimu_map", s["wimu_map"]),
                        "leg_blocks": s.get("leg_blocks"),
                        "cometa_map": s.get("cometa_map")})
    return out


SESSIONS = _build_sessions()
# Time base: cameras + sensors share an ABSOLUTE device clock. The `logs/events`
# `elapsed` column is a SEPARATE drifting clock and must NOT be used. Videos are
# aligned to the absolute timestamp; video t=0 = first camera frame, so T0 is set
# at runtime to the first camera frame timestamp.
# Current-session globals -- set by _apply_session(), do not edit here.
H5_PATH = ""; T0 = 0.0; WIN = (0.0, 0.0); CALIB = (0.0, 10.0)
TAG = ""; FOG_EVENTS = []; FI_WALK_REF = (0.0, 0.0); TURN_REF = None
WIMU_DEV = {}; LEG_BLOCKS = {}; COMETA_MAP = None    # from subject config
COMETA_BLOCK = {}                 # explicit COMETA_MAP or resolved per session
FUSE_FROM = 0.0                   # fuse COMETA continuously from here through WIN[1]

# COMETA 72 cols = 8 sensor blocks x 9 ch [acc(g) 0:3, gyro(deg/s) 3:6, mag 6:9].
# Per-side thigh/shin block assignment is resolved at runtime (S1/S2 vs S5/S6 was
# inverted for FOG002; auto-resolution avoids hardcoding it per subject).
COMETA_FS = 2000.0

# WIMU 8 cols = [counter, free_accel_xyz (m/s^2, gravity-removed), quat_wxyz].
# Verified: cols 1-3 read ~0 at rest and peak ~6g at foot strike -> free
# acceleration, NOT gyroscope (WIMU exports no raw gyro). Sagittal angular
# velocity for gait is reconstructed from the quaternion (quat_angular_velocity).

# Freeze Index
FI_WIN = 4.0                     # s
FI_STEP = 0.25                   # s
FI_LOCO = (0.5, 3.0)             # locomotor band (Hz)
FI_FREEZE = (3.0, 8.0)          # freeze band (Hz)
FI_THRESHOLD = 2.0               # plotted reference line

OUT_DIR = _HERE                  # save PNGs next to this script


# ── loading / slicing ──────────────────────────────────────────────────────
def load_cometa(f):
    d = f["Cometa/WaveX_IMU/data"]
    t = f["Cometa/WaveX_IMU/timestamps"][:] - T0
    return d, t            # d is h5 dataset (lazy), t relative seconds


def load_wimu(f, dev):
    d = f[f"WIMU/WIMU_MK3/data_{dev}"][:]
    t = f[f"WIMU/WIMU_MK3/timestamps_{dev}"][:] - T0
    return d, t


def win_idx(t, lo, hi):
    m = (t >= lo) & (t <= hi)
    return np.where(m)[0]


# ── COMETA parse + fusion ──────────────────────────────────────────────────
def cometa_block(d, block, i0, i1):
    """Return acc(g) (N,3) and gyro(deg/s) (N,3) for one sensor block, rows i0:i1."""
    seg = d[i0:i1, block * 9:block * 9 + 9].astype(np.float64)
    return seg[:, 0:3], seg[:, 3:6]


def fuse(acc_g, gyro_dps, fs):
    """imufusion AHRS (no magnetometer) -> quaternion array (N,4) w,x,y,z."""
    ahrs = imufusion.Ahrs()
    dt = 1.0 / fs
    q = np.empty((len(acc_g), 4))
    for i in range(len(acc_g)):
        ahrs.update_no_magnetometer(gyro_dps[i], acc_g[i], dt)
        q[i] = ahrs.quaternion.wxyz
    return q


def avg_quat(q):
    """Sign-aligned mean quaternion, normalized."""
    ref = q[0]
    qa = np.where((q @ ref)[:, None] < 0, -q, q)
    m = qa.mean(axis=0)
    return m / np.linalg.norm(m)


def long_axis_pitch(q, axis_vec):
    """Elevation of a sensor-local axis above the horizontal plane (deg).

    Reads only the global-Z (gravity) component of the rotated axis, so it is
    independent of heading/yaw -- essential for cross-system (COMETA<->WIMU)
    angles where the two devices do not share a yaw reference.
    """
    g = rotate_vector_by_quaternion(axis_vec, q)
    g = g / (np.linalg.norm(g) + 1e-9)
    return np.degrees(np.arcsin(np.clip(g[2], -1.0, 1.0)))


def _qmul_arr(a, b):
    w1, x1, y1, z1 = a.T
    w2, x2, y2, z2 = b.T
    return np.stack([w1*w2 - x1*x2 - y1*y2 - z1*z2,
                     w1*x2 + x1*w2 + y1*z2 - z1*y2,
                     w1*y2 - x1*z2 + y1*w2 + z1*x2,
                     w1*z2 + x1*y2 - y1*x2 + z1*w2], axis=1)


def quat_angular_velocity(q, t):
    """Body-frame angular velocity (deg/s, shape (N,3)) from a quaternion stream.

    The WIMU exports orientation (quaternion) + free-acceleration but NO raw
    gyroscope. Method-1 gait detection needs the sagittal angular velocity, so
    we reconstruct it: omega_body = 2 * conj(q) (x) dq/dt. Central-difference
    derivative is noisy, so low-pass at min(8Hz, ~Nyquist).
    """
    from scipy.signal import butter, filtfilt
    q = q / np.linalg.norm(q, axis=1, keepdims=True)
    qdot = np.gradient(q, t, axis=0)
    qconj = q * np.array([1.0, -1.0, -1.0, -1.0])
    w = 2.0 * _qmul_arr(qconj, qdot)[:, 1:]          # rad/s, body frame
    wdeg = np.degrees(w)
    fs = 1.0 / np.median(np.diff(t))
    fc = min(8.0, 0.45 * fs)
    b, a = butter(2, fc / (fs / 2.0), "low")
    return filtfilt(b, a, wdeg, axis=0)


# ── joint angles ───────────────────────────────────────────────────────────
def nearest_match(t_src, t_tgt):
    """For each t_tgt, index into t_src of nearest sample."""
    idx = np.searchsorted(t_src, t_tgt)
    idx = np.clip(idx, 1, len(t_src) - 1)
    left = t_src[idx - 1]
    right = t_src[idx]
    idx -= (np.abs(t_tgt - left) < np.abs(t_tgt - right)).astype(int)
    return idx


# ── Freeze Index ───────────────────────────────────────────────────────────
def freeze_index(sig, fs):
    """Return (centers, FI, freeze_power). freeze_power = absolute power in the
    3-8Hz band; used to gate out 'quiet' false positives (standing/slow turns)
    where the FI ratio is high only because the locomotor band is near zero."""
    n = int(round(FI_WIN * fs))
    step = int(round(FI_STEP * fs))
    if len(sig) < n:
        return np.array([]), np.array([]), np.array([])
    freqs = np.fft.rfftfreq(n, 1.0 / fs)
    loco_m = (freqs >= FI_LOCO[0]) & (freqs < FI_LOCO[1])
    frz_m = (freqs >= FI_FREEZE[0]) & (freqs < FI_FREEZE[1])
    centers, fis, pwrs = [], [], []
    win = np.hanning(n)
    for s in range(0, len(sig) - n + 1, step):
        seg = sig[s:s + n]
        seg = (seg - seg.mean()) * win
        p = np.abs(np.fft.rfft(seg)) ** 2
        loco = p[loco_m].sum()
        frz = p[frz_m].sum()
        fis.append(frz / loco if loco > 1e-12 else 0.0)
        pwrs.append(frz)
        centers.append((s + n / 2.0) / fs)
    return np.asarray(centers), np.asarray(fis), np.asarray(pwrs)


# ── gait detection (Method 1) ──────────────────────────────────────────────
def detect_gait(gyro_y, t, fs):
    """Method-1 style: mid-swing positive peaks + valleys on foot sagittal
    angular velocity (gyro-Y reconstructed from the quaternion).

    Heel-strike = first valley after a peak; toe-off = valley before a peak,
    following the IMUGaitFSM Method-1 valley/peak distance rule. Returns
    dict with hs/to times and a stance/swing phase timeline.
    """
    height = 0.3 * np.percentile(np.abs(gyro_y), 95)
    dist = int(0.3 * fs)
    peaks, _ = identify_gait_phases(gyro_y, peak_threshold=height, distance=dist,
                                    min_distance_between_peaks=dist, prominence=height)
    valleys = identify_valleys(gyro_y, valley_height=0.0, distance_valleys=dist,
                               min_distance_between_valleys=dist)
    # classify: HS = valley just AFTER a mid-swing peak; TO = valley just BEFORE
    hs, to = [], []
    for v in valleys:
        prev_pk = peaks[peaks < v]
        next_pk = peaks[peaks > v]
        d_prev = v - prev_pk[-1] if len(prev_pk) else np.inf
        d_next = next_pk[0] - v if len(next_pk) else np.inf
        (hs if d_prev <= d_next else to).append(v)
    hs = np.array(sorted(hs), dtype=int)
    to = np.array(sorted(to), dtype=int)
    return {"peaks": peaks, "hs": hs, "to": to,
            "t_hs": t[hs] if len(hs) else np.array([]),
            "t_to": t[to] if len(to) else np.array([])}


def ankle_series(qsh, foot_name, qwi, twi, t_co_run, calib_m, win=None):
    """Sagittal ankle angle (deg) for a shin-quaternion + foot WIMU pair over
    `win` (default WIN). Gravity-referenced long-axis pitch difference
    (yaw-drift-immune)."""
    win = WIN if win is None else win
    shin_ref = avg_quat(qsh[calib_m])
    fcm = (twi[foot_name] >= CALIB[0]) & (twi[foot_name] <= CALIB[1])
    foot_ref = avg_quat(qwi[foot_name][fcm])
    sh_axis = AXIS_VECTORS[detect_most_vertical_axis(shin_ref)]
    ft_axis = AXIS_VECTORS[detect_most_horizontal_axis(foot_ref)]
    off = long_axis_pitch(foot_ref, ft_axis) - long_axis_pitch(shin_ref, sh_axis)
    tf = twi[foot_name]
    fm = (tf >= win[0]) & (tf <= win[1])
    sidx = nearest_match(t_co_run, tf[fm])
    qsh_win, qf_win = qsh[sidx], qwi[foot_name][fm]
    ank = np.array([long_axis_pitch(qf_win[k], ft_axis)
                    - long_axis_pitch(qsh_win[k], sh_axis)
                    for k in range(len(qf_win))]) - off
    return tf[fm], ank


def resolve_leg_map(blk_quat, qwi, twi, t_co_run, calib_m):
    """Auto-resolve thigh vs shin per side from the unordered LEG_BLOCKS pair.

    The shank sits just above the foot so it moves WITH the foot -> small ankle
    (shank<->foot) pitch ROM; the thigh swings more relative to the foot -> larger
    ROM. So shin = the candidate with the SMALLER ankle ROM. Evaluated over the
    CLEAN-WALKING window (FI_WALK_REF), not the full WIN -- turns inflate the
    pitch difference for every block and destroy the separation.
    """
    cmap = {}
    for side, (a, b) in LEG_BLOCKS.items():
        foot = "R_foot" if side == "R" else "L_foot"
        _, ank_a = ankle_series(blk_quat[a], foot, qwi, twi, t_co_run, calib_m, FI_WALK_REF)
        _, ank_b = ankle_series(blk_quat[b], foot, qwi, twi, t_co_run, calib_m, FI_WALK_REF)
        rom_a, rom_b = np.ptp(ank_a), np.ptp(ank_b)
        shin, thigh = (a, b) if rom_a < rom_b else (b, a)
        cmap[(side, "shin")] = shin
        cmap[(side, "thigh")] = thigh
        print(f"[MAP {side}] walk-ankle-ROM blk{a}={rom_a:.0f} blk{b}={rom_b:.0f}  "
              f"-> shin=blk{shin} thigh=blk{thigh}")
    return cmap


# ── main ───────────────────────────────────────────────────────────────────
def _apply_session(cfg):
    global H5_PATH, WIN, CALIB, TAG, FOG_EVENTS, FI_WALK_REF, TURN_REF
    global WIMU_DEV, LEG_BLOCKS, COMETA_MAP
    H5_PATH = cfg["path"]; WIN = cfg["win"]; CALIB = cfg["calib"]
    TAG = cfg["tag"]; FOG_EVENTS = cfg["fog_events"]; FI_WALK_REF = cfg["walk_ref"]
    TURN_REF = cfg.get("turn_ref")
    WIMU_DEV = cfg["wimu_map"]; LEG_BLOCKS = cfg.get("leg_blocks"); COMETA_MAP = cfg.get("cometa_map")


def main():
    for cfg in SESSIONS:
        print(f"\n===== {cfg['tag']} =====")
        _apply_session(cfg)
        try:
            run_session()
        except Exception as e:
            print(f"[SKIP {cfg['tag']}] {type(e).__name__}: {e}")


def run_session():
    global T0
    f = h5py.File(H5_PATH, "r")
    T0 = float(f["Cameras/camera_2/frames"][0]["timestamp"])  # video t=0 (absolute)
    print(f"[TIME] T0 (first camera frame) = {T0:.3f}  -> window absolute "
          f"{T0+WIN[0]:.1f}-{T0+WIN[1]:.1f}")

    global COMETA_BLOCK

    # ---- COMETA: fuse the candidate leg blocks continuously [FUSE_FROM .. WIN[1]] ----
    d_co, t_co = load_cometa(f)
    fi0 = win_idx(t_co, FUSE_FROM, WIN[1])
    c0, c1 = fi0[0], fi0[-1] + 1
    t_co_run = t_co[c0:c1]
    print(f"[COMETA] fusing rows {c0}:{c1} ({c1-c0} samp, "
          f"{t_co_run[0]:.1f}-{t_co_run[-1]:.1f}s)")
    calib_m = (t_co_run >= CALIB[0]) & (t_co_run <= CALIB[1])
    win_m = (t_co_run >= WIN[0]) & (t_co_run <= WIN[1])

    # blocks to fuse: explicit COMETA_MAP, else the unordered LEG_BLOCKS pairs
    blocks = (set(COMETA_MAP.values()) if COMETA_MAP
              else {b for pair in LEG_BLOCKS.values() for b in pair})
    blk_quat = {}
    for blk in blocks:
        acc, gyr = cometa_block(d_co, blk, c0, c1)
        blk_quat[blk] = fuse(acc, gyr, COMETA_FS)

    # ---- WIMU quats + times (needed before resolving the COMETA leg map) ----
    qwi, twi, dwi = {}, {}, {}
    for name, dev in WIMU_DEV.items():
        d, t = load_wimu(f, dev)
        dwi[name], twi[name] = d, t
        qwi[name] = d[:, 4:8]

    def wimu_calib_ref(name):
        m = (twi[name] >= CALIB[0]) & (twi[name] <= CALIB[1])
        return avg_quat(qwi[name][m])

    # ---- COMETA leg map: explicit muscle montage, else auto-resolve thigh/shin ----
    if COMETA_MAP:
        COMETA_BLOCK = dict(COMETA_MAP)
        print(f"[MAP] explicit {{ {', '.join(f'{s}.{seg}=blk{b}' for (s,seg),b in COMETA_BLOCK.items())} }}")
    else:
        COMETA_BLOCK = resolve_leg_map(blk_quat, qwi, twi, t_co_run, calib_m)
    qco = {key: blk_quat[blk] for key, blk in COMETA_BLOCK.items()}

    # ============ KNEE (COMETA-COMETA, same fused frame) ============
    angles = {}
    for side in ("R", "L"):
        qt = qco[(side, "thigh")]
        qs = qco[(side, "shin")]
        off = angle_between_quaternions(avg_quat(qt[calib_m]), avg_quat(qs[calib_m]))
        knee = np.array([angle_between_quaternions(qt[i], qs[i]) for i in np.where(win_m)[0]]) - off
        angles[(side, "knee")] = (t_co_run[win_m], knee)
        print(f"[KNEE {side}] off={off:.1f}  ROM={np.ptp(knee):.1f}  "
              f"min={knee.min():.1f} max={knee.max():.1f}")

    # ============ HIP (pelvis WIMU <-> thigh COMETA) ============
    pelvis_ref = wimu_calib_ref("pelvis")
    tp = twi["pelvis"]
    pm = (tp >= WIN[0]) & (tp <= WIN[1])
    tp_win = tp[pm]
    for side in ("R", "L"):
        qt = qco[(side, "thigh")]
        thigh_ref = avg_quat(qt[calib_m])
        off = angle_between_quaternions(pelvis_ref, thigh_ref)
        midx = nearest_match(t_co_run, tp_win)         # thigh sample per pelvis sample
        hip = np.array([angle_between_quaternions(qwi["pelvis"][j], qt[midx[k]])
                        for k, j in enumerate(np.where(pm)[0])]) - off
        angles[(side, "hip")] = (tp_win, hip)
        print(f"[HIP {side}] off={off:.1f}  ROM={np.ptp(hip):.1f}  "
              f"min={hip.min():.1f} max={hip.max():.1f}")

    # ============ ANKLE (shin COMETA <-> foot WIMU) ============
    # Sagittal long-axis pitch difference (yaw-drift-immune); see ankle_series.
    for side in ("R", "L"):
        foot = "R_foot" if side == "R" else "L_foot"
        tf_win, ankle = ankle_series(qco[(side, "shin")], foot, qwi, twi,
                                     t_co_run, calib_m)
        angles[(side, "ankle")] = (tf_win, ankle)
        print(f"[ANKLE {side}] ROM={np.ptp(ankle):.1f}  "
              f"min={ankle.min():.1f} max={ankle.max():.1f}")

    # ============ gait (Method 1, both feet) ============
    gait = {}
    for side, foot in (("R", "R_foot"), ("L", "L_foot")):
        t = twi[foot]
        fm = (t >= WIN[0]) & (t <= WIN[1])
        fs = 1.0 / np.median(np.diff(t[fm]))
        # reconstruct foot angular velocity from quaternion; sagittal (ML) axis
        # = body axis carrying the swing rotation (largest variance)
        w = quat_angular_velocity(qwi[foot][fm], t[fm])
        gy = w[:, int(np.argmax(w.std(axis=0)))]
        # orient so mid-swing is a positive peak (Method-1 convention)
        if abs(gy.min()) > abs(gy.max()):
            gy = -gy
        g = detect_gait(gy, t[fm], fs)
        g["t"], g["gy"], g["fs"] = t[fm], gy, fs
        gait[side] = g
        nhs, nto = len(g["hs"]), len(g["to"])
        cyc = np.median(np.diff(g["t_hs"])) if nhs > 1 else float("nan")
        print(f"[GAIT {side}] fs={fs:.1f}  HS={nhs} TO={nto}  median cycle={cyc:.2f}s")

    # ============ Freeze Index (13 sensors) ============
    # precompute motion-norm per sensor over the whole fused range / full WIMU,
    # so FI can be evaluated on any sub-window (analysis WIN and turn-ref).
    # only sensors with KNOWN placement: the resolved COMETA leg blocks + WIMU.
    # The other COMETA blocks (unknown placement) are excluded from the analysis.
    com_norm = {}
    for blk in set(COMETA_BLOCK.values()):
        acc, _ = cometa_block(d_co, blk, c0, c1)
        com_norm[blk] = np.sqrt((acc ** 2).sum(1))
    wimu_norm = {n: np.sqrt((dwi[n][:, 1:4].astype(float) ** 2).sum(1)) for n in WIMU_DEV}

    def build_fi(lo, hi):
        out, wm = {}, (t_co_run >= lo) & (t_co_run <= hi)
        for (side, seg), blk in COMETA_BLOCK.items():
            out[f"COM_{side}_{seg}"] = freeze_index(com_norm[blk][wm], COMETA_FS) + (lo,)
        for name in WIMU_DEV:
            t = twi[name]; m = (t >= lo) & (t <= hi)
            fs = 1.0 / np.median(np.diff(t[m]))
            out[f"WIMU_{name}"] = freeze_index(wimu_norm[name][m], fs) + (lo,)
        return out

    fi = build_fi(*WIN)
    fi_turn = build_fi(*TURN_REF) if TURN_REF else None
    for k, v in fi.items():
        if len(v[1]):
            print(f"[FI] {k:16s} min={v[1].min():.2f} max={v[1].max():.2f} mean={v[1].mean():.2f}")

    rank = rank_sensors(fi, fi_turn)
    detect = fog_detector(fi, rank, fi_turn)

    f.close()
    make_figures(angles, gait, fi, detect)
    make_rank_figure(rank)


# ── FOG-vs-walk sensor separability ─────────────────────────────────────────
def _sep(fog, neg):
    """Cohen's d and AUC of FOG vs a negative sample."""
    if len(fog) < 2 or len(neg) < 2:
        return 0.0, 0.5
    sp = np.sqrt((fog.var(ddof=1) + neg.var(ddof=1)) / 2.0)
    d = (fog.mean() - neg.mean()) / sp if sp > 1e-9 else 0.0
    auc = np.greater.outer(fog, neg).mean() + 0.5 * np.equal.outer(fog, neg).mean()
    return d, auc


def rank_sensors(fi, fi_turn=None):
    """Per sensor, separability of its raw FI for FOG vs TWO matched negatives:
      * walk = clean straight-walking reference (easy contrast / baseline)
      * turn = clean turning reference, NO freeze (fi_turn) -- the matched-activity
               control, since the FOG occurred during a turn. A sensor that only
               separates FOG from walking but NOT from a clean turn will produce
               turn false positives; high d/AUC vs turn = a genuine FOG detector.
    Sorted by the turn-contrast d (the meaningful one) when available.
    """
    def in_evt(c, off):
        tt = c + off
        m = np.zeros(len(tt), bool)
        for a, b in FOG_EVENTS:
            m |= (tt >= a) & (tt <= b)
        return m

    out = []
    for k, (c, v, pwr, off) in fi.items():
        if not len(v):
            continue
        tt = c + off
        fog = v[in_evt(c, off)]
        walk = v[(tt >= FI_WALK_REF[0]) & (tt <= FI_WALK_REF[1])]
        d_w, auc_w = _sep(fog, walk)
        if fi_turn is not None and k in fi_turn and len(fi_turn[k][1]):
            d_t, auc_t = _sep(fog, fi_turn[k][1])
        else:
            d_t, auc_t = float("nan"), float("nan")
        out.append((k, d_w, auc_w, d_t, auc_t))
    key = 3 if fi_turn is not None else 1
    out.sort(key=lambda r: (r[key] if r[key] == r[key] else -9), reverse=True)
    print(f"[RANK] FOG {FOG_EVENTS} | neg: walk={FI_WALK_REF} vs turn={TURN_REF}")
    print(f"   {'sensor':16s} {'d_walk':>7} {'AUC_w':>6} | {'d_turn':>7} {'AUC_turn':>8}")
    for k, dw, aw, dt, at in out:
        print(f"   {k:16s} {dw:+7.2f} {aw:6.2f} | {dt:+7.2f} {at:8.2f}")
    return out


def _mask_to_intervals(times, mask):
    out, i, n = [], 0, len(mask)
    while i < n:
        if mask[i]:
            j = i
            while j + 1 < n and mask[j + 1]:
                j += 1
            out.append((times[i], times[j]))
            i = j + 1
        else:
            i += 1
    return out


DET_MIN_DUR = 1.0       # s, drop detections shorter than this (blips)


def fog_detector(fi, rank, fi_turn=None):
    """Single best-sensor FOG detection, tuned to minimise false positives.

    The barplot showed one sensor (top of the turn-contrast ranking, e.g.
    COM_R_shin) separates FOG from BOTH clean walking and clean turning. So we
    use that sensor alone and set its threshold ABOVE both the clean-walk AND the
    clean-turn FI level (each mean+2SD). A normal walk or turn stays below ->
    no false positive; only a freeze (FI above the turn level) fires.
    Sustained >= DET_MIN_DUR.
    """
    best = rank[0][0]                      # ranked by FOG-vs-turn separability
    c, v, pwr, off = fi[best]
    tt = c + off
    wm = (tt >= FI_WALK_REF[0]) & (tt <= FI_WALK_REF[1])
    thr = v[wm].mean() + 2.0 * v[wm].std()
    src = "walk+2SD"
    if fi_turn is not None and best in fi_turn and len(fi_turn[best][1]):
        tv = fi_turn[best][1]
        tthr = tv.mean() + 2.0 * tv.std()
        if tthr > thr:
            thr, src = tthr, "turn+2SD"
    intervals = [(a, b) for a, b in _mask_to_intervals(tt, v > thr)
                 if b - a >= DET_MIN_DUR]
    print(f"[DETECT] sensor={best} thr={thr:.2f} ({src})  "
          f"{len(intervals)} interval(s) (>= {DET_MIN_DUR}s):")
    for a, b in intervals:
        print(f"   {a:.1f}-{b:.1f}s")
    return {"sensor": best, "thr": thr, "intervals": intervals}


# ── figures ────────────────────────────────────────────────────────────────
def _detect_shade(ax, detect, label=False):
    """Hatched orange band where the best sensor's FI detector fires (FOG)."""
    for i, (a, b) in enumerate(detect["intervals"]):
        ax.axvspan(a, b, facecolor="none", edgecolor="darkorange", hatch="//",
                   lw=0, alpha=0.9,
                   label=f"FI detect ({detect['sensor']})" if label and i == 0 else None)


def _fog_shade(ax, label=False):
    """Mark visually-scored FOG episodes as a red band on the axis."""
    for i, (a, b) in enumerate(FOG_EVENTS):
        ax.axvspan(a, b, color="red", alpha=0.12, lw=0,
                   label="FOG (video)" if label and i == 0 else None)


def _phase_shade(ax, g):
    """Shade stance (HS->TO) light, swing (TO->HS) clear, using R-foot events."""
    ev = sorted([(t, "hs") for t in g["t_hs"]] + [(t, "to") for t in g["t_to"]])
    for i in range(len(ev) - 1):
        if ev[i][1] == "hs":
            ax.axvspan(ev[i][0], ev[i + 1][0], color="0.85", alpha=0.5, lw=0)


def make_figures(angles, gait, fi, detect=None):
    # (a) joint angles
    fig, axs = plt.subplots(3, 1, figsize=(13, 9), sharex=True)
    note = {"knee": "COMETA-COMETA (validated)",
            "hip": "pelvis WIMU + thigh COMETA",
            "ankle": "shin COMETA + foot WIMU - cross-system, approx (no common heading)"}
    for ax, joint in zip(axs, ("knee", "hip", "ankle")):
        for side, col in (("R", "C0"), ("L", "C3")):
            t, a = angles[(side, joint)]
            ax.plot(t, a, col, lw=1.0, label=f"{side} {joint}")
        _phase_shade(ax, gait["R"])
        _fog_shade(ax, label=(joint == "knee"))
        if detect:
            _detect_shade(ax, detect, label=(joint == "knee"))
        ax.set_ylabel(f"{joint}\n(deg)")
        ax.text(0.005, 0.97, note[joint], transform=ax.transAxes, fontsize=7,
                color="0.4", va="top", ha="left")
        ax.legend(loc="upper right", fontsize=8)
        ax.grid(alpha=0.3)
    axs[-1].set_xlabel("time (s)")
    axs[0].set_title(f"{TAG}: bilateral joint angles {WIN[0]:.0f}-{WIN[1]:.0f}s "
                     "(grey = R stance)")
    p = os.path.join(OUT_DIR, f"{TAG}_angles_{int(WIN[0])}_{int(WIN[1])}.png")
    fig.tight_layout(); fig.savefig(p, dpi=120); plt.close(fig)
    print("saved", p)

    # (b) gait
    fig, axs = plt.subplots(2, 1, figsize=(13, 7), sharex=True)
    for ax, side in zip(axs, ("R", "L")):
        g = gait[side]
        ax.plot(g["t"], g["gy"], "0.4", lw=0.8)
        ax.plot(g["t"][g["peaks"]], g["gy"][g["peaks"]], "g.", ms=8, label="mid-swing")
        if len(g["hs"]):
            ax.plot(g["t_hs"], g["gy"][g["hs"]], "r^", ms=9, label="HS")
        if len(g["to"]):
            ax.plot(g["t_to"], g["gy"][g["to"]], "bv", ms=9, label="TO")
        _phase_shade(ax, g)
        _fog_shade(ax, label=(side == "R"))
        ax.set_ylabel(f"{side} foot\nang.vel (deg/s)\nfrom quat")
        ax.legend(loc="upper right", fontsize=8)
        ax.grid(alpha=0.3)
    axs[-1].set_xlabel("time (s)")
    axs[0].set_title(f"{TAG}: Method-1 gait detection {WIN[0]:.0f}-{WIN[1]:.0f}s")
    p = os.path.join(OUT_DIR, f"{TAG}_gait_{int(WIN[0])}_{int(WIN[1])}.png")
    fig.tight_layout(); fig.savefig(p, dpi=120); plt.close(fig)
    print("saved", p)

    # (c) freeze index, z-scored per sensor so COMETA(acc) and WIMU(free-accel)
    # traces share a scale -- compare relative timing, not absolute FI magnitude.
    fig, ax = plt.subplots(figsize=(13, 7))
    for k, (c, v, pwr, off) in fi.items():
        if not len(v) or v.std() < 1e-9:
            continue
        z = (v - v.mean()) / v.std()
        ls = "-" if k.startswith("COM") else "--"
        ax.plot(c + off, z, ls, lw=1.0, label=k)
    ax.axhline(2.0, color="k", ls=":", lw=1.2, label="z = +2 SD")
    _fog_shade(ax, label=True)
    if detect:
        _detect_shade(ax, detect, label=True)
    ax.set_xlabel("time (s)"); ax.set_ylabel("Freeze Index (z-score per sensor)")
    ax.set_title(f"{TAG}: per-sensor Freeze Index (z-scored) {WIN[0]:.0f}-{WIN[1]:.0f}s "
                 "(solid=COMETA acc, dashed=WIMU free-accel)")
    ax.legend(loc="upper right", fontsize=7, ncol=2)
    ax.grid(alpha=0.3)
    p = os.path.join(OUT_DIR, f"{TAG}_freezeindex_{int(WIN[0])}_{int(WIN[1])}.png")
    fig.tight_layout(); fig.savefig(p, dpi=120); plt.close(fig)
    print("saved", p)

    # (d) RAW freeze index, log-y -- shows true magnitudes (a high absolute FI is
    # only meaningful vs that sensor's own baseline/threshold, NOT as a ranking
    # across sensors). Log axis keeps small-scale sensors visible next to large.
    fig, ax = plt.subplots(figsize=(13, 7))
    for k, (c, v, pwr, off) in fi.items():
        if not len(v):
            continue
        ls = "-" if k.startswith("COM") else "--"
        ax.plot(c + off, np.clip(v, 1e-2, None), ls, lw=1.0, label=k)
    ax.axhline(2.0, color="k", ls=":", lw=1.2, label="Bachlin FI=2")
    _fog_shade(ax, label=True)
    if detect:
        _detect_shade(ax, detect, label=True)
    ax.set_yscale("log")
    ax.set_xlabel("time (s)"); ax.set_ylabel("Freeze Index (raw, log scale)")
    ax.set_title(f"{TAG}: per-sensor RAW Freeze Index {WIN[0]:.0f}-{WIN[1]:.0f}s "
                 "(solid=COMETA acc, dashed=WIMU free-accel; abs. scale NOT "
                 "comparable across sensors)")
    ax.legend(loc="upper right", fontsize=7, ncol=2)
    ax.grid(alpha=0.3, which="both")
    p = os.path.join(OUT_DIR, f"{TAG}_freezeindex_raw_log_{int(WIN[0])}_{int(WIN[1])}.png")
    fig.tight_layout(); fig.savefig(p, dpi=120); plt.close(fig)
    print("saved", p)


def make_rank_figure(rank):
    """Grouped bars: Cohen's d of FOG vs clean-walk (light) and vs clean-turn
    (dark, matched-activity control). AUC labelled. The turn bar is what matters:
    high here = the sensor separates freeze from a normal turn (won't false-fire
    on turns); low/absent = turn false positives expected."""
    if not rank:
        return
    names = [r[0] for r in rank]
    dw = [r[1] for r in rank]; aw = [r[2] for r in rank]
    dt = [r[3] for r in rank]; at = [r[4] for r in rank]
    has_turn = any(x == x for x in dt)   # not all NaN
    x = np.arange(len(names)); w = 0.4
    fig, ax = plt.subplots(figsize=(13, 6))
    ax.bar(x - w/2, dw, w, color="0.7", label="vs clean walk")
    if has_turn:
        ax.bar(x + w/2, [0 if v != v else v for v in dt], w, color="C3",
               label="vs clean turn (matched)")
    for i in range(len(names)):
        ax.text(i - w/2, (dw[i] or 0) + 0.05, f"{aw[i]:.2f}", ha="center", fontsize=6, color="0.4")
        if has_turn and dt[i] == dt[i]:
            ax.text(i + w/2, dt[i] + 0.05, f"{at[i]:.2f}", ha="center", fontsize=6, color="C3")
    ax.axhline(0.8, color="k", ls=":", lw=1, label="d=0.8 (large effect)")
    ax.set_xticks(x); ax.set_xticklabels(names, rotation=60, ha="right", fontsize=8)
    ax.set_ylabel("Cohen's d  (FI: FOG vs negative)")
    ax.set_title(f"{TAG}: FOG-detection separability per sensor  "
                 f"(FOG {FOG_EVENTS}; AUC labelled on bars)")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(alpha=0.3, axis="y")
    p = os.path.join(OUT_DIR, f"{TAG}_fog_sensor_ranking.png")
    fig.tight_layout(); fig.savefig(p, dpi=120); plt.close(fig)
    print("saved", p)


if __name__ == "__main__":
    main()
