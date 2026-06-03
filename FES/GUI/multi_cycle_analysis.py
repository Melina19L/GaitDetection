"""Multi-cycle gait analysis from a plot_snapshot.pkl.

For each .pkl trial:
  1. Detect all valid knee-mid-swing peaks (= cycle anchors during real walking).
  2. Extract each consecutive cycle (peak → peak), time-normalize to 0-100%.
  3. Average across cycles → MEAN ± 1·SD bands.
  4. Plot the averaged curves vs the clinical reference (Whittle/Perry).
  5. Print per-joint mean ROM with literature comparison.

Why this matters
----------------
A single cycle picked at random has noise of ±10° peak-to-peak from sensor
jitter, magnetic drift, irregular stride, etc.  Averaging 10+ cycles cancels
most of this noise and gives a stable estimate of the subject's gait pattern.
Standard practice in clinical gait labs (Whittle, Perry).

Usage:
    python3 multi_cycle_analysis.py <trial>_plot.pkl
"""
import pickle, sys
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks


# ── LOAD ─────────────────────────────────────────────────────────────────
if len(sys.argv) < 2:
    print("Usage: python3 multi_cycle_analysis.py <plot.pkl>")
    sys.exit(1)

pkl_path = Path(sys.argv[1])
with open(pkl_path, "rb") as f:
    d = pickle.load(f)

side = "right"
knee_a = np.asarray(d[f"{side}_knee_angles"])
knee_t = np.asarray(d[f"{side}_knee_timestamps"])
ank_a  = np.asarray(d[f"{side}_ankle_angles"])
ank_t  = np.asarray(d[f"{side}_ankle_timestamps"])
hip_a  = np.asarray(d[f"{side}_hip_angles"])
hip_t  = np.asarray(d[f"{side}_hip_timestamps"])

# Shared t0 (use min timestamp as origin)
t0 = min(knee_t.min(), ank_t.min(), hip_t.min())
knee_t -= t0; ank_t -= t0; hip_t -= t0


# ── DETECT KNEE MID-SWING PEAKS (= cycle anchors) ─────────────────────────
# Mid-swing peaks > 30° clearly identify walking moments
peaks, _ = find_peaks(knee_a, distance=20, prominence=20, height=30)
print(f"Knee mid-swing peaks: {len(peaks)} found")

# Pair consecutive peaks → cycles in the normal duration range
cycles = []
for i in range(len(peaks) - 1):
    dur = knee_t[peaks[i+1]] - knee_t[peaks[i]]
    if 0.7 <= dur <= 1.5:
        cycles.append((peaks[i], peaks[i+1]))
print(f"Valid cycles (0.7-1.5 s): {len(cycles)}")

if len(cycles) < 3:
    print("\n⚠ Less than 3 cycles. Multi-cycle averaging needs ≥3.")
    sys.exit(1)


# ── EXTRACT EACH CYCLE NORMALIZED 0-100% ──────────────────────────────────
N_PCT = 101                     # 0..100 % in 1% steps
SHIFT_PCT = 25.0                # roll so HS≈0% (mid-swing was at ~75%)

def normalize_cycle(arr, ts, t_lo, t_hi):
    mask = (ts >= t_lo) & (ts <= t_hi)
    seg, tseg = arr[mask], ts[mask]
    if seg.size < 5:
        return None
    pct_native = 100.0 * (tseg - t_lo) / (t_hi - t_lo)
    grid = np.linspace(0, 100, N_PCT)
    # Shift so HS ~ 0% (knee mid-swing is at ~75% of HS-HS cycle)
    pct_native = (pct_native + SHIFT_PCT) % 100
    order = np.argsort(pct_native)
    return np.interp(grid, pct_native[order], seg[order])

knee_mat, ank_mat, hip_mat = [], [], []
for (i0, i1) in cycles:
    t_lo, t_hi = knee_t[i0], knee_t[i1]
    k = normalize_cycle(knee_a, knee_t, t_lo, t_hi)
    a = normalize_cycle(ank_a,  ank_t,  t_lo, t_hi)
    h = normalize_cycle(hip_a,  hip_t,  t_lo, t_hi)
    if k is not None: knee_mat.append(k)
    if a is not None: ank_mat.append(a)
    if h is not None: hip_mat.append(h)

knee_mat = np.array(knee_mat)
ank_mat  = np.array(ank_mat)
hip_mat  = np.array(hip_mat)
print(f"\nCycles per joint:  knee={len(knee_mat)},  ankle={len(ank_mat)},  hip={len(hip_mat)}")


# ── MEAN ± SD ─────────────────────────────────────────────────────────────
pct = np.linspace(0, 100, N_PCT)
def mean_sd(mat): return mat.mean(axis=0), mat.std(axis=0)

knee_m, knee_s = mean_sd(knee_mat)
ank_m,  ank_s  = mean_sd(ank_mat)
hip_m,  hip_s  = mean_sd(hip_mat)


