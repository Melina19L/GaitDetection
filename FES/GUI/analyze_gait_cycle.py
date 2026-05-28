"""
Offline gait-cycle analysis + gait-phase detection from a saved
plot_snapshot_*.pkl.

Joint angles
------------
The live SAA dispatcher in ``angle_calibrator.py`` is unsigned, so the post-test
.pkl only carries the magnitude of the rotation. This script LOADS THE RAW
QUATERNIONS (added to save_data on 2026-05-11) and recomputes every joint
angle as the first Euler angle of the relative quaternion, picking the
rotation order so the medio-lateral axis comes first. The static reference
is anchored on the GUI's calibrated angles (it picks a window where the
saved knee/ankle/hip all read ~0°), so the baseline matches the operator's
N-pose.

Gait phases
-----------
Detected from the FOOT pitch (angle of the foot's forward axis above /
below the world horizontal plane), following Sabatini 2005 / Mariani 2010:

    HS  (heel-strike)  : positive peak of pitch (toes up for ground clearance)
    FF  (foot-flat)    : pitch crosses zero going down
    HO  (heel-off)     : pitch starts dropping clearly negative
    TO  (toe-off)      : negative peak of pitch (deep plantar at push-off)
    MSw (mid-swing)    : pitch crosses zero going up

For each gait cycle we identify HS → next HS and split it into STANCE
(0-60%) and SWING (60-100%). The stance / swing regions are drawn as
coloured bands across every subplot so the operator can see at a glance
which part of the recording is which phase.

Usage:
    python3 analyze_gait_cycle.py try1.pkl
"""
import pickle
import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from scipy.signal import find_peaks
from scipy.spatial.transform import Rotation as R


# ── Quaternion helpers (our convention: [w, x, y, z], scalar first) ─────────
def qnorm(q):
    n = np.linalg.norm(q, axis=-1, keepdims=True)
    return q / (n + 1e-12)

def qconj(q):
    out = q.copy()
    out[..., 1:] = -out[..., 1:]
    return out

def qmul(a, b):
    w1, x1, y1, z1 = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    w2, x2, y2, z2 = b[..., 0], b[..., 1], b[..., 2], b[..., 3]
    return np.stack([
        w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
        w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
        w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
        w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
    ], axis=-1)

def qrotate_vec_one(q, v):
    """Rotate vector v by quaternion q (single sample). q in [w,x,y,z]."""
    qv = np.array([0.0, v[0], v[1], v[2]])
    return qmul(qmul(q, qv), qconj(q))[1:]

def qrotate_vec_series(q_arr, v):
    """Rotate a fixed vector ``v`` by every quaternion in ``q_arr``."""
    qv = np.zeros((q_arr.shape[0], 4))
    qv[:, 1] = v[0]; qv[:, 2] = v[1]; qv[:, 3] = v[2]
    return qmul(qmul(q_arr, qv), qconj(q_arr))[:, 1:]

def to_scipy(q):
    """Convert [w,x,y,z] → scipy's [x,y,z,w]."""
    return np.stack([q[..., 1], q[..., 2], q[..., 3], q[..., 0]], axis=-1)


# ── Axis auto-detection from the static reference quaternion ────────────────
AXIS_VEC = {'X': np.array([1.0, 0.0, 0.0]),
            'Y': np.array([0.0, 1.0, 0.0]),
            'Z': np.array([0.0, 0.0, 1.0])}

def detect_vertical_axis(q_static):
    best, best_score = 'X', -1.0
    for name, v in AXIS_VEC.items():
        gv = qrotate_vec_one(q_static, v)
        s = abs(gv[2])
        if s > best_score:
            best, best_score = name, s
    return best

def detect_horizontal_axis(q_static, exclude=None):
    best, best_score = None, -1.0
    for name, v in AXIS_VEC.items():
        if name == exclude:
            continue
        gv = qrotate_vec_one(q_static, v)
        s = 1.0 - abs(gv[2])
        if s > best_score:
            best, best_score = name, s
    return best

def auto_ml_axis(q_static_avg):
    vert = detect_vertical_axis(q_static_avg)
    fwd  = detect_horizontal_axis(q_static_avg, exclude=vert)
    return ({'X', 'Y', 'Z'} - {vert, fwd}).pop()


