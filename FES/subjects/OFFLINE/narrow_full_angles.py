"""Per-repetition joint angles for the Narrow Corridor task (FOG002/004/006).

One figure per subject: one ROW per repetition (START..STOP markers from
logs/events) x 3 columns (knee/hip/ankle), bilateral, with the visually-scored
FOG episodes shaded red where they fall inside a repetition.

Calibration = first 10 s standing (neutral-pose offset), same as reconstruct_fog_h5.
COMETA mapping per subject (FOG002 resolved; FOG004/006 = muscle montage RF/TA).
Reuses the maths in reconstruct_fog_h5.py.
"""
import os
import sys
import xml.etree.ElementTree as ET
import numpy as np
import h5py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import reconstruct_fog_h5 as R          # sets up FES/GUI path + reusable maths
from stimulator.closed_loop import (
    angle_between_quaternions, AXIS_VECTORS,
    detect_most_vertical_axis, detect_most_horizontal_axis,
)

CALIB = (0.0, 10.0)
PLOT_FS = 20.0                          # Hz, decimated rate for full-duration plot

# ELAN (.eaf) annotation files. Time values (ms) are aligned to the same video
# t=0 as our T0 (verified: EAF FOG tier matches the scored FOG seconds).
_EAF = ("/Users/chiaracazzoli/Library/CloudStorage/OneDrive-epfl.ch/"
        "File di Daniel Leal - ")
EAF_PATH = {
    "FOG002": _EAF + "FOG002/task_narrowCorridor_FOG002.eaf",
    "FOG004": _EAF + "FOG004/task_narrowCorridor_FOG004.eaf",
    "FOG006": _EAF + "FOG006/task_narrowcorridor_FOG006.eaf",
}
# annotation value -> (band color, alpha, legend label)
BAND_STYLE = [
    ("fog", "red", 0.40, "FOG"),
    ("straight walking", "green", 0.22, "straight walking"),
    ("turn - left", "orange", 0.32, "turn left"),
    ("turn - right", "gold", 0.34, "turn right"),
    ("narrow corridor", "lightblue", 0.30, "narrow corridor"),
]


def parse_eaf(path):
    """Return [(start_s, end_s, tier, value)] from an ELAN .eaf file."""
    root = ET.parse(path).getroot()
    ts = {s.get("TIME_SLOT_ID"): int(s.get("TIME_VALUE"))
          for s in root.iter("TIME_SLOT") if s.get("TIME_VALUE") is not None}
    out = []
    for tier in root.iter("TIER"):
        tid = tier.get("TIER_ID")
        for aa in tier.iter("ALIGNABLE_ANNOTATION"):
            v = (aa.find("ANNOTATION_VALUE").text or "").strip()
            a, b = ts.get(aa.get("TIME_SLOT_REF1")), ts.get(aa.get("TIME_SLOT_REF2"))
            if a is not None and b is not None:
                out.append((a / 1000.0, b / 1000.0, tid, v))
    return out


def band_style(tier, value):
    s = (tier + " " + value).lower()
    for key, col, alpha, lab in BAND_STYLE:
        if key in s:
            return col, alpha, lab
    return None, 0.0, None

# Narrow Corridor, FOG episodes = seconds from recording start (video t=0).
SUBJ = {
    "FOG002": {
        "wimu": {"R_foot": "dev5", "L_foot": "dev2", "pelvis": "dev7"},
        "cometa": {("R", "thigh"): 4, ("R", "shin"): 0,
                   ("L", "thigh"): 5, ("L", "shin"): 1},   # resolved montage
        "fog": [(112.53, 113.59), (831.42, 836.75)],
    },
    "FOG004": {
        "wimu": {"R_foot": "dev7", "L_foot": "dev2", "pelvis": "dev5"},
        "cometa": {("R", "thigh"): 0, ("R", "shin"): 2,
                   ("L", "thigh"): 1, ("L", "shin"): 3},   # RF=thigh, TA=shin
        "fog": [(324.63, 326.29), (571.2, 571.8)],
    },
    "FOG006": {
        "wimu": {"R_foot": "dev6", "L_foot": "dev2", "pelvis": "dev5"},
        "cometa": {("R", "thigh"): 0, ("R", "shin"): 2,
                   ("L", "thigh"): 1, ("L", "shin"): 3},
        "fog": [(439.89, 442.29)],
    },
}


def parse_reps(f, T0):
    """Repetition windows from logs/events: pair MARKER START..STOP, label from
    the following REPETITION row. Returns [(label, t_start, t_stop), ...]."""
    starts, stops, labels = [], [], []
    for r in f["logs/events"][:]:
        ty, ta = str(r["type"]), str(r["task"])
        t = float(r["timestamp"]) - T0
        if "MARKER" in ty and "START" in ta:
            starts.append(t)
        elif "MARKER" in ty and "STOP" in ta:
            stops.append(t)
        elif "REPETITION" in ty:
            labels.append(ta.strip("b'\" ").replace("Repetition", "Rep"))
    reps = []
    for i, (a, b) in enumerate(zip(starts, stops)):
        lab = labels[i] if i < len(labels) else f"Rep {i+1}"
        reps.append((lab, a, b))
    return reps


