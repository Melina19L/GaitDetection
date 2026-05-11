"""
Offline gait-cycle analysis with PROPER signed sagittal-plane decomposition.

The live data path in ``angle_calibrator.py`` uses unsigned SAA for the knee
and the hip (angle between two segment X-axes via arccos of a dot product).
This collapses extension and inversion into the same sign as flexion, so the
post-test plots loose the hip-extension valley and the knee loading-response
bump.

This script LOADS THE RAW QUATERNIONS saved in the .pkl (added by
``save_data`` after the 2026-05-11 fix) and recomputes every joint angle as
the first Euler angle of the relative quaternion, picking the rotation order
so the medio-lateral axis comes first. The result is a *signed* sagittal-plane
flexion/extension that matches the clinical convention (Whittle / Perry).

Usage:
    python3 analyze_gait_cycle.py try1.pkl
"""
import pickle
import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
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

def qrotate_vec(q, v):
    """Rotate vector v by quaternion q (single sample). q in [w,x,y,z]."""
    qv = np.array([0.0, v[0], v[1], v[2]])
    return qmul(qmul(q, qv), qconj(q))[1:]

def to_scipy(q):
    """Convert [w,x,y,z] → scipy's [x,y,z,w]."""
    return np.stack([q[..., 1], q[..., 2], q[..., 3], q[..., 0]], axis=-1)


def auto_ml_axis_variance(q_prox, q_dist, ref_start, ref_end):
    """Detect the segment's medio-lateral local axis dynamically using variance.
    
    Walking is predominantly a sagittal-plane motion. The true medio-lateral axis 
    is simply the one that experiences the largest angular excursion (variance) 
    in the relative joint rotation during the gait cycle.
    """
    q_prox_ref = qnorm(q_prox[ref_start:ref_end].mean(axis=0, keepdims=True))
    q_dist_ref = qnorm(q_dist[ref_start:ref_end].mean(axis=0, keepdims=True))
    
    q_rel_now = qmul(qconj(q_prox), q_dist)
    q_rel_ref = qmul(qconj(q_prox_ref), q_dist_ref)
    
    q_delta = qmul(q_rel_now, qconj(q_rel_ref))
    flip = q_delta[..., 0] < 0
    q_delta[flip] = -q_delta[flip]
    
    var_xyz = np.var(q_delta[..., 1:], axis=0)
    return ['X', 'Y', 'Z'][np.argmax(var_xyz)]


# ── Signed sagittal joint angle ─────────────────────────────────────────────
def signed_sagittal_series(q_prox, q_dist, q_prox_ref, q_dist_ref, ml_axis_prox):
    """Compute the signed sagittal-plane joint angle (degrees) for every sample.

    Math:
        q_rel_t   = conj(q_prox(t))  · q_dist(t)         (distal in prox frame)
        q_rel_ref = conj(q_prox_ref) · q_dist_ref        (the same at neutral)
        q_delta   = q_rel_t · conj(q_rel_ref)            (change since neutral)
        first Euler angle of q_delta around the ML axis  = sagittal flex
    """
    q_rel_now = qmul(qconj(q_prox), q_dist)
    q_rel_ref = qmul(qconj(q_prox_ref), q_dist_ref)
    q_delta   = qmul(q_rel_now, qconj(q_rel_ref))
    # Canonicalise w ≥ 0 for continuity across the q/-q double cover
    flip = q_delta[..., 0] < 0
    q_delta[flip] = -q_delta[flip]
    # scipy Rotation expects [x, y, z, w]
    r = R.from_quat(to_scipy(qnorm(q_delta)))
    order = {'X': 'XYZ', 'Y': 'YXZ', 'Z': 'ZXY'}[ml_axis_prox]
    eulers = r.as_euler(order, degrees=True)
    return eulers[..., 0]   # first axis = sagittal flex


# ── Resample-to-common-timeline ─────────────────────────────────────────────
def resample_quaternions(q_in, ts_in, ts_target):
    """Nearest-neighbour pick of quaternion samples onto a target timeline.

    Used because the four sensors arrive at slightly different rates / phases.
    Nearest-neighbour preserves the original sample values without inventing
    interpolated rotations (which would require slerp and add complexity for
    very little benefit at 60 Hz with ≤17 ms gaps).
    """
    if q_in.shape[0] == 0:
        return np.full((ts_target.size, 4), np.nan)
    idx = np.searchsorted(ts_in, ts_target)
    idx = np.clip(idx, 0, q_in.shape[0] - 1)
    # Also check the previous index — searchsorted gives the right boundary
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

