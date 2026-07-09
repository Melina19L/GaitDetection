# INSTRUCTIONS.md

Developer reference for this repository: architecture, conventions and how the
pieces fit together.

## What this is

GaitDetection is the software for an EPFL master thesis (part of the MAPP project): a real-time, closed-loop system that detects gait phases/subphases and stimulates leg muscles (FES + tSCS) in Parkinson's patients during freezing-of-gait episodes. It is a PySide6 desktop application built on the **PyDracula / PyOneDark** Qt Designer template.

Active development branch is `v2` (not `main`).

## Running & environment

The app runs from `FES/GUI/`:

```bash
cd FES/GUI
python main.py            # launches the GUI (entry point)
```

Dependencies (`FES/GUI/requirements.txt` or `gait.yml` for conda; conda env defaults to name `gait`):

```bash
pip install -r requirements.txt        # from FES/GUI/
# or: conda env create --name gait --file gait.yml
```

Key pinned deps and what they're for: **PySide6 6.9.0** (GUI), **pylsl 1.17.6** (Lab Streaming Layer — all sensor data flows over LSL), **bleak 0.22.3** + QtBluetooth (BLE FSR sensors), **pyserial** (stimulator), **pyqtgraph** (live plots), **imufusion** / **scipy** (quaternion math), **openpyxl/pandas** (data export). Movella/Xsens DOT IMUs need the separate Movella DOT PC SDK (see `FES/GUI/README.md`).

There is **no automated test suite**. The `test_*` / `debug_*` / `fix_*` / `analyze_raw*` scripts scattered in `FES/GUI/` are one-off exploratory throwaways, not a regression suite — treat them as low-value scratch.

`FES/GUI/venv/` is a vendored virtualenv (8000+ files) — NOT source. Real project source is ~157 `.py` files / ~35K lines. Ignore `venv/` when searching.

Platform note: codebase targets both Windows (production rig: stimulator on `COM3`, winrt BLE — commented-out deps at bottom of requirements.txt) and macOS (dev). `main.py` forces LSL onto IPv4 loopback.

## Architecture

The system is a 10ms real-time loop fed by sensor streams over LSL, driving a gait-phase state machine, which drives muscle stimulation over serial. Data is recorded to pickle + Excel.

### Real-time core — `FES/GUI/stimulator/` (the actual IP)

This is where the thesis contribution lives. Read these first.

