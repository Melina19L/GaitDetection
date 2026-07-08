"""Real-time stimulation loop classes.

``StimulationBasic`` is the abstract QObject that owns the 10 ms real-time loop
(``main_loop_iteration``: update sensors -> phase detection -> closed-loop update
-> current ramp -> stimulate), plus pause/resume and pickle/xlsx saving. The
concrete subclasses select the sensing/stimulation mode:

  * ``NoStimulation``       — record only, no stimulation output.
  * ``StimulationFSR``      — FSR-driven gait detection.
  * ``StimulationIMUs``     — IMU-driven gait detection + closed loop.
  * ``StimulationFSRandIMU``— fused FSR+IMU detection.
  * ``StimulationFESStep``  — fixed FES step sequence.

One instance lives in the ``ExperimentHandler`` thread; all cross-thread comms
is via Qt signals.
"""
from datetime import datetime,timezone
from .stimulator_parameters import StimulatorParameters
from .gait_detection_imu import IMUGaitFSM , IMUGaitFSM_2 , IMUGaitFSM_DUMMY
from .gait_detection_fsr import FSRGaitFSM , FSRGaitFSM_2 , FSRGaitFSM_DUMMY
from .gait_detection_imu_fsr import FSRIMUGaitFSM
from .ComPortFunc import SetSingleChanState, open_serial_port
from .gait_model_stimulation_functions import (
    open_stimulation_channel_phases_imu,
    open_stimulation_channel_phases_fsr,
    open_stimulation_channel_subphases,
    update_offset,
    open_stimulation_channel_phases_imu_fsr,
    open_stimulation_FES_step,
    start_ramp,
    stop_ramp,
)
from abc import ABCMeta, abstractmethod
from pylsl import StreamInlet, resolve_byprop
from serial import Serial
try:
    from typing import override  # Python 3.12+
except ImportError:
    def override(method): return method
from threading import Event
import time
import pickle
import os
import numpy as np
from PySide6.QtCore import QTimer, QObject, Signal
from PySide6.QtWidgets import QMessageBox
from .closed_loop import PIController, ROM

def export_xlsx_log(save_path, data_to_save):
    """Bundle every recorded stream into one Excel workbook.

    Sheets:
      - Joint_Angles: timestamps + Left/Right Hip/Knee/Ankle (degrees)
      - Raw_<sensor_key>: per-IMU raw acc/gyro/quat from rom_data
      - FSR_Left / FSR_Right: front/middle/back FSR samples (when available)
      - Stim_Events: stim/de-stim timestamps and currents per side
    """
    try:
        import openpyxl  # noqa: F401  (verify availability before pandas writer)
    except ImportError:
        print("Excel export skipped: openpyxl is not installed (pip install openpyxl).")
        return

    try:
        import pandas as pd
    except ImportError:
        print("Excel export skipped: pandas is not installed.")
        return

    base_dir = os.path.dirname(save_path)
    base_name = os.path.splitext(os.path.basename(save_path))[0]
    xlsx_path = os.path.join(base_dir, f"{base_name}.xlsx")

    def _series(arr):
        try:
            return list(arr) if arr is not None else []
        except Exception:
            return []

    def _clamp_ankle(arr, lo=-50.0, hi=50.0):
        """Clamp ankle angle samples to a physiological range.

        Magnetometer-induced quaternion wraparound on the foot IMU can produce
        ±100°/±300° spikes that contaminate the saved trace. Anything outside
        [lo, hi] is replaced with the previous valid sample (or 0.0 at the
        start) so downstream analysis sees a clean signal.
        """
        out, last = [], 0.0
        for v in (arr or []):
            try:
                x = float(v)
            except (TypeError, ValueError):
                out.append(v); continue
            if lo <= x <= hi:
                last = x
                out.append(x)
            else:
                out.append(last)
        return out

    def _frame_from_columns(cols: dict):
        max_len = max((len(v) for v in cols.values()), default=0)
        if max_len == 0:
            return None
        padded = {k: list(v) + [None] * (max_len - len(v)) for k, v in cols.items()}
        return pd.DataFrame(padded)

    sheets: dict[str, pd.DataFrame] = {}

    # 1) Joint angles
    angle_cols = {
        "Timestamp_LeftHip":  _series(data_to_save.get("imu_left_hip_timestamps")),
        "Left_Hip":           _series(data_to_save.get("imu_left_hip_angles")),
        "Timestamp_LeftKnee": _series(data_to_save.get("imu_left_knee_timestamps")),
        "Left_Knee":          _series(data_to_save.get("imu_left_knee_angles")),
        "Timestamp_LeftAnkle":_series(data_to_save.get("imu_left_ankle_timestamps")),
        "Left_Ankle":         _clamp_ankle(_series(data_to_save.get("imu_left_ankle_angles"))),
        "Timestamp_RightHip": _series(data_to_save.get("imu_right_hip_timestamps")),
        "Right_Hip":          _series(data_to_save.get("imu_right_hip_angles")),
        "Timestamp_RightKnee":_series(data_to_save.get("imu_right_knee_timestamps")),
        "Right_Knee":         _series(data_to_save.get("imu_right_knee_angles")),
        "Timestamp_RightAnkle":_series(data_to_save.get("imu_right_ankle_timestamps")),
        "Right_Ankle":        _clamp_ankle(_series(data_to_save.get("imu_right_ankle_angles"))),
    }
    df_angles = _frame_from_columns(angle_cols)
    if df_angles is not None:
        sheets["Joint_Angles"] = df_angles

    # 2) Raw IMU per-sensor (rom_data buckets)
    rom_data = data_to_save.get("rom_data", {}) or {}
    for sensor_key, sensor_data in rom_data.items():
        cols = {
            "Timestamp": _series(sensor_data.get("timestamps")),
            "AccX": _series(sensor_data.get("accx")),
            "AccY": _series(sensor_data.get("accy")),
            "AccZ": _series(sensor_data.get("accz")),
            "GyrX": _series(sensor_data.get("gx")),
            "GyrY": _series(sensor_data.get("gy")),
            "GyrZ": _series(sensor_data.get("gz")),
            "QuatW": _series(sensor_data.get("qw")),
            "QuatX": _series(sensor_data.get("qx")),
            "QuatY": _series(sensor_data.get("qy")),
            "QuatZ": _series(sensor_data.get("qz")),
        }
        df = _frame_from_columns(cols)
        if df is not None:
            # Excel sheet names are limited to 31 chars
            sheet = f"Raw_{sensor_key}"[:31]
            sheets[sheet] = df

    # 3) FSR (left / right)
    for side in ("left", "right"):
        cols = {
            "Timestamp":  _series(data_to_save.get(f"fsr_timestamps_{side}")),
            "Front_Foot": _series(data_to_save.get(f"fsr_data_ff_{side}")),
            "Mid_Foot":   _series(data_to_save.get(f"fsr_data_mf_{side}")),
            "Back_Foot":  _series(data_to_save.get(f"fsr_data_bf_{side}")),
            "CoP_X":      _series(data_to_save.get(f"fsr_cop_x_{side}")),
            "CoP_Y":      _series(data_to_save.get(f"fsr_cop_y_{side}")),
        }
        df = _frame_from_columns(cols)
        if df is not None:
            sheets[f"FSR_{side.capitalize()}"] = df

    # 3b) Gait events from FSR (discrete event timestamps per side).
    # Each column is independent (different lengths) — _frame_from_columns pads with None.
    fsr_event_cols = {}
    for side in ("left", "right"):
        side_cap = side.capitalize()
        for src_key, col_label in (
            ("fsr_heel_strike_timestamps", "HS"),
            ("fsr_mid_stance_timestamps",  "MS"),
            ("fsr_toe_off_timestamps",     "TO"),
            ("fsr_valley_timestamps",      "Valleys"),
        ):
            vals = data_to_save.get(f"{src_key}_{side}")
            try:
                if vals is not None and len(vals) > 0:
                    fsr_event_cols[f"{col_label}_{side_cap}"] = _series(vals)
            except Exception:
                pass
    df_fsr_events = _frame_from_columns(fsr_event_cols)
    if df_fsr_events is not None:
        sheets["Gait_Events_FSR"] = df_fsr_events

    # 3c) Gait events from IMU FSMs (discrete event timestamps per FSM).
    # Discovers dynamically every key matching `imu_<side>_<placement>_<suffix>_<event>`
    # where <event> ∈ {heel_strike_peaks, toe_off_peaks, valleys}.
    imu_event_cols = {}
    _imu_event_suffixes = ("_heel_strike_peaks", "_toe_off_peaks", "_valleys")
    for key, val in data_to_save.items():
        if not isinstance(key, str) or not key.startswith("imu_"):
            continue
        for sfx in _imu_event_suffixes:
            if key.endswith(sfx):
                try:
                    if val is not None and len(val) > 0:
                        # Strip the leading "imu_" so the column reads e.g.
                        # "right_shank_fsm1_heel_strike_peaks".
                        imu_event_cols[key[len("imu_"):]] = _series(val)
                except Exception:
                    pass
                break
    df_imu_events = _frame_from_columns(imu_event_cols)
    if df_imu_events is not None:
        sheets["Gait_Events_IMU"] = df_imu_events

    # 4) Stim events (timestamps + currents)
    stim_cols = {
        "Timestamp_Stim_Left":    _series(data_to_save.get("imu_timestamps_stim_left")),
        "Current_Left":           _series(data_to_save.get("imu_current_left")),
        "Timestamp_DeStim_Left":  _series(data_to_save.get("imu_timestamps_de_stim_left")),
        "Timestamp_Stim_Right":   _series(data_to_save.get("imu_timestamps_stim_right")),
        "Current_Right":          _series(data_to_save.get("imu_current_right")),
        "Timestamp_DeStim_Right": _series(data_to_save.get("imu_timestamps_de_stim_right")),
    }
    df_stim = _frame_from_columns(stim_cols)
    if df_stim is not None:
        sheets["Stim_Events"] = df_stim

    # 5) All_Synchronized_Data — IMU 60 Hz master grid, FSR & joint angles
    #    interpolated row-by-row onto the same timeline.
    #    Rationale: IMUs sample at 60 Hz (native), FSR at ~12 Hz (native).
    #    We build a uniform 60 Hz grid over the common time span and resample
    #    every channel onto it via np.interp. IMU keeps full resolution;
    #    FSR columns are linearly interpolated between native samples.
    imu_t_arrays = []
    for sensor_data in (rom_data.values() if rom_data else ()):
        ts = sensor_data.get("timestamps")
        if ts is None:
            continue
        arr = np.asarray(ts, dtype=float)
        if arr.size >= 2:
            imu_t_arrays.append(arr)

    if imu_t_arrays:
        # Intersection of all IMU sensor ranges -> no extrapolation
        t_lo = max(arr[0]  for arr in imu_t_arrays)
        t_hi = min(arr[-1] for arr in imu_t_arrays)
        if t_hi > t_lo:
            n_samples = int(round((t_hi - t_lo) * 60.0)) + 1
            master_t = np.linspace(t_lo, t_hi, n_samples)

            sync_cols = {"Timestamp": master_t.tolist()}

            # 5a) Per-sensor IMU channels -> interp onto master grid
            for sensor_key, sensor_data in rom_data.items():
                ts = np.asarray(sensor_data.get("timestamps", []), dtype=float)
                if ts.size < 2:
                    continue
                for var_key, col_suffix in (
                    ("accx", "AccX"), ("accy", "AccY"), ("accz", "AccZ"),
                    ("gx",   "GyrX"), ("gy",   "GyrY"), ("gz",   "GyrZ"),
                    ("qw",   "QuatW"), ("qx",  "QuatX"), ("qy",  "QuatY"), ("qz", "QuatZ"),
                ):
                    val = sensor_data.get(var_key)
                    vals = np.asarray(val if val is not None else [], dtype=float)
                    if vals.size != ts.size:
                        continue
                    sync_cols[f"{sensor_key}_{col_suffix}"] = np.interp(master_t, ts, vals).tolist()

            # 5b) FSR per side -> interp onto master grid (12 Hz -> 60 Hz, linear)
            for side in ("left", "right"):
                val_t = data_to_save.get(f"fsr_timestamps_{side}")
                fsr_t = np.asarray(val_t if val_t is not None else [], dtype=float)
                if fsr_t.size < 2:
                    continue
                side_cap = side.capitalize()
                for src_key, col_label in (
                    (f"fsr_data_ff_{side}", "FSR_Front"),
                    (f"fsr_data_mf_{side}", "FSR_Mid"),
                    (f"fsr_data_bf_{side}", "FSR_Back"),
                    (f"fsr_cop_x_{side}",   "FSR_CoP_X"),
                    (f"fsr_cop_y_{side}",   "FSR_CoP_Y"),
                ):
                    val = data_to_save.get(src_key)
                    vals = np.asarray(val if val is not None else [], dtype=float)
                    if vals.size != fsr_t.size:
                        continue
                    sync_cols[f"{side_cap}_Foot_{col_label}"] = np.interp(master_t, fsr_t, vals).tolist()

            # 5c) Joint angles per side -> interp onto master grid
            for side in ("left", "right"):
                side_cap = side.capitalize()
                for joint in ("hip", "knee", "ankle"):
                    val_t = data_to_save.get(f"imu_{side}_{joint}_timestamps")
                    jt = np.asarray(val_t if val_t is not None else [], dtype=float)
                    val_a = data_to_save.get(f"imu_{side}_{joint}_angles")
                    ja = np.asarray(val_a if val_a is not None else [], dtype=float)
                    if jt.size < 2 or jt.size != ja.size:
                        continue
                    sync_cols[f"{side_cap}_{joint.capitalize()}_Angle"] = np.interp(master_t, jt, ja).tolist()

            # Only emit the sheet if we got at least one data column beyond Timestamp
            if len(sync_cols) > 1:
                sheets["All_Synchronized_Data"] = pd.DataFrame(sync_cols)

    if not sheets:
        print("Excel export skipped: no streams to write.")
        return

    try:
        with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
            for name, df in sheets.items():
                df.to_excel(writer, sheet_name=name, index=False)
        print(f"Excel workbook exported to {xlsx_path}")
    except Exception as e:
        print(f"Failed to export Excel workbook: {e}")

