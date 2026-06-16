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
_GUI = os.path.normpath(os.path.join(_HERE, "..", "GUI"))
if _GUI not in sys.path:
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
H5_PATH = ("/Users/chiaracazzoli/Library/CloudStorage/OneDrive-epfl.ch/"
           "File di Daniel Leal - Recording sessions/Group_FOG/FOG002/MAPP/"
           "Narrow Corridor_1/recording_data.h5")
# Time base: cameras + sensors share an ABSOLUTE device clock (~1.208e6). The
# `logs/events` `elapsed` column is a SEPARATE clock that drifts from absolute
# (e.g. "Recording Started" elapsed=8.63 but ts-Task=5.10), so it must NOT be
# used. Videos are aligned to the absolute timestamp; video t=0 = first camera
# frame. T0 is therefore set at runtime to the first camera frame timestamp so
# the window matches what is seen in the video. (~1208214.75 for FOG002.)
T0 = 0.0                         # set in main() from first camera frame
WIN = (800.0, 860.0)             # analysis window, seconds from video start (13:20-14:20)
CALIB = (0.0, 10.0)              # standing-still calibration window
FUSE_FROM = 0.0                  # fuse COMETA continuously from here through WIN[1]

# COMETA 72 cols = 8 sensor blocks x 9 ch [acc(g) 0:3, gyro(deg/s) 3:6, mag 6:9]
# NOTE: the originally-supplied map (S1/S2=thigh, S5/S6=shin) is INVERTED. The
# ankle test (true shank paired with foot gives a physiological ~35-48 deg ROM,
# thigh gives an absurd ~100 deg) plus distal-faster gyro-RMS show S1/S2 are the
# shins and S5/S6 the thighs. Corrected mapping below.
COMETA_BLOCK = {("R", "thigh"): 4, ("R", "shin"): 0,
                ("L", "thigh"): 5, ("L", "shin"): 1}
COMETA_FS = 2000.0

# WIMU 8 cols = [counter, free_accel_xyz (m/s^2, gravity-removed), quat_wxyz].
# Verified: cols 1-3 read ~0 at rest and peak ~6g at foot strike -> free
# acceleration, NOT gyroscope (WIMU exports no raw gyro). Sagittal angular
# velocity for gait is reconstructed from the quaternion (quat_angular_velocity).
WIMU_DEV = {"R_foot": "dev5", "L_foot": "dev2",
            "wrist": "dev3", "cervical": "dev6", "pelvis": "dev7"}

# Freeze Index
FI_WIN = 4.0                     # s
FI_STEP = 0.25                   # s
FI_LOCO = (0.5, 3.0)             # locomotor band (Hz)
FI_FREEZE = (3.0, 8.0)          # freeze band (Hz)
FI_THRESHOLD = 2.0               # plotted reference line

OUT_DIR = _HERE                  # save PNGs next to this script
TAG = "fog002_narrow"

# Visually-scored FOG episodes (seconds from video start), marked on every plot.
FOG_EVENTS = [(831.0, 837.0)]
# Clean-walking reference window for FOG-vs-walk sensor separability ranking.
FI_WALK_REF = (810.0, 822.0)


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
    n = int(round(FI_WIN * fs))
    step = int(round(FI_STEP * fs))
    if len(sig) < n:
        return np.array([]), np.array([])
    freqs = np.fft.rfftfreq(n, 1.0 / fs)
    loco_m = (freqs >= FI_LOCO[0]) & (freqs < FI_LOCO[1])
    frz_m = (freqs >= FI_FREEZE[0]) & (freqs < FI_FREEZE[1])
    centers, fis = [], []
    win = np.hanning(n)
    for s in range(0, len(sig) - n + 1, step):
        seg = sig[s:s + n]
        seg = (seg - seg.mean()) * win
        p = np.abs(np.fft.rfft(seg)) ** 2
        loco = p[loco_m].sum()
        frz = p[frz_m].sum()
        fis.append(frz / loco if loco > 1e-12 else 0.0)
        centers.append((s + n / 2.0) / fs)
    return np.asarray(centers), np.asarray(fis)


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


