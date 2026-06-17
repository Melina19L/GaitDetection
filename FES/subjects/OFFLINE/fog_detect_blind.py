"""Blind FOG detection on one repetition: detect the freeze from the Freeze
Index WITHOUT using the scored FOG time, two ways -- (A) all known sensors
combined (consensus vote), (B) R_shin only -- and compare to the true FOG band.

Per-sensor threshold = mean+2SD of FI over NORMAL annotated activity ELSEWHERE
in the task (walk+turns of the other repetitions, FOG excluded). So the decision
never sees this repetition's freeze -> a fair blind test.

Targets: FOG002 Dual Task Rep 4 (idx8), FOG006 Single Task Rep 5 (idx4).
"""
import os
import sys
import numpy as np
import h5py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import reconstruct_fog_h5 as R
from narrow_full_angles import parse_eaf, parse_reps, EAF_PATH, SUBJ, band_style, BAND_STYLE
from fog_ranking_eaf import fi_full, spans_mask

TARGETS = [("FOG002", 8), ("FOG006", 4)]
GRID_DT = 0.10          # s, common time grid for combining sensors
PCT = 97.5              # threshold = this percentile of the sensor's normal-activity FI
VOTE = 2                # all-sensors: FOG where >= this many sensors exceed their threshold


def run(sid, rep_idx):
    cfg = SUBJ[sid]
    annots = parse_eaf(EAF_PATH[sid])
    fog = [(a, b) for a, b, ti, v in annots if "fog" in (ti + v).lower()]
    task = [(a, b) for a, b, ti, v in annots if "fog" not in (ti + v).lower()]

    path = R._ROOT + f"{sid}/MAPP/Narrow Corridor_1/recording_data.h5"
    f = h5py.File(path, "r"); T0 = float(f["Cameras/camera_2/frames"][0]["timestamp"])
    reps = parse_reps(f, T0); f.close()
    lab, ta, tb = reps[rep_idx]

    # FI on a common grid; threshold per sensor = high percentile of NORMAL
    # activity OUTSIDE this rep (matches the rank/AUC logic, robust to the skew
    # that turns add to the FI distribution).
    fis = fi_full(sid, cfg)
    grid = np.arange(ta, tb, GRID_DT)
    fi_g, thr, over = {}, {}, {}
    for name, (t, fi) in fis.items():
        base = spans_mask(t, task) & ~((t >= ta) & (t <= tb))
        thr[name] = np.percentile(fi[base], PCT) if base.sum() > 5 else np.inf
        fi_g[name] = np.interp(grid, t, fi)
        over[name] = fi_g[name] > thr[name]
    votes = np.sum([over[n] for n in fis], axis=0)
    det_all = R._mask_to_intervals(grid, votes >= VOTE)
    det_rs = R._mask_to_intervals(grid, over["COM_R_shin"])

    def bands(ax):
        for sa, sb, ti, v in annots:
            if sb < ta or sa > tb:
                continue
            col, al, _ = band_style(ti, v)
            if col and col != "red":
                ax.axvspan(max(sa, ta) - ta, min(sb, tb) - ta, color=col, alpha=al, lw=0)

    def true_fog(ax):
        for fa, fb in fog:
            if fb >= ta and fa <= tb:
                ax.axvspan(max(fa, ta) - ta, min(fb, tb) - ta, color="red", alpha=0.30, lw=0)

    def detected(ax, ivs):
        for a, b in ivs:
            ax.axvspan(a - ta, b - ta, facecolor="none", edgecolor="magenta", hatch="//", lw=0)

    fig, axs = plt.subplots(2, 1, figsize=(14, 7), sharex=True)
    # (A) all sensors combined - how many sensors exceed their normal-activity p97.5
    ax = axs[0]; bands(ax); true_fog(ax); detected(ax, det_all)
    ax.plot(grid - ta, votes, "k-", lw=1.2)
    ax.axhline(VOTE, color="purple", ls=":", lw=1.2, label=f"vote >= {VOTE}")
    ax.set_ylabel(f"# sensors above\np{PCT:g} (/{len(fis)})")
    ax.set_title(f"{sid} {lab} - blind FOG detection (red=true FOG, magenta=detected)\n"
                 f"(A) ALL {len(fis)} sensors fused (count above normal-activity p{PCT:g})", fontsize=10)
    ax.legend(loc="upper right", fontsize=8); ax.grid(alpha=0.3)

    # (B) R_shin only
    ax = axs[1]; bands(ax); true_fog(ax); detected(ax, det_rs)
    ax.plot(grid - ta, fi_g["COM_R_shin"], "C0-", lw=1.0)
    ax.axhline(thr["COM_R_shin"], color="purple", ls=":", lw=1.2,
               label=f"R_shin p{PCT:g} of normal activity")
    ax.set_ylabel("R_shin FI")
    ax.set_title("(B) R_shin only", fontsize=10)
    ax.set_xlabel("time in repetition (s)")
    ax.legend(loc="upper right", fontsize=8); ax.grid(alpha=0.3)

    handles = [Patch(facecolor=c, alpha=al, label=lb) for k, c, al, lb in BAND_STYLE if k != "fog"]
    handles += [Patch(facecolor="red", alpha=0.3, label="true FOG"),
                Patch(facecolor="none", edgecolor="magenta", hatch="//", label="detected")]
    fig.legend(handles=handles, loc="lower center", ncol=7, fontsize=8)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    p = os.path.join(_HERE, f"{sid.lower()}_rep{rep_idx}_blind_fog_detection.png")
    fig.savefig(p, dpi=120); plt.close(fig)
    print(f"[{sid} {lab}] det_all={[(round(a,1),round(b,1)) for a,b in det_all]} "
          f"det_Rshin={[(round(a,1),round(b,1)) for a,b in det_rs]}  saved {p}")


if __name__ == "__main__":
    for sid, idx in TARGETS:
        run(sid, idx)