- **`gait_phases.py`** — `Phase` enum, 9 values: UNKNOWN, STANCE, LOADING_RESPONSE, MID_STANCE, TERMINAL_STANCE, PRE_SWING, SWING, MID_SWING, TERMINAL_SWING. The shared vocabulary everything else speaks.
- **`gait_detection_imu.py`** — IMU gait FSMs over LSL (Movella/Xsens DOT shank/foot/thigh/pelvis, ~60–100Hz). `IMUGaitFSM` = **Method 1** (find_peaks/valleys on gyro-Y; HS vs TO classified by distance to valley/peak). `IMUGaitFSM_2` = **Method 2** (gyro-norm threshold gating for TO/HS + static Aminian pipeline). `_DUMMY` = no-op fallback. Both auto-tune via `_adaptive_update_params` (from measured cadence + peak heights); params scale by walking `speed`. Stance subphases are timed off the heel-strike via `QTimer.singleShot` (LR = stance/6, MST = stance/3, TST = stance/`terminal_stance_divider`).
- **`gait_detection_fsr.py`** — FSR (force-sensitive resistor: front/mid/back foot) FSMs: `FSRGaitFSM`, `FSRGaitFSM_2` (mean-threshold + hysteresis), `_DUMMY`.
- **`gait_detection_imu_fsr.py`** — `FSRIMUGaitFSM` fusion: FSR drives stance/swing; IMU gyro valley triggers MID_SWING→TERMINAL_SWING (FES only).
- **`closed_loop.py`** — quaternion joint-angle math. Knee = SAA (Segment Axis Angle) via `angle_between_quaternions` (the method that actually runs). Ankle = signed sagittal projection / hinge-axis SVD (`identify_hinge_axis`), decoupled from knee flexion. `ROM` class stores angles; `PIController` for closed-loop knee control.
- **`stimulator_parameters.py`** — `StimulatorParameters`: 8 channels, per-channel tSCS/FES mode, currents + max + PI offset, burst/carrier/pulse params. `MAX_CURRENT = 110mA`. Translates high-level params into `ComPortFunc` serial calls.
- **`gait_model_stimulation_functions.py`** — `MUSCULAR_GROUP_SELECTION` (and `_2`, without distal) maps each `Phase` → muscle targets per side (TA/GA/VM/BF/GM/RF + proximal/distal/full_leg electrodes). `open_stimulation_channel_phases_imu/fsr/imu_fsr`, `open_stimulation_FES_step`, `update_offset`, 10s current ramp.
- **`stimulation_classes.py`** — `StimulationBasic` (abstract QObject; 10ms QTimer `main_loop_iteration`: update_sensors → phase_detection → update_closed_loop → ramp → stimulate; pause/resume drains LSL inlets; saves pickle + `export_xlsx_log`). Subclasses: `NoStimulation`, `StimulationFSR`, `StimulationIMUs`, `StimulationFSRandIMU`, `StimulationFESStep`.
- **`experiment_handler.py`** — `ExperimentHandler` selects the `Stimulation*` subclass from `use_imus`/`use_fsr` kwargs, wires Qt signals (steps/phase/active-time) to the GUI, prevents sleep (`caffeinate` on mac).
- **`ComPortFunc.py`** — custom 7-bit-framed serial protocol over pyserial (COM3, 115200×8). MSB of every byte is reserved for framing (`MSG_END = 0x80`); checksum = XOR of all bytes `& 0x7F`. Key fns: `SetSingleChanSingleParam` (MSG_ID 221; var_id 6 = current mA float), `SetSingleChanState` (MSG_ID 223; must enable Power→HV→Output in order), `SetSingleChanAllParam` (MSG_ID 220). `uint32_to_binary`/`float_to_binary` split 32-bit values into 5×7-bit bytes.

### GUI layer — `FES/GUI/`

Built on PyDracula (files headed `BY: WANDERSON M.PIMENTA` are stock template; the project IP is the page content + wiring). Entry: `main.py` → `MainWindow`.

PyDracula wiring split (important for finding things):
- **`gui/uis/windows/main_window/setup_main_window.py`** (~7800 lines) — `SetupMainWindow` builds **all** page content + business logic. Despite the size, mostly widget construction. This is where the experiment is configured.
- **`gui/uis/windows/main_window/main_window.py`** — `MainWindow` controller: holds `ExperimentHandler` in its own `QThread`, two `FSRController` (BLE, per side), `BLEScanner`, `AngleCalibrator`; wires step/phase signals to the Test page; stopwatch; pause/resume (11s lockout).
- **`functions_main_window.py`** — `MainFunctions`, page/column navigation + animations. `ui_main.py` / `ui_main_pages.py` — PyDracula shell + Qt-Designer-generated pages 1–9.
- **`angle_calibrator.py`** (~1700 lines) — `AngleCalibrator`: live joint-angle engine feeding GUI plots. Resolves LSL streams per side via `LSLStreamResolver` worker thread; 20ms `record_data` time-matches paired snapshots into per-joint deques and computes knee/ankle/hip via `ROM`/`closed_loop`. `calibration()` = 1s neutral-pose quaternion offset; `ankle_functional_calibration()` = 5s flex → `identify_hinge_axis`.

**Experiment launch flow (trace this to understand the whole app):**
`confirm_clicked` → builds `StimulatorParameters` → `create_dict` (static, ~line 7700 of setup_main_window) assembles the full kwargs dict `dict_to_send` (stim params + channels + currents, `use_imus`/`use_fsr`/`nb_imus`, `method_imu`/`method_fsr`, knee offsets + ankle ref quats/axes from calibrator, PI gains + angle ranges, `closed_loop`, `FES`/`tSCS`, `terminal_stance_divider`) → `SensorReadinessDialog` warm-up gate → `start_experiment.emit(task_dict)` → `ExperimentHandler.start_experiment_safe` → a `Stimulation*` subclass.