COM_PORT = "COM3"  # Replace with your COM port
BAUDRATE = 115200 * 8  # Replace with your baud rate
TIMEOUT = 2  # seconds, time to wait for the streams to be found

PRIORITY = [("foot", "fsm2") , ("shank", "fsm2"), ("foot", "fsm1"), ("shank", "fsm1") ] # THIS NEED TO BE REVIEWED, AT THE END WE WILL ONLY USE ONE METHOD AND PLACMENT FOR STIMULATION

class MetaQObjectABC(type(QObject), ABCMeta):
    pass

class StimulationBasic(QObject, metaclass=MetaQObjectABC):
    """Abstract base for every stimulation mode: owns the 10 ms real-time loop.

    Each ``main_loop_iteration`` (driven by a 10 ms QTimer) updates the sensor
    inlets, runs phase detection, updates the closed loop, ramps current and
    stimulates. Handles start/pause/resume (draining LSL inlets on pause) and,
    on stop, saves the recording as pickle + ``export_xlsx_log``. Subclasses
    implement the mode-specific sensing and stimulation.
    """
    # Create a threading event for the STOP button in the GUI
    stop_main_event = Event()
    finished = Signal(tuple)
    error = Signal(Exception)
    # New: step count across all legs/modalities (total)
    step_count_changed = Signal(int)
    # NEW: live active run time signal (seconds, excludes pauses)
    active_run_seconds_changed = Signal(float)

    def __init__(self, **kwargs):
        super().__init__()
        # Extract the parameters from kwargs
        self.stim_param: StimulatorParameters = kwargs["stimulation_parameters"]
        self.channels: dict = kwargs["channels"]
        self.use_four_imus: bool = kwargs["nb_imus"] == 4
        self.do_phase_detection: bool = kwargs.get("do_phase_detection", False)
        #self.do_subphase_detection: bool = kwargs.get("do_subphase_detection", False) # DONT NEED
        self.save_path: str = kwargs.get("save_path_filename", "")
        self.stimulator_connection: Serial = kwargs.get("stimulator_connection", None)
        self.do_continuous_stimulation: bool = kwargs.get("do_continuous_stimulation", False)
        #self.fast_walking: bool = kwargs.get("fast_walking", False) # DONT NEED
        self._finished: bool = False  # NEW: track finalized state
        self.FES: bool = kwargs.get("FES", False)
        self.do_closed_loop: bool = kwargs.get("closed_loop", False)
        # RAMP state (non-blocking)
        self._continuous_ramp_active: bool = False
        self._continuous_ramp_start: float | None = None
        self._continuous_ramp_channel: int | None = None
        self._continuous_last_level: float | None = None

        if len(self.stim_param.stim_currents) > 0:
            # Prepare the channels for stimulation
            self.__connect_to_stimulator()
            self.__prepare_channels_for_stimulation()
        else:
            # Make sure the stimulator connection is None if no currents are set
            self.stimulator_connection = None

        self.stop_main_event.clear()  # Clear the event at the start

        # Setup the timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.safe_main_loop_iteration)

        # --- experiment timing ---
        self._exp_start_ts: float | None = None
        self._exp_end_ts: float | None = None

        # --- pause state ---
        self._paused: bool = False
        self._pause_started_at: float | None = None
        self._total_paused_duration: float = 0.0  # accumulated seconds of all completed pauses

        # Final exported metric
        self.active_run_seconds: float | None = None

        # NEW: UI tick (1 Hz) guarded to avoid double-starts
        self._ui_tick = QTimer(self)
        self._ui_tick.setInterval(1000)
        self._ui_tick.timeout.connect(self._emit_active_run_seconds)

    # ---------------------------------------------------------------------
    # Public methods
    # ---------------------------------------------------------------------
    @abstractmethod
    def phase_detection(self):
        # To be overridden in subclasses
        pass

    @abstractmethod
    def update_sensors(self):
        # To be overridden in subclasses
        pass

    @abstractmethod
    def update_closed_loop(self):
        # To be overridden in subclasses
        pass

    @abstractmethod
    def stimulate(self):
        # To be overridden in subclasses
        pass

    @staticmethod
    def stop_main_loop():
        # Set the event to stop the main loop
        StimulationBasic.stop_main_event.set()

    def stop_stimulation(self):
        # Close all stimulation channels
        if self.stimulator_connection is not None:
            StimulatorParameters.close_all_channels(self.stimulator_connection)
            print("Stimulator connection closed")

    @abstractmethod
    def save_data(self):
        # To be overridden in subclasses
        pass

    @abstractmethod
    def return_values(self):
        # Return values to be overridden in subclasses
        return None

    def force_stop_and_save(self):
        """Immediately finalize, even if paused (Stop pressed during pause)."""
        if getattr(self, "_finished", False):
            print("[ForceStop] Already finalized")
            return
        print("[ForceStop] Finalizing experiment...")
        try:
            self._exp_end_ts = time.time()
            self.active_run_seconds = self._compute_active_run_seconds()
        except Exception as e:
            print(f"[ForceStop] time calc error: {e}")
        # Stop timers
        try:
            if self.timer.isActive():
                self.timer.stop()
        except Exception:
            pass
        try:
            if self._ui_tick.isActive():
                self._ui_tick.stop()
        except Exception:
            pass
        # Close stim channels
        try:
            self.stop_stimulation()
        except Exception as e:
            print(f"[ForceStop] stop_stimulation error: {e}")
        # Persist data
        try:
            self.save_data()
        except Exception as e:
            print(f"[ForceStop] save_data error: {e}")
        # Emit finished
        try:
            self.finished.emit(self.return_values())
        except Exception as e:
            print(f"[ForceStop] finished emit error: {e}")
        self._finished = True
        print("[ForceStop] Done.")

    def start_main_loop(self) -> None:
        self.timer.setInterval(10)  # Set the timer interval to 10 ms

        # mark start time before starting timer
        self._exp_start_ts = time.time()
        self._exp_end_ts = None

        # clear pause state and start ticking
        self._paused = False
        self._pause_started_at = None
        self._total_paused_duration = 0.0

        # start control loop
        self.timer.start()

        # start UI tick ONCE
        try:
            self._emit_active_run_seconds()
            if not self._ui_tick.isActive():
                self._ui_tick.start()
        except Exception:
            pass

        # Start continuous stimulation if enabled
        if self.do_continuous_stimulation and self.stimulator_connection is not None:
            channel = self.channels["continuous"]
            print(f"Activating continuous stimulation on channel {channel}")
            self.ramp_activate_output(channel)
        # Start the global 10s ramp so closed-loop updates are ramped for the first 10s
        try:
            start_ramp()
        except Exception:
            pass

    def safe_main_loop_iteration(self) -> None:
        try:
            self.main_loop_iteration()
        except Exception as e:
            try:
                if self._ui_tick.isActive():
                    self._ui_tick.stop()
            except Exception:
                pass
            self.timer.stop()
            self.stop_stimulation()
            self.error.emit(e)

    def main_loop_iteration(self) -> None:
        if self.stop_main_event.is_set():
            # mark end time just before saving
            self._exp_end_ts = time.time()
            try:
                if self._ui_tick.isActive():
                    self._ui_tick.stop()
            except Exception:
                pass
            self.timer.stop()
            self.stop_stimulation()
            self.save_data()
            self.finished.emit(self.return_values())
            self._finished = True
            del self
            return

        if self._paused:
            return

        self.update_sensors()
        self.phase_detection()
        self.update_closed_loop()
        # update ramp (non-blocking)
        self._update_continuous_ramp()
        self.stimulate()

    def activate_hv(self, channel):
        if self.stimulator_connection is None:
            return
        # Activate High Voltage
        SetSingleChanState(self.stimulator_connection, channel, 1, 1, 0)

    def activate_output(self, channel):
        if self.stimulator_connection is None:
            return
        # Activate Output
        SetSingleChanState(self.stimulator_connection, channel, 1, 1, 1)

    def ramp_activate_output(self, channel):
        if self.stimulator_connection is None:
            return
        #start timer
        self._continuous_ramp_channel = channel
        self._continuous_ramp_start = time.monotonic()
        self._continuous_ramp_active = True
        self._continuous_last_level = None
        # ensure HV on & initial output on
        SetSingleChanState(self.stimulator_connection, channel, 1, 1, 1)
        self._update_continuous_ramp()

    def _update_continuous_ramp(self):
        """Advance ramp if active; called every timer tick."""
        if not self._continuous_ramp_active:
            return
        if self._continuous_ramp_channel is None or self.stimulator_connection is None:
            return
        elapsed = time.monotonic() - self._continuous_ramp_start
        if elapsed >= 10.0:
            level = 1.0
            self._continuous_ramp_active = False
        elif elapsed < 2:
            level = 0.5
        elif elapsed < 4:
            level = 0.6
        elif elapsed < 6:
            level = 0.7
        elif elapsed < 8:
            level = 0.8
        else:
            level = 0.9
        if level != self._continuous_last_level:
            try:
                # update current target
                self.stim_param.set_ramp_current_of_channel_from_target(
                    self.stimulator_connection, "continuous", level
                )
                # keep output active
                SetSingleChanState(self.stimulator_connection, self._continuous_ramp_channel, 1, 1, 1)
                self._continuous_last_level = level
            except Exception:
                pass

    def deactivate_output(self, channel):
        # Turn output OFF while keeping HV ON
        if self.stimulator_connection is None:
            return
        SetSingleChanState(self.stimulator_connection, channel, 1, 1, 0)
    # ---------------------------------------------------------------------
    # Pause / Resume
    # ---------------------------------------------------------------------
    def pause(self):
        """Pause real-time loop, ensure outputs are OFF, and drop any queued data from all LSL inlets."""
        if self._paused:
            return
        self._paused = True
        self._pause_started_at = time.time()
        try:
            self.timer.stop()
        except Exception:
            pass
        # STOP emitting active time while paused
        try:
            if self._ui_tick.isActive():
                self._ui_tick.stop()
        except Exception:
            pass
        try:
            if self.stimulator_connection is not None:
                for ch in set(self.channels.values()):
                    try:
                        self.deactivate_output(ch)
                    except Exception:
                        pass
        except Exception:
            pass

        # freeze ramp (will resume timing adjustment)
        if self._continuous_ramp_active and self._continuous_ramp_start is not None:
            # store remaining time
            self._continuous_ramp_remaining = max(0.0, 10.0 - (time.monotonic() - self._continuous_ramp_start))
        # stop the global ramp state on pause
        try:
            stop_ramp()
        except Exception:
            pass
        # Discard any currently queued samples so nothing from the pause gets processed
        try:
            self._drain_all_inlets()
        except Exception:
            pass

    def resume(self):
        """Resume real-time loop; discard backlog first so we resume from 'now'."""
        if not self._paused:
            return
        now = time.time()
        if self._pause_started_at is not None:
            self._total_paused_duration += (now - self._pause_started_at)
        self._pause_started_at = None
        self._paused = False

        # Drop all samples accumulated during pause (avoid catch-up)
        try:
            self._drain_all_inlets()
        except Exception:
            pass

        # If continuous stimulation is used, reactivate its output
        try:
            if self.do_continuous_stimulation and self.stimulator_connection is not None:
                ch = self.channels.get("continuous")
                if ch is not None:
                    self.ramp_activate_output(ch)
        except Exception:
            pass

        try:
            if not self.timer.isActive():
                self.timer.start()
        except Exception:
            pass

        # restart the global 10s ramp after resume
        try:
            start_ramp()
        except Exception:
            pass
        # RESTART active time emission only once
        try:
            if not self._ui_tick.isActive():
                self._ui_tick.start()
        except Exception:
            pass

        if getattr(self, "_continuous_ramp_remaining", None) is not None:
            if self._continuous_ramp_remaining > 0:
                self._continuous_ramp_start = time.monotonic() - (10.0 - self._continuous_ramp_remaining)
            self._continuous_ramp_remaining = None

    # ---------------- Active time helper ----------------
    def _compute_active_run_seconds(self) -> float:
        if self._exp_start_ts is None:
            return 0.0
        end = self._exp_end_ts or time.time()
        paused = self._total_paused_duration
        if self._paused and self._pause_started_at is not None:
            paused += (time.time() - self._pause_started_at)
        return max(0.0, end - self._exp_start_ts - paused)

    def _emit_active_run_seconds(self):
        try:
            self.active_run_seconds_changed.emit(float(self._compute_active_run_seconds()))
        except Exception:
            pass

    # ---------------------------------------------------------------------
    # Helpers to drain LSL queues on pause/resume
    # ---------------------------------------------------------------------
    def _iter_inlets(self):
        """Yield all StreamInlet-like objects used by any FSM in this stimulator."""
        seen = set()
        for _name, obj in self.__dict__.items():
            try:
                inlet = getattr(obj, "inlet", None)
            except Exception:
                inlet = None
            if inlet is not None and hasattr(inlet, "pull_chunk"):
                if id(inlet) not in seen:
                    seen.add(id(inlet))
                    yield inlet

    def _drain_inlet(self, inlet, max_loops: int = 200):
        """Read-and-discard until the inlet is empty (observed empty twice)."""
        empty_hits = 0
        for _ in range(max_loops):
            try:
                _samples, ts = inlet.pull_chunk(timeout=0.0, max_samples=4096)
            except Exception:
                break
            if not ts:
                empty_hits += 1
                if empty_hits >= 2:
                    break
                # brief sleep to let producer push a bit more; avoids tight loop
                try:
                    time.sleep(0.01)
                except Exception:
                    pass
            else:
                empty_hits = 0  # got data; keep draining

    def _drain_all_inlets(self):
        for inlet in self._iter_inlets():
            self._drain_inlet(inlet)

    # ---------------------------------------------------------------------
    # Private methods
    # ---------------------------------------------------------------------
    def __connect_to_stimulator(self):
        # Return if the stimulator connection is already established
        if self.stimulator_connection:
            return
        # Establish a connection with the stimulator
        self.stimulator_connection = open_serial_port(COM_PORT, BAUDRATE)
        if not self.stimulator_connection:
            raise RuntimeError("Connection to the stimulator failed")

    def __prepare_channels_for_stimulation(self):
        try:
            StimulatorParameters.close_all_channels(self.stimulator_connection)
            for channel in self.channels.values():
                # Activate the high voltage of the channel
                self.activate_hv(channel)

                # Send the waveform parameters to the channel
                self.__set_channels_debug(channel)

        except Exception as e:
            print("Error {e} detected or user interruption. Shutting down all channels...")
            StimulatorParameters.close_all_channels(self.stimulator_connection)
            self.error.emit(e)  # This doesn't do anything as it in the constructor and thus not connected yet

    # This function addresses a limitation in the stimulator's firmware, where stimulation parameters must be set
    # even after enabling the channel. The time.sleep is necessary for this operation (if the sleep duration is less
    # than 0.05 seconds, the parameter setting may occasionally fail). This function ensures that the stimulation
    # parameters are correctly applied.
    def __set_channels_debug(self, channel):
        mode = 0  # 0 for continuous stimulation, 1 for single shot
        for _ in range(3):
            self.stim_param.set_all_param_of_channel(self.stimulator_connection, channel, mode)
            self.stim_param.set_all_param_of_channel(self.stimulator_connection, channel, mode)
            self.stim_param.set_all_param_of_channel(self.stimulator_connection, channel, mode)
            time.sleep(0.5)

    def _resolve_streaminlet(self, stream_name: str):
        # Resolve the stream by its name
        stream = resolve_byprop("name", stream_name, timeout=TIMEOUT)
        if not stream:
            raise RuntimeError(f"No {stream_name} stream found")
        return StreamInlet(stream[0])

    # --- helper to attach experiment meta to saved files ---
    def _experiment_meta(self) -> dict:
        start_ts = self._exp_start_ts
        end_ts = self._exp_end_ts if self._exp_end_ts is not None else time.time()
        duration_s = end_ts - start_ts if (start_ts is not None and end_ts is not None) else None

        def to_iso(ts: float | None) -> str | None:
            return datetime.fromtimestamp(ts).isoformat(timespec="seconds") if ts is not None else None

        return {
            "experiment_start_unix": start_ts,
            "experiment_end_unix": end_ts,
            "experiment_start_iso": to_iso(start_ts),
            "experiment_end_iso": to_iso(end_ts),
            "experiment_duration_s": duration_s,
        }

