"""Verifica dei joint angles ricalcolati con la pipeline CORRETTA.

Per ogni file ``*_plot.pkl`` di questa cartella (registrazioni gamba DESTRA):
  1. ricostruisce hip/knee/ankle dai quaternioni grezzi con il ROM corretto
     - knee  = thigh ↔ shank   (angle_between_quaternions, generico)
     - hip   = pelvis ↔ thigh   (generico)
     - ankle = shank ↔ foot     (METODO FUNZIONALE FIRMATO: extract_functional_angle
                                  con hinge axis SVD — quello attivato dal fix)
  2. deriva offline la calibrazione (i file vecchi non la contengono):
     - posa neutra = media dei quaternioni nella finestra più statica (~1 s)
     - hinge axis  = identify_hinge_axis(SVD) sul moto di cammino
  3. segmenta in cicli del passo (heel-strike dal pitch del piede, Aminian)
  4. normalizza 0-100 %, fa la media d'insieme (mean ± SD)
  5. confronta con le bande normative di cammino LENTO per soggetti sani.

Convenzione segno: + = flessione (hip/knee), + = dorsiflessione (ankle).
"""
import os
import sys
import glob
import pickle
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "GUI"))
from stimulator.closed_loop import (                       # noqa: E402
    angle_between_quaternions, extract_functional_angle, identify_hinge_axis,
    detect_most_vertical_axis, detect_most_horizontal_axis, normalize,
)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "GUI"))
from offline_gait_analyzer import _compute_foot_pitch, _aminian_gait_events_from_pitch  # noqa: E402

# ── Bande normative cammino LENTO, soggetto sano (≈0.6-0.9 m/s) ───────────────
# Approssimazione da Perry & Burnfield / Winter: (percentuali di ciclo, media°).
# Slow walk riduce le ampiezze rispetto al cammino a velocità naturale.
LIT = {
    "Hip flex(+)/ext(-)": {
        "x":   [0, 10, 30, 50, 62, 75, 87, 100],
        "mean":[22, 18,  6, -5, -8,  8, 20,  22],
        "sd":  5.0, "rom": (28, 40), "color": "#8be9fd",
    },
    "Knee flex(+)": {
        "x":   [0,  8, 15, 30, 45, 60, 70, 73, 85, 100],
        "mean":[4, 12, 15,  6,  4, 12, 50, 55, 30,  4],
        "sd":  6.0, "rom": (52, 65), "color": "#f1fa8c",
    },
    "Ankle dorsi(+)/plantar(-)": {
        "x":   [0,  8, 25, 45, 50, 62, 70, 80, 100],
        "mean":[0, -4,  3,  9,  6, -12, -8, -2,   0],
        "sd":  4.0, "rom": (20, 30), "color": "#50fa7b",
    },
}


def load(path):
    with open(path, "rb") as f:
        return pickle.load(f)


def build_pair(qa, ta, qb, tb):
    """Allinea due serie di quaternioni [w,x,y,z] sulla timeline di a (nearest)."""
    out_q_a, out_q_b, out_t = [], [], []
    for i in range(len(ta)):
        j = int(np.argmin(np.abs(tb - ta[i])))
        if abs(tb[j] - ta[i]) < 0.05:
            out_q_a.append(qa[i]); out_q_b.append(qb[j]); out_t.append(ta[i])
    return np.array(out_q_a), np.array(out_q_b), np.array(out_t)


def static_window(q, t, win_s=1.0):
    """Indici della finestra ~win_s più statica (minima velocità angolare)."""
    qn = q / (np.linalg.norm(q, axis=1, keepdims=True) + 1e-12)
    d = np.abs(np.sum(qn[1:] * qn[:-1], axis=1))
    ang_spd = 2 * np.arccos(np.clip(d, -1, 1))            # rad tra campioni
    dt = np.median(np.diff(t)) if len(t) > 1 else 1 / 60
    w = max(5, int(win_s / dt))
    csum = np.convolve(ang_spd, np.ones(w), "valid")
    s = int(np.argmin(csum))
    return s, s + w


def mean_quat(q):
    ref = q[0]
    aligned = np.array([qi if np.dot(qi, ref) > 0 else -qi for qi in q])
    m = aligned.mean(axis=0)
    return normalize(m)