Page flow (`QStackedWidget`): p1 home/serial-port, p2 subject demographics, p3 task + stim params + study phase, p5 stim setup (8-channel amp/max, electrode↔channel↔target), p6 confirmation, p7 results, **p8 FSR setup** (BLE scan/connect, insole size→CoP), **p9 IMU setup** (per-segment toggles, knee/ankle/hip scale+target+PI, AngleCalibrator built here, calibrate offsets/ankle axis), **p10 Test Execution** (embedded live plots + per-channel testing + Start/Pause/Stop + Status&Log), **p11 Pre-Test review**.

### Hardware I/O — `FES/GUI/ble/`

- **`fsr_controller.py`** — `FSRController(foot)`: per-foot QtBluetooth on a dedicated QThread; scans, connects `QLowEnergyController`, subscribes the FSR characteristic (writes `0100` to CCCD). Payload = 4 bytes `<BBBB>` → `updateFSR([ff,mf,bf])`. Per-foot service/char UUIDs are hardcoded. MainWindow wraps each sample with CoP and pushes to LSL `FSR_Left`/`FSR_Right`.
- **`ble_scanner.py`** — `BLEScanner`, generic LE scan.

### Offline analysis — `FES/subjects/`

Standalone post-processing of recorded trials (the GUI saves `<base>.pkl` + `<base>_plot.pkl` + `<base>.xlsx`). **All hardcode their input paths.**
- `gait_pattern_analyzer.py` — FSR analyzer: heel-strike detect, segment + normalize cycles to 100 pts, plot raw + mean±SD + CoP.
- `testsorosh/trial2/sync_data.py` — single-trial clock-domain merger: maps FSR (~6000s LSL domain) onto the IMU clock, recomputes CoP, **overwrites the `.pkl`**, writes a 3-sheet xlsx (60Hz master grid + events).
- `testsorosh/trial2/compare_gui_vs_mocap.py` — validates GUI IMU angles vs Vicon inverse-kinematics gold standard: one normalized gait cycle, per-joint ROM + RMSE.

Saved-file schema: `rom_data[<side>_<placement>_fsm{1,2}]` (raw acc/gyro/quat + timestamps), `imu_<side>_<joint>_angles/timestamps`, `fsr_*` raw + events, `imu_<side>_<placement>_fsm2_{heel_strike,toe_off}_peaks`.

Each run writes four files (see `FES/GUI/README.md` for the user-level version):
- `<base>.pkl` — the master record (the schema above).
- `<base>.xlsx` — the same, as an Excel workbook. Sheets written by
  `export_xlsx_log` (in `stimulation_classes.py`): `Joint_Angles`,
  `Raw_<sensor>` (one per IMU), `FSR_Left` / `FSR_Right`, `Gait_Events_FSR`,
  `Gait_Events_IMU`, `Stim_Events`, `All_Synchronized_Data`.
- `<base>_plot.pkl` — the `AngleCalibrator` angle buffers (dense, plain dict).
- `<base>_plot.xlsx` — sheets: `Joint_Angles_Native`, `Joint_Angles_Resampled`
  (uniform 60 Hz grid + `is_walking`), `Calibration` (SVD/CARD per joint),
  `Walk_Window`, `Raw_*`.

The IMU angles inside the master `.xlsx`/`.pkl` are sparse (updated only when the
stimulation logic queries them); for continuous per-joint angles use the
`_plot.xlsx` `Joint_Angles_Resampled` sheet.

## How the joint angles are computed

**The maths lives in `stimulator/closed_loop.py`.** It works from per-segment IMU
quaternions (Movella DOT orientation, [w,x,y,z]) and produces one angle per joint:

- **Knee** — Segment Axis Angle: `angle_between_quaternions(q_thigh, q_shank)`,
  the angle between the two segments' long axes. This is the path that actually
  runs for the knee.
- **Hip** — functional hinge: the pelvis↔thigh rotation projected onto the hip
  hinge axis found at calibration (`identify_hinge_axis` → SVD), extracted with
  `extract_functional_angle` (swing-twist). Yaw-invariant.