############################################################################
""" Class in case of no gait detection, and no stimulation """
############################################################################

class NoStimulation(StimulationBasic):
    """This class is used when nothing should be done and is more used for testing purposes."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Debug
        self.current = True

    @override
    def phase_detection(self):
        # No phase detection
        pass

    @override
    def update_sensors(self):
        # No phase detection
        pass

    @override
    def update_closed_loop(self):
        # No closed loop update
        pass

    @override
    def stimulate(self):
        # No stimulation
        pass

    @override
    def save_data(self):
        # Just save zero data to the file (to have a timestamp of the experiment)
        data_to_save = {
            **self._experiment_meta(), # time information
            "data": []
        }
        # Save the dictionary to a single file
        try:
            with open(
                self.save_path,
                "wb",
            ) as f:
                pickle.dump(data_to_save, f)
        except FileNotFoundError:
            print("Data not saved, no valid path provided")
            return

        print("Saving completed")

    @override
    def return_values(self):
        # No data to return
        return None

############################################################################
""" Class for gait detection and stimulation with FSR """
############################################################################

class StimulationFSR(StimulationBasic):
    # New per-leg FSR step signals
    fsr_left_step_count_changed = Signal(int)
    fsr_right_step_count_changed = Signal(int)

    # New per-leg FSR phase signals (emit Phase value as int)
    fsr_left_phase_changed = Signal(int)
    fsr_right_phase_changed = Signal(int)

    def __init__(self, **kwargs):
        self.method = kwargs.get("method_fsr", "Method 1 - FSR")
        self.gait_model= kwargs.get("gait_model", "Gait Model with Distal")
        self.personalized_gait_model: bool = kwargs.get("personalized_gait_model", False)
        self.terminal_stance_divider=kwargs.get("terminal_stance_divider", 4)

        super().__init__(**kwargs)

        if self.method == "Method 1 - FSR":
            self.threshold_left: int = kwargs.get("threshold_left", 20)
            self.threshold_right: int = kwargs.get("threshold_right", 20)

            # Instantiate the fsm for the FSR
            self.right_fsr_fsm = FSRGaitFSM(self._resolve_streaminlet("FSR_Right"), self.threshold_right)
            self.left_fsr_fsm = FSRGaitFSM(self._resolve_streaminlet("FSR_Left"), self.threshold_left)

        else:  # method 2
            self.threshold_left: int = kwargs.get("threshold_left", 5)
            self.threshold_right: int = kwargs.get("threshold_right", 5)

            # Instantiate the fsm for the FSR
            self.right_fsr_fsm = FSRGaitFSM_2(self._resolve_streaminlet("FSR_Right"), self.threshold_right, self.terminal_stance_divider)
            self.left_fsr_fsm = FSRGaitFSM_2(self._resolve_streaminlet("FSR_Left"), self.threshold_left, self.terminal_stance_divider)

        if self.right_fsr_fsm is None:
            self.right_fsr_fsm = FSRGaitFSM_DUMMY()

        if self.left_fsr_fsm is None:
            self.left_fsr_fsm = FSRGaitFSM_DUMMY()

        self.right_fsr_fsm.steps_changed.connect(self.__on_fsr_leg_steps_changed)
        self.left_fsr_fsm.steps_changed.connect(self.__on_fsr_leg_steps_changed)

        # NEW: forward per-leg FSR counts
        self.right_fsr_fsm.steps_changed.connect(
            lambda _c: self.fsr_right_step_count_changed.emit(int(self.right_fsr_fsm.get_step_count()))
        )
        self.left_fsr_fsm.steps_changed.connect(
            lambda _c: self.fsr_left_step_count_changed.emit(int(self.left_fsr_fsm.get_step_count()))
        )

        # forward FSR phase changes to top-level signals
        try:
            self.right_fsr_fsm.phase_changed.connect(lambda v: self.fsr_right_phase_changed.emit(int(v)))
            self.left_fsr_fsm.phase_changed.connect(lambda v: self.fsr_left_phase_changed.emit(int(v)))
        except Exception:
            pass

    @override
    def phase_detection(self):
        if self.do_phase_detection:
            self.right_fsr_fsm.fsr_phase_detection()
            self.left_fsr_fsm.fsr_phase_detection()
            #self.fsr_fsm.fsr_phase_detection()

        #if self.do_subphase_detection:
            # TODO implement subphase detection with FSR
            #pass

    @override
    def update_sensors(self):
        # Update the FSR data
        self.right_fsr_fsm.update_fsr()
        self.left_fsr_fsm.update_fsr()

        #self.fsr_fsm.update_fsr()

    @override
    def update_closed_loop(self):
        # No closed loop update for FSR
        pass

    @override
    def stimulate(self):
        if self.stimulator_connection is None:
            return

        if self.do_phase_detection:
            # Stimulation phases
            if right_fsr_fsm is None:
             right_fsr_fsm = FSRGaitFSM_DUMMY()

            if left_fsr_fsm is None:
             left_fsr_fsm = FSRGaitFSM_DUMMY()

            if not self.__check_for_unknown_phases():
               open_stimulation_channel_phases_fsr(
                    self.stimulator_connection,
                    self.channels,
                    right_leg=self.right_fsr_fsm,
                    left_leg=self.left_fsr_fsm,
                    stim_param=self.stim_param,
                    gait_model=self.gait_model,
                    personalized_gait_model= self.personalized_gait_model,
                    method_fsr= self.method,
                    _total_paused_duration=self._total_paused_duration
                )

        elif self.do_subphase_detection:
            # Stimulation subphases
            # TODO implement stimulation subphases with FSR
            pass

    @override
    def save_data(self):
        # TODO implement complete method for data saving for FSR
        data_to_save = {
            **self._experiment_meta(), # time information

            "fsr_data_ff_left": self.left_fsr_fsm.data_ff_offline,
            "fsr_data_mf_left": self.left_fsr_fsm.data_mf_offline,
            "fsr_data_bf_left": self.left_fsr_fsm.data_bf_offline,
            "fsr_cop_x_left": self.left_fsr_fsm.data_cop_x_offline,
            "fsr_cop_y_left": self.left_fsr_fsm.data_cop_y_offline,
            "fsr_timestamps_left": self.left_fsr_fsm.timestamps_offline,
            "fsr_heel_strike_left": self.left_fsr_fsm.heel_strike,
            "fsr_mid_stance_left": self.left_fsr_fsm.mid_stance,
            "fsr_toe_off_left": self.left_fsr_fsm.toe_off,
            "fsr_heel_strike_timestamps_left": self.left_fsr_fsm.heel_strike_timestamps,
            "fsr_mid_stance_timestamps_left": self.left_fsr_fsm.mid_stance_timestamps,
            "fsr_toe_off_timestamps_left": self.left_fsr_fsm.toe_off_timestamps,

            "fsr_data_ff_right": self.right_fsr_fsm.data_ff_offline,
            "fsr_data_mf_right": self.right_fsr_fsm.data_mf_offline,
            "fsr_data_bf_right": self.right_fsr_fsm.data_bf_offline,
            "fsr_cop_x_right": self.right_fsr_fsm.data_cop_x_offline,
            "fsr_cop_y_right": self.right_fsr_fsm.data_cop_y_offline,
            "fsr_timestamps_right": self.right_fsr_fsm.timestamps_offline,
            "fsr_heel_strike_right": self.right_fsr_fsm.heel_strike,
            "fsr_mid_stance_right": self.right_fsr_fsm.mid_stance,
            "fsr_toe_off_right": self.right_fsr_fsm.toe_off,
            "fsr_heel_strike_timestamps_right": self.right_fsr_fsm.heel_strike_timestamps,
            "fsr_mid_stance_timestamps_right": self.right_fsr_fsm.mid_stance_timestamps,
            "fsr_toe_off_timestamps_right": self.right_fsr_fsm.toe_off_timestamps,
            # FSR phase timestamps and counters (this class uses *_fsr_fsm — the
            # *_fsr_imu_fsm attribute only exists in StimulationFSRandIMU).
            "fsr_phase_timestamps_left":  getattr(self.left_fsr_fsm,  "phase_timestamps", None),
            "fsr_phase_timestamps_right": getattr(self.right_fsr_fsm, "phase_timestamps", None),
            "fsr_phase_counters_left":    getattr(self.left_fsr_fsm,  "phase_counters",   None),
            "fsr_phase_counters_right":   getattr(self.right_fsr_fsm, "phase_counters",   None),

            # FSR Method 2 durations (only when using Method 2), safe fallback to empty list
            "fsr_loading_response_durations_right": (
                self.right_fsr_fsm.FSR2_loading_response_durations
                if getattr(self, "method_fsr", "") == "Method 2 - FSR" and getattr(self.right_fsr_fsm, "FSR2_loading_response_durations", None) is not None
                else []
            ),
            "fsr_loading_response_durations_left": (
                self.left_fsr_fsm.FSR2_loading_response_durations
                if getattr(self, "method_fsr", "") == "Method 2 - FSR" and getattr(self.left_fsr_fsm, "FSR2_loading_response_durations", None) is not None
                else []
            ),
            "fsr_mid_stance_durations_right": (
                self.right_fsr_fsm.FSR2_mid_stance_durations
                if getattr(self, "method_fsr", "") == "Method 2 - FSR" and getattr(self.right_fsr_fsm, "FSR2_mid_stance_durations", None) is not None
                else []
            ),
            "fsr_mid_stance_durations_left": (
                self.left_fsr_fsm.FSR2_mid_stance_durations
                if getattr(self, "method_fsr", "") == "Method 2 - FSR" and getattr(self.left_fsr_fsm, "FSR2_mid_stance_durations", None) is not None
                else []
            ),
            "fsr_stance_durations_right": (
                self.right_fsr_fsm.FSR2_stance_durations
                if getattr(self, "method_fsr", "") == "Method 2 - FSR" and getattr(self.right_fsr_fsm, "FSR2_stance_durations", None) is not None
                else []
            ),
            "fsr_stance_durations_left": (
                self.left_fsr_fsm.FSR2_stance_durations
                if getattr(self, "method_fsr", "") == "Method 2 - FSR" and getattr(self.left_fsr_fsm, "FSR2_stance_durations", None) is not None
                else []
            ),

            #add active run time
            "active_run_seconds": getattr(self, "active_run_seconds", self._compute_active_run_seconds())
        }
        # Save the dictionary to a single file
        try:
            with open(
                self.save_path,
                "wb",
            ) as f:
                pickle.dump(data_to_save, f)
        except FileNotFoundError:
            print("Data not saved, no valid path provided")
            return

        print("Saving completed")
        export_xlsx_log(self.save_path, data_to_save)

    @override
    def __check_for_unknown_phases(self):
        # Check if the current phase is unknown for both legs
        return self.right_fsr_fsm.is_phase_unknown() and self.left_fsr_fsm.is_phase_unknown()

    @override
    def return_values(self):
        # TODO implement return values for FSR
        pass

    def __on_fsr_leg_steps_changed(self):
        total = 0
        try:
            if self.right_fsr_fsm:
                total += self.right_fsr_fsm.get_step_count()
            if self.left_fsr_fsm:
                total += self.left_fsr_fsm.get_step_count()
        except Exception:
            pass
        self.step_count_changed.emit(int(total))

############################################################################
""" Class for gait detection and stimulation with IMU """
############################################################################

class StimulationIMUs(StimulationBasic):
    # New per-leg IMU step signals
    imu_left_step_count_changed = Signal(int)
    imu_right_step_count_changed = Signal(int)
    # New per-leg IMU subphase signals (emit Phase value as int)
    imu_left_phase_changed = Signal(int)
    imu_right_phase_changed = Signal(int)

    def __init__(self, **kwargs):
        self.method = kwargs.get("method_imu", "Method 1 - IMU")  # "Method 1" | "Method 2" | "Both"
        self.speed  = kwargs.get("walking_speed", 0.4)
        self.gait_model= kwargs.get("gait_model", "Gait Model with Distal")
        self.personalized_gait_model: bool = kwargs.get("personalized_gait_model", False)
        self.terminal_stance_divider=kwargs.get("terminal_stance_divider", 4)

        super().__init__(**kwargs)

        # Map methods to FSM classes and attribute suffixes
        fsm_by_method = {
            "Method 1 - IMU": (IMUGaitFSM,  "fsm1"),
            "Method 2 - IMU": (IMUGaitFSM_2, "fsm2"),
        }
        if self.method == "Both":
            methods_to_use = ("Method 1 - IMU", "Method 2 - IMU")
        elif self.method in fsm_by_method:
            methods_to_use = (self.method,)
        else:
            raise ValueError(f"Unknown method: {self.method!r}")

        # Pre-create all attributes as None so later code can safely check them
        for side in ("right", "left"):
            for placement in ("shank", "foot", "thigh"):
                setattr(self, f"{side}_leg_{placement}_fsm1", None)
                setattr(self, f"{side}_leg_{placement}_fsm2", None)
        # Single shared pelvis FSM (replaces the previous left/right trunk FSMs).
        self.pelvis_fsm1 = None
        self.pelvis_fsm2 = None

        # Try to connect both SHANK and FOOT for each leg; if found, instantiate the requested method(s)
        for side_label in ("Right", "Left"):
            side = side_label.lower()
            for placement_label in ("Shank", "Foot", "Thigh"):
                placement = placement_label.lower()
                stream_name = f"{side_label} {placement_label}"
                inlet = None
                try:
                    inlet = self._resolve_streaminlet(stream_name)
                except Exception as e:
                    # silently skip; attribute remains None
                    inlet = None

                if inlet is None:
                    continue

                for m in methods_to_use:
                    try:
                        inlet_m = self._resolve_streaminlet(stream_name)  # <- get a new inlet each time
                    except Exception:
                        inlet_m = None
                    if inlet_m is None:
                        continue

                    fsm_cls, suffix = fsm_by_method[m]
                    attr = f"{side}_leg_{placement}_{suffix}"
                    try:
                        # instantiate and store the FSM

                        fsm = fsm_cls(inlet=inlet_m, speed=self.speed, terminal_stance_divider=self.terminal_stance_divider,  FES=self.FES,  both_imu_methods=(self.method=="Both"), do_closed_loop=self.do_closed_loop)
                        setattr(self, attr, fsm)

                        # Forward fsm phase updates dynamically (only for shank/foot)
                        try:
                            if placement in ("shank", "foot"):
                                if hasattr(fsm, "phase_changed"):
                                    target_sig = getattr(self, f"imu_{side}_phase_changed", None)
                                    if target_sig is not None:
                                        fsm.phase_changed.connect(lambda v, _sig=target_sig: _sig.emit(int(v)))
                        except Exception:
                            pass

                    except Exception:
                        print("debug: did not create gait fsms")
                        pass

        # Single pelvis stream (shared between both hips). Try "Pelvis", fallback to "Custom 1".
        for pelvis_stream_name in ("Pelvis", "Custom 1"):
            try:
                inlet_check = self._resolve_streaminlet(pelvis_stream_name)
            except Exception:
                inlet_check = None
            if inlet_check is None:
                continue
            for m in methods_to_use:
                try:
                    inlet_m = self._resolve_streaminlet(pelvis_stream_name)
                except Exception:
                    inlet_m = None
                if inlet_m is None:
                    continue
                fsm_cls, suffix = fsm_by_method[m]
                try:
                    fsm = fsm_cls(inlet=inlet_m, speed=self.speed, terminal_stance_divider=self.terminal_stance_divider, FES=self.FES, both_imu_methods=(self.method=="Both"), do_closed_loop=self.do_closed_loop)
                    setattr(self, f"pelvis_{suffix}", fsm)
                except Exception:
                    print("debug: did not create pelvis fsm")
            break  # bound to the first stream name that resolves

        # Choose which IMU stream drives the frontend step counters (prefer Foot; fallback to Shank)
        self._chosen_step_fsm = {"left": None, "right": None}
        self._wire_preferred_step_signals()

        self.left_knee_rom  = ROM(kwargs.get("offset_left",        0.0), kwargs.get("scale_left",  1.0))
        self.right_knee_rom = ROM(kwargs.get("offset_right",       0.0), kwargs.get("scale_right", 1.0))
        self.left_ankle_rom = ROM(kwargs.get("offset_left_ankle",  0.0), kwargs.get("scale_left",  1.0))
        self.right_ankle_rom= ROM(kwargs.get("offset_right_ankle", 0.0), kwargs.get("scale_right", 1.0))
        self.left_hip_rom   = ROM(kwargs.get("offset_left_hip",    0.0), kwargs.get("scale_left",  1.0))
        self.right_hip_rom  = ROM(kwargs.get("offset_right_hip",   0.0), kwargs.get("scale_right", 1.0))

        # Wire the auto-detected per-side ankle axes into the ROM so the saved
        # `imu_*_ankle_angles` (in `.pkl` / `.xlsx`) match the live calibrator
        # plots instead of falling back to the hardcoded X-axis assumption.
        self.left_ankle_rom.set_ankle_axes(
            kwargs.get("ankle_left_shank_axis",  'X'),
            kwargs.get("ankle_left_foot_axis",   'X'),
        )
        self.right_ankle_rom.set_ankle_axes(
            kwargs.get("ankle_right_shank_axis", 'X'),
            kwargs.get("ankle_right_foot_axis",  'X'),
        )

        # Set ankle reference quaternions + hinge axis for the SVD/swing-twist
        # algorithm. Previously the hinge axis was dropped on the floor here
        # -> ROM saved hinge_axis=None -> the saved .pkl appeared uncalibrated
        # even when the user had pressed both calibration buttons.
        l_qs   = kwargs.get("ankle_left_qshank_ref");  l_qf   = kwargs.get("ankle_left_qfoot_ref")
        r_qs   = kwargs.get("ankle_right_qshank_ref"); r_qf   = kwargs.get("ankle_right_qfoot_ref")
        l_ahg  = kwargs.get("ankle_left_hinge_axis");  r_ahg  = kwargs.get("ankle_right_hinge_axis")
        if l_qs is not None and l_qf is not None:
            self.left_ankle_rom.set_ankle_reference(l_qs, l_qf, l_ahg)
        if r_qs is not None and r_qf is not None:
            self.right_ankle_rom.set_ankle_reference(r_qs, r_qf, r_ahg)

        # Knee functional sagittal-hinge calibration (mirror of ankle).
        l_kth = kwargs.get("knee_left_qthigh_ref");  l_ksh = kwargs.get("knee_left_qshank_ref");  l_khg = kwargs.get("knee_left_hinge_axis")
        r_kth = kwargs.get("knee_right_qthigh_ref"); r_ksh = kwargs.get("knee_right_qshank_ref"); r_khg = kwargs.get("knee_right_hinge_axis")
        if l_kth is not None and l_ksh is not None:
            self.left_knee_rom.set_knee_reference(l_kth, l_ksh, l_khg)
        if r_kth is not None and r_ksh is not None:
            self.right_knee_rom.set_knee_reference(r_kth, r_ksh, r_khg)

        # Hip functional sagittal-hinge calibration.
        l_hpe = kwargs.get("hip_left_qpelvis_ref");  l_hth = kwargs.get("hip_left_qthigh_ref");  l_hhg = kwargs.get("hip_left_hinge_axis")
        r_hpe = kwargs.get("hip_right_qpelvis_ref"); r_hth = kwargs.get("hip_right_qthigh_ref"); r_hhg = kwargs.get("hip_right_hinge_axis")
        if l_hpe is not None and l_hth is not None:
            self.left_hip_rom.set_hip_reference(l_hpe, l_hth, l_hhg)
        if r_hpe is not None and r_hth is not None:
            self.right_hip_rom.set_hip_reference(r_hpe, r_hth, r_hhg)

        dt = self.timer.interval() / 1000.0  # Convert milliseconds to seconds

        # Initialize the PI controllers for the legs
        self.left_pi_controller = PIController(
            kp=kwargs["left_knee_pi_params"].get("kp", 0.1),
            ki=kwargs["left_knee_pi_params"].get("ki", 0.01),
            dt=dt,
            target_extension=kwargs.get("left_knee_angle_range", [10, 60])[0],
            target_flexion=kwargs.get("left_knee_angle_range", [10, 60])[1],
        )
        self.right_pi_controller = PIController(
            kp=kwargs["right_knee_pi_params"].get("kp", 0.1),
            ki=kwargs["right_knee_pi_params"].get("ki", 0.01),
            dt=dt,
            target_extension=kwargs.get("right_knee_angle_range", [10, 60])[0],
            target_flexion=kwargs.get("right_knee_angle_range", [10, 60])[1],
        )

    def update_offsets(self,
                       knee_left:   float, knee_right:   float,
                       ankle_left:  float, ankle_right:  float,
                       ankle_left_qshank_ref  = None, ankle_left_qfoot_ref   = None,
                       ankle_right_qshank_ref = None, ankle_right_qfoot_ref  = None,
                       ankle_left_hinge_axis  = None, ankle_right_hinge_axis = None) -> None:
        """Hot-update the ROM calibration offsets while the test is running.

        Called whenever 'Calibrate Offsets' is pressed (even mid-test) so that
        the ROM objects immediately reflect the new neutral-pose offset without
        needing to restart the test.

        When reference quaternions are provided, the ankle ROMs switch to the
        stable relative-quaternion algorithm (set_ankle_reference), which is
        more robust than numeric offset subtraction.
        """
        self.left_knee_rom.set_offset(knee_left)
        self.right_knee_rom.set_offset(knee_right)
        # Ankle: prefer reference-quaternion path
        if ankle_left_qshank_ref is not None and ankle_left_qfoot_ref is not None:
            self.left_ankle_rom.set_ankle_reference(ankle_left_qshank_ref, ankle_left_qfoot_ref, ankle_left_hinge_axis)
        else:
            self.left_ankle_rom.set_offset(ankle_left)
        if ankle_right_qshank_ref is not None and ankle_right_qfoot_ref is not None:
            self.right_ankle_rom.set_ankle_reference(ankle_right_qshank_ref, ankle_right_qfoot_ref, ankle_right_hinge_axis)
        else:
            self.right_ankle_rom.set_offset(ankle_right)

    def _iter_pairs(self):
        """
        Yield tuples: (placement, method_suffix, right_fsm, left_fsm)
        placement: 'shank' | 'foot'
        method_suffix: 'fsm1' | 'fsm2'
        Only yields when both right and left FSMs exist.
        """
        for placement in ("shank", "foot" , "thigh"):
            for suffix in ("fsm1", "fsm2"):
                r = getattr(self, f"right_leg_{placement}_{suffix}", None)
                l = getattr(self, f"left_leg_{placement}_{suffix}", None)
                if r is not None and l is not None:
                    yield placement, suffix, r, l

    def _both_phases_known(self, right_fsm, left_fsm) -> bool:
        return (not right_fsm.is_phase_unknown()) and (not left_fsm.is_phase_unknown())

    def _iter_all_fsms(self):
        """Yield every existing FSM instance (any side, any placement, any method).

        The pelvis sensor is side-less and yielded with side="pelvis", placement="pelvis"
        so callers that build keys from (side, placement) get a stable identifier.
        """
        for placement in ("shank", "foot", "thigh"):
            for suffix in ("fsm1", "fsm2"):
                for side in ("right", "left"):
                    fsm = getattr(self, f"{side}_leg_{placement}_{suffix}", None)
                    if fsm is not None:
                        yield side, placement, suffix, fsm
        for suffix in ("fsm1", "fsm2"):
            fsm = getattr(self, f"pelvis_{suffix}", None)
            if fsm is not None:
                yield "pelvis", "pelvis", suffix, fsm

    # Preferred-step-counter selection and wiring
    def _get_preferred_fsm_for_side(self, side: str):
        # Priority: Foot Method1 -> Foot Method2 -> Shank Method1 -> Shank Method2
        for placement, suffix in (("foot", "fsm2"), ("foot", "fsm1"), ("shank", "fsm2"), ("shank", "fsm1")):
            fsm = getattr(self, f"{side}_leg_{placement}_{suffix}", None)
            print(fsm)
            if fsm is not None:
                return fsm
        return None

    def _wire_preferred_step_signals(self):
        # Reset is_preferred on all FSMs first
        for _side, _placement, _suffix, any_fsm in self._iter_all_fsms():
            any_fsm.is_preferred = False

        # Connect only the preferred IMU per side to frontend signals and total steps
        for side in ("left", "right"):
            fsm = self._get_preferred_fsm_for_side(side)
            self._chosen_step_fsm[side] = fsm
            if fsm is not None:
                fsm.is_preferred = True
            try:
                sig = getattr(self, f"imu_{side}_step_count_changed")
            except Exception:
                sig = None
            if fsm is not None and sig is not None:
                # Per-leg frontend update from the chosen IMU only
                fsm.steps_changed.connect(lambda _c, _f=fsm, _sig=sig: _sig.emit(int(_f.get_step_count())))
                # Recompute and emit total from chosen pair
                fsm.steps_changed.connect(self.__on_imu_leg_steps_changed)

    def __on_imu_leg_steps_changed(self, *_):
        total = 0
        for side in ("left", "right"):
            fsm = self._chosen_step_fsm.get(side)
            if fsm is not None:
                try:
                    total += int(fsm.get_step_count())
                except Exception:
                    pass
        self.step_count_changed.emit(int(total))
    @override
    def update_sensors(self):
        # Pull raw samples from every IMU FSM, including the pelvis FSM —
        # the pelvis quaternions feed hip ROM computation in update_closed_loop.
        for _side, _placement, _suffix, fsm in self._iter_all_fsms():
            fsm.update_imu()

    @override
    def phase_detection(self):
        # The pelvis sensor is a kinematic source only (hip angle reference); it
        # does NOT participate in gait-phase detection. Its IMUGaitFSM never
        # receives stream-name-based threshold initialization (TO_threshold /
        # HS_threshold are only set for shank/foot/thigh streams), so calling
        # imu_phase_detection on it raises AttributeError. Skip it.
        for side, _placement, _suffix, fsm in self._iter_all_fsms():
            if side == "pelvis":
                continue
            fsm.imu_phase_detection()

    # Helper to get the first available FSM for a side
    def get_first_available_fsm(self, side: str):
        for placement, suffix in PRIORITY:
            fsm = getattr(self, f"{side}_leg_{placement}_{suffix}", None)
            if fsm is not None and not fsm.is_phase_unknown():
                return fsm
        return None

    @override
    def stimulate(self):
        if self.stimulator_connection is None:
            return
        if not getattr(self, "do_phase_detection", True):
            return  # nothing to do

        # Get available FSMs for each side independently
        right_fsm = self.get_first_available_fsm(side="right")
        if right_fsm is None:
            right_fsm = IMUGaitFSM_DUMMY()
        left_fsm = self.get_first_available_fsm(side="left")
        if left_fsm is None:
            left_fsm = IMUGaitFSM_DUMMY()

        # If at least one side is available, stimulate accordingly
        if right_fsm or left_fsm:
            open_stimulation_channel_phases_imu(
                self.stimulator_connection,
                self.channels,
                right_leg=right_fsm,
                left_leg=left_fsm,
                stim_param=self.stim_param,
                gait_model=self.gait_model,
                personalized_gait_model=self.personalized_gait_model,
               _total_paused_duration=self._total_paused_duration
            )

    @override
    def save_data(self):
        def rom_block(gait_fsm):
            return {
                "gx": gait_fsm.data_gx_rom,
                "gy": gait_fsm.data_gy_rom,
                "gz": gait_fsm.data_gz_rom,
                "accx": gait_fsm.data_accx_rom,
                "accy": gait_fsm.data_accy_rom,
                "accz": gait_fsm.data_accz_rom,
                "qw" : gait_fsm.data_quatw_rom,
                "qx" : gait_fsm.data_quatx_rom,
                "qy" : gait_fsm.data_quaty_rom,
                "qz" : gait_fsm.data_quatz_rom,
                # "magx" : gait_fsm.data_magx_rom, we dont send magnetometer data :(
                # "magy" : gait_fsm.data_magy_rom,
                # "magz" : gait_fsm.data_magz_rom,
                "timestamps": gait_fsm.timestamps_rom,
            }

        # Create a dictionary to store all the data
        data_to_save = {
            **self._experiment_meta(),  # time information

            # stim info (single set shared across all)
            "imu_timestamps_stim_right": getattr(self.stim_param, "timestamps_stim_right", None),
            "imu_timestamps_stim_left":  getattr(self.stim_param, "timestamps_stim_left",  None),
            "imu_timestamps_de_stim_right": getattr(self.stim_param, "timestamps_de_stim_right", None),
            "imu_timestamps_de_stim_left":  getattr(self.stim_param, "timestamps_de_stim_left",  None),
            "imu_current_right":         getattr(self.stim_param, "stim_values_right",     None),
            "imu_current_left":          getattr(self.stim_param, "stim_values_left",      None),
            "imu_initial_currents": getattr(self.stim_param, "stim_currents", None),
            "imu_maximum_currents": getattr(self.stim_param, "max_stim_currents", None),
            "imu_pi_current_offset": getattr(self.stim_param, "pi_current_offset", None),
            # IMU data will be filled below
            "rom_data": {},
            # save walking speed used
            "walking_speed": getattr(self, "speed", None),
            #add active run time
            "active_run_seconds": getattr(self, "active_run_seconds", self._compute_active_run_seconds()),
            # --- add knee ROM + PI controller data ---
            "imu_left_knee_angles": getattr(self.left_knee_rom, "angles", None)[:, 1] if hasattr(self.left_knee_rom, "angles") else None,
            "imu_right_knee_angles": getattr(self.right_knee_rom, "angles", None)[:, 1] if hasattr(self.right_knee_rom, "angles") else None,
            "imu_left_knee_timestamps": getattr(self.left_knee_rom, "angles", None)[:, 0] if hasattr(self.left_knee_rom, "angles") else None,
            "imu_right_knee_timestamps": getattr(self.right_knee_rom, "angles", None)[:, 0] if hasattr(self.right_knee_rom, "angles") else None,
            # Temp saving of angle estimation method:
            "imu_left_knee_angles_algo2": getattr(self.left_knee_rom, "angles_algo2", None)[:, 1] if hasattr(self.left_knee_rom, "angles_algo2") else None,
            "imu_right_knee_angles_algo2": getattr(self.right_knee_rom, "angles_algo2", None)[:, 1] if hasattr(self.right_knee_rom, "angles_algo2") else None,
            "imu_left_knee_timestamps_algo2": getattr(self.left_knee_rom, "angles_algo2", None)[:, 0] if hasattr(self.left_knee_rom, "angles_algo2") else None,
            "imu_right_knee_timestamps_algo2": getattr(self.right_knee_rom, "angles_algo2", None)[:, 0] if hasattr(self.right_knee_rom, "angles_algo2") else None,

            # --- add ankle ROM data ---
            "imu_left_ankle_angles": getattr(self.left_ankle_rom, "angles", None)[:, 1] if hasattr(self.left_ankle_rom, "angles") else None,
            "imu_right_ankle_angles": getattr(self.right_ankle_rom, "angles", None)[:, 1] if hasattr(self.right_ankle_rom, "angles") else None,
            "imu_left_ankle_timestamps": getattr(self.left_ankle_rom, "angles", None)[:, 0] if hasattr(self.left_ankle_rom, "angles") else None,
            "imu_right_ankle_timestamps": getattr(self.right_ankle_rom, "angles", None)[:, 0] if hasattr(self.right_ankle_rom, "angles") else None,

            # --- add hip ROM data ---
            "imu_left_hip_angles": getattr(self.left_hip_rom, "angles", None)[:, 1] if hasattr(self.left_hip_rom, "angles") else None,
            "imu_right_hip_angles": getattr(self.right_hip_rom, "angles", None)[:, 1] if hasattr(self.right_hip_rom, "angles") else None,
            "imu_left_hip_timestamps": getattr(self.left_hip_rom, "angles", None)[:, 0] if hasattr(self.left_hip_rom, "angles") else None,
            "imu_right_hip_timestamps": getattr(self.right_hip_rom, "angles", None)[:, 0] if hasattr(self.right_hip_rom, "angles") else None,

            # --- ankle functional-calibration refs (for offline SVD/hinge reconstruction) ---
            "left_ankle_offset":      getattr(self.left_ankle_rom,  "offset",      0.0),
            "right_ankle_offset":     getattr(self.right_ankle_rom, "offset",      0.0),
            "left_ankle_qshank_ref":  getattr(self.left_ankle_rom,  "q_shank_ref", None),
            "left_ankle_qfoot_ref":   getattr(self.left_ankle_rom,  "q_foot_ref",  None),
            "left_ankle_hinge_axis":  getattr(self.left_ankle_rom,  "hinge_axis",  None),
            "left_ankle_shank_axis":  getattr(self.left_ankle_rom,  "shank_axis",  'X'),
            "left_ankle_foot_axis":   getattr(self.left_ankle_rom,  "foot_axis",   'X'),
            "right_ankle_qshank_ref": getattr(self.right_ankle_rom, "q_shank_ref", None),
            "right_ankle_qfoot_ref":  getattr(self.right_ankle_rom, "q_foot_ref",  None),
            "right_ankle_hinge_axis": getattr(self.right_ankle_rom, "hinge_axis",  None),
            "right_ankle_shank_axis": getattr(self.right_ankle_rom, "shank_axis",  'X'),
            "right_ankle_foot_axis":  getattr(self.right_ankle_rom, "foot_axis",   'X'),
            # --- knee / hip functional-calibration refs (mirror of ankle) ---
            "left_knee_qthigh_ref":   getattr(self.left_knee_rom,   "q_thigh_ref_knee", None),
            "left_knee_qshank_ref":   getattr(self.left_knee_rom,   "q_shank_ref_knee", None),
            "left_knee_hinge_axis":   getattr(self.left_knee_rom,   "knee_hinge_axis",  None),
            "right_knee_qthigh_ref":  getattr(self.right_knee_rom,  "q_thigh_ref_knee", None),
            "right_knee_qshank_ref":  getattr(self.right_knee_rom,  "q_shank_ref_knee", None),
            "right_knee_hinge_axis":  getattr(self.right_knee_rom,  "knee_hinge_axis",  None),
            "left_hip_qpelvis_ref":   getattr(self.left_hip_rom,    "q_pelvis_ref_hip", None),
            "left_hip_qthigh_ref":    getattr(self.left_hip_rom,    "q_thigh_ref_hip",  None),
            "left_hip_hinge_axis":    getattr(self.left_hip_rom,    "hip_hinge_axis",   None),
            "right_hip_qpelvis_ref":  getattr(self.right_hip_rom,   "q_pelvis_ref_hip", None),
            "right_hip_qthigh_ref":   getattr(self.right_hip_rom,   "q_thigh_ref_hip",  None),
            "right_hip_hinge_axis":   getattr(self.right_hip_rom,   "hip_hinge_axis",   None),

            "imu_left_pi_timestamps": getattr(self.left_pi_controller, "timestamps", None),
            "imu_right_pi_timestamps": getattr(self.right_pi_controller, "timestamps", None),
            "imu_left_pi_errors": getattr(self.left_pi_controller, "errors", None),
            "imu_right_pi_errors": getattr(self.right_pi_controller, "errors", None),
            "imu_left_pi_outputs": getattr(self.left_pi_controller, "outputs", None),
            "imu_right_pi_outputs": getattr(self.right_pi_controller, "outputs", None),
            "imu_target_change_left": getattr(self.left_pi_controller, "target_changes", None),
            "imu_target_change_right": getattr(self.right_pi_controller, "target_changes", None),
            "imu_left_Kp_value":   getattr(self.left_pi_controller, "kp", None),
            "imu_left_Ki_value":   getattr(self.left_pi_controller, "ki", None),
            "imu_right_Kp_value":   getattr(self.right_pi_controller, "kp", None),
            "imu_right_Ki_value":   getattr(self.right_pi_controller, "ki", None),
        }

        # Per FSM (side/placement/method) add phase timestamps and event timestamps; plus ROM
        for side, placement, suffix, fsm in self._iter_all_fsms():
            side_u = "right" if side == "right" else "left"  # keep explicit
            key_prefix = f"imu_{side_u}_{placement}_{suffix}"  # e.g., imu_right_shank_fsm1

            # Phase timestamps
            data_to_save[f"{key_prefix}_phase_timestamps"] = getattr(fsm, "phase_timestamps", None)
            # Phase counters
            data_to_save[f"{key_prefix}_phase_counters"] = getattr(fsm, "phase_counters", None)

            # Subphase timestamps (you said you don't use subphase now, but safe to store if present)
            sub_ts = getattr(fsm, "subphase_timestamps", None)
            if sub_ts is not None:
                data_to_save[f"{key_prefix}_subphase_timestamps"] = sub_ts

            # Events (guard for attributes that may not exist in your FSM variant)
            if hasattr(fsm, "heel_strike_peaks_timestamps"):
                data_to_save[f"{key_prefix}_heel_strike_peaks"] = fsm.heel_strike_peaks_timestamps
            if hasattr(fsm, "toe_off_peaks_timestamps"):
                data_to_save[f"{key_prefix}_toe_off_peaks"] = fsm.toe_off_peaks_timestamps
            # valleys were commented out in your class; only save if present
            if hasattr(fsm, "valleys_timestamps"):
                data_to_save[f"{key_prefix}_valleys"] = fsm.valleys_timestamps
            # save durations of Loading response
            if hasattr(fsm, "loading_response_durations"):
                data_to_save[f"{key_prefix}_loading_response_durations"] = fsm.loading_response_durations

            # save durations of mid-stance
            if hasattr(fsm, "mid_stance_durations"):
                data_to_save[f"{key_prefix}_mid_stance_durations"] = fsm.mid_stance_durations

            # save durations of stance
            if hasattr(fsm, "stance_durations"):
                data_to_save[f"{key_prefix}_stance_durations"] = fsm.stance_durations

            # ROM data bucket: rom_data[right_shank_fsm1] = {...}
            rom_key = f"{side_u}_{placement}_{suffix}"
            data_to_save["rom_data"][rom_key] = rom_block(fsm)

        # Save the dictionary to a single file
        try:
            with open(self.save_path, "wb") as f:
                pickle.dump(data_to_save, f)
            print("Saving completed")
            export_xlsx_log(self.save_path, data_to_save)
        except Exception as e:
            print(f"Data not saved: {e}")

    #OLD VERSION
    ##########
    # @override
    # def phase_detection(self):
    #     if not self.do_subphase_detection:
    #         # Detect the gait phases
    #         self.right_leg_shank_fsm.imu_phase_detection()
    #         self.left_leg_shank_fsm.imu_phase_detection()

    #     else:
    #         # Detect the gait subphases
    #         self.right_leg_shank_fsm.imu_subphase_detection(self.left_leg_shank_fsm)
    #         self.left_leg_shank_fsm.imu_subphase_detection(self.right_leg_shank_fsm)

    # @override
    # def update_sensors(self):
    #     # Update the IMU data
    #     self.right_leg_shank_fsm.update_imu()
    #     self.left_leg_shank_fsm.update_imu()
    #     if self.use_four_imus:
    #         self.right_leg_thigh_fsm.update_imu()
    #         self.left_leg_thigh_fsm.update_imu()

    @override
    def update_closed_loop(self):

        # Availability checks (shank + at least one between thigh and foot)
        left_shank_ready_fsm1 = getattr(self, "left_leg_shank_fsm1", None) is not None
        left_thigh_ready_fsm1 = getattr(self, "left_leg_thigh_fsm1", None) is not None
        left_foot_ready_fsm1 = getattr(self, "left_leg_foot_fsm1", None) is not None

        left_shank_ready_fsm2 = getattr(self, "left_leg_shank_fsm2", None) is not None
        left_thigh_ready_fsm2 = getattr(self, "left_leg_thigh_fsm2", None) is not None
        left_foot_ready_fsm2 = getattr(self, "left_leg_foot_fsm2", None) is not None

        right_shank_ready_fsm1 = getattr(self, "right_leg_shank_fsm1", None) is not None
        right_thigh_ready_fsm1 = getattr(self, "right_leg_thigh_fsm1", None) is not None
        right_foot_ready_fsm1 = getattr(self, "right_leg_foot_fsm1", None) is not None

        right_shank_ready_fsm2 = getattr(self, "right_leg_shank_fsm2", None) is not None
        right_thigh_ready_fsm2 = getattr(self, "right_leg_thigh_fsm2", None) is not None
        right_foot_ready_fsm2 = getattr(self, "right_leg_foot_fsm2", None) is not None

        # Single pelvis sensor (shared between both hips). FSM1 and FSM2 are the
        # two acquisition pipelines; whichever is wired up provides the pelvis stream.
        pelvis_ready_fsm1 = getattr(self, "pelvis_fsm1", None) is not None
        pelvis_ready_fsm2 = getattr(self, "pelvis_fsm2", None) is not None

        left_ready_fsm1 = left_shank_ready_fsm1 and (left_thigh_ready_fsm1 or left_foot_ready_fsm1)
        left_ready_fsm2 = left_shank_ready_fsm2 and (left_thigh_ready_fsm2 or left_foot_ready_fsm2)
        right_ready_fsm1 = right_shank_ready_fsm1 and (right_thigh_ready_fsm1 or right_foot_ready_fsm1)
        right_ready_fsm2 = right_shank_ready_fsm2 and (right_thigh_ready_fsm2 or right_foot_ready_fsm2)

        left_ready = True if left_ready_fsm1 or left_ready_fsm2 else False
        right_ready = True if right_ready_fsm1 or right_ready_fsm2 else False

        # Single pelvis quaternion array — shared between left and right hip computation.
        # Resolved once before the per-leg blocks so each side can reuse it.
        try:
            if pelvis_ready_fsm1:
                q_pelvis_array = self.pelvis_fsm1.get_quaternion(last_n=150)
            elif pelvis_ready_fsm2:
                q_pelvis_array = self.pelvis_fsm2.get_quaternion(last_n=150)
            else:
                q_pelvis_array = None
        except Exception as e:
            print(f"[Pelvis] Failed to read quaternions: {e}")
            q_pelvis_array = None

        # ----------------
        # LEFT LEG (if ready)
        # ----------------
        if left_ready:
            try:
                if left_ready_fsm1:
                    q_shank_left_array = self.left_leg_shank_fsm1.get_quaternion(last_n=150)
                    q_thigh_left_array = self.left_leg_thigh_fsm1.get_quaternion(last_n=150) if left_thigh_ready_fsm1 else None
                    q_foot_left_array = self.left_leg_foot_fsm1.get_quaternion(last_n=150) if left_foot_ready_fsm1 else None
                elif left_ready_fsm2:
                    q_shank_left_array = self.left_leg_shank_fsm2.get_quaternion(last_n=150)
                    q_thigh_left_array = self.left_leg_thigh_fsm2.get_quaternion(last_n=150) if left_thigh_ready_fsm2 else None
                    q_foot_left_array = self.left_leg_foot_fsm2.get_quaternion(last_n=150) if left_foot_ready_fsm2 else None
                else:
                    pass
            except Exception as e:
                print(f"[Left] Failed to read quaternions: {e}")
                q_shank_left_array = q_thigh_left_array = q_foot_left_array = None

            if getattr(q_shank_left_array, "size", 0) > 0 and (getattr(q_thigh_left_array, "size", 0) > 0 or getattr(q_foot_left_array, "size", 0) > 0):
                # Prefer device time from shank array (assuming first column = timestamp)

                ts_left = time.time()

                # Compute Knee ROM if thigh is available
                if getattr(q_thigh_left_array, "size", 0) > 0:
                    self.left_knee_rom.compute_from_list(q_thigh_left_array, q_shank_left_array, ts_left)

                # Compute Ankle ROM if foot is available (signed Z-axis method)
                if getattr(q_foot_left_array, "size", 0) > 0:
                    self.left_ankle_rom.ankle_compute_from_list(q_shank_left_array, q_foot_left_array, ts_left)

                # Compute Hip ROM if pelvis and thigh are available
                if getattr(q_pelvis_array, "size", 0) > 0 and getattr(q_thigh_left_array, "size", 0) > 0:
                    self.left_hip_rom.compute_from_list(q_pelvis_array, q_thigh_left_array, ts_left)

                # Choose phase/subphase
                left_fsm = self.get_first_available_fsm(side="left")
                phase_left = left_fsm.active_phase if left_fsm is not None else None

                # PI target and compute (guard against missing FSM, only run stimulation if do_closed_loop is active)
                if self.do_closed_loop and phase_left is not None:
                    self.left_pi_controller.update_target(phase_left, self.left_knee_rom.get_pi_angle())
                    output_left = self.left_pi_controller.compute(self.left_knee_rom.get_pi_angle(), ts_left)

                    # Apply to stim (True = left)
                    update_offset(self.stimulator_connection, self.stim_param, phase_left, output_left, ts_left, True)

        # ----------------
        # RIGHT LEG (if ready)
        # ----------------
        if right_ready:
            #print("Debug: right leg ready")
            try:
                if right_ready_fsm1:
                    q_shank_right_array = self.right_leg_shank_fsm1.get_quaternion(last_n=150)
                    q_thigh_right_array = self.right_leg_thigh_fsm1.get_quaternion(last_n=150) if right_thigh_ready_fsm1 else None
                    q_foot_right_array = self.right_leg_foot_fsm1.get_quaternion(last_n=150) if right_foot_ready_fsm1 else None
                elif right_ready_fsm2:
                    q_shank_right_array = self.right_leg_shank_fsm2.get_quaternion(last_n=150)
                    q_thigh_right_array = self.right_leg_thigh_fsm2.get_quaternion(last_n=150) if right_thigh_ready_fsm2 else None
                    q_foot_right_array = self.right_leg_foot_fsm2.get_quaternion(last_n=150) if right_foot_ready_fsm2 else None
                else:
                    q_shank_right_array = q_thigh_right_array = q_foot_right_array = None

            except Exception as e:
                #print(f"[Right] Failed to read quaternions: {e}")
                q_shank_right_array = q_thigh_right_array = q_foot_right_array = None

            if getattr(q_shank_right_array, "size", 0) > 0 and (getattr(q_thigh_right_array, "size", 0) > 0 or getattr(q_foot_right_array, "size", 0) > 0):
                # Prefer device time from shank array

                ts_right = time.time()

                # Compute Knee ROM if thigh is available
                if getattr(q_thigh_right_array, "size", 0) > 0:
                    self.right_knee_rom.compute_from_list(q_thigh_right_array, q_shank_right_array, ts_right)

                # Compute Ankle ROM if foot is available (signed Z-axis method)
                if getattr(q_foot_right_array, "size", 0) > 0:
                    self.right_ankle_rom.ankle_compute_from_list(q_shank_right_array, q_foot_right_array, ts_right)

                # Compute Hip ROM if pelvis and thigh are available
                if getattr(q_pelvis_array, "size", 0) > 0 and getattr(q_thigh_right_array, "size", 0) > 0:
                    self.right_hip_rom.compute_from_list(q_pelvis_array, q_thigh_right_array, ts_right)

                right_fsm = self.get_first_available_fsm(side="right")
                phase_right = right_fsm.active_phase if right_fsm is not None else None

                if self.do_closed_loop and phase_right is not None:
                    self.right_pi_controller.update_target(phase_right, self.right_knee_rom.get_pi_angle())
                    output_right = self.right_pi_controller.compute(self.right_knee_rom.get_pi_angle(), ts_right)

                    update_offset(self.stimulator_connection, self.stim_param, phase_right, output_right, ts_right, False)

    # @override
    # def stimulate(self):
    #     if self.stimulator_connection is None:
    #         return

    #     if self.do_phase_detection:
    #         # Stimulation phases
    #         if not self.__check_for_unknown_phases():
    #             open_stimulation_channel_phases_imu(
    #                 self.stimulator_connection,
    #                 self.channels,
    #                 right_leg=self.right_leg_shank_fsm,
    #                 left_leg=self.left_leg_shank_fsm,
    #                 stim_param=self.stim_param,
    #             )

    #     elif self.do_subphase_detection:
    #         # Stimulation subphases
    #         if not self.__check_for_unknown_subphases():
    #             open_stimulation_channel_subphases(
    #                 self.stimulator_connection,
    #                 self.channels,
    #                 right_leg=self.right_leg_shank_fsm,
    #                 left_leg=self.left_leg_shank_fsm,
    #                 stim_param=self.stim_param,
    #             )

    # @override
    # def save_data(self):
    #     def save_rom_data(gait_fsm: IMUGaitFSM):
    #         imu_rom = {
    #             "gx": gait_fsm.data_gx_rom,
    #             "gy": gait_fsm.data_gy_rom,
    #             "gz": gait_fsm.data_gz_rom,
    #             "accx": gait_fsm.data_accx_rom,
    #             "accy": gait_fsm.data_accy_rom,
    #             "accz": gait_fsm.data_accz_rom,
    #             "timestamps": gait_fsm.timestamps_rom,
    #         }
    #         return imu_rom

    #     # Create a dictionary to store all the data
    #     data_to_save = {
    #         "imu_subphase_timestamps_right_shank": self.right_leg_shank_fsm.subphase_timestamps,
    #         "imu_subphase_timestamps_left_shank": self.left_leg_shank_fsm.subphase_timestamps,
    #         "imu_phase_timestamps_right_shank": self.right_leg_shank_fsm.phase_timestamps,
    #         "imu_phase_timestamps_left_shank": self.left_leg_shank_fsm.phase_timestamps,
    #         "imu_timestamps_stim_right": self.stim_param.timestamps_stim_right,
    #         "imu_timestamps_stim_left": self.stim_param.timestamps_stim_left,
    #         "imu_current_right": self.stim_param.stim_values_right,
    #         "imu_current_left": self.stim_param.stim_values_left,
    #         "imu_heel_strike_peaks_right_shank": self.right_leg_shank_fsm.heel_strike_peaks_timestamps,
    #         "imu_heel_strike_peaks_left_shank": self.left_leg_shank_fsm.heel_strike_peaks_timestamps,
    #         "imu_toe_off_peaks_right_shank": self.right_leg_shank_fsm.toe_off_peaks_timestamps,
    #         "imu_toe_off_peaks_left_shank": self.left_leg_shank_fsm.toe_off_peaks_timestamps,
    #         "imu_valleys_right_shank": self.right_leg_shank_fsm.valleys_timestamps,
    #         "imu_valleys_left_shank": self.left_leg_shank_fsm.valleys_timestamps,
    #         "imu_left_knee_angles": self.left_knee_rom.angles[:, 1],  # Only the angles, not the timestamps
    #         "imu_right_knee_angles": self.right_knee_rom.angles[:, 1],  # Only the angles, not the timestamps
    #         "imu_left_knee_timestamps": self.left_knee_rom.angles[:, 0],  # Timestamps for the left knee angles
    #         "imu_right_knee_timestamps": self.right_knee_rom.angles[:, 0],  # Timestamps for the right knee angles
    #         "imu_left_pi_timestamps": self.left_pi_controller.timestamps,
    #         "imu_right_pi_timestamps": self.right_pi_controller.timestamps,
    #         "imu_left_pi_errors": self.left_pi_controller.errors,
    #         "imu_right_pi_errors": self.right_pi_controller.errors,
    #         "imu_left_pi_outputs": self.left_pi_controller.outputs,
    #         "imu_right_pi_outputs": self.right_pi_controller.outputs,
    #         "imu_target_change_left": self.left_pi_controller.target_changes,
    #         "imu_target_change_right": self.right_pi_controller.target_changes,
    #         "rom_data": {
    #             "right_shank": save_rom_data(self.right_leg_shank_fsm),
    #             "left_shank": save_rom_data(self.left_leg_shank_fsm),
    #         },
    #     }

    #     if self.use_four_imus:
    #         data_to_save["rom_data"]["right_thigh"] = save_rom_data(self.right_leg_thigh_fsm)
    #         data_to_save["rom_data"]["left_thigh"] = save_rom_data(self.left_leg_thigh_fsm)

    #     # Save the dictionary to a single file
    #     try:
    #         with open(
    #             self.save_path,
    #             "wb",
    #         ) as f:
    #             pickle.dump(data_to_save, f)
    #     except FileNotFoundError:
    #         print("Data not saved, no valid path provided")
    #         return

    #     print("Saving completed")

    @override
    def return_values(self) -> dict:
        # Close all present inlets
        for _side, _placement, _suffix, fsm in self._iter_all_fsms():
            try:
                fsm.inlet.close_stream()
            except Exception:
                pass

        # Collect counters per stream/method
        out = {}
        for side, placement, suffix, fsm in self._iter_all_fsms():
            key = f"{side}_{placement}_{suffix}"  # e.g., right_shank_fsm1
            out[key] = {
                "phase_counters": getattr(fsm, "phase_counters", None),
                "subphase_counters": getattr(fsm, "subphase_counters", None),
            }
        return out

    def __check_for_unknown_phases(self, right_fsm, left_fsm) -> bool:
        """Return True iff BOTH legs are UNKNOWN for this specific pair."""
        return right_fsm.is_phase_unknown() and left_fsm.is_phase_unknown()

############################################################################
""" Class for gait detection and stimulation with FSR and IMU """
############################################################################

class StimulationFSRandIMU(StimulationIMUs):
    # New per-leg FSR step signals (IMU signals are inherited from StimulationIMUs)
    fsr_imu_left_step_count_changed = Signal(int)
    fsr_imu_right_step_count_changed = Signal(int)

    fsr_imu_left_phase_changed = Signal(int)
    fsr_imu_right_phase_changed = Signal(int)

    def __init__(self, **kwargs):

        self.terminal_stance_divider: int = kwargs.get("terminal_stance_divider", 4)
        self.FES: bool = kwargs.get("FES", False)
        self.do_closed_loop: bool = kwargs.get("do_closed_loop")

        super().__init__(**kwargs)

        self.threshold_left: int = kwargs.get("threshold_left", 5)
        self.threshold_right: int = kwargs.get("threshold_right", 5)

        # Prefer Shank over Foot; Method 1 over Method 2 (edit if needed)
        PRIORITY = [("foot", "fsm2") , ("shank", "fsm2"), ("foot", "fsm1"), ("shank", "fsm1") ]

        # Choose the first available IMU inlet for each side (priority order)
        right_imu_inlet = None
        left_imu_inlet = None

        for placement, suffix in PRIORITY:
            # Stream labels in your system are "Right Shank", "Left Foot", etc.
            right_name = f"Right {placement.capitalize()}"
            left_name = f"Left {placement.capitalize()}"

            if right_imu_inlet is None:
                try:
                    right_imu_inlet = self._resolve_streaminlet(right_name)
                except Exception:
                    right_imu_inlet = None

            if left_imu_inlet is None:
                try:
                    left_imu_inlet = self._resolve_streaminlet(left_name)
                except Exception:
                    left_imu_inlet = None

            # stop early if we've found both
            if right_imu_inlet is not None and left_imu_inlet is not None:
                break

        # Resolve FSR inlets safely (fallback to None if missing)
        try:
            right_fsr_inlet = self._resolve_streaminlet("FSR_Right")
        except Exception:
            right_fsr_inlet = None

        try:
            left_fsr_inlet = self._resolve_streaminlet("FSR_Left")
        except Exception:
            left_fsr_inlet = None

        # Instantiate combined FSMs (guard if FSR inlet missing)
        if right_fsr_inlet is not None:
            self.right_fsr_imu_fsm = FSRIMUGaitFSM(
                inlet_fsr=right_fsr_inlet,
                inlet_imu=right_imu_inlet,    # may be None: FSRIMUGaitFSM should guard
                threshold=self.threshold_right,
                terminal_stance_divider=self.terminal_stance_divider,
                FES=self.FES,
                do_closed_loop=self.do_closed_loop,
            )
        else:
            self.right_fsr_imu_fsm = FSRGaitFSM_DUMMY()

        if left_fsr_inlet is not None:
            self.left_fsr_imu_fsm = FSRIMUGaitFSM(
                inlet_fsr=left_fsr_inlet,
                inlet_imu=left_imu_inlet,
                threshold=self.threshold_left,  # use left threshold
                terminal_stance_divider=self.terminal_stance_divider,
                FES=self.FES,
                do_closed_loop=self.do_closed_loop,
            )
        else:
            self.left_fsr_imu_fsm = FSRGaitFSM_DUMMY()

        # NEW: forward per-leg FSR counts in combined mode
        self.right_fsr_imu_fsm.steps_changed.connect(
            lambda _c: self.fsr_imu_right_step_count_changed.emit(int(self.right_fsr_imu_fsm.get_step_count()))
        )
        self.left_fsr_imu_fsm.steps_changed.connect(
            lambda _c: self.fsr_imu_left_step_count_changed.emit(int(self.left_fsr_imu_fsm.get_step_count()))
        )

        try:
            # forward FSR phase -> stim signals
            if hasattr(self.left_fsr_imu_fsm, "phase_changed"):
                    self.left_fsr_imu_fsm.phase_changed.connect(lambda v: self.fsr_imu_left_phase_changed.emit(int(v)))

            if hasattr(self.right_fsr_imu_fsm, "phase_changed"):
                self.right_fsr_imu_fsm.phase_changed.connect(lambda v: self.fsr_imu_right_phase_changed.emit(int(v)))

        except Exception:
            pass

    @override
    def phase_detection(self):
        # IMUs — skip pelvis (kinematic source only, no phase detection).
        for side, _placement, _suffix, fsm in self._iter_all_fsms():
            if side == "pelvis":
                continue
            fsm.imu_phase_detection()
        # FSRs (no subphase per your current design)
        self.right_fsr_imu_fsm.fsr_phase_detection()
        self.left_fsr_imu_fsm.fsr_phase_detection()

    @override
    def update_sensors(self):
        # IMUs (all connected shank/foot × method 1/2)
        for _side, _placement, _suffix, fsm in self._iter_all_fsms():
            fsm.update_imu()
        # FSRs
        self.right_fsr_imu_fsm.update_fsr_imu()
        self.left_fsr_imu_fsm.update_fsr_imu()

    @override
    def stimulate(self):
        if self.stimulator_connection is None:
            return
        if not getattr(self, "do_phase_detection", True):
            return

        open_stimulation_channel_phases_imu_fsr(
            self.stimulator_connection,
            self.channels,
            right_leg=self.right_fsr_imu_fsm,
            left_leg=self.left_fsr_imu_fsm,
            stim_param=self.stim_param,
            method_fsr=getattr(self, "method_fsr", getattr(self, "method", None)),
            _total_paused_duration=self._total_paused_duration,

        )
        return  # fire once per tick

    @override
    def save_data(self):
        def rom_block(gait_fsm):
            # Include quaternions so the unified .xlsx Raw_<sensor> sheets carry
            # the same payload regardless of which Stimulation* subclass runs.
            block = {
                "gx": gait_fsm.data_gx_rom,
                "gy": gait_fsm.data_gy_rom,
                "gz": gait_fsm.data_gz_rom,
                "accx": gait_fsm.data_accx_rom,
                "accy": gait_fsm.data_accy_rom,
                "accz": gait_fsm.data_accz_rom,
                "timestamps": gait_fsm.timestamps_rom,
            }
            for short, attr in (("qw", "data_quatw_rom"), ("qx", "data_quatx_rom"),
                                ("qy", "data_quaty_rom"), ("qz", "data_quatz_rom")):
                if hasattr(gait_fsm, attr):
                    block[short] = getattr(gait_fsm, attr)
            return block

        # ROM/PI helpers — used to extract joint angles/timestamps when the parent
        # ROM calibrator may or may not have computed anything yet.
        def _rom_angles(rom):
            arr = getattr(rom, "angles", None) if rom is not None else None
            return arr[:, 1] if arr is not None and getattr(arr, "size", 0) > 0 else None

        def _rom_timestamps(rom):
            arr = getattr(rom, "angles", None) if rom is not None else None
            return arr[:, 0] if arr is not None and getattr(arr, "size", 0) > 0 else None

        # Create a dictionary to store all the data
        data_to_save = {
            **self._experiment_meta(),  # time information

            # stim metadata (timestamps + per-channel currents, both stim and de-stim)
            "imu_timestamps_stim_right":    getattr(self.stim_param, "timestamps_stim_right",    None),
            "imu_timestamps_stim_left":     getattr(self.stim_param, "timestamps_stim_left",     None),
            "imu_timestamps_de_stim_right": getattr(self.stim_param, "timestamps_de_stim_right", None),
            "imu_timestamps_de_stim_left":  getattr(self.stim_param, "timestamps_de_stim_left",  None),
            "imu_current_right":            getattr(self.stim_param, "stim_values_right",        None),
            "imu_current_left":             getattr(self.stim_param, "stim_values_left",         None),

            # IMU buckets will be filled below
            "rom_data": {},

            # Joint angles + timestamps for the unified xlsx "Joint_Angles" sheet.
            # Pulled from the ROM calibrators that StimulationIMUs (parent) builds.
            "imu_left_knee_angles":      _rom_angles(getattr(self,  "left_knee_rom",  None)),
            "imu_right_knee_angles":     _rom_angles(getattr(self,  "right_knee_rom", None)),
            "imu_left_knee_timestamps":  _rom_timestamps(getattr(self, "left_knee_rom",  None)),
            "imu_right_knee_timestamps": _rom_timestamps(getattr(self, "right_knee_rom", None)),
            "imu_left_ankle_angles":      _rom_angles(getattr(self,  "left_ankle_rom",  None)),
            "imu_right_ankle_angles":     _rom_angles(getattr(self,  "right_ankle_rom", None)),
            "imu_left_ankle_timestamps":  _rom_timestamps(getattr(self, "left_ankle_rom",  None)),
            "imu_right_ankle_timestamps": _rom_timestamps(getattr(self, "right_ankle_rom", None)),
            "imu_left_hip_angles":        _rom_angles(getattr(self,  "left_hip_rom",   None)),
            "imu_right_hip_angles":       _rom_angles(getattr(self,  "right_hip_rom",  None)),
            "imu_left_hip_timestamps":    _rom_timestamps(getattr(self, "left_hip_rom",   None)),
            "imu_right_hip_timestamps":   _rom_timestamps(getattr(self, "right_hip_rom",  None)),

            # Ankle functional-calibration refs (for offline SVD/hinge reconstruction).
            # Pulled from the ankle ROM instances (set via set_ankle_reference). None
            # when functional calibration wasn't performed -> offline falls back to legacy.
            "left_ankle_offset":      getattr(getattr(self, "left_ankle_rom",  None), "offset",      0.0),
            "right_ankle_offset":     getattr(getattr(self, "right_ankle_rom", None), "offset",      0.0),
            "left_ankle_qshank_ref":  getattr(getattr(self, "left_ankle_rom",  None), "q_shank_ref", None),
            "left_ankle_qfoot_ref":   getattr(getattr(self, "left_ankle_rom",  None), "q_foot_ref",  None),
            "left_ankle_hinge_axis":  getattr(getattr(self, "left_ankle_rom",  None), "hinge_axis",  None),
            "left_ankle_shank_axis":  getattr(getattr(self, "left_ankle_rom",  None), "shank_axis",  'X'),
            "left_ankle_foot_axis":   getattr(getattr(self, "left_ankle_rom",  None), "foot_axis",   'X'),
            "right_ankle_qshank_ref": getattr(getattr(self, "right_ankle_rom", None), "q_shank_ref", None),
            "right_ankle_qfoot_ref":  getattr(getattr(self, "right_ankle_rom", None), "q_foot_ref",  None),
            "right_ankle_hinge_axis": getattr(getattr(self, "right_ankle_rom", None), "hinge_axis",  None),
            "right_ankle_shank_axis": getattr(getattr(self, "right_ankle_rom", None), "shank_axis",  'X'),
            "right_ankle_foot_axis":  getattr(getattr(self, "right_ankle_rom", None), "foot_axis",   'X'),
            # Knee / hip functional refs (mirror of ankle).
            "left_knee_qthigh_ref":  getattr(getattr(self, "left_knee_rom",  None), "q_thigh_ref_knee", None),
            "left_knee_qshank_ref":  getattr(getattr(self, "left_knee_rom",  None), "q_shank_ref_knee", None),
            "left_knee_hinge_axis":  getattr(getattr(self, "left_knee_rom",  None), "knee_hinge_axis",  None),
            "right_knee_qthigh_ref": getattr(getattr(self, "right_knee_rom", None), "q_thigh_ref_knee", None),
            "right_knee_qshank_ref": getattr(getattr(self, "right_knee_rom", None), "q_shank_ref_knee", None),
            "right_knee_hinge_axis": getattr(getattr(self, "right_knee_rom", None), "knee_hinge_axis",  None),
            "left_hip_qpelvis_ref":  getattr(getattr(self, "left_hip_rom",   None), "q_pelvis_ref_hip", None),
            "left_hip_qthigh_ref":   getattr(getattr(self, "left_hip_rom",   None), "q_thigh_ref_hip",  None),
            "left_hip_hinge_axis":   getattr(getattr(self, "left_hip_rom",   None), "hip_hinge_axis",   None),
            "right_hip_qpelvis_ref": getattr(getattr(self, "right_hip_rom",  None), "q_pelvis_ref_hip", None),
            "right_hip_qthigh_ref":  getattr(getattr(self, "right_hip_rom",  None), "q_thigh_ref_hip",  None),
            "right_hip_hinge_axis":  getattr(getattr(self, "right_hip_rom",  None), "hip_hinge_axis",   None),

            # save walking speed used
            "walking_speed": getattr(self, "speed", None),

            # FSR raw and event data (both sides)
            "fsr_data_ff_left": self.left_fsr_imu_fsm.data_ff_offline,
            "fsr_data_mf_left": self.left_fsr_imu_fsm.data_mf_offline,
            "fsr_data_bf_left": self.left_fsr_imu_fsm.data_bf_offline,
            "fsr_cop_x_left": self.left_fsr_imu_fsm.data_cop_x_offline,
            "fsr_cop_y_left": self.left_fsr_imu_fsm.data_cop_y_offline,
            "fsr_timestamps_left": self.left_fsr_imu_fsm.timestamps_fsr_offline,
            "fsr_heel_strike_left": self.left_fsr_imu_fsm.heel_strike,
            "fsr_mid_stance_left": self.left_fsr_imu_fsm.mid_stance,
            "fsr_toe_off_left": self.left_fsr_imu_fsm.toe_off,
            "fsr_heel_strike_timestamps_left": self.left_fsr_imu_fsm.heel_strike_timestamps,
            "fsr_mid_stance_timestamps_left": self.left_fsr_imu_fsm.mid_stance_timestamps,
            "fsr_toe_off_timestamps_left": self.left_fsr_imu_fsm.toe_off_timestamps,

            "fsr_data_ff_right": self.right_fsr_imu_fsm.data_ff_offline,
            "fsr_data_mf_right": self.right_fsr_imu_fsm.data_mf_offline,
            "fsr_data_bf_right": self.right_fsr_imu_fsm.data_bf_offline,
            "fsr_cop_x_right": self.right_fsr_imu_fsm.data_cop_x_offline,
            "fsr_cop_y_right": self.right_fsr_imu_fsm.data_cop_y_offline,
            "fsr_timestamps_right": self.right_fsr_imu_fsm.timestamps_fsr_offline,
            "fsr_heel_strike_right": self.right_fsr_imu_fsm.heel_strike,
            "fsr_mid_stance_right": self.right_fsr_imu_fsm.mid_stance,
            "fsr_toe_off_right": self.right_fsr_imu_fsm.toe_off,
            "fsr_heel_strike_timestamps_right": self.right_fsr_imu_fsm.heel_strike_timestamps,
            "fsr_mid_stance_timestamps_right": self.right_fsr_imu_fsm.mid_stance_timestamps,
            "fsr_toe_off_timestamps_right": self.right_fsr_imu_fsm.toe_off_timestamps,

            "fsr_valley_timestamps_left": self.left_fsr_imu_fsm.valleys_timestamps,
            "fsr_valley_timestamps_right": self.right_fsr_imu_fsm.valleys_timestamps,

            # FSR phase timestamps and counters
            "fsr_phase_timestamps_left": getattr(self.left_fsr_imu_fsm, "phase_timestamps", None),
            "fsr_phase_timestamps_right": getattr(self.right_fsr_imu_fsm, "phase_timestamps", None),
            "fsr_phase_counters_left": getattr(self.left_fsr_imu_fsm, "phase_counters", None),
            "fsr_phase_counters_right": getattr(self.right_fsr_imu_fsm, "phase_counters", None),

            #add active run time
            "active_run_seconds": getattr(self, "active_run_seconds", self._compute_active_run_seconds()),

            # FSR Method 2 loading-response durations (only when using Method 2), safe fallback to empty list
            "fsr_loading_response_durations_right": (
                self.right_fsr_imu_fsm.FSR2_loading_response_durations

            ),
            "fsr_loading_response_durations_left": (
                self.left_fsr_imu_fsm.FSR2_loading_response_durations

            ),

            "fsr_mid_stance_durations_right": (
                self.right_fsr_imu_fsm.FSR2_mid_stance_durations

            ),
            "fsr_mid_stance_durations_left": (
                self.left_fsr_imu_fsm.FSR2_mid_stance_durations

            ),
            "fsr_stance_durations_right": (
                self.right_fsr_imu_fsm.FSR2_stance_durations

            ),
            "fsr_stance_durations_left": (
                self.left_fsr_imu_fsm.FSR2_stance_durations

            ),

            }

        # IMU data for every connected stream: side/placement/method
        for side, placement, suffix, fsm in self._iter_all_fsms():
            key_prefix = f"imu_{side}_{placement}_{suffix}"  # e.g., imu_right_shank_fsm1

            # Phase timestamps (always save)
            data_to_save[f"{key_prefix}_phase_timestamps"] = getattr(fsm, "phase_timestamps", None)
            # Phase counters
            data_to_save[f"{key_prefix}_phase_counters"] = getattr(fsm, "phase_counters", None)

            # Subphase timestamps (kept if present, harmless otherwise)
            sub_ts = getattr(fsm, "subphase_timestamps", None)
            if sub_ts is not None:
                data_to_save[f"{key_prefix}_subphase_timestamps"] = sub_ts

            # Events (guard presence)
            if hasattr(fsm, "heel_strike_peaks_timestamps"):
                data_to_save[f"{key_prefix}_heel_strike_peaks"] = fsm.heel_strike_peaks_timestamps
            if hasattr(fsm, "toe_off_peaks_timestamps"):
                data_to_save[f"{key_prefix}_toe_off_peaks"] = fsm.toe_off_peaks_timestamps
            if hasattr(fsm, "valleys_timestamps"):
                data_to_save[f"{key_prefix}_valleys"] = fsm.valleys_timestamps

            # ROM per-IMU
            data_to_save["rom_data"][f"{side}_{placement}_{suffix}"] = rom_block(fsm)

        # Persist
        try:
            with open(self.save_path, "wb") as f:
                pickle.dump(data_to_save, f)
            print("Saving completed")
            export_xlsx_log(self.save_path, data_to_save)
        except Exception as e:
            print(f"Data not saved: {e}")

    def __check_for_unknown_phases(self, right_imu, left_imu) -> bool:
        """True iff IMU pair is unknown on both legs AND both FSRs are unknown."""
        imu_unknown = right_imu.is_phase_unknown() and left_imu.is_phase_unknown()
        fsr_unknown = self.right_fsr_imu_fsm.is_phase_unknown() and self.left_fsr_imu_fsm.is_phase_unknown()
        return imu_unknown and fsr_unknown

    @override
    def return_values(self) -> dict:
        # Close all IMU inlets
        for _side, _placement, _suffix, fsm in self._iter_all_fsms():
            try:
                fsm.inlet.close_stream()
            except Exception:
                pass

        # Close FSR inlets if they expose one
        for fsr in (self.right_fsr_imu_fsm, self.left_fsr_imu_fsm):
            try:
                fsr.inlet.close_stream()
            except Exception:
                pass

        # Build counters per IMU and per FSR
        out = {"imu": {}, "fsr": {}}

        for side, placement, suffix, fsm in self._iter_all_fsms():
            key = f"{side}_{placement}_{suffix}"  # e.g., right_shank_fsm1
            out["imu"][key] = {
                "phase_counters": getattr(fsm, "phase_counters", None),
                "subphase_counters": getattr(fsm, "subphase_counters", None),
            }

        out["fsr"]["right"] = {
            "phase_counters": getattr(self.right_fsr_imu_fsm, "phase_counters", None),
            "subphase_counters": getattr(self.right_fsr_imu_fsm, "subphase_counters", None),
        }
        out["fsr"]["left"] = {
            "phase_counters": getattr(self.left_fsr_imu_fsm, "phase_counters", None),
            "subphase_counters": getattr(self.left_fsr_imu_fsm, "subphase_counters", None),
        }
        return out

############################################################################
""" Class for Stimulating Step using FES """
############################################################################

class StimulationFESStep(StimulationBasic):
    """This class is used when calibrating FES for to have a Functional step and is more used for testing purposes."""

    def __init__(self, **kwargs):
        self.fes_speed= kwargs.get("fes_speed", "0.8")
        self.fes_steps= kwargs.get("fes_steps", "3")
        self.fes_side = kwargs.get("fes_side", "left")

        super().__init__(**kwargs)
        # Debug
        self.current = True

    @override
    def phase_detection(self):
        # No phase detection
        pass

    @override
    def update_sensors(self):
        # No phase detection
        pass

    @override
    def update_closed_loop(self):
        # No closed loop update
        pass

    @override
    def stimulate(self):

        open_stimulation_FES_step( self.stimulator_connection,
                              self.channels,
                              stim_param = self.stim_param,
                              fes_side = self.fes_side,
                              fes_speed= self.fes_speed,
                              fes_steps= self.fes_steps
                              )
        pass

    @override
    def save_data(self):
        # Just save zero data to the file (to have a timestamp of the experiment)
        data_to_save = {
            "data": []
        }
        # Save the dictionary to a single file
        try:
            with open(
                self.save_path,
                "wb",
            ) as f:
                pickle.dump(data_to_save, f)
        except FileNotFoundError:
            print("Data not saved, no valid path provided")
            return

        print("Saving completed")

    @override
    def return_values(self):
        # No data to return
        return None
