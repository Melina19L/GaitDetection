# FOG H5 Kinematic Reconstruction — Design

**Date:** 2026-06-16
**Status:** Approved (design)

## Goal

Standalone, reusable offline analysis script that, given a MAPP `recording_data.h5`
file and a time window, produces:

1. **Kinematic reconstruction** — bilateral knee, hip, ankle joint angles vs time.
2. **Gait detection** — Method 1 IMU FSM on both feet (phase timeline + HS/TO markers).
3. **Freeze Index** — per sensor (5 WIMU + 8 COMETA blocks), sliding window over time.

First target: `Group_FOG/FOG002/MAPP/Narrow Corridor_1/recording_data.h5`,
plotting **only elapsed window 800–860 s (13:20–14:20)**.

## Input data (verified by inspection)

H5 layout (`recording_data.h5`):

- `Cometa/WaveX_IMU/data` — shape `(1988460, 72)` @ **2000 Hz**. 8 sensor blocks × 9 ch.
  Per block (verify empirically): `[acc_xyz (g), gyro_xyz (deg/s), acc/mag_xyz]`.
  **No quaternion stored** → orientation must be fused.
- `Cometa/WaveX_EMG/data` — `(1988415, 8)` @ 2000 Hz. Not used.
- `WIMU/WIMU_MK3/data_devN` — `(~80000, 8)` @ ~100 Hz. Columns:
  `[counter, m1, m2, m3, q_w, q_x, q_y, q_z]`. Cols 4-7 = quaternion (norm = 1.0,
  verified). Cols 1-3 = motion (gyro deg/s **or** free-accel m/s² — both fit ±40
  observed range; classify empirically at implementation).
  - dev5 = right foot · dev2 = left foot · dev3 = right wrist · dev6 = cervical · dev7 = back/pelvis.
- `logs/events` — 48 rows, fields `(timestamp, elapsed, …, type, task, message)`.
- `session_info/start_time` = 1773682071.198 (unix wall clock).

**Clock domain:** sensor timestamps and event `timestamp` share a device clock
(~1.208e6). Recording-relative time: `elapsed = raw_ts − T0`, `T0 = 1208209.66`
(first event, "Task started"). Total span ~994 s. Per-stream rates differ (COMETA
2000 Hz, WIMU ~100 Hz) → each stream sliced by its own timestamps.

## COMETA segment mapping (user-provided, verified by script)

1-indexed sensors → 0-indexed blocks (block k = cols 9k … 9k+8):

| Segment        | Sensor | Block | Cols   |
|----------------|--------|-------|--------|
| Right thigh    | 1      | 0     | 0–8    |
| Left thigh     | 2      | 1     | 9–17   |
| Right shin     | 5      | 4     | 36–44  |
| Left shin      | 6      | 5     | 45–53  |

Verification (warn, don't hard-fail): shank gyro-RMS > thigh gyro-RMS in walk
window; each thigh/shin pair phase-locks to its own foot cadence. Blocks 2,3,6,7
unused (assumed other body sites).

## Joint pairs

| Joint       | Segment A (quat)        | Segment B (quat)       | Method |
|-------------|-------------------------|------------------------|--------|
| R knee      | R thigh (blk0, fused)   | R shin (blk4, fused)   | SAA `angle_between_quaternions` |
| L knee      | L thigh (blk1, fused)   | L shin (blk5, fused)   | SAA |
| R hip       | pelvis (dev7)           | R thigh (blk0)         | SAA |
| L hip       | pelvis (dev7)           | L thigh (blk1)         | SAA |
| R ankle     | R shin (blk4)           | R foot (dev5)          | signed sagittal / hinge (ankle pipeline) |
| L ankle     | L shin (blk5)           | L foot (dev2)          | signed sagittal / hinge |

Cross-system pairs (hip, ankle: 2000 Hz COMETA vs 100 Hz WIMU) time-matched by
nearest timestamp before angle computation.

## Calibration

First **10 s standing** (elapsed 0–10 s) = neutral pose. Loaded as a separate
slice. Per segment: median quaternion over the 10 s → neutral reference offset,
applied like GUI `closed_loop` / `calibration()`. Reported angles are offset to
zero at neutral stance.

## Approach (chosen)

Reuse the application's own math rather than reimplement, so offline numbers stay
consistent with the live thesis system:

- **Orientation:** `imufusion` AHRS (Madgwick) per needed COMETA block @ 2000 Hz →
  quaternion timeseries. WIMU quaternions used directly.
- **Joint angles:** `stimulator.closed_loop` (SAA for knee/hip; signed/hinge for ankle).
- **Gait:** `stimulator.gait_detection_imu.IMUGaitFSM` (Method 1) replayed offline,
  fed foot angular-velocity-Y per side.

Rejected: raw gyro integration (drifts), custom FSM (diverges from system).

## Components (single script `FES/subjects/reconstruct_fog_h5.py`)

Config constants at top: `H5_PATH`, `T0`, `WIN = (800, 860)`, `CALIB = (0, 10)`,
COMETA block map, WIMU device map, FI params, output dir. Reusable on other H5 files.

1. **`load_h5`** — open file, return per-stream `(data, t_rel)` for COMETA + each WIMU
   device, plus events. Provides window-slice and calib-slice helpers.
2. **`parse_cometa`** — reshape 72 → (N, 8, 9); extract acc, gyro per block.
3. **`fuse_orientation`** — imufusion per COMETA block → quaternion array.
4. **`verify_mapping`** — check shank>thigh gyro-RMS + foot phase-lock; log warnings.
5. **`compute_calibration`** — median quat per segment over 0–10 s.
6. **`joint_angles`** — bilateral knee/hip/ankle via `closed_loop`, calibrated,
   cross-system time-matched.
7. **`gait_method1`** — `IMUGaitFSM` per foot → phase timeline + HS/TO indices.
8. **`freeze_index`** — per sensor: FI = Σpower(3–8 Hz)/Σpower(0.5–3 Hz), sliding
   4 s window / 0.25 s step on motion-norm (COMETA acc-norm; WIMU available
   motion-norm). Welch/FFT per window.
9. **`make_figures`** — save PNGs to `FES/subjects/`:
   - (a) bilateral knee/hip/ankle vs time, phase shading.
   - (b) both feet: gyro-Y + HS/TO markers + phase bands.
   - (c) FI of all 13 sensors vs time + freeze threshold line.

**Reuse wiring:** `sys.path.insert` `FES/GUI` → import `stimulator.closed_loop`,
`stimulator.gait_detection_imu`, `stimulator.gait_phases`.

## Known limitations

- No functional calibration in FOG protocol → angles offset relative to standing
  neutral, not anatomically zeroed.
- Cross-system hip/ankle accuracy depends on COMETA↔WIMU clock alignment.
- WIMU Freeze Index uses gyro-norm if cols 1–3 prove to be angular velocity (FI is
  conventionally defined on linear accel); flagged on the plot.
- COMETA blocks 2,3,6,7 unverified; mapping warns but does not abort.
