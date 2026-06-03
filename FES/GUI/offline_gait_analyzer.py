import pickle
import matplotlib.pyplot as plt
import numpy as np
import os
import argparse
from tkinter import Tk, filedialog

# Attempt to import ROM for offline ankle computation fallback
try:
    from stimulator.closed_loop import ROM
except ImportError:
    ROM = None

def _compute_angle_offline(data_dict, proxy_1_key, proxy_2_key):
    """Calcola l'angolo in batch tra due sensori (es: shank e foot) usando i quaternioni salvati."""
    if ROM is None or "rom_data" not in data_dict:
        return None, None
    rom_data = data_dict["rom_data"]
    if proxy_1_key not in rom_data or proxy_2_key not in rom_data:
        return None, None
    
    # Prendi il numero minimo di campioni tra i due sensori
    p1 = rom_data[proxy_1_key]
    p2 = rom_data[proxy_2_key]
    n = min(len(p1["timestamps"]), len(p2["timestamps"]))
    if n == 0:
        return None, None
        
    timestamps = p1["timestamps"][:n]
    
    # Ricostruisci i sample come si aspetta ROM
    # format: [[0, 0, 0, 0, qw, qx, qy, qz], ...] 
    # l'indice 4,5,6,7 sono i quaternioni in __compute_angles_from_data
    fake_samples_1 = []
    fake_samples_2 = []
    for i in range(n):
        s1 = [0]*8
        s1[4] = p1["qw"][i]
        s1[5] = p1["qx"][i]
        s1[6] = p1["qy"][i]
        s1[7] = p1["qz"][i]
        fake_samples_1.append(s1)
        
        s2 = [0]*8
        s2[4] = p2["qw"][i]
        s2[5] = p2["qx"][i]
        s2[6] = p2["qy"][i]
        s2[7] = p2["qz"][i]
        fake_samples_2.append(s2)
        
    temp_rom = ROM()
    angles = []
    for i in range(n):
        ang = temp_rom.calculate_joint_angle(False, [fake_samples_1[i]], [fake_samples_2[i]])
        angles.append(ang[0] if ang.size else 0.0)
    
    return np.array(timestamps), np.array(angles)

