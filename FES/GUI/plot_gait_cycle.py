"""Single-gait-cycle plotter that reuses the GUI's step-counter logic.

The GUI's `IMUGaitFSM` (Method 1) detects heel strikes by running
`scipy.signal.find_peaks` on the shank gyroscope-Y signal with speed-tuned
thresholds. Whenever the GUI saves a recording, those heel-strike timestamps
are persisted to the `.pkl` as
``imu_<side>_<placement>_<fsm>_heel_strike_peaks`` — they are the ground truth.

This script's cycle-detection priority:
  1. **GUI events**: read ``imu_<side>_<placement>_<fsm>_heel_strike_peaks``
     directly from the file. No re-computation. Highest priority because these
     are the same events the GUI's step counter showed during the test.
  2. **GUI algorithm replay**: if no events are saved, replicate Method 1
     (`find_peaks(data_gy, height=peak_threshold, distance=…, prominence=…)`)
     on `rom_data[<side>_shank_fsm1].gy`, using the same speed-tuned thresholds.
  3. **Knee peaks**: last-resort fallback for legacy `.pkl` (calibrator-only)
     that has neither saved events nor `rom_data`.

Two views in one window:
  - Top: full-recording overview (knee + ankle) with red bars at every detected
    heel strike, plus a violet band on the currently selected cycle. Lets you
    visually verify what the detector picked.
  - Bottom: ONE selected cycle of Hip / Knee / Ankle on a normalised 0–100 %
    gait-cycle x-axis.

CLI:
    python plot_gait_cycle.py                             # file picker
    python plot_gait_cycle.py file.pkl --side left
    python plot_gait_cycle.py file.pkl --source gui       # default
    python plot_gait_cycle.py file.pkl --source replay --speed 1.0
    python plot_gait_cycle.py file.pkl --source knee --min-amp 25
    python plot_gait_cycle.py file.pkl --list             # dump key structure
"""

import os
import sys
import pickle
import argparse

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, RadioButtons


# ────────────────────────────────────────────────────────────────────────────
# Loading helpers
# ────────────────────────────────────────────────────────────────────────────

def load_pkl(path: str) -> dict:
    with open(path, "rb") as f:
        return pickle.load(f)


def _series(data: dict, *keys) -> np.ndarray:
    """Return first present key as a numpy array, or empty."""
    for k in keys:
        v = data.get(k)
        if v is not None and len(np.asarray(v)) > 0:
            return np.asarray(v, dtype=float)
    return np.array([])


def angle_arrays(data: dict, side: str) -> dict:
    """Return ``{joint: (timestamps, angles)}`` aligned per joint."""
    out = {}
    for joint in ("hip", "knee", "ankle"):
        ts = _series(data, f"imu_{side}_{joint}_timestamps", f"{side}_{joint}_timestamps")
        an = _series(data, f"imu_{side}_{joint}_angles",     f"{side}_{joint}_angles")
        if ts.size and an.size:
            n = min(ts.size, an.size)
            out[joint] = (ts[:n], an[:n])
    return out


def list_event_keys(data: dict) -> list:
    """Return every key in `data` that could carry HS / TO / phase events."""
    suffixes = ("_heel_strike_peaks", "_toe_off_peaks", "_valleys",
                "heel_strike_timestamps", "toe_off_timestamps")
    return sorted(k for k in data.keys()
                  if isinstance(k, str) and any(s in k for s in suffixes))


def list_rom_sensors(data: dict) -> list:
    rom = data.get("rom_data") or {}
    return sorted(rom.keys()) if isinstance(rom, dict) else []


# ────────────────────────────────────────────────────────────────────────────
# Detection — three sources
# ────────────────────────────────────────────────────────────────────────────

