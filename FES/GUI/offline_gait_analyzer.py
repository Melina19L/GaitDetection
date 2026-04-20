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
    has_events = any("peaks" in k or "hs" in k.lower() or "toe" in k.lower() for k in data.keys())
    
    print(f" - Angoli Ginocchio pre-calcolati: {'SI' if has_knee else 'NO'}")
    print(f" - Angoli Caviglia pre-calcolati: {'SI' if has_ankle else 'NO'}")
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
            
    return data

def plot_angles(data):
    """
    Funzione per plottare Angoli di Ginocchio e Caviglia (se presenti).
    """
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
    ax_knee, ax_ankle = axes

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

    ax_ankle.set_xlabel("Timestamp (s)", fontsize=12)
    
    return fig, axes

def add_gait_events(data, axes):
    """
    Aggiunge le linee verticali per indicare gli eventi del passo:
    - Heel Strike (Linea continua Blu)
    - Toe Off (Linea tratteggiata Arancione)
    Supporta i dati FSR e FSM (IMU).
    """
    ax_knee, ax_ankle = axes
    
    # Colori per gli eventi
    hs_color = "#8be9fd" # Ciano
    to_color = "#ffb86c" # Arancione

    events_added = False

    # FSR Events Left
    if "fsr_heel_strike_timestamps_left" in data:
        for hs in data["fsr_heel_strike_timestamps_left"]:
            ax_knee.axvline(x=hs, color=hs_color, linestyle="-", alpha=0.5)
            ax_ankle.axvline(x=hs, color=hs_color, linestyle="-", alpha=0.5)
            events_added = True
    if "fsr_toe_off_timestamps_left" in data:
        for to in data["fsr_toe_off_timestamps_left"]:
            ax_knee.axvline(x=to, color=to_color, linestyle="--", alpha=0.5)
            ax_ankle.axvline(x=to, color=to_color, linestyle="--", alpha=0.5)
            events_added = True

    # IMU Events (esempio: right shank FSM 2)
    # Cerchiamo dinamicamente tutte le chiavi che indicano hs/to peaks nel file FSM
    for key in data.keys():
        if "heel_strike_peaks" in key:
            for hs in data[key]:
                ax_knee.axvline(x=hs, color=hs_color, linestyle="-", alpha=0.5)
                ax_ankle.axvline(x=hs, color=hs_color, linestyle="-", alpha=0.5)
                events_added = True
        elif "toe_off_peaks" in key:
            for to in data[key]:
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