# Verify the .pkl has the new raw_* fields (added 2026-05-11).
side = "right"
needed = [f"raw_{side}_thigh_quat",  f"raw_{side}_shank_quat",
          f"raw_{side}_foot_quat",   "raw_pelvis_quat"]
missing = [k for k in needed if k not in d]
if missing:
    print("⚠  This .pkl does NOT contain raw quaternions:")
    for k in missing: print(f"     missing  {k}")
    print("Run a fresh test after the 2026-05-11 fix to angle_calibrator.save_data,")
    print("then re-save the plot from the Setup IMU dialog. The old .pkl only has")
    print("the computed (unsigned-SAA) angles which we cannot fix offline.")
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


# ── 2. COMMON TIMELINE — use the shank as the master clock ──────────────────
t_master = t_sh.copy()
t0 = t_master[0]
t_rel = t_master - t0
q_th_r = resample_quaternions(q_th, t_th, t_master)
q_sh_r = resample_quaternions(q_sh, t_sh, t_master)
q_ft_r = resample_quaternions(q_ft, t_ft, t_master)
q_pv_r = resample_quaternions(q_pv, t_pv, t_master)

fs = 1.0 / np.median(np.diff(t_master))
print(f"\nMaster clock = shank ({t_master.size} samples, {t_rel[-1]:.1f} s, ~{fs:.1f} Hz)")


# ── 3. STATIC REFERENCE — use the GUI's calibrated angles as the anchor ─────
# The previous "look for any quiet window" heuristic was fooled by BLE
# warm-up at t=0..5s, where all sensors return frozen quaternions for a few
# seconds before they start streaming valid data. That period IS quiet but
# does not correspond to the user's neutral pose.
#
# The .pkl carries the SAA-calibrated knee/ankle/hip angles (one number per
# sample, computed from the GUI's "Calibrate Offsets"). They read ~0° iff
# the user is genuinely in the calibrated N-pose. Find a contiguous window
# where ALL THREE computed angles are within a tight band, and use the raw
# quaternions at that moment as the reference for our signed Euler math.

knee_pkl  = np.asarray(d[f"{side}_knee_angles"],     dtype=np.float64)
knee_tpkl = np.asarray(d[f"{side}_knee_timestamps"], dtype=np.float64)
ank_pkl   = np.asarray(d[f"{side}_ankle_angles"],    dtype=np.float64)
ank_tpkl  = np.asarray(d[f"{side}_ankle_timestamps"],dtype=np.float64)
hip_pkl   = np.asarray(d[f"{side}_hip_angles"],      dtype=np.float64)
hip_tpkl  = np.asarray(d[f"{side}_hip_timestamps"],  dtype=np.float64)

# Interpolate the computed angles onto the shank master clock so all 3
# streams share the same time index as our raw quaternions.
def _interp_to(t_target, t_src, val_src):
    if t_src.size == 0:
        return np.full_like(t_target, np.nan)
    return np.interp(t_target, t_src, val_src,
                     left=np.nan, right=np.nan)

knee_at_master = _interp_to(t_master, knee_tpkl, knee_pkl)
ank_at_master  = _interp_to(t_master, ank_tpkl,  ank_pkl)
hip_at_master  = _interp_to(t_master, hip_tpkl,  hip_pkl)

# Tight thresholds: the user is in N-pose only if every joint reads ~0°.
NPOSE_KNEE  = 3.0
NPOSE_ANKLE = 3.0
NPOSE_HIP   = 5.0   # hip naturally drifts a bit more on the pelvis sensor

npose_mask = (
    np.isfinite(knee_at_master) &
    np.isfinite(ank_at_master)  &
    np.isfinite(hip_at_master)  &
    (np.abs(knee_at_master) < NPOSE_KNEE)  &
    (np.abs(ank_at_master)  < NPOSE_ANKLE) &
    (np.abs(hip_at_master)  < NPOSE_HIP)
)
# Require a contiguous window of ≥ 0.5 s of stillness.
WIN = int(0.5 * fs)