def load_data(file_path):
    print(f"\nCaricamento file: {file_path}")
    with open(file_path, "rb") as f:
        data = pickle.load(f)
        
    print("Contenuto trovato nel file:")
    has_knee = any("knee_angles" in k for k in data.keys())
    has_ankle = any("ankle_angles" in k for k in data.keys())
    has_hip = any("hip_angles" in k for k in data.keys())
    has_events = any("peaks" in k or "hs" in k.lower() or "toe" in k.lower() for k in data.keys())
    
    print(f" - Angoli Ginocchio pre-calcolati: {'SI' if has_knee else 'NO'}")
    print(f" - Angoli Caviglia pre-calcolati: {'SI' if has_ankle else 'NO'}")
    print(f" - Angoli Anca pre-calcolati: {'SI' if has_hip else 'NO'}")
    print(f" - Makers Fasi del Passo: {'SI' if has_events else 'NO'}")
    
    # Se mancano le caviglie ma abbiamo i dati RAW (Salvataggio della finestra principale)
    if not has_ankle and "rom_data" in data:
        print(" - Ricostruzione angoli caviglia offline dai quaternioni raw...")
        # Prova a sinistra (shank + foot)
        ts_l, ang_l = _compute_angle_offline(data, "left_shank_fsm1", "left_foot_fsm1")
        if ts_l is not None:
            data["left_ankle_timestamps"] = ts_l
            data["left_ankle_angles"] = ang_l
            print("   -> Ricostruita Caviglia Sinistra")

        # Prova a destra (shank + foot)
        ts_r, ang_r = _compute_angle_offline(data, "right_shank_fsm1", "right_foot_fsm1")
        if ts_r is not None:
            data["right_ankle_timestamps"] = ts_r
            data["right_ankle_angles"] = ang_r
            print("   -> Ricostruita Caviglia Destra")

    # Se mancano gli hip ma abbiamo i dati RAW di pelvis + thigh, li ricostruiamo offline.
    # Per i .pkl più vecchi che usavano left_trunk/right_trunk separati, facciamo fallback
    # a quelle chiavi così il file legacy resta caricabile senza modifiche.
    if not has_hip and "rom_data" in data:
        print(" - Ricostruzione angoli anca offline dai quaternioni raw...")
        rom_data = data.get("rom_data", {})

        def _pick_pelvis_key():
            for candidate in ("pelvis_fsm1", "pelvis_fsm2", "Pelvis_fsm1", "Pelvis_fsm2"):
                if candidate in rom_data:
                    return candidate
            return None

        pelvis_key = _pick_pelvis_key()

        # LEFT hip
        prox_left = pelvis_key or ("left_trunk_fsm1" if "left_trunk_fsm1" in rom_data else None)
        if prox_left and "left_thigh_fsm1" in rom_data:
            ts_l, ang_l = _compute_angle_offline(data, prox_left, "left_thigh_fsm1")
            if ts_l is not None:
                data["left_hip_timestamps"] = ts_l
                data["left_hip_angles"] = ang_l
                print(f"   -> Ricostruita Anca Sinistra (proximal={prox_left})")

        # RIGHT hip
        prox_right = pelvis_key or ("right_trunk_fsm1" if "right_trunk_fsm1" in rom_data else None)
        if prox_right and "right_thigh_fsm1" in rom_data:
            ts_r, ang_r = _compute_angle_offline(data, prox_right, "right_thigh_fsm1")
            if ts_r is not None:
                data["right_hip_timestamps"] = ts_r
                data["right_hip_angles"] = ang_r
                print(f"   -> Ricostruita Anca Destra (proximal={prox_right})")
            
    # Normalizza i timestamp per farli partire da 0
    print(" - Normalizzazione timestamps (partenza da t=0s)...")
    min_time = float('inf')
    
    # Primo passaggio: Trova il tempo minimo assoluto
    for key, value in data.items():
        if ("timestamps" in key or "peaks" in key or "valleys" in key) and isinstance(value, (list, np.ndarray)) and len(value) > 0:
            current_min = np.min(value)
            if current_min < min_time:
                min_time = current_min
                
    # Secondo passaggio: Sottrai il tempo minimo e converti in array numpy
    if min_time != float('inf'):
        for key, value in data.copy().items():
            if ("timestamps" in key or "peaks" in key or "valleys" in key) and isinstance(value, (list, np.ndarray)) and len(value) > 0:
                data[key] = np.array(value) - min_time

    return data

def _compute_foot_pitch(quat_arr, ref_n=60):
    """Foot pitch (degrees) computed from the foot sensor's quaternions.

    Pitch = signed angle of the foot's "forward" local axis above the world
    horizontal plane. + value = toes UP (heel-strike attitude), - value =
    toes DOWN (push-off / toe-off attitude). The first ``ref_n`` samples are
    used as a static reference and subtracted so the signal starts at 0°.

    Auto-detects which local axis is forward by picking the most-horizontal
    one at the reference window.
    """
    if quat_arr is None or quat_arr.shape[0] < ref_n:
        return None

    def qmul(a, b):
        w1, x1, y1, z1 = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
        w2, x2, y2, z2 = b[..., 0], b[..., 1], b[..., 2], b[..., 3]
        return np.stack([
            w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
            w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
        ], axis=-1)
    def qconj(q):
        out = q.copy(); out[..., 1:] = -out[..., 1:]; return out
    def qrot(q, v):
        qv = np.zeros((q.shape[0], 4)); qv[:, 1] = v[0]; qv[:, 2] = v[1]; qv[:, 3] = v[2]
        return qmul(qmul(q, qv), qconj(q))[:, 1:]

    q = quat_arr / (np.linalg.norm(quat_arr, axis=1, keepdims=True) + 1e-12)
    q_ref = q[:ref_n].mean(axis=0)
    q_ref = q_ref / (np.linalg.norm(q_ref) + 1e-12)
    # Pick the most-horizontal local axis at reference (≈ "forward")
    best_axis, best_horiz = np.array([0., 1., 0.]), -1.0
    for v in (np.array([1., 0., 0.]), np.array([0., 1., 0.]), np.array([0., 0., 1.])):
        vw = qrot(q_ref.reshape(1, 4), v)[0]
        horiz = 1.0 - abs(vw[2])
        if horiz > best_horiz:
            best_horiz, best_axis = horiz, v
    fwd_w = qrot(q, best_axis)
    fwd_w /= (np.linalg.norm(fwd_w, axis=1, keepdims=True) + 1e-12)
    pitch = np.degrees(np.arcsin(np.clip(fwd_w[:, 2], -1.0, 1.0)))
    pitch -= float(pitch[:ref_n].mean())
    return pitch


