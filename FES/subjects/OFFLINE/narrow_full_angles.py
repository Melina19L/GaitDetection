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
import numpy as np
import h5py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

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


def run(sid, cfg):
    path = R._ROOT + f"{sid}/MAPP/Narrow Corridor_1/recording_data.h5"
    f = h5py.File(path, "r")
    T0 = float(f["Cameras/camera_2/frames"][0]["timestamp"])
    reps = parse_reps(f, T0)
    print(f"[{sid}] {len(reps)} repetitions")
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

    joints = ("knee", "hip", "ankle")
    nr = len(reps)
    fig, axs = plt.subplots(nr, 3, figsize=(15, 2.0 * nr), squeeze=False)
    for ri, (lab, ta, tb) in enumerate(reps):
        for ci, joint in enumerate(joints):
            ax = axs[ri][ci]
            for side, col in (("R", "C0"), ("L", "C3")):
                t, a = angles[(side, joint)]
                m = (t >= ta) & (t <= tb)
                ax.plot(t[m] - ta, a[m], col, lw=0.8, label=side)
            for fa, fb in cfg["fog"]:           # FOG band if it overlaps this rep
                if fb >= ta and fa <= tb:
                    ax.axvspan(max(fa, ta) - ta, min(fb, tb) - ta,
                               color="red", alpha=0.35, lw=0)
            ax.grid(alpha=0.3); ax.tick_params(labelsize=6)
            if ri == 0:
                ax.set_title(joint, fontsize=10)
            if ci == 0:
                ax.set_ylabel(f"{lab}\n(deg)", fontsize=6.5)
            if ri == nr - 1:
                ax.set_xlabel("time in rep (s)", fontsize=7)
    axs[0][2].legend(loc="upper right", fontsize=7)
    fig.suptitle(f"{sid} Narrow Corridor - joint angles per repetition "
                 "(red = scored FOG; angles unreliable during turns)", y=0.997)
    p = os.path.join(_HERE, f"{sid.lower()}_narrow_byrep_angles.png")
    fig.tight_layout(); fig.savefig(p, dpi=110); plt.close(fig)
    print("saved", p)


if __name__ == "__main__":
    for sid, cfg in SUBJ.items():
        run(sid, cfg)