def _longest_run(mask):
    """Return (start, length) of the longest True run in ``mask``."""
    best_start, best_len = -1, 0
    run_start, run_len = -1, 0
    for i, m in enumerate(mask):
        if m:
            if run_start < 0: run_start = i
            run_len += 1
        else:
            if run_len > best_len:
                best_start, best_len = run_start, run_len
            run_start, run_len = -1, 0
    if run_len > best_len:
        best_start, best_len = run_start, run_len
    return best_start, best_len

ref_start, ref_len = _longest_run(npose_mask)
if ref_start < 0 or ref_len < WIN:
    print("\n⚠ Could not find a contiguous 0.5 s window where all three")
    print(f"  GUI-computed angles read |.|<{NPOSE_KNEE}° (knee/ankle) and")
    print(f"  |.|<{NPOSE_HIP}° (hip). The .pkl was probably saved without")
    print("  a clean N-pose moment after Calibrate Offsets. Walk back into")
    print("  N-pose for ≥ 1 s during the recording, then re-save.")
    sys.exit(1)

# Use the middle of the longest static window for the reference average
ref_end = ref_start + min(ref_len, int(1.0 * fs))   # cap at 1 s
print(f"N-pose reference window (from GUI-computed angles ~0):")
print(f"   samples {ref_start}..{ref_end}  "
      f"(t = {t_rel[ref_start]:.2f}..{t_rel[ref_end-1]:.2f} s, {ref_len} samples)")
print(f"   knee  during ref: mean {knee_at_master[ref_start:ref_end].mean():+.2f}°, "
      f"std {knee_at_master[ref_start:ref_end].std():.2f}°")
print(f"   ankle during ref: mean {ank_at_master[ref_start:ref_end].mean():+.2f}°, "
      f"std {ank_at_master[ref_start:ref_end].std():.2f}°")
print(f"   hip   during ref: mean {hip_at_master[ref_start:ref_end].mean():+.2f}°, "
      f"std {hip_at_master[ref_start:ref_end].std():.2f}°")

q_th_ref = qnorm(q_th_r[ref_start:ref_end].mean(axis=0))
q_sh_ref = qnorm(q_sh_r[ref_start:ref_end].mean(axis=0))
q_ft_ref = qnorm(q_ft_r[ref_start:ref_end].mean(axis=0))
q_pv_ref = qnorm(q_pv_r[ref_start:ref_end].mean(axis=0))

# Auto-detect medio-lateral axis using dynamic variance over the gait cycle
ml_thigh  = auto_ml_axis_variance(q_th_r, q_sh_r, ref_start, ref_end)
ml_shank  = auto_ml_axis_variance(q_sh_r, q_ft_r, ref_start, ref_end)
ml_pelvis = auto_ml_axis_variance(q_pv_r, q_th_r, ref_start, ref_end)
print(f"Auto-detected medio-lateral axes (by variance): pelvis = {ml_pelvis}, "
      f"thigh = {ml_thigh}, shank = {ml_shank}")


# ── 4. COMPUTE SIGNED SAGITTAL ANGLES (Euler decomposition) ─────────────────
# Knee = thigh ↔ shank,  ML axis taken in the THIGH frame (proximal)
knee  = signed_sagittal_series(q_th_r, q_sh_r, q_th_ref, q_sh_ref, ml_thigh)
# Hip = pelvis ↔ thigh, ML axis in the PELVIS frame
hip   = signed_sagittal_series(q_pv_r, q_th_r, q_pv_ref, q_th_ref, ml_pelvis)
# Ankle = shank ↔ foot, ML axis in the SHANK frame
ankle = signed_sagittal_series(q_sh_r, q_ft_r, q_sh_ref, q_ft_ref, ml_shank)

# Fix signs to match clinical conventions (Whittle / Perry)
# Knee and Hip flexion are positive in clinical convention. 
# They naturally spend more time / have higher peaks in flexion.
if np.abs(np.min(knee)) > np.max(knee):
    print("   ⚠ Sign-flipped: Knee flexion appeared negative. Inverting.")
    knee = -knee
if np.abs(np.min(hip)) > np.max(hip):
    print("   ⚠ Sign-flipped: Hip flexion appeared negative. Inverting.")
    hip = -hip