# ── main ───────────────────────────────────────────────────────────────────
def main():
    global T0
    f = h5py.File(H5_PATH, "r")
    T0 = float(f["Cameras/camera_2/frames"][0]["timestamp"])  # video t=0 (absolute)
    print(f"[TIME] T0 (first camera frame) = {T0:.3f}  -> window absolute "
          f"{T0+WIN[0]:.1f}-{T0+WIN[1]:.1f}")

    # ---- COMETA: fuse needed blocks continuously [FUSE_FROM .. WIN[1]] ----
    d_co, t_co = load_cometa(f)
    fi0 = win_idx(t_co, FUSE_FROM, WIN[1])
    c0, c1 = fi0[0], fi0[-1] + 1
    t_co_run = t_co[c0:c1]
    print(f"[COMETA] fusing rows {c0}:{c1} ({c1-c0} samp, "
          f"{t_co_run[0]:.1f}-{t_co_run[-1]:.1f}s)")
    qco = {}
    for (side, seg), blk in COMETA_BLOCK.items():
        acc, gyr = cometa_block(d_co, blk, c0, c1)
        qco[(side, seg)] = fuse(acc, gyr, COMETA_FS)
        print(f"  fused {side} {seg} (blk{blk}) qnorm~{np.linalg.norm(qco[(side,seg)],axis=1).mean():.3f}")

    calib_m = (t_co_run >= CALIB[0]) & (t_co_run <= CALIB[1])
    win_m = (t_co_run >= WIN[0]) & (t_co_run <= WIN[1])

    # ---- WIMU quats + times ----
    qwi, twi, dwi = {}, {}, {}
    for name, dev in WIMU_DEV.items():
        d, t = load_wimu(f, dev)
        dwi[name], twi[name] = d, t
        qwi[name] = d[:, 4:8]

    def wimu_calib_ref(name):
        m = (twi[name] >= CALIB[0]) & (twi[name] <= CALIB[1])
        return avg_quat(qwi[name][m])

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
    # Sagittal pitch difference of segment long axes. Yaw-drift-immune, so it
    # survives the COMETA(no-mag) <-> WIMU(mag) frame mismatch that wrecks the
    # relative-quaternion method here.
    for side in ("R", "L"):
        foot = "R_foot" if side == "R" else "L_foot"
        qsh = qco[(side, "shin")]
        shin_ref = avg_quat(qsh[calib_m])
        foot_ref = wimu_calib_ref(foot)
        sh_axis = AXIS_VECTORS[detect_most_vertical_axis(shin_ref)]      # along tibia
        ft_axis = AXIS_VECTORS[detect_most_horizontal_axis(foot_ref)]    # along foot
        off = long_axis_pitch(foot_ref, ft_axis) - long_axis_pitch(shin_ref, sh_axis)
        tf = twi[foot]
        fm = (tf >= WIN[0]) & (tf <= WIN[1])
        tf_win = tf[fm]
        sidx = nearest_match(t_co_run, tf_win)         # shin sample per foot sample
        qsh_win = qsh[sidx]
        qf_win = qwi[foot][fm]
        ankle = np.array([long_axis_pitch(qf_win[k], ft_axis)
                          - long_axis_pitch(qsh_win[k], sh_axis)
                          for k in range(len(qf_win))]) - off
        angles[(side, "ankle")] = (tf_win, ankle)
        print(f"[ANKLE {side}] sh_axis/ft_axis pitch  off={off:.1f}  ROM={np.ptp(ankle):.1f}  "
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
    fi = {}
    for (side, seg), blk in COMETA_BLOCK.items():
        acc, _ = cometa_block(d_co, blk, c0, c1)
        norm = np.sqrt((acc[win_m] ** 2).sum(1))
        fi[f"COM_{side}_{seg}"] = freeze_index(norm, COMETA_FS) + (WIN[0],)
    # remaining COMETA blocks (2,3,6,7) for full per-sensor FI
    for blk in (2, 3, 6, 7):
        acc, _ = cometa_block(d_co, blk, c0, c1)
        norm = np.sqrt((acc[win_m] ** 2).sum(1))
        fi[f"COM_blk{blk}"] = freeze_index(norm, COMETA_FS) + (WIN[0],)
    for name in WIMU_DEV:
        t = twi[name]
        m = (t >= WIN[0]) & (t <= WIN[1])
        fs = 1.0 / np.median(np.diff(t[m]))
        norm = np.sqrt((dwi[name][m, 1:4].astype(float) ** 2).sum(1))  # free-accel norm
        fi[f"WIMU_{name}"] = freeze_index(norm, fs) + (WIN[0],)
    for k, v in fi.items():
        if len(v[1]):
            print(f"[FI] {k:16s} min={v[1].min():.2f} max={v[1].max():.2f} mean={v[1].mean():.2f}")

    rank = rank_sensors(fi)

    f.close()
    make_figures(angles, gait, fi)
    make_rank_figure(rank)


# ── FOG-vs-walk sensor separability ─────────────────────────────────────────
def rank_sensors(fi):
    """Per sensor, how well its raw FI separates FOG from clean walking.

    Cohen's d = (mean_FOG - mean_walk) / pooled_std (effect size, fair across
    sensors of different units/noise). AUC = P(FI_FOG > FI_walk). Returns a list
    sorted by d, descending.
    """
    def in_win(c, off, w):
        tt = c + off
        return (tt >= w[0]) & (tt <= w[1])

    out = []
    for k, (c, v, off) in fi.items():
        if not len(v):
            continue
        fog = v[in_win(c, off, FOG_EVENTS[0])]
        walk = v[in_win(c, off, FI_WALK_REF)]
        if len(fog) < 2 or len(walk) < 2:
            continue
        sp = np.sqrt((fog.var(ddof=1) + walk.var(ddof=1)) / 2.0)
        d = (fog.mean() - walk.mean()) / sp if sp > 1e-9 else 0.0
        auc = (np.greater.outer(fog, walk).mean()
               + 0.5 * np.equal.outer(fog, walk).mean())
        out.append((k, d, auc))
    out.sort(key=lambda r: r[1], reverse=True)
    print(f"[RANK] FOG {FOG_EVENTS[0]} vs walk {FI_WALK_REF} (by Cohen's d)")
    for k, d, auc in out:
        print(f"   {k:16s} d={d:+.2f}  AUC={auc:.2f}")
    return out


# ── figures ────────────────────────────────────────────────────────────────
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


def make_figures(angles, gait, fi):
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
    for k, (c, v, off) in fi.items():
        if not len(v) or v.std() < 1e-9:
            continue
        z = (v - v.mean()) / v.std()
        ls = "-" if k.startswith("COM") else "--"
        ax.plot(c + off, z, ls, lw=1.0, label=k)
    ax.axhline(2.0, color="k", ls=":", lw=1.2, label="z = +2 SD")
    _fog_shade(ax, label=True)
    ax.set_xlabel("time (s)"); ax.set_ylabel("Freeze Index (z-score per sensor)")
    ax.set_title(f"{TAG}: per-sensor Freeze Index (z-scored) {WIN[0]:.0f}-{WIN[1]:.0f}s "
                 "(solid=COMETA acc, dashed=WIMU free-accel)")
    ax.legend(loc="upper right", fontsize=7, ncol=2)
    ax.grid(alpha=0.3)
    p = os.path.join(OUT_DIR, f"{TAG}_freezeindex_{int(WIN[0])}_{int(WIN[1])}.png")
    fig.tight_layout(); fig.savefig(p, dpi=120); plt.close(fig)
    print("saved", p)


def make_rank_figure(rank):
    """Bar plot of which sensor best separates FOG from walking (Cohen's d), AUC on top."""
    if not rank:
        return
    names = [r[0] for r in rank]
    ds = [r[1] for r in rank]
    aucs = [r[2] for r in rank]
    cols = ["C0" if n.startswith("COM") else "C1" for n in names]
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.bar(range(len(names)), ds, color=cols)
    for i, (d, a) in enumerate(zip(ds, aucs)):
        ax.text(i, d + (0.05 if d >= 0 else -0.12), f"{a:.2f}",
                ha="center", fontsize=7, color="0.3")
    ax.axhline(0.8, color="k", ls=":", lw=1, label="d=0.8 (large effect)")
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels(names, rotation=60, ha="right", fontsize=8)
    ax.set_ylabel("Cohen's d  (FI: FOG vs walk)")
    ax.set_title(f"{TAG}: which sensor detects FOG best  "
                 f"(FOG {FOG_EVENTS[0]} vs walk {FI_WALK_REF}; AUC labelled; "
                 "blue=COMETA acc, orange=WIMU free-accel)")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(alpha=0.3, axis="y")
    p = os.path.join(OUT_DIR, f"{TAG}_fog_sensor_ranking.png")
    fig.tight_layout(); fig.savefig(p, dpi=120); plt.close(fig)
    print("saved", p)


if __name__ == "__main__":
    main()
