"""Per-sensor FOG-detection separability over the WHOLE Narrow Corridor task,
using the ELAN (.eaf) annotations to build the negative classes.

For each subject the Freeze Index is computed over the full recording (acc-norm,
no orientation fusion needed) for the known-placement sensors (COMETA legs +
WIMU). FOG is then contrasted against TWO annotation-derived negatives:
  * task = ALL annotated activity except FOG (straight walking + turns + narrow)
  * turn = only the Turn-Left / Turn-Right annotations (no FOG)

Bar plot per subject: Cohen's d for both negatives, AUC labelled.
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
import reconstruct_fog_h5 as R                 # FI + _sep + paths
from narrow_full_angles import parse_eaf, EAF_PATH, SUBJ   # EAF + sensor maps

FOG_GUARD = 2.0   # s, exclude +-this around FOG from the negatives


def fi_full(sid, cfg):
    """Freeze Index over the full recording for each known-placement sensor.
    Returns {name: (t_centers_s, FI)}."""
    path = R._ROOT + f"{sid}/MAPP/Narrow Corridor_1/recording_data.h5"
    f = h5py.File(path, "r")
    T0 = float(f["Cameras/camera_2/frames"][0]["timestamp"])
    d_co = f["Cometa/WaveX_IMU/data"]
    t_co = f["Cometa/WaveX_IMU/timestamps"][:] - T0
    out = {}
    for (side, seg), blk in cfg["cometa"].items():
        acc = d_co[:, blk * 9:blk * 9 + 3].astype(np.float64)
        norm = np.sqrt((acc ** 2).sum(1))
        c, fi, _ = R.freeze_index(norm, 2000.0)
        out[f"COM_{side}_{seg}"] = (c + t_co[0], fi)
    for name, dev in cfg["wimu"].items():
        d = f["WIMU/WIMU_MK3/data_" + dev][:]
        t = f["WIMU/WIMU_MK3/timestamps_" + dev][:] - T0
        fs = 1.0 / np.median(np.diff(t))
        norm = np.sqrt((d[:, 1:4].astype(np.float64) ** 2).sum(1))
        c, fi, _ = R.freeze_index(norm, fs)
        out[f"WIMU_{name}"] = (c + t[0], fi)
    f.close()
    return out


def spans_mask(t, spans):
    m = np.zeros(len(t), bool)
    for a, b in spans:
        m |= (t >= a) & (t <= b)
    return m


def run(sid, cfg):
    annots = parse_eaf(EAF_PATH[sid])
    fog = [(a, b) for a, b, tier, v in annots if "fog" in (tier + v).lower()]
    turn = [(a, b) for a, b, tier, v in annots if "turn" in v.lower()]
    task = [(a, b) for a, b, tier, v in annots          # all activity, not FOG
            if "fog" not in (tier + v).lower()]
    fog_guard = [(a - FOG_GUARD, b + FOG_GUARD) for a, b in fog]
    print(f"[{sid}] FOG spans={len(fog)} turn spans={len(turn)} task spans={len(task)}")

    fis = fi_full(sid, cfg)
    rows = []
    for name, (t, fi) in fis.items():
        if not len(fi):
            continue
        guard = spans_mask(t, fog_guard)
        m_fog = spans_mask(t, fog)
        m_turn = spans_mask(t, turn) & ~guard
        m_task = spans_mask(t, task) & ~guard
        d_t, auc_t = R._sep(fi[m_fog], fi[m_task])
        d_u, auc_u = R._sep(fi[m_fog], fi[m_turn])
        rows.append((name, d_t, auc_t, d_u, auc_u))
    rows.sort(key=lambda r: r[3], reverse=True)
    print(f"   {'sensor':16s} {'d_task':>7} {'AUC':>5} | {'d_turn':>7} {'AUC':>5}")
    for n, dt, at, du, au in rows:
        print(f"   {n:16s} {dt:+7.2f} {at:5.2f} | {du:+7.2f} {au:5.2f}")

    names = [r[0] for r in rows]
    x = np.arange(len(names)); w = 0.4
    fig, ax = plt.subplots(figsize=(13, 6))
    ax.bar(x - w/2, [r[1] for r in rows], w, color="0.6", label="vs whole task")
    ax.bar(x + w/2, [r[3] for r in rows], w, color="C3", label="vs turns only")
    for i, r in enumerate(rows):
        ax.text(i - w/2, r[1] + 0.04, f"{r[2]:.2f}", ha="center", fontsize=6, color="0.4")
        ax.text(i + w/2, r[3] + 0.04, f"{r[4]:.2f}", ha="center", fontsize=6, color="C3")
    ax.axhline(0.8, color="k", ls=":", lw=1, label="d=0.8 (large)")
    ax.set_xticks(x); ax.set_xticklabels(names, rotation=60, ha="right", fontsize=8)
    ax.set_ylabel("Cohen's d  (FI: FOG vs negative)")
    ax.set_title(f"{sid} Narrow Corridor - FOG separability per sensor over the "
                 "WHOLE task (EAF annotations; AUC on bars)")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(alpha=0.3, axis="y")
    p = os.path.join(_HERE, f"{sid.lower()}_narrow_ranking_wholetask.png")
    fig.tight_layout(); fig.savefig(p, dpi=120); plt.close(fig)
    print("saved", p)


if __name__ == "__main__":
    for sid, cfg in SUBJ.items():
        run(sid, cfg)