def _detect_foot_events(pitch, timestamps, distance_s=0.4):
    """Detect heel-strikes (positive pitch peaks = toes up) and toe-offs
    (negative pitch peaks = toes down).

    Returns ``(pitch_corrected, hs_times, to_times)``. The pitch is sign-
    flipped if the auto-detected polarity is reversed (so the returned curve
    always follows the clinical convention).
    """
    from scipy.signal import find_peaks
    if pitch is None or timestamps.size < 10:
        return pitch, np.array([]), np.array([])
    fs = 1.0 / np.median(np.diff(timestamps))
    rng = float(pitch.max() - pitch.min())
    if rng < 8.0:
        return pitch, np.array([]), np.array([])
    prom = max(4.0, min(0.4 * rng, 30.0))
    dist = int(distance_s * fs)
    # Standard polarity (+pitch = toes up = HS, -pitch = toes down = TO)
    hs_a, _ = find_peaks(+pitch, distance=dist, prominence=prom)
    to_a, _ = find_peaks(-pitch, distance=dist, prominence=prom)
    # Flipped polarity
    hs_b, _ = find_peaks(-pitch, distance=dist, prominence=prom)
    to_b, _ = find_peaks(+pitch, distance=dist, prominence=prom)
    if len(hs_a) + len(to_a) >= len(hs_b) + len(to_b):
        return pitch, timestamps[hs_a], timestamps[to_a]
    return -pitch, timestamps[hs_b], timestamps[to_b]


def _pair_hs_to(hs_times, to_times, min_cycle=0.7, max_cycle=1.5):
    """For each consecutive HS pair (within a normal cycle duration) find the
    TO that falls between them — used to shade stance / swing bands.
    Returns a list of ``(hs0, to, hs1)`` triples in seconds.
    """
    triples = []
    if hs_times.size < 2 or to_times.size < 1:
        return triples
    for i in range(len(hs_times) - 1):
        h0, h1 = float(hs_times[i]), float(hs_times[i + 1])
        if not (min_cycle <= h1 - h0 <= max_cycle):
            continue
        inside = [t for t in to_times if h0 < t < h1]
        if not inside:
            continue
        target = h0 + 0.60 * (h1 - h0)
        to = min(inside, key=lambda x: abs(float(x) - target))
        triples.append((h0, float(to), h1))
    return triples


