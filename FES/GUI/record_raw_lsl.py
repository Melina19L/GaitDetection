import time
import numpy as np
from pylsl import resolve_stream, StreamInlet

def main():
    print("Cerco gli stream LSL per i sensori Right Shank e Right Foot...")
    streams = resolve_stream('type', 'Orientation')
    
    inlet_shank = None
    inlet_foot = None
    
    for stream in streams:
        name = stream.name()
        if "Right_Shank" in name or "Right_Shin" in name or "Shank_R" in name or "Right Shank" in name or "Sens1" in name or "03fa" in name:
            print(f"Trovato Shank: {name}")
            inlet_shank = StreamInlet(stream)
        if "Right_Foot" in name or "Foot_R" in name or "Right Foot" in name or "Sens2" in name or "03f6" in name:
            print(f"Trovato Foot: {name}")
            inlet_foot = StreamInlet(stream)
            
    # Try generic names if not found
    if not inlet_shank or not inlet_foot:
        print("Trovati i seguenti stream, scelgo i primi due:")
        for i, s in enumerate(streams):
            print(f" - {s.name()}")
            if i == 0: inlet_shank = StreamInlet(s)
            if i == 1: inlet_foot = StreamInlet(s)
            
    if not inlet_shank or not inlet_foot:
        print("Errore: impossibile trovare due stream LSL.")
        return

    print("\nInizio registrazione per 15 secondi.")
    print("Fai questo: Stai fermo 5 secondi, poi fai dorsi/planta flessione per 10 secondi.")
    
    data_shank = []
    data_foot = []
    
    start_time = time.time()
    while time.time() - start_time < 15.0:
        # Pull shank
        sample_s, ts_s = inlet_shank.pull_sample(timeout=0.0)
        if sample_s:
            data_shank.append([time.time()] + sample_s)
            
        # Pull foot
        sample_f, ts_f = inlet_foot.pull_sample(timeout=0.0)
        if sample_f:
            data_foot.append([time.time()] + sample_f)
            
        time.sleep(0.01)
        
    print("\nRegistrazione completata!")
    np.savez('raw_imu_data.npz', shank=np.array(data_shank), foot=np.array(data_foot))
    print("Dati salvati in 'raw_imu_data.npz'.")

if __name__ == '__main__':
    main()
