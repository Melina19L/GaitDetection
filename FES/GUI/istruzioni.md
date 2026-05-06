# NeuroPulse Analyzer - Project Context & Guide

## Project Scope
This project focuses on the **Development of Transcutaneous Spinal Cord Stimulation (tSCS) and Functional Electrical Stimulation (FES) Strategies for Gait Rehabilitation**, with a specific focus on addressing Freezing of Gait in Parkinson's Disease. 

The core of the project is a Python-based GUI (built with PySide6) that performs **real-time gait detection** using IMU sensors and FSRs (Force Sensing Resistors). It tracks joint angles (ankle dorsi/plantarflexion, hip, trunk) and identifies key gait cycle phases (such as Heel Strike and Toe Off using gyroscope peak/valley detection) to trigger closed-loop neuromodulation.

## Directory & Data Management
The application employs a dynamic, OS-independent file management system for clinical data:

**Base Data Path:**
- **macOS:** `~/Library/Application Support/NeuroPulse Analyzer/NeuroPulseAnalyzer_Dataset/phase1`
- **Windows:** `%APPDATA%\Programs\NeuroPulse Analyzer\NeuroPulseAnalyzer_Dataset\phase1`
- **Linux:** `~/.local/share/NeuroPulse Analyzer/NeuroPulseAnalyzer_Dataset/phase1`

*(Note: Fallback is `NeuroPulseAnalyzer_Dataset/phase1` in the local workspace directory if the above paths fail).*

**Data Organization:**
- **Session/Patient Subdirectories:** Dynamically generated based on the patient's name and session info inputted via the GUI.
- **Saved File Types:**
  - `*.pkl`: Serialized databases containing complete session recordings and sensor data streams.
  - `*.xlsx`: Unified workbook with sheets for joint angles, raw IMU streams (one sheet per sensor), FSR streams, and stim events. *(Sole destination for raw data — replaces the legacy `raw_data/` folder and `*_joint_angles.csv` file, both removed.)*
  - `*_plot.pkl`: AngleCalibrator buffers for offline replay/plotting.

## Core Architecture
- **`gui/`**: Contains the PySide6 frontend (Main Window, Pages, Widgets). The main entry point for UI setup and interactions is `gui/uis/windows/main_window/setup_main_window.py`.
- **`stimulator/`**: Handles backend logic, including serial communication for the stimulator, stimulation parameters, closed-loop control triggers (`closed_loop.py`), and the biological gait phase models.
- **`ble/`**: Manages Bluetooth Low Energy connections, specifically containing the `FSRController` for real-time foot pressure data and the IMU `BLEScanner`.
- **`offline_gait_analyzer.py`**: A standalone script used to validate and refine the real-time detection algorithms on pre-recorded `.pkl` data.
- **`angle_calibrator.py`**: Manages the functional calibration procedure to biomechanically align and center IMU angles (e.g., setting ankle to 0° during quiet standing).