def _aminian_gait_events_from_pitch(pitch, timestamps,
                                    ms_threshold_degps=50.0,
                                    ms_prominence=50.0,
                                    ms_min_spacing_s=0.7,
                                    hs_window_s=(0.05, 0.20),
                                    to_window_s=(0.30, 0.10),
                                    pitch_smooth_cutoff_hz=None,
                                    cycle_min_s=0.7,
                                    cycle_max_s=1.5):
    """Aminian-style HS/TO detection (Salarian 2004; Sabatini 2005) adapted to
    work from foot pitch (deg). Computes pitch rate by central differencing
    (functionally equivalent to gyro_Y in the sagittal plane) then applies the
    standard pipeline:

      0. (Optional) Pre-smooth pitch with Butterworth (``pitch_smooth_cutoff_hz``).
      1. Butterworth 2nd-order 15 Hz low-pass, zero-phase (filtfilt) on rate.
      2. Mid-swing (MS) = positive peaks > 50 °/s (min spacing 0.7s avoids the
         intra-cycle sub-peak that the pitch-differentiation introduces).
      3. (Optional) Cycle validation: keep only MS with a neighbour in
         ``[cycle_min_s, cycle_max_s]`` — useful when the recording contains
         sporadic non-gait motion.
      4. HS = first local minimum 50-200 ms AFTER each MS (foot-slap).
      5. TO = last local minimum 100-300 ms BEFORE each MS (push-off).

    Returns ``(gyr_filtered, ms_times, hs_times, to_times)``. ``gyr_filtered``
    matches the input timestamps; the three time arrays are subsets of it.
    """
    from scipy.signal import butter, filtfilt, find_peaks, argrelextrema
    empty = (None, np.array([]), np.array([]), np.array([]))
    if pitch is None or timestamps is None or len(timestamps) < 100:
        return empty
    ts = np.asarray(timestamps, dtype=float)
    fs = 1.0 / np.median(np.diff(ts))

    # 0) Pre-smooth pitch (kills high-freq artifact before differentiation)
    pitch_in = np.asarray(pitch, dtype=float)
    if pitch_smooth_cutoff_hz and pitch_smooth_cutoff_hz < fs/2:
        b_p, a_p = butter(2, pitch_smooth_cutoff_hz/(fs/2), btype="low")
        pitch_in = filtfilt(b_p, a_p, pitch_in)

    pitch_rate = np.gradient(pitch_in, ts)  # °/s

    # 1) Filter the pitch rate (standard Aminian)
    b, a = butter(2, 15.0/(fs/2), btype="low")
    gyr_f = filtfilt(b, a, pitch_rate)

    # 2) Mid-swing peaks
    ms_idx, _ = find_peaks(gyr_f,
                           height=ms_threshold_degps,
                           distance=int(ms_min_spacing_s * fs),
                           prominence=ms_prominence)

    # 3) Cycle validation
    if cycle_min_s and cycle_max_s and ms_idx.size > 1:
        t_ms = ts[ms_idx]
        keep = np.zeros(ms_idx.size, dtype=bool)
        for i, t in enumerate(t_ms):
            others = np.delete(t_ms, i)
            if others.size == 0:
                continue
            nearest_dt = float(np.min(np.abs(others - t)))
            if cycle_min_s <= nearest_dt <= cycle_max_s:
                keep[i] = True
        ms_idx = ms_idx[keep]

    # 4-5) HS / TO windowed search around each surviving MS
    hs_list, to_list = [], []
    hs_w0_s, hs_w1_s = hs_window_s
    to_w0_s, to_w1_s = to_window_s
    for ip in ms_idx:
        w0, w1 = ip + int(hs_w0_s*fs), ip + int(hs_w1_s*fs)
        if w1 < gyr_f.size:
            mins = argrelextrema(gyr_f[w0:w1], np.less)[0]
            hs_list.append(int(w0 + (mins[0] if mins.size else int(np.argmin(gyr_f[w0:w1])))))
        w0, w1 = ip - int(to_w0_s*fs), ip - int(to_w1_s*fs)
        if w0 >= 0 and w1 > w0:
            mins = argrelextrema(gyr_f[w0:w1], np.less)[0]
            to_list.append(int(w0 + (mins[-1] if mins.size else int(np.argmin(gyr_f[w0:w1])))))

    return (gyr_f,
            ts[ms_idx.astype(int)],
            ts[np.array(hs_list, dtype=int)] if hs_list else np.array([]),
            ts[np.array(to_list, dtype=int)] if to_list else np.array([]))