# ── Signed sagittal joint angle from relative quaternion ────────────────────
def signed_sagittal_series(q_prox, q_dist, q_prox_ref, q_dist_ref, ml_axis_prox):
    q_rel_now = qmul(qconj(q_prox), q_dist)
    q_rel_ref = qmul(qconj(q_prox_ref), q_dist_ref)
    q_delta   = qmul(q_rel_now, qconj(q_rel_ref))
    flip = q_delta[..., 0] < 0
    q_delta[flip] = -q_delta[flip]
    r = R.from_quat(to_scipy(qnorm(q_delta)))
    order = {'X': 'XYZ', 'Y': 'YXZ', 'Z': 'ZXY'}[ml_axis_prox]
    eulers = r.as_euler(order, degrees=True)
    return eulers[..., 0]


def resample_quaternions(q_in, ts_in, ts_target):
    """Nearest-neighbour quaternion samples onto a target timeline."""
    if q_in.shape[0] == 0:
        return np.full((ts_target.size, 4), np.nan)
    idx = np.searchsorted(ts_in, ts_target)
    idx = np.clip(idx, 0, q_in.shape[0] - 1)
    idx_prev = np.clip(idx - 1, 0, q_in.shape[0] - 1)
    use_prev = np.abs(ts_in[idx_prev] - ts_target) < np.abs(ts_in[idx] - ts_target)
    chosen = np.where(use_prev, idx_prev, idx)
    return q_in[chosen]


# ── 1. LOAD ─────────────────────────────────────────────────────────────────
if len(sys.argv) < 2:
    print("Usage: python3 analyze_gait_cycle.py <plot_snapshot.pkl>")
    sys.exit(1)

pkl_path = Path(sys.argv[1])
with open(pkl_path, "rb") as f:
    d = pickle.load(f)

side = "right"
needed = [f"raw_{side}_thigh_quat", f"raw_{side}_shank_quat",
          f"raw_{side}_foot_quat",  "raw_pelvis_quat"]
missing = [k for k in needed if k not in d]
if missing:
    print("⚠  This .pkl does NOT contain raw quaternions:")
    for k in missing: print(f"     missing  {k}")
    print("Save a fresh .pkl after the 2026-05-11 fix to save_data.")
    sys.exit(1)

q_th = qnorm(np.asarray(d[f"raw_{side}_thigh_quat"], dtype=np.float64))
q_sh = qnorm(np.asarray(d[f"raw_{side}_shank_quat"], dtype=np.float64))
q_ft = qnorm(np.asarray(d[f"raw_{side}_foot_quat"],  dtype=np.float64))
q_pv = qnorm(np.asarray(d["raw_pelvis_quat"],        dtype=np.float64))
t_th = np.asarray(d[f"raw_{side}_thigh_timestamps"], dtype=np.float64)
t_sh = np.asarray(d[f"raw_{side}_shank_timestamps"], dtype=np.float64)
t_ft = np.asarray(d[f"raw_{side}_foot_timestamps"],  dtype=np.float64)
t_pv = np.asarray(d["raw_pelvis_timestamps"],        dtype=np.float64)
for name, q in [("thigh", q_th), ("shank", q_sh), ("foot", q_ft), ("pelvis", q_pv)]:
    print(f"   raw {name}: {q.shape[0]} samples")

if min(q_th.shape[0], q_sh.shape[0], q_ft.shape[0], q_pv.shape[0]) < 100:
    print("\n⚠ One or more sensors has very few samples. Was it connected?")
    sys.exit(1)


# ── 2. COMMON TIMELINE — shank is the master clock ──────────────────────────
t_master = t_sh.copy()
t0 = t_master[0]
t_rel = t_master - t0
q_th_r = resample_quaternions(q_th, t_th, t_master)
q_sh_r = resample_quaternions(q_sh, t_sh, t_master)
q_ft_r = resample_quaternions(q_ft, t_ft, t_master)
q_pv_r = resample_quaternions(q_pv, t_pv, t_master)

fs = 1.0 / np.median(np.diff(t_master))
print(f"\nMaster clock = shank ({t_master.size} samples, {t_rel[-1]:.1f} s, ~{fs:.1f} Hz)")