- **Ankle** — `signed_ankle_angle` (gravity-constrained sagittal projection) or
  the functional hinge, decoupled from knee flexion, with a ±50° clamp and a
  spike-rejection guard against foot-IMU heading glitches.

Calibration is what makes these meaningful: it stores each joint's neutral
reference and hinge axis. `ROM` (also in `closed_loop.py`) holds those references
and the running angle series.

**Real-time (during a session):** `angle_calibrator.py` is the engine. Its 20 ms
`record_data` timer pulls the latest paired quaternions per side, calls the
`ROM`/`closed_loop` functions above, and stores knee/ankle/hip in per-joint
buffers. Those buffers feed the live plots and, at the end of the run, are written
to `<base>_plot.pkl` / `<base>_plot.xlsx`. Calibration itself is also here:
`global_calibration_10s` (standing neutral offset + knee/hip hinge from the
sit-down) and `ankle_functional_calibration` (seated flex → ankle hinge). The box
that reports **SVD vs CARD** per joint comes from `get_method_per_joint`.

**Offline (to look at the angles later):** the angles are already computed and
saved, so the simplest path is to just open `<base>_plot.xlsx`
(`Joint_Angles_Resampled` sheet — all joints on one time grid). If instead you
need to *recompute* angles from scratch (a different method, a validation), the
raw quaternions/acc/gyro are in the main `<base>.pkl` under
`rom_data[<side>_<placement>_fsm{1,2}]`, and you call the same
`closed_loop.py` functions on them in a script.

### Which code to analyse them offline

Offline post-processing lives in `FES/subjects/` (all scripts hardcode their
input paths — edit the path at the top):

- **`gait_pattern_analyzer.py`** — FSR: detects heel strikes, segments and
  normalises cycles to 100 points, plots raw + mean±SD.
- **`testsorosh/trial2/compare_gui_vs_mocap.py`** — validates the GUI IMU angles
  against a Vicon inverse-kinematics gold standard (one normalised gait cycle,
  per-joint ROM + RMSE). This is the template for angle validation: read the
  `_plot` data, segment into gait cycles, compare.

The general recipe for any offline angle analysis: read `<base>_plot.pkl`
(dense angles, plain dict, no custom classes needed) or the raw quaternions from
`<base>.pkl`, then segment/normalise/plot.

## Gait detection

The detectors are finite-state machines that all expose the same interface and
emit `Phase` values; you pick IMU-only, FSR-only or fused at runtime.

### FSR (force insoles) — `stimulator/gait_detection_fsr.py`

The insole reports force under three foot zones (front / mid / back), streamed per
side over LSL (`FSR_Left` / `FSR_Right`). Logic is straightforward: **foot loaded
= stance, foot unloaded = swing**; the load onset is heel-strike, the release is
toe-off. `FSRGaitFSM` (Method 1) uses a fixed force threshold; `FSRGaitFSM_2`
(Method 2) uses a mean threshold with hysteresis to reject chatter and splits the
stance subphases via `terminal_stance_divider`. `_DUMMY` is the no-op fallback.
Because it measures ground contact directly, FSR is simple and robust for
stance/swing, but gives less information about what the leg is doing mid-swing.

### IMU — `stimulator/gait_detection_imu.py`

The detection sensor is the **shank (shin) IMU gyroscope**, one per side — the
shank angular velocity has clear, repeatable peaks and valleys across the gait
cycle. (The other IMUs are for angles, not detection: foot for the ankle and the
fusion swing-trigger, thigh for knee/hip, pelvis as the hip reference.) Two
methods, selectable at runtime:

- **Method 1 — `IMUGaitFSM`** (peaks/valleys on shank gyro-Y): finds the peaks
  and valleys of the shank angular velocity and classifies heel-strike vs toe-off
  by distance to the neighbouring valley/peak.
  - *Pros:* annotation-free, no fixed thresholds to tune, and the most robust in
    validation — it holds up well in straight walking and even through turns.
  - *Cons:* relies on the signal having clear peaks; very slow, shuffling or
    irregular gait with low gyro amplitude can make peaks harder to pick.