def plot_angles(data):
    """
    Funzione per plottare Angoli di Anca, Ginocchio e Caviglia (se presenti).

    Se il file contiene quaternioni grezzi del piede (``raw_<side>_foot_quat``),
    aggiunge un quarto pannello con il segnale gyro del piede e gli eventi
    HS/TO/MS rilevati con la pipeline Aminian (Salarian 2004; Sabatini 2005).
    Gli stessi eventi sono proiettati come linee verticali sui pannelli
    Hip / Knee / Ankle per la lettura biomeccanica sincronizzata.
    """
    has_hip = any("hip_angles" in k for k in data.keys())

    # Capire se possiamo aggiungere il foot pitch (richiede quaternioni raw).
    foot_side = None
    foot_quat = None
    foot_ts   = None
    for s in ("right", "left"):
        q_key  = f"raw_{s}_foot_quat"
        ts_key = f"raw_{s}_foot_timestamps"
        if q_key in data and ts_key in data:
            q  = np.asarray(data[q_key])
            ts = np.asarray(data[ts_key])
            if q.shape[0] >= 60 and ts.shape[0] == q.shape[0]:
                foot_side, foot_quat, foot_ts = s, q, ts
                break
    has_foot = foot_quat is not None

    n_rows = (3 if has_hip else 2) + (1 if has_foot else 0)
    fig, axes_arr = plt.subplots(n_rows, 1, figsize=(14, 3 * n_rows + 1), sharex=True)
    if n_rows == 1:
        axes_arr = [axes_arr]
    axes = list(axes_arr)

    if has_hip:
        ax_hip, ax_knee, ax_ankle = axes[0], axes[1], axes[2]
    else:
        ax_hip = None
        ax_knee, ax_ankle = axes[0], axes[1]
    ax_foot = axes[-1] if has_foot else None

    # --- HIP
    if ax_hip is not None:
        hip_plotted = False
        if "left_hip_timestamps" in data and "left_hip_angles" in data:
            ax_hip.plot(data["left_hip_timestamps"], data["left_hip_angles"], 
                         label="Left Hip", color="#8be9fd", linewidth=2) # Cyan
            hip_plotted = True
        elif "imu_left_hip_timestamps" in data and "imu_left_hip_angles" in data:
            ax_hip.plot(data["imu_left_hip_timestamps"], data["imu_left_hip_angles"], 
                         label="Left Hip", color="#8be9fd", linewidth=2)
            hip_plotted = True

        if "right_hip_timestamps" in data and "right_hip_angles" in data:
            ax_hip.plot(data["right_hip_timestamps"], data["right_hip_angles"], 
                         label="Right Hip", color="#ffb86c", linewidth=2) # Orange
            hip_plotted = True
        elif "imu_right_hip_timestamps" in data and "imu_right_hip_angles" in data:
            ax_hip.plot(data["imu_right_hip_timestamps"], data["imu_right_hip_angles"], 
                         label="Right Hip", color="#ffb86c", linewidth=2)
            hip_plotted = True

        if hip_plotted:
            ax_hip.set_title("Hip Angle", fontsize=14, fontweight='bold')
            ax_hip.set_ylabel("Angle (°)")
            ax_hip.legend(loc="upper right")
            ax_hip.grid(True, linestyle="--", alpha=0.6)

    # --- KNEE 
    knee_plotted = False
    if "left_knee_timestamps" in data and "left_knee_angles" in data:
        ax_knee.plot(data["left_knee_timestamps"], data["left_knee_angles"], 
                     label="Left Knee", color="#f1fa8c", linewidth=2) # Yellow
        knee_plotted = True
    elif "imu_left_knee_timestamps" in data and "imu_left_knee_angles" in data:
        ax_knee.plot(data["imu_left_knee_timestamps"], data["imu_left_knee_angles"], 
                     label="Left Knee", color="#f1fa8c", linewidth=2)
        knee_plotted = True

    if "right_knee_timestamps" in data and "right_knee_angles" in data:
        ax_knee.plot(data["right_knee_timestamps"], data["right_knee_angles"], 
                     label="Right Knee", color="#ff5555", linewidth=2) # Red
        knee_plotted = True
    elif "imu_right_knee_timestamps" in data and "imu_right_knee_angles" in data:
        ax_knee.plot(data["imu_right_knee_timestamps"], data["imu_right_knee_angles"], 
                     label="Right Knee", color="#ff5555", linewidth=2)
        knee_plotted = True

    if knee_plotted:
        ax_knee.set_title("Knee Angle", fontsize=14, fontweight='bold')
        ax_knee.set_ylabel("Angle (°)")
        ax_knee.legend(loc="upper right")
        ax_knee.grid(True, linestyle="--", alpha=0.6)

    # --- ANKLE
    ankle_plotted = False
    if "left_ankle_timestamps" in data and "left_ankle_angles" in data:
        ax_ankle.plot(data["left_ankle_timestamps"], data["left_ankle_angles"], 
                      label="Left Ankle", color="#50fa7b", linewidth=2) # Green
        ankle_plotted = True
        
    if "right_ankle_timestamps" in data and "right_ankle_angles" in data:
        ax_ankle.plot(data["right_ankle_timestamps"], data["right_ankle_angles"], 
                      label="Right Ankle", color="#bd93f9", linewidth=2) # Purple
        ankle_plotted = True

    if ankle_plotted:
        ax_ankle.set_title("Ankle Angle", fontsize=14, fontweight='bold')
        ax_ankle.set_ylabel("Angle (°)")
        ax_ankle.legend(loc="upper right")
        ax_ankle.grid(True, linestyle="--", alpha=0.6)

    # --- FOOT GYR Y + Aminian gait detection (master signal) -------------
    if has_foot and ax_foot is not None:
        pitch = _compute_foot_pitch(foot_quat)
        # Restrict foot data to the joint-angle time window: events outside
        # this window come from pre-calibration / setup / transitions and
        # are not part of the analyzed gait task.
        angle_keys = ("left_hip_timestamps",  "right_hip_timestamps",
                      "left_knee_timestamps", "right_knee_timestamps",
                      "left_ankle_timestamps","right_ankle_timestamps")
        t_min, t_max = float("inf"), float("-inf")
        for k in angle_keys:
            ts_k = data.get(k)
            if ts_k is not None and len(ts_k) > 0:
                t_min = min(t_min, float(np.min(ts_k)))
                t_max = max(t_max, float(np.max(ts_k)))
        if t_min != float("inf"):
            mask = (foot_ts >= t_min) & (foot_ts <= t_max)
            foot_ts_win = foot_ts[mask]
            pitch_win = pitch[mask] if pitch is not None else None
        else:
            foot_ts_win, pitch_win = foot_ts, pitch
        gyr_f_win, ms_times, hs_times, to_times = _aminian_gait_events_from_pitch(
            pitch_win, foot_ts_win)
        # Re-embed the filtered signal in the original timeline (zeros outside
        # the window) so the foot panel still draws on the full time axis.
        gyr_f = np.zeros_like(foot_ts) if gyr_f_win is not None else None
        if gyr_f_win is not None and t_min != float("inf"):
            gyr_f[mask] = gyr_f_win

        # Panel 4: filtered pitch-rate (≡ gyrY in sagittal plane)
        if gyr_f is not None:
            ax_foot.plot(foot_ts, gyr_f, color="#8be9fd", linewidth=1.4,
                         label=f"Foot pitch rate ({foot_side}) — Butter 15 Hz")
        ax_foot.axhline(50, color="black", linewidth=0.6, linestyle=":",
                        alpha=0.5, label="MS threshold 50 °/s")
        ax_foot.axhline(0, color="#6272a4", linewidth=0.6, linestyle="--",
                        alpha=0.6)

        # Event markers on the foot panel (filled at peak height for context)
        if gyr_f is not None and ms_times.size:
            ms_y = np.interp(ms_times, foot_ts, gyr_f)
            ax_foot.plot(ms_times, ms_y, "o", color="#5599ff", ms=6,
                         label=f"MS (mid-swing, n={ms_times.size})")
        if gyr_f is not None and hs_times.size:
            hs_y = np.interp(hs_times, foot_ts, gyr_f)
            ax_foot.plot(hs_times, hs_y, "v", color="#50fa7b", ms=7,
                         label=f"HS (heel-strike, n={hs_times.size})")
        if gyr_f is not None and to_times.size:
            to_y = np.interp(to_times, foot_ts, gyr_f)
            ax_foot.plot(to_times, to_y, "v", color="#ff5555", ms=7,
                         label=f"TO (toe-off, n={to_times.size})")

        ax_foot.set_title(
            "Gait Detection — Master signal (foot pitch rate, Aminian pipeline)",
            fontsize=14, fontweight='bold')
        ax_foot.set_ylabel("Pitch rate (°/s)")
        ax_foot.legend(loc="upper right", fontsize=9)
        ax_foot.grid(True, linestyle="--", alpha=0.6)

        # Project events as vertical lines on ALL panels (incl. foot itself)
        # MS faint (blue), HS green, TO red. Drawn behind the curves.
        for ax in axes:
            for p in ms_times:
                ax.axvline(p, color="#5599ff", linewidth=0.9, alpha=0.35, zorder=0)
            for p in hs_times:
                ax.axvline(p, color="#50fa7b", linewidth=1.1, alpha=0.55, zorder=0)
            for p in to_times:
                ax.axvline(p, color="#ff5555", linewidth=1.1, alpha=0.55, zorder=0)

    # Set x-label on the BOTTOM panel only
    axes[-1].set_xlabel("Timestamp (s)", fontsize=12)

    # Trim the x-axis so the plot starts where joint angles begin (not at
    # t=0 of the foot quaternion log, which often contains 30-60 s of idle
    # pre-recording before the operator starts walking).
    angle_keys = ("left_hip_timestamps",  "right_hip_timestamps",
                  "left_knee_timestamps", "right_knee_timestamps",
                  "left_ankle_timestamps","right_ankle_timestamps",
                  "imu_left_hip_timestamps",  "imu_right_hip_timestamps",
                  "imu_left_knee_timestamps", "imu_right_knee_timestamps")
    first_angle_t = float('inf')
    last_angle_t  = float('-inf')
    for k in angle_keys:
        ts = data.get(k)
        if ts is not None and len(ts) > 0:
            first_angle_t = min(first_angle_t, float(np.min(ts)))
            last_angle_t  = max(last_angle_t,  float(np.max(ts)))
    if first_angle_t != float('inf'):
        # Small margin (1 s) on either side so the first / last sample isn't
        # glued to the axis border.
        for ax in axes:
            ax.set_xlim(left=first_angle_t - 1.0, right=last_angle_t + 1.0)

    return fig, axes

