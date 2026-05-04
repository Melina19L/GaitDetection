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
  - `*_joint_angles.csv`: Exported biomechanical kinematic data.
  - `raw_data/`: Directory containing raw sensor logs (including recently fixed IMU trunk logging).

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

## AI System Instructions (CRITICAL)
**Mandatory Logging Rule:** At the end of any significant coding session, feature implementation, or bug fix, the AI Assistant **MUST** update this `CLAUDE.md` file. 
You must add a new bullet point to the "**Recent Milestones & Changes**" section detailing:
- What was modified or implemented.
- Why the change was necessary.
- Which core files were affected.

This ensures a continuous, up-to-date log of the project's evolution and state.