def _from_gui_events(data: dict, side: str) -> tuple[np.ndarray, str]:
    """Read pre-computed HS timestamps saved by the GUI's step counter."""
    candidates = (
        f"imu_{side}_shank_fsm1_heel_strike_peaks",
        f"imu_{side}_shank_fsm2_heel_strike_peaks",
        f"imu_{side}_foot_fsm1_heel_strike_peaks",
        f"imu_{side}_foot_fsm2_heel_strike_peaks",
        f"fsr_heel_strike_timestamps_{side}",
    )
    for k in candidates:
        ts = _series(data, k)
        if ts.size >= 2:
            return ts, k
    return np.array([]), ""


def _gui_method1_thresholds(speed: float) -> dict:
    """Replicate the speed-tuned shank-gyro thresholds used by IMUGaitFSM (Method 1).

    Mirrors the if/elif chain in `gait_detection_imu.py` for shank streams.
    """
    if speed <= 0.3:
        return dict(peak_threshold=0.25, distance=35, min_distance_between_peaks=35,
                    prominence=0.25)
    if 0.3 < speed <= 0.4:
        return dict(peak_threshold=0.22, distance=30, min_distance_between_peaks=30,
                    prominence=0.22)
    if 0.4 < speed <= 0.8:
        return dict(peak_threshold=0.20, distance=25, min_distance_between_peaks=25,
                    prominence=0.20)
    if 0.8 < speed <= 1.5:
        return dict(peak_threshold=0.14, distance=30, min_distance_between_peaks=30,
                    prominence=0.10)
    # default for ≥1.5 km/h (the original 3 km/h tuning)
    return dict(peak_threshold=0.25, distance=25, min_distance_between_peaks=25,
                prominence=0.25)


def _filter_by_min_distance(idx: np.ndarray, min_distance: int) -> np.ndarray:
    """Mirror gait_detection_imu.filter_peaks_by_min_distance."""
    if idx.size == 0:
        return idx
    kept = [int(idx[0])]
    for i in idx[1:]:
        if int(i) - kept[-1] >= min_distance:
            kept.append(int(i))
    return np.asarray(kept, dtype=int)


def _replay_gui_algorithm(data: dict, side: str, speed: float) -> tuple[np.ndarray, str]:
    """Re-run the GUI's Method-1 peak detection on saved shank gyro-Y.

    The shank rom_data is checked first under both fsm1 and fsm2 keys; falls
    back to foot if shank is missing.
    """
    rom = data.get("rom_data") or {}
    if not isinstance(rom, dict):
        return np.array([]), "no rom_data"

    for key in (f"{side}_shank_fsm1", f"{side}_shank_fsm2",
                f"{side}_foot_fsm1",  f"{side}_foot_fsm2"):
        sensor = rom.get(key)
        if not isinstance(sensor, dict):
            continue
        gy = np.asarray(sensor.get("gy") or [], dtype=float)
        ts = np.asarray(sensor.get("timestamps") or [], dtype=float)
        if gy.size < 100 or ts.size < gy.size:
            continue

        # GUI flips sign for open-loop (line 338 in gait_detection_imu.py).
        # We don't know which mode produced the recording, so try the original
        # sign first; if no peaks, try the negation.
        try:
            from scipy.signal import find_peaks
        except ImportError:
            return np.array([]), "scipy missing"

        params = _gui_method1_thresholds(speed)
        for mult in (1.0, -1.0):
            peaks, _ = find_peaks(
                mult * gy,
                height=params["peak_threshold"],
                distance=params["distance"],
                prominence=params["prominence"],
            )
            peaks = _filter_by_min_distance(peaks, params["min_distance_between_peaks"])
            if peaks.size >= 2:
                src = f"replay({key}, sign={'+' if mult > 0 else '-'}, speed={speed} km/h)"
                return ts[peaks], src
    return np.array([]), "no usable rom_data"