# ── 3. STATIC REFERENCE — anchored on the GUI's calibrated angles ───────────
# (a window where the saved knee/ankle/hip all read ~0° = the operator was
# in the GUI-calibrated N-pose at that moment)
knee_pkl  = np.asarray(d[f"{side}_knee_angles"],     dtype=np.float64)
knee_tpkl = np.asarray(d[f"{side}_knee_timestamps"], dtype=np.float64)
ank_pkl   = np.asarray(d[f"{side}_ankle_angles"],    dtype=np.float64)
ank_tpkl  = np.asarray(d[f"{side}_ankle_timestamps"],dtype=np.float64)
hip_pkl   = np.asarray(d[f"{side}_hip_angles"],      dtype=np.float64)
hip_tpkl  = np.asarray(d[f"{side}_hip_timestamps"],  dtype=np.float64)

def _interp_to(t_target, t_src, val_src):
    if t_src.size == 0:
        return np.full_like(t_target, np.nan)
    return np.interp(t_target, t_src, val_src, left=np.nan, right=np.nan)

knee_at_master = _interp_to(t_master, knee_tpkl, knee_pkl)
ank_at_master  = _interp_to(t_master, ank_tpkl,  ank_pkl)
hip_at_master  = _interp_to(t_master, hip_tpkl,  hip_pkl)

NPOSE_KNEE, NPOSE_ANKLE, NPOSE_HIP = 3.0, 3.0, 5.0
npose_mask = (
    np.isfinite(knee_at_master) & np.isfinite(ank_at_master) & np.isfinite(hip_at_master) &
    (np.abs(knee_at_master) < NPOSE_KNEE) &
    (np.abs(ank_at_master)  < NPOSE_ANKLE) &
    (np.abs(hip_at_master)  < NPOSE_HIP)
)
WIN = int(0.5 * fs)

def _longest_run(mask):
    best_start, best_len = -1, 0
    rs, rl = -1, 0
    for i, m in enumerate(mask):
        if m:
            if rs < 0: rs = i
            rl += 1
        else:
            if rl > best_len:
                best_start, best_len = rs, rl
            rs, rl = -1, 0
    if rl > best_len:
        best_start, best_len = rs, rl
    return best_start, best_len

ref_start, ref_len = _longest_run(npose_mask)
if ref_start < 0 or ref_len < WIN:
    print("\n⚠ No 0.5 s window where the GUI-computed angles read ~0°.")
    print("  Stand still in N-pose for ≥1 s during the recording, then re-save.")
    sys.exit(1)

ref_end = ref_start + min(ref_len, int(1.0 * fs))
print(f"N-pose reference: samples {ref_start}..{ref_end} "
      f"(t = {t_rel[ref_start]:.2f}..{t_rel[ref_end-1]:.2f} s, {ref_len} samples)")

q_th_ref = qnorm(q_th_r[ref_start:ref_end].mean(axis=0))
q_sh_ref = qnorm(q_sh_r[ref_start:ref_end].mean(axis=0))
q_ft_ref = qnorm(q_ft_r[ref_start:ref_end].mean(axis=0))
q_pv_ref = qnorm(q_pv_r[ref_start:ref_end].mean(axis=0))

ml_thigh  = auto_ml_axis(q_th_ref)
ml_shank  = auto_ml_axis(q_sh_ref)
ml_pelvis = auto_ml_axis(q_pv_ref)
foot_vert = detect_vertical_axis(q_ft_ref)
foot_fwd  = detect_horizontal_axis(q_ft_ref, exclude=foot_vert)
print(f"Auto-detected medio-lateral axes:  pelvis={ml_pelvis}  "
      f"thigh={ml_thigh}  shank={ml_shank}   |   foot: vertical={foot_vert}, "
      f"forward={foot_fwd}")


# ── 4. JOINT ANGLES (signed Euler) ──────────────────────────────────────────
knee  = signed_sagittal_series(q_th_r, q_sh_r, q_th_ref, q_sh_ref, ml_thigh)
hip   = signed_sagittal_series(q_pv_r, q_th_r, q_pv_ref, q_th_ref, ml_pelvis)
ankle = signed_sagittal_series(q_sh_r, q_ft_r, q_sh_ref, q_ft_ref, ml_shank)