def reconstruct(d):
    qp, tp = d["raw_pelvis_quat"],      d["raw_pelvis_timestamps"]
    qt, tt = d["raw_right_thigh_quat"], d["raw_right_thigh_timestamps"]
    qs, ts = d["raw_right_shank_quat"], d["raw_right_shank_timestamps"]
    qf, tf = d["raw_right_foot_quat"],  d["raw_right_foot_timestamps"]

    # neutra dalla finestra statica della shank, mappata su ogni segmento
    s0, s1 = static_window(qs, ts)
    t_lo, t_hi = ts[s0], ts[s1 - 1]

    def neutral(q, t):
        m = (t >= t_lo) & (t <= t_hi)
        return mean_quat(q[m]) if m.sum() >= 3 else mean_quat(q[:30])

    qp_ref, qt_ref, qs_ref, qf_ref = neutral(qp, tp), neutral(qt, tt), neutral(qs, ts), neutral(qf, tf)

    # ── KNEE (thigh ↔ shank) ──
    a_t, a_s, t_knee = build_pair(qt, tt, qs, ts)
    off_knee = angle_between_quaternions(qt_ref, qs_ref)
    knee = np.array([angle_between_quaternions(a_t[i], a_s[i]) - off_knee for i in range(len(a_t))])

    # ── HIP (pelvis ↔ thigh) ──
    a_p, a_th, t_hip = build_pair(qp, tp, qt, tt)
    off_hip = angle_between_quaternions(qp_ref, qt_ref)
    hip = np.array([angle_between_quaternions(a_p[i], a_th[i]) - off_hip for i in range(len(a_p))])

    # ── ANKLE (shank ↔ foot) — metodo FUNZIONALE firmato ──
    a_sh, a_ft, t_ank = build_pair(qs, ts, qf, tf)
    hinge = identify_hinge_axis(a_sh, a_ft)
    ankle = np.array([extract_functional_angle(a_sh[i], a_ft[i], qs_ref, qf_ref, hinge)
                      for i in range(len(a_sh))])
    # orienta il segno: dorsiflessione positiva (correlazione col pitch del piede)
    pitch_f = _compute_foot_pitch(qf)
    if pitch_f is not None:
        pf = np.interp(t_ank, tf, pitch_f)
        if np.corrcoef(ankle, pf)[0, 1] < 0:
            ankle = -ankle

    return {
        "Hip flex(+)/ext(-)":        (t_hip,  hip),
        "Knee flex(+)":              (t_knee, knee),
        "Ankle dorsi(+)/plantar(-)": (t_ank,  ankle),
        "_foot": (qf, tf),
    }


def heel_strikes(qf, tf):
    pitch = _compute_foot_pitch(qf)
    if pitch is None:
        return np.array([])
    _, _, hs, _ = _aminian_gait_events_from_pitch(pitch, np.asarray(tf, float))
    return hs


def ensemble(t, ang, hs, n=101, cyc=(0.7, 2.5)):
    grid = np.linspace(0, 100, n)
    cycles = []
    for i in range(len(hs) - 1):
        a, b = hs[i], hs[i + 1]
        if not (cyc[0] <= b - a <= cyc[1]):
            continue
        m = (t >= a) & (t <= b)
        if m.sum() < 10:
            continue
        pct = (t[m] - a) / (b - a) * 100
        cycles.append(np.interp(grid, pct, ang[m]))
    if not cycles:
        return grid, None, None, 0
    C = np.array(cycles)
    return grid, C.mean(0), C.std(0), len(cycles)


def main():
    files = sorted(glob.glob(os.path.join(os.path.dirname(__file__), "*_plot*.pkl")))
    print(f"File trovati: {[os.path.basename(f) for f in files]}")
    for path in files:
        name = os.path.basename(path)
        print("\n" + "=" * 72 + f"\n{name}")
        d = load(path)
        rec = reconstruct(d)
        qf, tf = rec.pop("_foot")
        hs = heel_strikes(qf, tf)
        print(f"  heel-strikes rilevati: {len(hs)}")
        if len(hs) < 3:
            print("  troppi pochi cicli — skip"); continue

        fig, axes = plt.subplots(1, 3, figsize=(16, 4.6))
        for ax, (joint, (t, ang)) in zip(axes, rec.items()):
            grid, mu, sd, ncyc = ensemble(t, ang, hs)
            ref = LIT[joint]
            # banda letteratura
            rx = np.linspace(0, 100, 101)
            rm = np.interp(rx, ref["x"], ref["mean"])
            ax.fill_between(rx, rm - ref["sd"], rm + ref["sd"], color=ref["color"],
                            alpha=0.18, label="Letteratura (slow) ±SD")
            ax.plot(rx, rm, color=ref["color"], lw=1.5, ls="--", alpha=0.8)
            if mu is not None:
                ax.fill_between(grid, mu - sd, mu + sd, color="#ff5555", alpha=0.15)
                ax.plot(grid, mu, color="#ff5555", lw=2.2, label=f"Ricalcolato (n={ncyc})")
                rom = float(mu.max() - mu.min())
                lo, hi = ref["rom"]
                ok = "OK" if lo - 8 <= rom <= hi + 8 else "FUORI"
                print(f"  {joint:30s} ROM ricalc={rom:5.1f}°  atteso~{lo}-{hi}°  [{ok}]  cicli={ncyc}")
            ax.axhline(0, color="#888", lw=0.6)
            ax.set_title(joint, fontsize=11, fontweight="bold")
            ax.set_xlabel("% ciclo del passo")
            ax.set_ylabel("Angolo (°)")
            ax.legend(fontsize=8, loc="best")
            ax.grid(True, ls="--", alpha=0.4)
        fig.suptitle(f"Verifica joint angles (gamba DX, cammino lento) — {name}",
                     fontsize=13, fontweight="bold")
        fig.tight_layout()
        out = os.path.join(os.path.dirname(__file__), f"verify_{name.replace(' ', '_')}.png")
        fig.savefig(out, dpi=130, facecolor="white")
        plt.close(fig)
        print(f"  -> salvato {os.path.basename(out)}")


if __name__ == "__main__":
    main()