def _knee_peak_detection(data: dict, side: str, min_distance_s: float,
                         min_height: float) -> tuple[np.ndarray, str]:
    angs = angle_arrays(data, side)
    knee = angs.get("knee")
    if knee is None:
        return np.array([]), "no knee signal"
    kts, kang = knee
    try:
        from scipy.signal import find_peaks
        dt = float(np.median(np.diff(kts)))
        if dt <= 0:
            return np.array([]), "knee timestamps invalid"
        distance = max(1, int(round(min_distance_s / dt)))
        idx, _ = find_peaks(kang, distance=distance, height=min_height)
        return kts[idx], "knee peaks"
    except ImportError:
        # Manual fallback
        out = []
        for i in range(1, kang.size - 1):
            if kang[i] >= min_height and kang[i] > kang[i - 1] and kang[i] >= kang[i + 1]:
                if not out or (kts[i] - kts[out[-1]]) >= min_distance_s:
                    out.append(i)
        return kts[np.asarray(out, dtype=int)] if out else np.array([]), "knee peaks (manual)"


def detect_cycle_boundaries(
    data: dict,
    side: str,
    source: str = "gui",
    speed_kmh: float = 3.0,
    min_cycle_s: float = 0.4,
    max_cycle_s: float = 2.5,
    min_amp_deg: float = 15.0,
) -> tuple[np.ndarray, str]:
    """Return ``(boundary_timestamps, source_label)``.

    Boundaries are sorted, monotone, and pair-filtered: each consecutive pair
    must have duration ∈ ``[min_cycle_s, max_cycle_s]`` and the knee signal on
    that window must have peak-to-trough ≥ ``min_amp_deg`` degrees.

    ``source`` ∈ ``{"gui", "replay", "knee", "auto"}``:
        - gui    : use pre-computed events saved by the GUI step counter.
        - replay : re-run GUI Method 1 on shank gyro-Y (rom_data).
        - knee   : peak detection on knee angle (no GUI dependency).
        - auto   : try gui → replay → knee in that order.
    """
    if source == "auto":
        for s in ("gui", "replay", "knee"):
            b, label = detect_cycle_boundaries(
                data, side, s, speed_kmh,
                min_cycle_s, max_cycle_s, min_amp_deg,
            )
            if b.size >= 2:
                return b, label
        return np.array([]), "auto: no source produced events"

    if source == "gui":
        raw, label = _from_gui_events(data, side)
    elif source == "replay":
        raw, label = _replay_gui_algorithm(data, side, speed_kmh)
    elif source == "knee":
        raw, label = _knee_peak_detection(data, side, min_cycle_s, min_amp_deg)
    else:
        return np.array([]), f"unknown source {source!r}"

    if raw.size < 2:
        return np.array([]), f"{source}: {label} (got {raw.size} events)"

    raw = np.unique(np.sort(raw.astype(float)))
    knee = angle_arrays(data, side).get("knee")

    # Pairwise filter: keep pairs whose duration AND knee amplitude are valid.
    # We reset the chain when a gap is too big (so a transient at t=0 doesn't
    # block all subsequent valid cycles).
    keep = []
    for i in range(raw.size - 1):
        t0, t1 = float(raw[i]), float(raw[i + 1])
        dur = t1 - t0
        if dur < min_cycle_s or dur > max_cycle_s:
            continue
        if knee is not None and not _cycle_has_amplitude(knee, t0, t1, min_amp_deg):
            continue
        if not keep or keep[-1] != t0:
            keep.append(t0)
        keep.append(t1)

    return np.asarray(keep, dtype=float), f"{source}: {label}"


def _cycle_has_amplitude(knee: tuple, t0: float, t1: float, min_amp: float) -> bool:
    kts, kang = knee
    mask = (kts >= t0) & (kts < t1)
    if not mask.any():
        return False
    seg = kang[mask]
    return (seg.max() - seg.min()) >= min_amp


def cycle_slice(ts: np.ndarray, ang: np.ndarray, t0: float, t1: float):
    mask = (ts >= t0) & (ts < t1)
    if not mask.any() or t1 <= t0:
        return np.array([]), np.array([])
    seg_ts = ts[mask]
    seg_an = ang[mask]
    pct = (seg_ts - t0) / (t1 - t0) * 100.0
    return pct, seg_an


# ────────────────────────────────────────────────────────────────────────────
# Plot
# ────────────────────────────────────────────────────────────────────────────