# ── 5. DETECT TOE-OFFS + DERIVE HEEL-STRIKES (HS-HS convention) ─────────────
# The new Euler-based math gives physiological magnitudes (~10-20° plantar at
# toe-off, not the ~50° the old SAA produced). Use ADAPTIVE thresholds
# instead of fixed 15° so the detection survives whatever the current data
# magnitude is. Also try BOTH polarities — depending on how the medio-lateral
# axis sign falls out of the auto-detection, plantar may be the local minima
# OR the local maxima.
print(f"\nAnkle signal stats: range [{ankle.min():+.1f}..{ankle.max():+.1f}]°, "
      f"std = {ankle.std():.1f}°")

def detect_gait_events(signal, fs, label="signal"):
    """Try both polarities of ``signal``, return the one with more clean peaks.
    Adaptive threshold = 0.5 × signal range, capped at 30°."""
    rng = float(signal.max() - signal.min())
    if rng < 8.0:
        print(f"   {label}: range only {rng:.1f}° — no walking-like motion.")
        return np.array([], dtype=int), False
    # Threshold scales with the actual data, but never below 4° (= rejects
    # micro-jitter) or above 30° (= keeps real ROM in).
    thr = max(4.0, min(0.3 * rng, 30.0))
    prom = max(4.0, min(0.4 * rng, 30.0))
    print(f"   {label}: adaptive thresholds  height ≥ {thr:.1f}°,  "
          f"prominence ≥ {prom:.1f}°  (signal range {rng:.1f}°)")

    # Try plantar = NEGATIVE direction (standard convention)
    pks_neg, _ = find_peaks(-signal, distance=int(0.5 * fs),
                              prominence=prom, height=thr)
    # Also try plantar = POSITIVE (sign-flipped axis)
    pks_pos, _ = find_peaks(+signal, distance=int(0.5 * fs),
                              prominence=prom, height=thr)
    if len(pks_neg) >= len(pks_pos):
        return pks_neg, False    # standard polarity, no flip
    return pks_pos, True         # need to flip the ankle sign for plot

toe_offs, flip_sign = detect_gait_events(ankle, fs, label="ankle")
if flip_sign:
    print("   ⚠ Sign-flipped: ankle plantar appears POSITIVE in the raw")
    print("      Euler output. Inverting so plots use the clinical convention.")
    ankle = -ankle

print(f"Toe-offs detected: {len(toe_offs)}")
for i, idx in enumerate(toe_offs[:15]):
    print(f"   TO #{i+1}:  t = {t_rel[idx]:6.2f}s   ankle = {ankle[idx]:+6.1f}°")
if len(toe_offs) < 2:
    print("\n⚠ Less than 2 toe-offs — couldn't identify walking.")
    print("  Plotting full buffer for diagnosis. If you DID walk, the ankle")
    print("  signal might be too noisy or the calibration was unstable.")
    fig_diag, axd = plt.subplots(3, 1, figsize=(14, 8), sharex=True)
    axd[0].plot(t_rel, ankle, color="purple", lw=0.8); axd[0].set_ylabel("Caviglia (°)"); axd[0].grid(alpha=0.3)
    axd[0].axhline(0, color="k", lw=0.4)
    axd[0].set_title(f"Buffer completo (no toe-offs trovati) — {pkl_path.name}")
    axd[1].plot(t_rel, knee, color="orange", lw=0.8); axd[1].set_ylabel("Ginocchio (°)"); axd[1].grid(alpha=0.3)
    axd[1].axhline(0, color="k", lw=0.4)
    axd[2].plot(t_rel, hip, color="goldenrod", lw=0.8); axd[2].set_ylabel("Anca (°)"); axd[2].grid(alpha=0.3)
    axd[2].axhline(0, color="k", lw=0.4)
    axd[2].set_xlabel("Tempo (s)")
    fig_diag.tight_layout()
    plt.show()
    sys.exit(0)

# HS = 40% of the TO-TO cycle after the previous TO
hs_times = [t_rel[toe_offs[i]] + 0.4 * (t_rel[toe_offs[i+1]] - t_rel[toe_offs[i]])
            for i in range(len(toe_offs) - 1)]
hs_times = np.array(hs_times)
print(f"Heel-strikes derived: {len(hs_times)}")


# ── 6. PLOT FULL BUFFER WITH EVENT MARKERS ──────────────────────────────────
fig1, axes = plt.subplots(3, 1, figsize=(14, 8), sharex=True)
hs_idx_plot = np.searchsorted(t_rel, hs_times)
hs_idx_plot = np.clip(hs_idx_plot, 0, t_rel.size - 1)

