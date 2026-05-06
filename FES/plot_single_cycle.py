import pickle
import sys
import types
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import interp1d

# Hack per importare il pickle con i moduli mancanti
class FakeModule(types.ModuleType):
    def __getattr__(self, name):
        return type(name, (), {
            '__init__': lambda self, *a, **kw: None,
            '__setstate__': lambda self, state: self.__dict__.update(state) if isinstance(state, dict) else None,
            '__hash__': lambda self: id(self),
        })

for mod_name in ['stimulator', 'stimulator.gait_phases', 'stimulator.gait_detection_imu',
                 'stimulator.gait_detection_fsr', 'stimulator.stimulation_classes',
                 'stimulator.stimulator_parameters', 'stimulator.closed_loop',
                 'stimulator.experiment_handler', 'stimulator.gait_model_stimulation_functions',
                 'stimulator.gait_detection_imu_fsr', 'stimulator.ComPortFunc']:
    sys.modules[mod_name] = FakeModule(mod_name)

TEST_PKL = "/Users/chiaracazzoli/Desktop/TESI EPFL/GaitDetection/FES/subjects/SUBJCET4/test0605.pkl"
PLOT_PKL = "/Users/chiaracazzoli/Desktop/TESI EPFL/GaitDetection/FES/subjects/SUBJCET4/plottest0605.pkl"

# Caricamento file per gli eventi
with open(TEST_PKL, 'rb') as f:
    test_data = pickle.load(f)
    
hs_times = np.array(test_data.get('imu_right_foot_fsm2_heel_strike_peaks', []))
if len(hs_times) == 0:
    hs_times = np.array(test_data.get('imu_right_shank_fsm2_heel_strike_peaks', []))

# Caricamento file per gli angoli
with open(PLOT_PKL, 'rb') as f:
    plot_data = pickle.load(f)

t_hip = np.array(plot_data.get('right_hip_timestamps', []))
a_hip = np.array(plot_data.get('right_hip_angles', []))

t_knee = np.array(plot_data.get('right_knee_timestamps', []))
a_knee = np.array(plot_data.get('right_knee_angles', []))

t_ankle = np.array(plot_data.get('right_ankle_timestamps', []))
a_ankle = np.array(plot_data.get('right_ankle_angles', []))

if len(hs_times) < 2:
    print("Non ci sono abbastanza Heel Strike per identificare un ciclo del passo completo.")
    sys.exit(1)

# Scegliamo un ciclo del passo centrale stabile
cycle_idx = len(hs_times) // 2
start_t = hs_times[cycle_idx]
end_t = hs_times[cycle_idx + 1]

print(f"Analizzando il ciclo da t={start_t:.2f} a t={end_t:.2f} s")

def interpolate_cycle(t, angles, start, end):
    # Prendi solo i dati all'interno del ciclo
    mask = (t >= start) & (t <= end)
    t_cycle = t[mask]
    a_cycle = angles[mask]
    
    if len(t_cycle) < 2:
        return np.zeros(100), np.zeros(100)
        
    # Normalizza il tempo da 0 a 100%
    t_norm = (t_cycle - start) / (end - start) * 100
    
    # Crea un vettore 0-100% regolare
    t_interp = np.linspace(0, 100, 100)
    
    # Interpola
    f = interp1d(t_norm, a_cycle, kind='cubic', fill_value="extrapolate")
    return t_interp, f(t_interp)

t_percent, hip_cycle = interpolate_cycle(t_hip, a_hip, start_t, end_t)
_, knee_cycle = interpolate_cycle(t_knee, a_knee, start_t, end_t)
_, ankle_cycle = interpolate_cycle(t_ankle, a_ankle, start_t, end_t)

# Creiamo il plot stile letteratura
fig, axes = plt.subplots(3, 1, figsize=(8, 10), sharex=True)

# 1. Ankle
axes[0].plot(t_percent, ankle_cycle, 'k-', linewidth=2)
axes[0].set_title("ANKLE", fontweight='bold')
axes[0].set_ylabel("ANGLE (DEGREES)")
axes[0].grid(True, linestyle='--', alpha=0.6)
axes[0].axhline(0, color='gray', linewidth=0.8)

# 2. Knee
axes[1].plot(t_percent, knee_cycle, 'k-', linewidth=2)
axes[1].set_title("KNEE", fontweight='bold')
axes[1].set_ylabel("ANGLE (DEGREES)")
axes[1].grid(True, linestyle='--', alpha=0.6)
axes[1].axhline(0, color='gray', linewidth=0.8)

# 3. Hip
axes[2].plot(t_percent, hip_cycle, 'k-', linewidth=2)
axes[2].set_title("HIP", fontweight='bold')
axes[2].set_xlabel("PERCENT OF GAIT CYCLE (%)", fontweight='bold')
axes[2].set_ylabel("ANGLE (DEGREES)")
axes[2].grid(True, linestyle='--', alpha=0.6)
axes[2].axhline(0, color='gray', linewidth=0.8)
axes[2].set_xlim(0, 100)
axes[2].set_xticks(np.arange(0, 101, 10))

plt.suptitle("Right Leg Kinematics - Single Gait Cycle", fontsize=14, fontweight='bold')
plt.tight_layout()

output_path = "/Users/chiaracazzoli/Desktop/TESI EPFL/GaitDetection/FES/single_gait_cycle_comparison.png"
plt.savefig(output_path, dpi=300)
print(f"Grafico salvato in {output_path}")