# ── 5. FOOT PITCH (gait-phase signal) ───────────────────────────────────────
# Pitch = angle of the foot's forward axis above (positive) / below
# (negative) the world horizontal plane.
#   + value = toes UP    (e.g. heel-strike attitude)
#   - value = toes DOWN  (e.g. push-off / toe-off attitude)
fwd_local = AXIS_VEC[foot_fwd]
fwd_world = qrotate_vec_series(q_ft_r, fwd_local)
# Normalise + clip for arcsin safety
fwd_world /= np.linalg.norm(fwd_world, axis=1, keepdims=True) + 1e-12
foot_pitch = np.degrees(np.arcsin(np.clip(fwd_world[:, 2], -1.0, 1.0)))
# Sign: world Z is UP. If the user's mounting has the foot-fwd vector pointing
# toward toes with a Z component > 0 at neutral (toe slightly raised), the
# pitch is positive at HS as expected. We subtract the reference pitch so the
# zero is at neutral standing.
foot_pitch_ref = float(foot_pitch[ref_start:ref_end].mean())
foot_pitch -= foot_pitch_ref
print(f"\nFoot pitch (reference subtracted): "
      f"range [{foot_pitch.min():+.1f}..{foot_pitch.max():+.1f}]°")


# ── 6. DETECT HEEL-STRIKE / TOE-OFF FROM FOOT PITCH ─────────────────────────
# Adaptive thresholds based on the signal range. Try both polarities in case
# the auto-detected sign is flipped relative to the clinical convention.
def detect_events(signal, fs, distance_s=0.4, min_prom=4.0):
    rng = float(signal.max() - signal.min())
    if rng < 8.0:
        print(f"   pitch range only {rng:.1f}° — no walking-like motion.")
        return None, None, False
    prom = max(min_prom, min(0.4 * rng, 30.0))
    dist = int(distance_s * fs)

    # Standard polarity: HS = +peak, TO = −peak
    hs_n, _ = find_peaks(+signal, distance=dist, prominence=prom)
    to_n, _ = find_peaks(-signal, distance=dist, prominence=prom)
    score_n = len(hs_n) + len(to_n)

    # Flipped polarity
    hs_p, _ = find_peaks(-signal, distance=dist, prominence=prom)
    to_p, _ = find_peaks(+signal, distance=dist, prominence=prom)
    score_p = len(hs_p) + len(to_p)

    if score_n >= score_p:
        return hs_n, to_n, False
    return hs_p, to_p, True

hs_idx, to_idx, flipped = detect_events(foot_pitch, fs)
if flipped:
    print("   ⚠ Foot pitch sign appears flipped — inverting for plot.")
    foot_pitch = -foot_pitch

if hs_idx is None or hs_idx.size < 2 or to_idx is None or to_idx.size < 2:
    print("\n⚠ Could not detect heel-strikes / toe-offs. Showing diagnostic plot only.")
    fig_diag, axd = plt.subplots(4, 1, figsize=(14, 10), sharex=True)
    axd[0].plot(t_rel, ankle, color="purple", lw=0.8); axd[0].set_ylabel("Caviglia (°)")
    axd[0].axhline(0, color="k", lw=0.4); axd[0].grid(alpha=0.3)
    axd[1].plot(t_rel, knee, color="orange", lw=0.8); axd[1].set_ylabel("Ginocchio (°)")
    axd[1].axhline(0, color="k", lw=0.4); axd[1].grid(alpha=0.3)
    axd[2].plot(t_rel, hip, color="goldenrod", lw=0.8); axd[2].set_ylabel("Anca (°)")
    axd[2].axhline(0, color="k", lw=0.4); axd[2].grid(alpha=0.3)
    axd[3].plot(t_rel, foot_pitch, color="steelblue", lw=0.8); axd[3].set_ylabel("Foot pitch (°)")
    axd[3].axhline(0, color="k", lw=0.4); axd[3].grid(alpha=0.3)
    axd[3].set_xlabel("Tempo (s)")
    fig_diag.suptitle(f"Buffer completo (no events detected) — {pkl_path.name}")
    fig_diag.tight_layout()
    plt.show()
    sys.exit(0)

