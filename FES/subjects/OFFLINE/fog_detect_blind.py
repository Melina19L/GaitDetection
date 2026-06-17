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
from narrow_full_angles import (parse_eaf, parse_reps, EAF_PATH, SUBJ,
                                 band_style, BAND_STYLE, compute_angles)
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

    def det_lines(ax, ivs):                # detected-FOG span (duration, dashed edge)
        for a, b in ivs:
            ax.axvspan(a - ta, b - ta, facecolor="magenta", alpha=0.25,
                       edgecolor="magenta", ls="--", lw=1.3)

    # joint angles for this repetition (background "pattern"), with the blind
    # FOG detection drawn as dashed vertical lines: left col = all-sensors
    # consensus, right col = R_shin only.
    angles, _, _, _, _ = compute_angles(sid, cfg)
    joints = ("knee", "hip", "ankle")
    cols = [("all sensors consensus", det_all), ("R_shin only", det_rs)]
    fig, axs = plt.subplots(3, 2, figsize=(15, 9), sharex=True, squeeze=False)
    for ri, joint in enumerate(joints):
        for ci, (cname, ivs) in enumerate(cols):
            ax = axs[ri][ci]
            bands(ax); true_fog(ax)
            for side, c in (("R", "C0"), ("L", "C3")):
                t, a = angles[(side, joint)]
                m = (t >= ta) & (t <= tb)
                ax.plot(t[m] - ta, a[m], c, lw=0.8)
            det_lines(ax, ivs)
            ax.grid(alpha=0.3); ax.tick_params(labelsize=7)
            if ri == 0:
                ax.set_title(f"detection: {cname}", fontsize=10)
            if ci == 0:
                ax.set_ylabel(f"{joint}\n(deg)")
            if ri == 2:
                ax.set_xlabel("time in repetition (s)")
    handles = [Patch(facecolor=c, alpha=al, label=lb) for k, c, al, lb in BAND_STYLE if k != "fog"]
    handles += [Patch(facecolor="red", alpha=0.3, label="true FOG"),
                Patch(facecolor="magenta", alpha=0.25, edgecolor="magenta",
                      ls="--", label="detected FOG")]
    fig.legend(handles=handles, loc="lower center", ncol=7, fontsize=8)
    fig.suptitle(f"{sid} {lab} - blind FOG detection on joint angles "
                 "(dashed = FOG detected from FI)", y=0.998)
    fig.tight_layout(rect=(0, 0.04, 1, 0.99))
    p = os.path.join(_HERE, f"{sid.lower()}_rep{rep_idx}_blind_fog_detection.png")
    fig.savefig(p, dpi=120); plt.close(fig)
    print(f"[{sid} {lab}] det_all={[(round(a,1),round(b,1)) for a,b in det_all]} "
          f"det_Rshin={[(round(a,1),round(b,1)) for a,b in det_rs]}  saved {p}")


if __name__ == "__main__":
    for sid, idx in TARGETS:
        run(sid, idx)
