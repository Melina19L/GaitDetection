import pickle
import numpy as np

with open("try4.pkl", "rb") as f:
    d = pickle.load(f)

def unwrap_timestamps(ts):
    ts = ts.copy()
    diffs = np.diff(ts)
    jumps = np.where(diffs < -1000.0)[0]
    for j in jumps:
        ts[j+1:] += 4294.967296
    return ts

t_sh = unwrap_timestamps(np.asarray(d["raw_right_shank_timestamps"], dtype=np.float64))
t_master = t_sh.copy()

knee_pkl = np.asarray(d["right_knee_angles"], dtype=np.float64)
knee_tpkl = unwrap_timestamps(np.asarray(d["right_knee_timestamps"], dtype=np.float64))
ank_pkl = np.asarray(d["right_ankle_angles"], dtype=np.float64)
ank_tpkl = unwrap_timestamps(np.asarray(d["right_ankle_timestamps"], dtype=np.float64))
hip_pkl = np.asarray(d["right_hip_angles"], dtype=np.float64)
hip_tpkl = unwrap_timestamps(np.asarray(d["right_hip_timestamps"], dtype=np.float64))

def _interp_to(t_target, t_src, val_src):
    if t_src.size == 0:
        return np.full_like(t_target, np.nan)
    return np.interp(t_target, t_src, val_src, left=np.nan, right=np.nan)

knee_at_master = _interp_to(t_master, knee_tpkl, knee_pkl)
ank_at_master  = _interp_to(t_master, ank_tpkl,  ank_pkl)
hip_at_master  = _interp_to(t_master, hip_tpkl,  hip_pkl)

NPOSE_KNEE  = 3.0
NPOSE_ANKLE = 3.0
NPOSE_HIP   = 5.0

npose_mask = (
    np.isfinite(knee_at_master) &
    np.isfinite(ank_at_master)  &
    np.isfinite(hip_at_master)  &
    (np.abs(knee_at_master) < NPOSE_KNEE)  &
    (np.abs(ank_at_master)  < NPOSE_ANKLE) &
    (np.abs(hip_at_master)  < NPOSE_HIP)
)

print("Total npose matches:", np.sum(npose_mask))

def _longest_run(mask):
    best_start, best_len = -1, 0
    run_start, run_len = -1, 0
    for i, m in enumerate(mask):
        if m:
            if run_start < 0: run_start = i
            run_len += 1
        else:
            if run_len > best_len:
                best_start, best_len = run_start, run_len
            run_start, run_len = -1, 0
    if run_len > best_len:
        best_start, best_len = run_start, run_len
    return best_start, best_len

start, length = _longest_run(npose_mask)
print(f"Longest run: {length} at {start}")

# try wider thresholds
npose_mask2 = (
    np.isfinite(knee_at_master) &
    np.isfinite(ank_at_master)  &
    np.isfinite(hip_at_master)  &
    (np.abs(knee_at_master) < 5.0)  &
    (np.abs(ank_at_master)  < 5.0) &
    (np.abs(hip_at_master)  < 7.0)
)
start2, length2 = _longest_run(npose_mask2)
print(f"Longest run with wider thresholds: {length2} at {start2}")