def compute_angles(sid, cfg):
    """Full-recording bilateral knee/hip/ankle (decimated to PLOT_FS).
    Returns (angles{(side,joint):(t,a)}, reps, annots, qwi, twi)."""
    path = R._ROOT + f"{sid}/MAPP/Narrow Corridor_1/recording_data.h5"
    f = h5py.File(path, "r")
    T0 = float(f["Cameras/camera_2/frames"][0]["timestamp"])
    reps = parse_reps(f, T0)
    annots = parse_eaf(EAF_PATH[sid])     # (start_s, end_s, tier, value)
    print(f"[{sid}] {len(reps)} repetitions, {len(annots)} EAF annotations")
    t_co = f["Cometa/WaveX_IMU/timestamps"][:] - T0
    d_co = f["Cometa/WaveX_IMU/data"]
    n = len(t_co)
    print(f"[{sid}] fusing {n} COMETA samples ({t_co[-1]:.0f}s) x "
          f"{len(set(cfg['cometa'].values()))} blocks ...")
    qb = {}
    for blk in set(cfg["cometa"].values()):
        seg = d_co[:, blk * 9:blk * 9 + 9].astype(np.float64)
        qb[blk] = R.fuse(seg[:, 0:3], seg[:, 3:6], 2000.0)
    qco = {key: qb[blk] for key, blk in cfg["cometa"].items()}
    cm = (t_co >= CALIB[0]) & (t_co <= CALIB[1])

    qwi, twi = {}, {}
    for name, dev in cfg["wimu"].items():
        d = f["WIMU/WIMU_MK3/data_" + dev][:]
        twi[name] = f["WIMU/WIMU_MK3/timestamps_" + dev][:] - T0
        qwi[name] = d[:, 4:8]
    f.close()

    step = max(1, int(round(2000.0 / PLOT_FS)))
    idx = np.arange(0, n, step)
    angles = {}

    # knee (COMETA-COMETA)
    for side in ("R", "L"):
        qt, qs = qco[(side, "thigh")], qco[(side, "shin")]
        off = angle_between_quaternions(R.avg_quat(qt[cm]), R.avg_quat(qs[cm]))
        knee = np.array([angle_between_quaternions(qt[i], qs[i]) for i in idx]) - off
        angles[(side, "knee")] = (t_co[idx], knee)

    # hip (pelvis WIMU <-> thigh COMETA)
    pel, tp = qwi["pelvis"], twi["pelvis"]
    pcm = (tp >= CALIB[0]) & (tp <= CALIB[1])
    pidx = np.arange(0, len(tp), max(1, int(round(len(tp) / len(idx)))))
    for side in ("R", "L"):
        qt = qco[(side, "thigh")]
        off = angle_between_quaternions(R.avg_quat(pel[pcm]), R.avg_quat(qt[cm]))
        midx = R.nearest_match(t_co, tp[pidx])
        hip = np.array([angle_between_quaternions(pel[j], qt[midx[k]])
                        for k, j in enumerate(pidx)]) - off
        angles[(side, "hip")] = (tp[pidx], hip)

    # ankle (shin COMETA <-> foot WIMU, sagittal pitch difference)
    for side in ("R", "L"):
        foot = "R_foot" if side == "R" else "L_foot"
        qs = qco[(side, "shin")]
        tf = twi[foot]
        sref = R.avg_quat(qs[cm])
        fref = R.avg_quat(qwi[foot][(tf >= CALIB[0]) & (tf <= CALIB[1])])
        sax = AXIS_VECTORS[detect_most_vertical_axis(sref)]
        fax = AXIS_VECTORS[detect_most_horizontal_axis(fref)]
        off = R.long_axis_pitch(fref, fax) - R.long_axis_pitch(sref, sax)
        fidx = np.arange(0, len(tf), max(1, int(round(len(tf) / len(idx)))))
        sidx = R.nearest_match(t_co, tf[fidx])
        ank = np.array([R.long_axis_pitch(qwi[foot][j], fax)
                        - R.long_axis_pitch(qs[sidx[k]], sax)
                        for k, j in enumerate(fidx)]) - off
        angles[(side, "ankle")] = (tf[fidx], ank)
    return angles, reps, annots, qwi, twi