print(f"\nHeel-strikes detected: {len(hs_idx)}")
print(f"Toe-offs detected:     {len(to_idx)}")


# ── 7. BUILD GAIT-CYCLE WINDOWS (HS → next HS) ──────────────────────────────
# Pair each HS with the next HS, and find the TO that falls between them.
def pair_events(hs_idx, to_idx, t_rel):
    """Return a list of (hs, to_in_cycle, next_hs) index triples."""
    cycles = []
    for i in range(len(hs_idx) - 1):
        h0, h1 = hs_idx[i], hs_idx[i + 1]
        dur = t_rel[h1] - t_rel[h0]
        if not (0.7 <= dur <= 1.5):
            continue
        # Toe-offs that fall inside (h0, h1)
        inside = [t for t in to_idx if h0 < t < h1]
        if not inside:
            continue
        # Pick the TO closest to 60 % of the cycle
        target = h0 + int(0.60 * (h1 - h0))
        to = min(inside, key=lambda x: abs(x - target))
        cycles.append((h0, to, h1))
    return cycles

cycles = pair_events(hs_idx, to_idx, t_rel)
print(f"Gait cycles found (HS→HS, 0.7-1.5 s, with internal TO): {len(cycles)}")

if not cycles:
    print("⚠ No valid gait cycle. Showing diagnostic plot.")
    sys.exit(0)


# ── 8. STANCE / SWING BAND HELPER ───────────────────────────────────────────
def shade_phases(ax, cycles, t_rel, alpha=0.10):
    """Shade stance (HS→TO) and swing (TO→next HS) for every cycle."""
    for (h0, to, h1) in cycles:
        ax.axvspan(t_rel[h0], t_rel[to], color="#2ecc71", alpha=alpha)   # stance
        ax.axvspan(t_rel[to], t_rel[h1], color="#e67e22", alpha=alpha)   # swing


# ── 9. FULL-BUFFER PLOT (4 panels: ankle/knee/hip + foot pitch) ─────────────
fig1, axes = plt.subplots(4, 1, figsize=(14, 10), sharex=True)
shade_phases(axes[0], cycles, t_rel)
shade_phases(axes[1], cycles, t_rel)
shade_phases(axes[2], cycles, t_rel)
shade_phases(axes[3], cycles, t_rel)

axes[0].plot(t_rel, ankle, color="purple", lw=0.8)
axes[0].axhline(0, color="k", lw=0.4)
axes[0].set_ylabel("Caviglia (°)"); axes[0].grid(alpha=0.3)

axes[1].plot(t_rel, knee, color="orange", lw=0.8)
axes[1].axhline(0, color="k", lw=0.4)
axes[1].set_ylabel("Ginocchio (°)"); axes[1].grid(alpha=0.3)

axes[2].plot(t_rel, hip, color="goldenrod", lw=0.8)
axes[2].axhline(0, color="k", lw=0.4)
axes[2].set_ylabel("Anca (°)"); axes[2].grid(alpha=0.3)

axes[3].plot(t_rel, foot_pitch, color="steelblue", lw=0.9)
axes[3].axhline(0, color="k", lw=0.4)
axes[3].plot(t_rel[hs_idx], foot_pitch[hs_idx], "^", color="green", ms=7, label="Heel-strike (HS)")
axes[3].plot(t_rel[to_idx], foot_pitch[to_idx], "v", color="red",   ms=7, label="Toe-off (TO)")
axes[3].set_ylabel("Foot pitch (°)\n+ toes up / − toes down")
axes[3].set_xlabel("Tempo (s)")
axes[3].grid(alpha=0.3)
axes[3].legend(loc="upper right", fontsize=9)

# Phase-legend handles on the top panel
green_patch  = Patch(color="#2ecc71", alpha=0.3, label="Stance (HS→TO)")
orange_patch = Patch(color="#e67e22", alpha=0.3, label="Swing (TO→HS)")
axes[0].legend(handles=[green_patch, orange_patch], loc="upper right", fontsize=9)

