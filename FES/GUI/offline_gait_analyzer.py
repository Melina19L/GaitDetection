import pickle
import matplotlib.pyplot as plt
import numpy as np
import os
import argparse
from tkinter import Tk, filedialog

def load_data(file_path):
    print(f"Caricamento file: {file_path}")
    with open(file_path, "rb") as f:
        data = pickle.load(f)
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