## Recent Milestones & Changes
1. **Data Directory Restructuring:** Implemented dynamic patient-specific directory generation to robustly organize `.pkl`, `.csv`, and raw logs across operating systems.
2. **IMU Calibration & Stability:** Resolved instability in real-time ankle angle estimation by strictly enforcing "Calibrate Offsets" during quiet standing to prevent signal drift. Renamed GUI sensor positions to explicitly use "Right Trunk" and "Left Trunk".
3. **FSR GUI Integration:** Added real-time FSR data streaming (front, middle, back foot) into the GUI for constant visual monitoring and validation.
4. **Algorithm Synchronization:** Unified the real-time GUI gait detection logic with the offline analysis script (`offline_gait_analyzer.py`), ensuring consistent phase segmentation (Heel Strike, Toe Off) calibrated for realistic walking speeds (e.g., 3 km/h).
5. **Connection Logic:** Enhanced IMU connection workflow robustness, including independent toggles for left/right legs, connection status feedback, and strict checks before allowing calibration or real-time graphing.
6. **Setup vs Test Data-Flow Refactor:** Reorganised plotting and persistence so that the **Setup IMU** page is now preview-only (the "Save Data..." button on the floating `PlotDialog` was removed) and the **Esecuzione Test** page is the single point of acquisition. Page 10 now embeds the same Hip/Knee/Ankle real-time plots so the operator can monitor live signals while data is being acquired. At the end of every test the system writes (a) the existing master `.pkl` and per-sensor CSVs, (b) a new unified `<base>.xlsx` workbook with sheets for joint angles, raw IMU streams, FSR streams and stim events, and (c) a `<base>_plot.pkl` containing the calibrator angle buffers (the old "Save Data..." function moved to the post-test stage). Affected files: [plot_dialog.py](FES/GUI/gui/widgets/py_angle_plot/plot_dialog.py), [py_angle_plot/__init__.py](FES/GUI/gui/widgets/py_angle_plot/__init__.py), [widgets/__init__.py](FES/GUI/gui/widgets/__init__.py), [setup_main_window.py](FES/GUI/gui/uis/windows/main_window/setup_main_window.py), [main_window.py](FES/GUI/gui/uis/windows/main_window/main_window.py), [stimulation_classes.py](FES/GUI/stimulator/stimulation_classes.py), [requirements.txt](FES/GUI/requirements.txt) (added `openpyxl`).
7. **Test-Page UI Split (Pre-Test ↔ Test Execution):** The single, cluttered Page 10 was split into two pages so parameters and live monitoring no longer compete for screen space.
   - **Page 11 — Pre-Test:** owns the title "Stimulation Parameters", the carrier-frequency row, the Left/Right channel-current grids with the electrode image, and the Set/Start/Stop test-trigger buttons. A new **`Next →`** button at the bottom advances to the test-execution page.
   - **Page 10 — Test Execution:** now contains only the real-time Knee/Ankle/Hip plots, the **`Confirm and Start` / `Pause` / `Stop`** control buttons, and the Status & Log panel (Timer + Step Counter + Active Phase). A new "Test Execution — Real-Time Monitoring" header was added at the top. All five navigation entry points that previously landed on Page 10 (left-menu `btn_stimulation_2`, `subj_clicked`, `finish_btn_clicked`, `cancel_clicked`, `finish_result_clicked`) now land on Page 11; only the in-flight start-experiment confirm hop still routes to Page 10. Affected files: [setup_main_window.py](FES/GUI/gui/uis/windows/main_window/setup_main_window.py).
8. **Unified Excel Persistence (raw_data folder removed):** Eliminated the legacy `raw_data/` directory and the `<base>_joint_angles.csv` file. The unified `<base>.xlsx` workbook (sheets `Joint_Angles`, `Raw_<sensor>` per IMU, `FSR_Left/Right`, `Stim_Events`) is now the sole destination for raw and computed kinematic data. The `export_csv_logs` function and the `import csv` it pulled in were deleted from `stimulation_classes.py`; the master `.pkl` and `<base>_plot.pkl` saves are unchanged. Affected file: [stimulation_classes.py](FES/GUI/stimulator/stimulation_classes.py).
9. **Hardware Update — 8 IMUs → 7 IMUs (Pelvis sensor):** Replaced the two trunk sensors (`left_trunk`, `right_trunk`) with a single pelvis IMU shared between both hip computations. New sensor count: *Right/Left Foot, Right/Left Shank, Right/Left Thigh, Pelvis* (7 total).
   - `AngleCalibrator` now exposes a single `pelvis_inlet`; `_diag` and `_acc` per-key dictionaries dropped the trunk entries and added `"pelvis"`. The hip math reads pelvis as the proximal segment vs. each thigh as the distal one. Pelvis samples are snapshot-shared between left and right hip per tick, then the maximum number of samples consumed by either side is popped from the shared deque exactly once.
   - `LSLStreamResolver` resolves the single pelvis stream (`"Pelvis"` → fallback `"Custom 1"`) on the first leg connect; the second leg connect skips resolution to avoid binding two inlets to the same stream. Disconnect closes the pelvis inlet only when both legs are gone, and resets the `pelvis_already_bound` flag so a future re-connect can re-resolve.
   - `StimulationIMUs` (`update_closed_loop` and the FSM-construction loop) now reads a single `pelvis_fsm1/2` shared between left and right hip ROM updates instead of the previous per-side `*_leg_trunk_fsm1/2`.
   - GUI hip-toggle validation in `setup_main_window.py` now references `cal.pelvis_inlet` (with side-specific thigh) and the user-facing message reads "Pelvis + Left/Right Thigh".
   - `offline_gait_analyzer.py` reconstructs hip angles offline from `pelvis_fsmN` + `*_thigh_fsmN`, with a fallback to legacy `*_trunk_fsmN` keys so older `.pkl` files still load.
   - Affected files: [angle_calibrator.py](FES/GUI/angle_calibrator.py), [stimulation_classes.py](FES/GUI/stimulator/stimulation_classes.py), [setup_main_window.py](FES/GUI/gui/uis/windows/main_window/setup_main_window.py), [offline_gait_analyzer.py](FES/GUI/offline_gait_analyzer.py).