COLORS_LEFT  = {"hip": "#8be9fd", "knee": "#f1fa8c", "ankle": "#50fa7b"}
COLORS_RIGHT = {"hip": "#ffb86c", "knee": "#ff5555", "ankle": "#bd93f9"}


def _style_axes(*axes):
    for ax in axes:
        ax.set_facecolor("#282a36")
        ax.tick_params(colors="#f8f8f2")
        ax.xaxis.label.set_color("#f8f8f2")
        ax.yaxis.label.set_color("#f8f8f2")
        ax.title.set_color("#f8f8f2")
        for s in ax.spines.values():
            s.set_color("#44475a")
        ax.grid(True, linestyle="--", alpha=0.35, color="#6272a4")


def make_plot(data: dict, args):
    fig = plt.figure(figsize=(13, 9))
    fig.patch.set_facecolor("#282a36")

    gs = fig.add_gridspec(5, 1, height_ratios=[1.4, 1, 1, 1, 0.3], hspace=0.55)
    ax_overview = fig.add_subplot(gs[0])
    ax_hip   = fig.add_subplot(gs[1])
    ax_knee  = fig.add_subplot(gs[2], sharex=ax_hip)
    ax_ankle = fig.add_subplot(gs[3], sharex=ax_hip)
    _style_axes(ax_overview, ax_hip, ax_knee, ax_ankle)
    fig.subplots_adjust(left=0.08, right=0.98, top=0.95, bottom=0.10)

    state = {"side": args.side, "cycle_idx": 0,
             "boundaries": np.array([]), "src": "", "pairs": []}

    title = fig.suptitle("", color="#f8f8f2", fontsize=12, fontweight="bold")

    def _refresh_boundaries():
        b, src = detect_cycle_boundaries(
            data, state["side"], source=args.source,
            speed_kmh=args.speed, min_cycle_s=args.min_cycle,
            max_cycle_s=args.max_cycle, min_amp_deg=args.min_amp,
        )
        # Build cycle pairs from consecutive boundary points.
        # Filter out duplicate-zero-length gaps (b can repeat shared endpoints).
        pairs = []
        i = 0
        while i < b.size - 1:
            t0, t1 = float(b[i]), float(b[i + 1])
            if t1 > t0 and (args.min_cycle <= (t1 - t0) <= args.max_cycle):
                pairs.append((t0, t1))
                i += 2 if (i + 2 < b.size and b[i + 2] != t1) else 1
            else:
                i += 1
        # Dedupe pairs
        seen = set(); uniq = []
        for p in pairs:
            if p not in seen:
                uniq.append(p); seen.add(p)
        state["boundaries"] = b
        state["pairs"]      = uniq
        state["src"]        = src
        return uniq

    def redraw():
        side = state["side"]
        angs = angle_arrays(data, side)
        pairs = state["pairs"]
        n_cycles = len(pairs)

        # ── OVERVIEW ──────────────────────────────────────────────────────
        ax_overview.clear()
        _style_axes(ax_overview)
        ax_overview.set_title(
            f"Overview — {side.upper()} — {n_cycles} cycles  "
            f"[{state['src']}]  "
            f"(filters: {args.min_cycle:.2f}≤dur≤{args.max_cycle:.2f}s, knee amp≥{args.min_amp:.0f}°)",
            fontsize=10,
        )
        ax_overview.set_xlabel("Time (s)")
        ax_overview.set_ylabel("Angle (°)")
        colors = COLORS_LEFT if side == "left" else COLORS_RIGHT
        t_ref = None
        if "knee" in angs:
            kts, kang = angs["knee"]
            t_ref = float(kts[0]) if kts.size else 0.0
            ax_overview.plot(kts - t_ref, kang, color=colors["knee"], linewidth=1.0, label="Knee")
        if "ankle" in angs:
            ats, aang = angs["ankle"]
            tref_a = t_ref if t_ref is not None else (float(ats[0]) if ats.size else 0.0)
            ax_overview.plot(ats - tref_a, aang, color=colors["ankle"], linewidth=1.0, alpha=0.7, label="Ankle")
        if t_ref is not None:
            for (t0, t1) in pairs:
                ax_overview.axvline(t0 - t_ref, color="#ff5555", linewidth=0.5, alpha=0.55)
            if pairs:
                last = pairs[-1][1]
                ax_overview.axvline(last - t_ref, color="#ff5555", linewidth=0.5, alpha=0.55)
        if pairs and 0 <= state["cycle_idx"] < n_cycles and t_ref is not None:
            t0, t1 = pairs[state["cycle_idx"]]
            ax_overview.axvspan(t0 - t_ref, t1 - t_ref, color="#bd93f9", alpha=0.28)
        ax_overview.legend(loc="upper right", facecolor="#282a36", edgecolor="#44475a", labelcolor="#f8f8f2")

        # ── SINGLE CYCLE ──────────────────────────────────────────────────
        for ax in (ax_hip, ax_knee, ax_ankle):
            ax.clear()
            _style_axes(ax)

        if n_cycles == 0:
            title.set_text(f"{side.upper()} side — no valid cycles detected")
            ax_hip.set_ylabel("Hip (°)")
            ax_knee.set_ylabel("Knee (°)")
            ax_ankle.set_ylabel("Ankle (°)")
            ax_ankle.set_xlabel("Gait cycle (%)")
            slider.ax.set_visible(False)
            fig.canvas.draw_idle()
            return
        slider.ax.set_visible(True)

        idx = max(0, min(state["cycle_idx"], n_cycles - 1))
        state["cycle_idx"] = idx
        slider.valmax = max(0, n_cycles - 1)
        slider.ax.set_xlim(slider.valmin, slider.valmax)
        slider.eventson = False
        slider.set_val(idx)
        slider.eventson = True

        t0, t1 = pairs[idx]
        duration = t1 - t0

        for ax, joint in zip((ax_hip, ax_knee, ax_ankle), ("hip", "knee", "ankle")):
            ax.set_ylabel(f"{joint.title()} (°)")
            if joint not in angs:
                ax.set_title(f"{joint.title()} — no data", fontsize=10)
                continue
            ts, an = angs[joint]
            x, y = cycle_slice(ts, an, t0, t1)
            if y.size == 0:
                ax.set_title(f"{joint.title()} — empty in window", fontsize=10)
                continue
            ax.plot(x, y, color=colors[joint], linewidth=2.0)
            ax.axhline(0, color="#6272a4", linewidth=0.6, alpha=0.6)
            ax.set_xlim(0, 100)
            ax.set_title(
                f"{joint.title()} — {y.min():+.1f}° → {y.max():+.1f}° (peak-to-peak {y.max() - y.min():.1f}°)",
                fontsize=10,
            )
        ax_ankle.set_xlabel("Gait cycle (%)")
        title.set_text(f"{side.upper()} side — cycle {idx + 1}/{n_cycles}  duration={duration:.2f}s")
        fig.canvas.draw_idle()

    # Slider
    slider_ax = fig.add_axes([0.10, 0.04, 0.75, 0.025], facecolor="#44475a")
    slider = Slider(slider_ax, "Cycle", 0, max(1, _initial_n_cycles(data, args)),
                    valinit=0, valstep=1, color="#bd93f9")
    slider.label.set_color("#f8f8f2")
    slider.valtext.set_color("#f8f8f2")
    slider.on_changed(lambda val: (state.update(cycle_idx=int(val)), redraw()))

    # Radio (Left / Right)
    radio_ax = fig.add_axes([0.88, 0.03, 0.10, 0.05], facecolor="#44475a")
    radio = RadioButtons(radio_ax, ("right", "left"),
                         active=0 if args.side == "right" else 1,
                         activecolor="#bd93f9")
    for label in radio.labels:
        label.set_color("#f8f8f2")

    def on_side(label):
        state["side"] = label
        pairs = _refresh_boundaries()
        state["cycle_idx"] = max(0, len(pairs) // 2)
        redraw()
    radio.on_clicked(on_side)

    # Initial draw — middle cycle
    pairs = _refresh_boundaries()
    state["cycle_idx"] = max(0, len(pairs) // 2)
    redraw()

    fig._slider = slider     # type: ignore[attr-defined]
    fig._radio  = radio      # type: ignore[attr-defined]
    return fig


def _initial_n_cycles(data: dict, args) -> int:
    b, _ = detect_cycle_boundaries(
        data, args.side, source=args.source, speed_kmh=args.speed,
        min_cycle_s=args.min_cycle, max_cycle_s=args.max_cycle,
        min_amp_deg=args.min_amp,
    )
    return max(1, b.size - 1)


# ────────────────────────────────────────────────────────────────────────────
# CLI
# ────────────────────────────────────────────────────────────────────────────

def _print_structure(data: dict):
    print(f"\nFile contains {len(data)} top-level keys:")
    for k in sorted(data.keys()):
        v = data[k]
        if isinstance(v, dict):
            print(f"  {k}: dict with {len(v)} entries")
        elif hasattr(v, "__len__"):
            print(f"  {k}: len={len(v)}")
        else:
            print(f"  {k}: {type(v).__name__}")
    rom = list_rom_sensors(data)
    if rom:
        print(f"\nROM sensors ({len(rom)}):")
        for s in rom:
            keys = list(data["rom_data"][s].keys()) if isinstance(data["rom_data"][s], dict) else []
            print(f"  {s}: {keys}")
    ev = list_event_keys(data)
    if ev:
        print(f"\nGait-event keys ({len(ev)}):")
        for k in ev:
            v = data.get(k)
            try:
                n = len(np.asarray(v))
            except Exception:
                n = "?"
            print(f"  {k}: n={n}")


def main():
    parser = argparse.ArgumentParser(description="Single gait-cycle plotter (uses GUI step-counter logic).")
    parser.add_argument("pkl", nargs="?", help="Path to .pkl file (omit for file picker)")
    parser.add_argument("--side", choices=("right", "left"), default="right")
    parser.add_argument("--source", choices=("auto", "gui", "replay", "knee"), default="auto",
                        help="auto = try gui → replay → knee in order [default]")
    parser.add_argument("--speed", type=float, default=3.0,
                        help="Walking speed in km/h (used by --source replay) [default 3.0]")
    parser.add_argument("--min-cycle", type=float, default=0.4)
    parser.add_argument("--max-cycle", type=float, default=2.5)
    parser.add_argument("--min-amp",   type=float, default=15.0,
                        help="Minimum knee peak-to-trough per cycle in degrees [default 15]")
    parser.add_argument("--list", action="store_true",
                        help="Print the structure of the .pkl and exit (debug)")
    args = parser.parse_args()

    path = args.pkl
    if not path:
        try:
            from tkinter import Tk, filedialog
            root = Tk(); root.withdraw()
            path = filedialog.askopenfilename(
                title="Select recording .pkl",
                filetypes=[("Pickle files", "*.pkl"), ("All files", "*.*")],
            )
        except Exception as e:
            print(f"No file given and tkinter unavailable: {e}")
            sys.exit(1)
    if not path:
        print("No file selected. Exiting.")
        sys.exit(0)
    if not os.path.isfile(path):
        print(f"File not found: {path}")
        sys.exit(1)

    print(f"Loading {path}")
    data = load_pkl(path)

    if args.list:
        _print_structure(data)
        sys.exit(0)

    print(f"Keys: {len(data)}  •  ROM sensors: {len(list_rom_sensors(data))}  •  "
          f"Event keys: {len(list_event_keys(data))}")
    for s in ("right", "left"):
        b, src = detect_cycle_boundaries(
            data, s, source=args.source, speed_kmh=args.speed,
            min_cycle_s=args.min_cycle, max_cycle_s=args.max_cycle,
            min_amp_deg=args.min_amp,
        )
        print(f"  {s.upper()}: {max(0, b.size - 1)} cycle boundaries  [{src}]")

    fig = make_plot(data, args)
    plt.show()


if __name__ == "__main__":
    main()