def add_gait_events(data, axes):
    """
    Aggiunge le linee verticali per indicare gli eventi del passo:
    - Heel Strike (Linea continua Blu)
    - Toe Off (Linea tratteggiata Arancione)
    Supporta i dati FSR e FSM (IMU).
    """
    # axes layout:  [hip?, knee, ankle, foot?]   — hip and foot are optional
    # We add the FSR/IMU event lines on hip/knee/ankle only (the foot panel
    # already has its own heel-strike / toe-off markers from the pitch).
    has_hip  = (len(axes) >= 3) and (
        len(axes) == 3 or  # hip + knee + ankle
        (len(axes) == 4)   # hip + knee + ankle + foot
    )
    # Determine which axes are joint panels
    if len(axes) == 4:   # hip + knee + ankle + foot
        ax_hip, ax_knee, ax_ankle = axes[0], axes[1], axes[2]
    elif len(axes) == 3 and has_hip:   # hip + knee + ankle
        ax_hip, ax_knee, ax_ankle = axes
    elif len(axes) == 3:   # knee + ankle + foot (no hip)
        ax_hip = None
        ax_knee, ax_ankle = axes[0], axes[1]
    else:   # knee + ankle only
        ax_hip = None
        ax_knee, ax_ankle = axes[0], axes[1]
    
    # Colori per gli eventi
    hs_color = "#8be9fd" # Ciano
    to_color = "#ffb86c" # Arancione

    events_added = False

    # FSR Events Left
    if "fsr_heel_strike_timestamps_left" in data:
        for hs in data["fsr_heel_strike_timestamps_left"]:
            if ax_hip is not None: ax_hip.axvline(x=hs, color=hs_color, linestyle="-", alpha=0.5)
            ax_knee.axvline(x=hs, color=hs_color, linestyle="-", alpha=0.5)
            ax_ankle.axvline(x=hs, color=hs_color, linestyle="-", alpha=0.5)
            events_added = True
    if "fsr_toe_off_timestamps_left" in data:
        for to in data["fsr_toe_off_timestamps_left"]:
            if ax_hip is not None: ax_hip.axvline(x=to, color=to_color, linestyle="--", alpha=0.5)
            ax_knee.axvline(x=to, color=to_color, linestyle="--", alpha=0.5)
            ax_ankle.axvline(x=to, color=to_color, linestyle="--", alpha=0.5)
            events_added = True

    # IMU Events (esempio: right shank FSM 2)
    # Cerchiamo dinamicamente tutte le chiavi che indicano hs/to peaks nel file FSM
    for key in data.keys():
        if "heel_strike_peaks" in key:
            for hs in data[key]:
                if ax_hip is not None: ax_hip.axvline(x=hs, color=hs_color, linestyle="-", alpha=0.5)
                ax_knee.axvline(x=hs, color=hs_color, linestyle="-", alpha=0.5)
                ax_ankle.axvline(x=hs, color=hs_color, linestyle="-", alpha=0.5)
                events_added = True
        elif "toe_off_peaks" in key:
            for to in data[key]:
                if ax_hip is not None: ax_hip.axvline(x=to, color=to_color, linestyle="--", alpha=0.5)
                ax_knee.axvline(x=to, color=to_color, linestyle="--", alpha=0.5)
                ax_ankle.axvline(x=to, color=to_color, linestyle="--", alpha=0.5)
                events_added = True

    if events_added:
        # Aggiungiamo linee fittizie solo a scopo di legenda
        ax_knee.plot([], [], color=hs_color, linestyle="-", label="Heel Strike")
        ax_knee.plot([], [], color=to_color, linestyle="--", label="Toe Off")
        ax_knee.legend(loc="upper right")

def main():
    root = Tk()
    root.withdraw() # Nascondi la finestra di root
    
    # Prompt per scegliere il file
    file_path = filedialog.askopenfilename(
        title="Seleziona un file .pkl acquisito",
        filetypes=[("Pickle files", "*.pkl"), ("All files", "*.*")]
    )
    
    if not file_path:
        print("Nessun file selezionato. Chiusura in corso.")
        return

    data = load_data(file_path)
    
    # 1. Crea i grafici degli angoli
    fig, axes = plot_angles(data)
    
    # 2. Aggiungi le linee verticali di Heel Strike e Toe Off se i dati lo permettono
    add_gait_events(data, axes)
    
    # 3. Formattazione finale del grafico (dark theme)
    fig.patch.set_facecolor('#282a36')
    for ax in axes:
        ax.set_facecolor('#282a36')
        ax.tick_params(colors='#f8f8f2')
        ax.xaxis.label.set_color('#f8f8f2')
        ax.yaxis.label.set_color('#f8f8f2')
        ax.title.set_color('#f8f8f2')
        for spine in ax.spines.values():
            spine.set_color('#44475a')
    
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()