# Highlight the BEST cycle for the per-cycle plot.
# We pick the cycle whose ankle ROM is closest to a physiological 35° (Whittle
# reference). Earlier "max ROM" picked sensor-shake artefacts where the
# quaternions varied wildly (e.g. while the operator was removing the sensors
# from the patient) — those segments give ROMs >80° that are anatomically
# impossible. Distance-from-target penalises both too-small (no real walking)
# and too-large (sensor noise) cycles.
PHYSIO_ANKLE_ROM = 35.0   # Whittle / Perry, normal walking
def cycle_score(c):
    h0, to, h1 = c
    rom = ankle[h0:h1].max() - ankle[h0:h1].min()
    return -abs(rom - PHYSIO_ANKLE_ROM)   # higher (less negative) is better
best_cycle = max(cycles, key=cycle_score)
h0, to_best, h1 = best_cycle
for ax in axes:
    ax.axvspan(t_rel[h0], t_rel[h1], facecolor="none", edgecolor="blue", lw=2, alpha=0.6)

fig1.suptitle(
    f"Buffer completo — {pkl_path.name}   "
    f"(angoli signed Euler; bande verde=stance / arancio=swing)",
    fontsize=11)
fig1.tight_layout()


# ── 10. SINGLE-CYCLE COMPARISON (HS→HS, 4 panels with clinical reference) ──
def slice_idx(arr, i0, i1): return arr[i0:i1]

ank_c = slice_idx(ankle,      h0, h1)
kne_c = slice_idx(knee,       h0, h1)
hip_c = slice_idx(hip,        h0, h1)
pit_c = slice_idx(foot_pitch, h0, h1)
pct   = np.linspace(0, 100, h1 - h0)
to_pct = 100.0 * (to_best - h0) / (h1 - h0)   # actual toe-off position in the cycle

print(f"\n✓ Best cycle: t = [{t_rel[h0]:.2f}, {t_rel[h1]:.2f}] s, "
      f"dur = {t_rel[h1]-t_rel[h0]:.2f} s, TO at {to_pct:.0f}% (rif ~60%)")
print(f"   Ankle: dorsi {ank_c.max():+.1f}°, plantar {ank_c.min():+.1f}°")
print(f"   Knee:  peak flex {kne_c.max():+.1f}°  "
      f"(loading 0-20%: {kne_c[pct < 20].max():+.1f}°)")
print(f"   Hip:   flex {hip_c.max():+.1f}°, ext {hip_c.min():+.1f}°")
print(f"   Foot pitch: at HS {pit_c[0]:+.1f}°, at TO {pit_c[int(to_pct)]:+.1f}°")

fig2, ax3 = plt.subplots(4, 1, figsize=(11, 12), sharex=True)
ref_pct = np.linspace(0, 100, 101)

# Phase backgrounds on every subplot
for ax in ax3:
    ax.axvspan(0,        to_pct, color="#2ecc71", alpha=0.10, label="_stance")
    ax.axvspan(to_pct,   100,    color="#e67e22", alpha=0.10, label="_swing")
    ax.axvline(to_pct,   color="red", ls=":", lw=1.0, alpha=0.6)

# Clinical reference curves (Whittle / Perry schematic, HS-HS convention)
def _ref_ankle():
    out = np.zeros(101)
    for i, p in enumerate(ref_pct):
        if   p < 10:    out[i] = -5 * np.sin(np.pi * p / 10.0)
        elif p < 50:    out[i] = 12 * np.sin(np.pi * (p - 10) / 40.0) - 1
        elif p < 70:    out[i] = 8 - 28 * np.sin(np.pi * (p - 50) / 40.0)
        else:
            x = (p - 70) / 30
            out[i] = -20 + 15 * np.sin(np.pi * x / 2.0)
    return out
def _ref_knee():
    out = np.zeros(101)
    for i, p in enumerate(ref_pct):
        if   p < 20:   out[i] = 5  + 15 * np.sin(np.pi * p / 20.0)
        elif p < 40:   out[i] = 5  + 5  * np.sin(np.pi * (40 - p) / 20.0)
        elif p < 75:   out[i] = 5  + 60 * (p - 40) / 35.0
        else:          out[i] = 65 - 60 * (p - 75) / 25.0
    return out