def run(sid, cfg):
    angles, reps, annots, qwi, twi = compute_angles(sid, cfg)
    joints = ("knee", "hip", "ankle")
    nr = len(reps)
    fig, axs = plt.subplots(nr, 3, figsize=(15, 2.0 * nr), squeeze=False)
    for ri, (lab, ta, tb) in enumerate(reps):
        for ci, joint in enumerate(joints):
            ax = axs[ri][ci]
            # activity / FOG bands from the EAF annotations overlapping this rep
            for sa, sb, tier, val in annots:
                if sb < ta or sa > tb:
                    continue
                col, alpha, _ = band_style(tier, val)
                if col:
                    ax.axvspan(max(sa, ta) - ta, min(sb, tb) - ta,
                               color=col, alpha=alpha, lw=0)
            for side, col in (("R", "C0"), ("L", "C3")):
                t, a = angles[(side, joint)]
                m = (t >= ta) & (t <= tb)
                ax.plot(t[m] - ta, a[m], col, lw=0.9)
            ax.grid(alpha=0.3); ax.tick_params(labelsize=6)
            if ri == 0:
                ax.set_title(joint, fontsize=10)
            if ci == 0:
                ax.set_ylabel(f"{lab}\n(deg)", fontsize=6.5)
            if ri == nr - 1:
                ax.set_xlabel("time in rep (s)", fontsize=7)
    handles = ([Patch(color="C0", label="R"), Patch(color="C3", label="L")]
               + [Patch(facecolor=c, alpha=al, label=lb) for _, c, al, lb in BAND_STYLE])
    fig.legend(handles=handles, loc="upper right", fontsize=8, ncol=7)
    fig.suptitle(f"{sid} Narrow Corridor - joint angles per repetition "
                 "(EAF activity bands; angles unreliable during turns)", y=0.998)
    p = os.path.join(_HERE, f"{sid.lower()}_narrow_byrep_angles.png")
    fig.tight_layout(); fig.savefig(p, dpi=110); plt.close(fig)
    print("saved", p)

    plot_gait_byrep(sid, reps, annots, qwi, twi)


def plot_gait_byrep(sid, reps, annots, qwi, twi):
    """Method-1 gait detection per repetition (both feet) with EAF activity bands.
    Sagittal foot angular velocity reconstructed from the WIMU quaternion; HS/TO
    via the same detector as reconstruct_fog_h5."""
    feet = [("R", "R_foot"), ("L", "L_foot")]
    gy_full, t_full = {}, {}
    for side, foot in feet:
        w = R.quat_angular_velocity(qwi[foot], twi[foot])
        gy = w[:, int(np.argmax(w.std(axis=0)))]
        if abs(gy.min()) > abs(gy.max()):
            gy = -gy
        gy_full[side], t_full[side] = gy, twi[foot]

    nr = len(reps)
    fig, axs = plt.subplots(nr, 2, figsize=(13, 2.0 * nr), squeeze=False)
    for ri, (lab, ta, tb) in enumerate(reps):
        for ci, (side, foot) in enumerate(feet):
            ax = axs[ri][ci]
            for sa, sb, tier, val in annots:
                if sb < ta or sa > tb:
                    continue
                col, alpha, _ = band_style(tier, val)
                if col:
                    ax.axvspan(max(sa, ta) - ta, min(sb, tb) - ta,
                               color=col, alpha=alpha, lw=0)
            t, gy = t_full[side], gy_full[side]
            m = (t >= ta) & (t <= tb)
            tr, gr = t[m] - ta, gy[m]
            if len(gr) > 20:
                fs = 1.0 / np.median(np.diff(t[m]))
                g = R.detect_gait(gr, tr, fs)
                ax.plot(tr, gr, "0.4", lw=0.7)
                ax.plot(tr[g["peaks"]], gr[g["peaks"]], "g.", ms=5)
                if len(g["hs"]):
                    ax.plot(tr[g["hs"]], gr[g["hs"]], "r^", ms=6)
                if len(g["to"]):
                    ax.plot(tr[g["to"]], gr[g["to"]], "bv", ms=6)
            ax.grid(alpha=0.3); ax.tick_params(labelsize=6)
            if ri == 0:
                ax.set_title(f"{side} foot ang.vel (deg/s)", fontsize=9)
            if ci == 0:
                ax.set_ylabel(lab, fontsize=6.5)
            if ri == nr - 1:
                ax.set_xlabel("time in rep (s)", fontsize=7)
    handles = ([plt.Line2D([], [], color="g", marker=".", ls="", label="mid-swing"),
                plt.Line2D([], [], color="r", marker="^", ls="", label="HS"),
                plt.Line2D([], [], color="b", marker="v", ls="", label="TO")]
               + [Patch(facecolor=c, alpha=al, label=lb) for _, c, al, lb in BAND_STYLE])
    fig.legend(handles=handles, loc="upper right", fontsize=8, ncol=8)
    fig.suptitle(f"{sid} Narrow Corridor - Method-1 gait detection per repetition "
                 "(EAF activity bands)", y=0.998)
    p = os.path.join(_HERE, f"{sid.lower()}_narrow_byrep_gait.png")
    fig.tight_layout(); fig.savefig(p, dpi=110); plt.close(fig)
    print("saved", p)


if __name__ == "__main__":
    for sid, cfg in SUBJ.items():
        run(sid, cfg)