# ── ROM TABLE -------------------------------------------------------------
print(f"\n{'Joint':<8}{'mean ROM':>11}{'ROM SD':>9}{'Lit':>10}    Status")
print("-" * 62)
def row(name, m, lit_text, lit_target):
    rom_per_cycle = [c.max() - c.min() for c in
                     (knee_mat if name=='Knee' else
                      ank_mat  if name=='Ankle' else hip_mat)]
    mean_rom = float(np.mean(rom_per_cycle))
    sd_rom   = float(np.std(rom_per_cycle))
    err_pct  = 100 * (mean_rom - lit_target) / lit_target
    status = "✓"  if abs(err_pct) < 20 else ("⚠" if abs(err_pct) < 50 else "✗")
    print(f"{name:<8}{mean_rom:>9.1f}°{sd_rom:>+7.1f}°{lit_text:>9}    {status}  Δ={err_pct:+.0f}%")

row("Hip",   hip_m,  "~35°", 35.0)
row("Knee",  knee_m, "~60°", 60.0)
row("Ankle", ank_m,  "~30°", 30.0)


# ── PLOT (4 panels: hip / knee / ankle + per-cycle overlay) ───────────────
fig, ax = plt.subplots(3, 1, figsize=(11, 10), sharex=True)
TO_PCT = 60.0

# Clinical reference curves (Whittle/Perry schematic)
ref_ank = np.where(pct<10, -5*np.sin(np.pi*pct/10),
          np.where(pct<50, 12*np.sin(np.pi*(pct-10)/40)-1,
          np.where(pct<70, 8 - 28*np.sin(np.pi*(pct-50)/40),
                          -20+15*np.sin(np.pi*(pct-70)/30/2))))
ref_kne = np.where(pct<20, 5+15*np.sin(np.pi*pct/20),
          np.where(pct<40, 5+5*np.sin(np.pi*(40-pct)/20),
          np.where(pct<75, 5+60*(pct-40)/35,
                           65-60*(pct-75)/25)))
ref_hip = np.where(pct<50, 25-35*(pct/50), -10+35*((pct-50)/50))

# ── Ankle
for c in ank_mat:
    ax[0].plot(pct, c, color="purple", lw=0.6, alpha=0.18)
ax[0].plot(pct, ank_m, color="purple", lw=2.5, label=f"Mean (n={len(ank_mat)})")
ax[0].fill_between(pct, ank_m-ank_s, ank_m+ank_s, color="purple", alpha=0.25, label="±1 SD")
ax[0].plot(pct, ref_ank, "k--", lw=1.2, alpha=0.6, label="Clinical ref")
ax[0].axvline(TO_PCT, color="red", ls=":", alpha=0.5)
ax[0].set_ylabel("Ankle (°)\n+dorsi / −plantar")
ax[0].set_title(f"Ankle — mean ROM {(ank_m.max()-ank_m.min()):.1f}° (lit ~30°)")
ax[0].grid(alpha=0.3); ax[0].axhline(0, color="k", lw=0.3); ax[0].legend(loc="lower left")

# ── Knee
for c in knee_mat:
    ax[1].plot(pct, c, color="orange", lw=0.6, alpha=0.18)
ax[1].plot(pct, knee_m, color="orange", lw=2.5, label=f"Mean (n={len(knee_mat)})")
ax[1].fill_between(pct, knee_m-knee_s, knee_m+knee_s, color="orange", alpha=0.25, label="±1 SD")
ax[1].plot(pct, ref_kne, "k--", lw=1.2, alpha=0.6, label="Clinical ref")
ax[1].axvline(TO_PCT, color="red", ls=":", alpha=0.5)
ax[1].set_ylabel("Knee (°)\n+flex")
ax[1].set_title(f"Knee — mean ROM {(knee_m.max()-knee_m.min()):.1f}° (lit ~60°)")
ax[1].grid(alpha=0.3); ax[1].axhline(0, color="k", lw=0.3); ax[1].legend(loc="upper left")

# ── Hip
for c in hip_mat:
    ax[2].plot(pct, c, color="goldenrod", lw=0.6, alpha=0.18)
ax[2].plot(pct, hip_m, color="goldenrod", lw=2.5, label=f"Mean (n={len(hip_mat)})")
ax[2].fill_between(pct, hip_m-hip_s, hip_m+hip_s, color="goldenrod", alpha=0.25, label="±1 SD")
ax[2].plot(pct, ref_hip, "k--", lw=1.2, alpha=0.6, label="Clinical ref")
ax[2].axvline(TO_PCT, color="red", ls=":", alpha=0.5)
ax[2].set_ylabel("Hip (°)\n+flex / −ext")
ax[2].set_title(f"Hip — mean ROM {(hip_m.max()-hip_m.min()):.1f}° (lit ~35°)")
ax[2].grid(alpha=0.3); ax[2].axhline(0, color="k", lw=0.3); ax[2].legend(loc="upper left")
ax[2].set_xlabel("% gait cycle  (HS→HS)")

fig.suptitle(
    f"Multi-cycle gait analysis — {pkl_path.name}\n"
    f"n cycles per joint: knee {len(knee_mat)}, ankle {len(ank_mat)}, hip {len(hip_mat)}",
    fontsize=12, y=0.995)
fig.tight_layout()
out_png = pkl_path.parent / (pkl_path.stem + "_multicycle.png")
fig.savefig(out_png, dpi=110)
print(f"\nSaved plot: {out_png}")
plt.show()