axes[0].plot(t_rel, ankle, color="purple", lw=0.8)
axes[0].axhline(0, color="k", lw=0.4)
axes[0].plot(t_rel[toe_offs], ankle[toe_offs], "v", color="red", ms=8, label="Toe-off")
axes[0].plot(t_rel[hs_idx_plot], ankle[hs_idx_plot], "^", color="green", ms=8, label="Heel-strike")
axes[0].set_ylabel("Caviglia (°)")
axes[0].grid(alpha=0.3)
axes[0].set_title(f"Buffer completo — {pkl_path.name}  (angoli ricalcolati da quaternioni grezzi)")
axes[0].legend(loc="upper right")

axes[1].plot(t_rel, knee, color="orange", lw=0.8)
axes[1].axhline(0, color="k", lw=0.4)
axes[1].set_ylabel("Ginocchio (°)")
axes[1].grid(alpha=0.3)

axes[2].plot(t_rel, hip, color="goldenrod", lw=0.8)
axes[2].axhline(0, color="k", lw=0.4)
axes[2].set_ylabel("Anca (°)")
axes[2].set_xlabel("Tempo (s)")
axes[2].grid(alpha=0.3)
fig1.tight_layout()


# ── 7. PICK THE CLEANEST HS-HS CYCLE ────────────────────────────────────────
def slice_by_time(arr, ts, t_lo, t_hi):
    mask = (ts >= t_lo) & (ts <= t_hi)
    return arr[mask], ts[mask]

best = None
best_score = -np.inf
for i in range(len(hs_times) - 1):
    t_start, t_end = hs_times[i], hs_times[i + 1]
    dur = t_end - t_start
    if not (0.7 <= dur <= 1.5):
        continue
    seg, _ = slice_by_time(ankle, t_rel, t_start, t_end)
    if seg.size < 10:
        continue
    score = seg.max() - seg.min()
    if score > best_score:
        best_score = score
        best = (t_start, t_end, dur)

if best is None:
    best = (hs_times[0], hs_times[1], hs_times[1] - hs_times[0])
t_start, t_end, dur = best
print(f"\n✓ Cycle (HS→HS): t = [{t_start:.2f}, {t_end:.2f}] s, dur = {dur:.2f} s")

for ax in axes:
    ax.axvspan(t_start, t_end, color="green", alpha=0.15)


# ── 8. EXTRACT EACH JOINT FOR THE CYCLE ─────────────────────────────────────
ank_c, ank_t = slice_by_time(ankle, t_rel, t_start, t_end)
kne_c, kne_t = slice_by_time(knee,  t_rel, t_start, t_end)
hip_c, hip_t = slice_by_time(hip,   t_rel, t_start, t_end)

def to_pct(t_seg, t_lo, t_hi):
    return 100.0 * (t_seg - t_lo) / (t_hi - t_lo)

ank_p = to_pct(ank_t, t_start, t_end)
kne_p = to_pct(kne_t, t_start, t_end)
hip_p = to_pct(hip_t, t_start, t_end)

print(f"   Ankle  dorsi peak: {ank_c.max():+.1f}°  (rif +5/+15)")
print(f"   Ankle  plantar peak: {ank_c.min():+.1f}°  (rif −15/−25)")
print(f"   Knee   peak flex: {kne_c.max():+.1f}°  (rif ~60° in swing)")
print(f"   Knee   loading bump (0-20%): {kne_c[kne_p < 20].max() if (kne_p < 20).any() else float('nan'):+.1f}°  (rif ~+15°)")
print(f"   Hip    peak flex: {hip_c.max():+.1f}°  (rif +25°)")
print(f"   Hip    peak ext:  {hip_c.min():+.1f}°  (rif −10°)")


# ── 9. PLOT ALL 3 JOINTS vs CLINICAL REFERENCE (HS-HS convention) ───────────
fig2, ax3 = plt.subplots(3, 1, figsize=(11, 10), sharex=True)
ref_pct = np.linspace(0, 100, 101)