def _ref_hip():
    out = np.zeros(101)
    for i, p in enumerate(ref_pct):
        if   p < 50:   out[i] = 25 - 35 * (p / 50.0)
        else:          out[i] = -10 + 35 * ((p - 50) / 50.0)
    return out
ref_a = _ref_ankle(); ref_k = _ref_knee(); ref_h = _ref_hip()

ax3[0].plot(pct, ank_c, color="purple", lw=2.5, label="Misurata")
ax3[0].plot(ref_pct, ref_a, "k--", lw=1.2, alpha=0.6, label="Riferimento clinico")
ax3[0].fill_between(ref_pct, ref_a - 5, ref_a + 5, color="gray", alpha=0.12)
ax3[0].axhline(0, color="k", lw=0.3)
ax3[0].set_ylabel("Caviglia (°)\n+dorsi / −plantar")
ax3[0].set_title(f"Caviglia — dorsi {ank_c.max():+.1f}°, plantar {ank_c.min():+.1f}°")
ax3[0].legend(loc="lower left", fontsize=9)
ax3[0].grid(alpha=0.3)
ax3[0].set_ylim(-50, 30)

ax3[1].plot(pct, kne_c, color="orange", lw=2.5, label="Misurata")
ax3[1].plot(ref_pct, ref_k, "k--", lw=1.2, alpha=0.6, label="Riferimento clinico")
ax3[1].fill_between(ref_pct, ref_k - 5, ref_k + 5, color="gray", alpha=0.12)
ax3[1].axhline(0, color="k", lw=0.3)
ax3[1].set_ylabel("Ginocchio (°)\n+flex")
ax3[1].set_title(f"Ginocchio — peak flex {kne_c.max():+.1f}° (rif ~60°)")
ax3[1].legend(loc="upper left", fontsize=9)
ax3[1].grid(alpha=0.3)
ax3[1].set_ylim(-15, 80)

ax3[2].plot(pct, hip_c, color="goldenrod", lw=2.5, label="Misurata")
ax3[2].plot(ref_pct, ref_h, "k--", lw=1.2, alpha=0.6, label="Riferimento clinico")
ax3[2].fill_between(ref_pct, ref_h - 5, ref_h + 5, color="gray", alpha=0.12)
ax3[2].axhline(0, color="k", lw=0.3)
ax3[2].set_ylabel("Anca (°)\n+flex / −ext")
ax3[2].set_title(f"Anca — flex {hip_c.max():+.1f}°, ext {hip_c.min():+.1f}°")
ax3[2].legend(loc="upper left", fontsize=9)
ax3[2].grid(alpha=0.3)
ax3[2].set_ylim(-25, 40)

ax3[3].plot(pct, pit_c, color="steelblue", lw=2.5, label="Foot pitch (sagittal)")
ax3[3].axhline(0, color="k", lw=0.3)
ax3[3].set_ylabel("Foot pitch (°)\n+ toes up / − toes down")
ax3[3].set_xlabel("% Ciclo del passo  (Heel-strike → Heel-strike)")
ax3[3].set_title(f"Foot pitch — HS @ 0%  |  TO @ {to_pct:.0f}%  (rif ~60%)")
# Label the phases
mid_stance = to_pct / 2
mid_swing  = (to_pct + 100) / 2
ax3[3].annotate("STANCE", xy=(mid_stance, ax3[3].get_ylim()[0]), xytext=(0, 5),
                textcoords="offset points", ha="center", va="bottom",
                fontsize=10, color="#229954", fontweight="bold")
ax3[3].annotate("SWING", xy=(mid_swing, ax3[3].get_ylim()[0]), xytext=(0, 5),
                textcoords="offset points", ha="center", va="bottom",
                fontsize=10, color="#cb6a14", fontweight="bold")
ax3[3].grid(alpha=0.3)
ax3[3].legend(loc="upper left", fontsize=9)

fig2.suptitle(
    f"Ciclo del passo (HS→HS) — angoli signed Euler + foot pitch\n"
    f"{pkl_path.name},  cycle = {t_rel[h1]-t_rel[h0]:.2f}s,  TO@{to_pct:.0f}%",
    fontsize=12, y=0.995)
fig2.tight_layout()
plt.show()