10. **Page 10 Plot Layout Rework (taller, readable amplitudes):** The Knee/Ankle/Hip plots on the Test Execution page were previously stacked vertically inside a `QVBoxLayout`, producing wide-but-short canvases (~1500×150 px) that hid waveform amplitudes. Switched the `page10_plots_frame` to a horizontal `QHBoxLayout` of three equal columns (one per joint), each column being a `QVBoxLayout` of `[title, plot, legend]`. Each plot now occupies ~1/3 of the window width and the full plot-frame height (~500×500 px on a typical screen), so left/right sinusoid amplitudes are clearly readable. Bumped the plot frame's stretch factor in the Page-10 main layout from 1 to 3 and capped `page10_footer_row.setMaximumHeight(280)` so Status & Log can no longer steal vertical real estate; added `page10_plots_frame.setMinimumHeight(380)` to guard against collapse on smaller screens. Affected file: [setup_main_window.py](FES/GUI/gui/uis/windows/main_window/setup_main_window.py).
11. **`StimulationFSRandIMU.save_data` Coverage Fix (gait + FSR test mode):** A static AST audit of every `Stimulation*.save_data` against the keys the unified xlsx writer expects revealed that the realistic IMU+FSR test class wrote an incomplete workbook: missing quaternions in the per-sensor `Raw_*` sheets, an empty `Joint_Angles` sheet, and missing de-stimulation timestamps in `Stim_Events`. The fixes:
    - `rom_block` now also writes `qw/qx/qy/qz` when the FSM exposes them, so `Raw_<sensor>` sheets are uniform across all subclasses.
    - Added the 12 joint-angle keys (`imu_left/right_knee/ankle/hip_angles` + `_timestamps`) by pulling from the parent class's ROM calibrators via two helpers (`_rom_angles`, `_rom_timestamps`) that guard against empty `angles` arrays.
    - Added `imu_timestamps_de_stim_left/right` so `Stim_Events` carries the de-stim column once stimulation lands.
    - Separately, `StimulationFSR.save_data` had four references to the wrong attribute (`*_fsr_imu_fsm` — only exists in `StimulationFSRandIMU`); corrected to `*_fsr_fsm` so phase timestamps/counters actually populate in FSR-only mode (they previously fell through to `None` via `getattr`).
    - Verified via AST coverage check: in the realistic `StimulationFSRandIMU` mode, `Joint_Angles`, `Raw_<sensor>`, `FSR_Left/Right`, and `Stim_Events` sheets are all populated. Affected file: [stimulation_classes.py](FES/GUI/stimulator/stimulation_classes.py).
12. **Gait Event Sheets in Unified Excel (`Gait_Events_FSR` + `Gait_Events_IMU`):** Added two sheets to `export_xlsx_log` so the operator can validate gait-cycle phase classification offline without leaving the workbook.
    - **`Gait_Events_FSR`** — discrete-event timestamps from the FSR detector, one column per (event × side): `HS_Left`, `MS_Left`, `TO_Left`, `Valleys_Left` and the corresponding `_Right` columns. Different-length arrays are padded with None by `_frame_from_columns`.
    - **`Gait_Events_IMU`** — discrete-event timestamps from the IMU FSMs, dynamically discovered. For every `data_to_save` key matching `imu_<side>_<placement>_<suffix>_<event>` with `<event> ∈ {heel_strike_peaks, toe_off_peaks, valleys}`, a column is emitted (e.g. `right_shank_fsm1_heel_strike_peaks`).
    - Source data is already produced by the FSR/IMU FSMs and persisted to the `.pkl`; the new sheets simply expose them at the xlsx layer so users can overlay events on the joint-angle traces, compare FSR vs IMU detection latency, and measure stance/swing durations from a single Excel file.
    - Stim event coverage is tracked but currently dormant (the stim pipeline isn't wired up); the `Stim_Events` sheet is written when stim keys are present and skipped otherwise. Affected file: [stimulation_classes.py](FES/GUI/stimulator/stimulation_classes.py).

## AI System Instructions (CRITICAL)
**Mandatory Logging Rule:** At the end of any significant coding session, feature implementation, or bug fix, the AI Assistant **MUST** update this `istruzioni.md` file. 
You must add a new bullet point to the "**Recent Milestones & Changes**" section detailing:
- What was modified or implemented.
- Why the change was necessary.
- Which core files were affected.

This ensures a continuous, up-to-date log of the project's evolution and state.