# Schematic clinical curves (Whittle / Perry, normal walking)
def _ref_ankle():
    out = np.zeros(101)
    for i, p in enumerate(ref_pct):
        if   p < 10:       out[i] = -5 * np.sin(np.pi * p / 10.0)
        elif p < 50:       out[i] = 12 * np.sin(np.pi * (p - 10) / 40.0) - 1
        elif p < 70:       out[i] = 8 - 28 * np.sin(np.pi * (p - 50) / 40.0)
        else:
            x = (p - 70) / 30
            out[i] = -20 + 15 * np.sin(np.pi * x / 2.0)
    return out

def _ref_knee():
    out = np.zeros(101)
    for i, p in enumerate(ref_pct):
        if   p < 20:    out[i] = 5 + 15 * np.sin(np.pi * p / 20.0)
        elif p < 40:    out[i] = 5 + 5  * np.sin(np.pi * (40 - p) / 20.0)
        elif p < 75:    out[i] = 5 + 60 * (p - 40) / 35.0
        else:           out[i] = 65 - 60 * (p - 75) / 25.0
    return out

def _ref_hip():
    out = np.zeros(101)
    for i, p in enumerate(ref_pct):
        if   p < 50:    out[i] = 25 - 35 * (p / 50.0)
        else:           out[i] = -10 + 35 * ((p - 50) / 50.0)
    return out

ref_ankle = _ref_ankle()
ref_knee  = _ref_knee()
ref_hip   = _ref_hip()

ax3[0].plot(ank_p, ank_c, color="purple", lw=2.5, label="Misurata (Euler signed)")
ax3[0].plot(ref_pct, ref_ankle, "k--", lw=1.2, alpha=0.6, label="Riferimento clinico")
ax3[0].fill_between(ref_pct, ref_ankle - 5, ref_ankle + 5, color="gray", alpha=0.15)
ax3[0].axhline(0, color="k", lw=0.3)
ax3[0].axvline(60, color="red", ls=":", alpha=0.4, label="Toe-off (~60%)")
ax3[0].set_ylabel("Caviglia (°)\n+dorsi / −plantar")
ax3[0].set_title(f"Caviglia — dorsi {ank_c.max():+.1f}°, plantar {ank_c.min():+.1f}°")
ax3[0].legend(loc="lower left", fontsize=9)
ax3[0].grid(alpha=0.3)
ax3[0].set_ylim(-50, 30)

ax3[1].plot(kne_p, kne_c, color="orange", lw=2.5, label="Misurata (Euler signed)")
ax3[1].plot(ref_pct, ref_knee, "k--", lw=1.2, alpha=0.6, label="Riferimento clinico")
ax3[1].fill_between(ref_pct, ref_knee - 5, ref_knee + 5, color="gray", alpha=0.15)
ax3[1].axhline(0, color="k", lw=0.3)
ax3[1].axvline(60, color="red", ls=":", alpha=0.4)
ax3[1].set_ylabel("Ginocchio (°)\n+flex")
ax3[1].set_title(f"Ginocchio — peak flex {kne_c.max():+.1f}° (rif ~60°)")
ax3[1].legend(loc="upper left", fontsize=9)
ax3[1].grid(alpha=0.3)
ax3[1].set_ylim(-15, 80)

ax3[2].plot(hip_p, hip_c, color="goldenrod", lw=2.5, label="Misurata (Euler signed)")
ax3[2].plot(ref_pct, ref_hip, "k--", lw=1.2, alpha=0.6, label="Riferimento clinico")
ax3[2].fill_between(ref_pct, ref_hip - 5, ref_hip + 5, color="gray", alpha=0.15)
ax3[2].axhline(0, color="k", lw=0.3)
ax3[2].axvline(60, color="red", ls=":", alpha=0.4)
ax3[2].set_ylabel("Anca (°)\n+flex / −ext")
ax3[2].set_xlabel("% Ciclo del passo  (Heel-strike → Heel-strike)")
ax3[2].set_title(f"Anca — flex {hip_c.max():+.1f}°, ext {hip_c.min():+.1f}° (rif +25/−10)")
ax3[2].legend(loc="upper left", fontsize=9)
ax3[2].grid(alpha=0.3)
ax3[2].set_ylim(-25, 40)

fig2.suptitle(
    f"Ciclo del passo (HS→HS) — angoli ricalcolati con Euler decomposition\n"
    f"{pkl_path.name},  cycle = {dur:.2f}s",
    fontsize=12, y=0.995)
fig2.tight_layout()
plt.show()