- **Method 2 — `IMUGaitFSM_2`** (gyro-norm threshold gating + static Aminian
  pipeline): gates toe-off/heel-strike on the gyro *norm* crossing a threshold.
  - *Pros:* uses the full 3-axis magnitude, can be more sensitive to onset.
  - *Cons:* the norm threshold is less robust in **turns** (the norm behaves
    differently when the leg is also rotating in the transverse plane), where it
    tends to mis-fire. Threshold-based, so more sensitive to tuning.

Both auto-tune from the measured cadence and peak heights and scale with the
walking `speed` you set. `_DUMMY` is the no-op fallback.

In short: **Method 1 (shank peaks/valleys) is the default, annotation-free and
turn-robust choice; Method 2 (norm) can be more sensitive but degrades in turns.**

### Fused — `stimulator/gait_detection_imu_fsr.py`

`FSRIMUGaitFSM`: the FSR insole drives the stance/swing split (direct ground
contact), while an IMU gyro valley after toe-off triggers the
MID_SWING → TERMINAL_SWING transition. Combines FSR's reliable contact timing with
the IMU's mid-swing information.

## What each GUI file contains

Quick map of the source (ignore `venv/`; files headed `BY: WANDERSON M.PIMENTA`
are stock PyDracula template — the project work is the page content and wiring):

- **`main.py`** — entry point; sets up LSL loopback, launches `MainWindow`.
- **`angle_calibrator.py`** — the live joint-angle engine + calibration (see the
  angle section above).
- **`modify_svg.py`** — parses/labels/recolours the electrode SVG.
- **`stimulator/`** — the real-time core (the thesis IP):
  - `gait_phases.py` — the `Phase` enum (shared vocabulary).
  - `gait_detection_imu.py` / `gait_detection_fsr.py` / `gait_detection_imu_fsr.py`
    — the gait FSMs (see the detection section above).
  - `closed_loop.py` — the joint-angle maths + `PIController`.
  - `stimulation_classes.py` — the 10 ms real-time loop and data saving.
  - `gait_model_stimulation_functions.py` — phase→muscle mapping and channel control.
  - `stimulator_parameters.py` — the 8-channel configuration.
  - `ComPortFunc.py` — the low-level serial protocol to the stimulator.
  - `experiment_handler.py` — picks the stimulation mode and wires it to the GUI.
- **`gui/`** — the interface:
  - `uis/windows/main_window/setup_main_window.py` — builds every page's content
    and logic (the biggest file).
  - `uis/windows/main_window/main_window.py` — the controller: owns the worker
    threads and connects their signals to the pages.
  - `uis/windows/main_window/functions_main_window.py`, `ui_main*.py` — PyDracula
    navigation/shell and the generated page layouts.
  - `widgets/py_angle_plot/` — the live knee/ankle/hip plot widgets and their
    pop-out dialog.
- **`ble/`** — Bluetooth I/O: `fsr_controller.py` (one insole per side) and
  `ble_scanner.py` (device scan).

## Conventions & gotchas

- **LSL is the data bus.** Sensors → LSL outlets → FSM inlets. Stream names: `Right/Left Shank/Foot/Thigh`, `Pelvis`/`Custom 1`, `FSR_Right`/`FSR_Left`. To add/route a sensor, work through LSL, not direct calls.
- **Everything real-time is Qt-signal-driven across QThreads.** The stimulation loop, each FSR controller, and the experiment handler each live in their own thread; cross-thread comms is Qt signals only. Don't touch GUI widgets from worker threads.
- **Method 1 vs Method 2** for both IMU and FSR detection are selectable at runtime; the UI uses friendly names ("Main (norm)") that `create_dict` maps to internal names ("Method 2 - IMU"). When changing detection, know which method the experiment selected.
- Two distinct stimulation modes coexist per channel: **tSCS** (spinal) and **FES** (muscle). Channel config carries the mode; stimulation functions branch on it.
- `FES/GUI/.claude/CLAUDE.md` is a generic LLM-coding-discipline file, not project documentation — separate concern from this file.
