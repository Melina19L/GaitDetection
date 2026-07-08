"""Main window controller (runtime wiring, not page layout).

``MainWindow`` holds the ``ExperimentHandler`` in its own ``QThread``, the two
per-side ``FSRController`` BLE workers, the ``BLEScanner`` and the
``AngleCalibrator``. It wires the step/phase signals to the Test page, runs the
stopwatch and manages pause/resume (with the post-pause lockout). Page layout
and business logic live in ``SetupMainWindow`` (``setup_main_window.py``).
"""
from qt_core import *
from gui.core.json_settings import Settings
from gui.core.functions import Functions
from gui.uis.windows.main_window import *
from stimulator.experiment_handler import ExperimentHandler
from ble.fsr_controller import FSRController
from ble.ble_scanner import BLEScanner
import pylsl
from typing import Optional
from stimulator.gait_phases import Phase

DEVICE_ADDRESS_LEFT = "92:51:51:57:E3:30"

DEVICE_ADDRESS_RIGHT = "34:7A:39:AA:CA:A7"

# MAIN WINDOW
class MainWindow(QMainWindow):
    """Top-level window: owns the worker threads and wires runtime signals.

    Builds the UI via ``SetupMainWindow``, launches the experiment/BLE/angle
    workers on their threads and connects their signals to the Test-page widgets
    (steps, phase, active time, stopwatch, pause/resume).
    """
    # Signals
    start_experiment = Signal(dict)
    stop_experiment = Signal()
    connect_fsr_left_device = Signal(str, list)
    connect_fsr_right_device = Signal(str, list)
    disconnect_fsr_left_device = Signal()
    disconnect_fsr_right_device = Signal()
    # NEW: pause/resume experiment
    pause_experiment = Signal()
    resume_experiment = Signal()

    def __init__(self):
        super().__init__()

        # UI Setup
        self.ui = UI_MainWindow()
        self.ui.setup_ui(self)

        # Load settings
        settings = Settings()
        self.settings = settings.items

        # Setup GUI
        self.hide_grips = True
        SetupMainWindow.setup_gui(self)

        # Stopwatch
        self.stopwatch = QTimer(self)
        self.stopwatch.setInterval(1000)
        self.stopwatch.timeout.connect(self.update_time)
        self.start_time = QTime.currentTime()

        # -------------------- Experiment Thread --------------------
        self.experiment_thread = QThread()
        self.experiment_thread.setObjectName("Experiment Thread")
        self.experiment_handler = ExperimentHandler()
        self.experiment_handler.moveToThread(self.experiment_thread)
        self.start_experiment.connect(self.experiment_handler.start_experiment_safe)
        self.stop_experiment.connect(self.experiment_handler.stop_experiment)
        self.experiment_handler.starting_experiment.connect(self.start_timer)
        self.experiment_handler.finished.connect(self.show_results)
        self.experiment_handler.finished.connect(self._save_plot_pkl_after_test)
        self.experiment_handler.error_message.connect(self.error_handler)

         # NEW: connect pause/resume to handler
        self.pause_experiment.connect(self.experiment_handler.pause_experiment)
        self.resume_experiment.connect(self.experiment_handler.resume_experiment)

        # Track pause state and elapsed offset for stopwatch
        self._paused = False
        self._elapsed_ms_before_pause = 0

        # pause delay 10s before enabling
        self._experiment_running = False  # track running state
        self._pause_enable_delay = QTimer(self)
        self._pause_enable_delay.setSingleShot(True)
        self._pause_enable_delay.timeout.connect(self._enable_page10_pause_btn)

        # NEW: connect active run seconds from backend to UI
        try:
            self.experiment_handler.active_run_seconds_changed.connect(self.on_active_run_seconds_changed)
        except Exception:
            pass

        # Connect step updates from the worker
        try:
            self.experiment_handler.step_count_changed.connect(self.on_step_count_changed)
        except Exception:
            pass

        # NEW: connect per-leg signals from ExperimentHandler
        try:
            self.experiment_handler.imu_left_step_count_changed.connect(self.on_left_step_count_changed)
            self.experiment_handler.imu_right_step_count_changed.connect(self.on_right_step_count_changed)
            self.experiment_handler.fsr_left_step_count_changed.connect(self.on_left_step_count_changed)
            self.experiment_handler.fsr_right_step_count_changed.connect(self.on_right_step_count_changed)
            self.experiment_handler.fsr_imu_left_step_count_changed.connect(self.on_left_step_count_changed)
            self.experiment_handler.fsr_imu_right_step_count_changed.connect(self.on_right_step_count_changed)
            # connect phase signals (using "phase" naming)
            try:
                self.experiment_handler.imu_left_phase_changed.connect(self.on_imu_left_phase_changed)
                self.experiment_handler.imu_right_phase_changed.connect(self.on_imu_right_phase_changed)
                self.experiment_handler.fsr_left_phase_changed.connect(self.on_imu_left_phase_changed)
                self.experiment_handler.fsr_right_phase_changed.connect(self.on_imu_right_phase_changed)
                self.experiment_handler.fsr_imu_left_phase_changed.connect(self.on_imu_left_phase_changed)
                self.experiment_handler.fsr_imu_right_phase_changed.connect(self.on_imu_right_phase_changed)
            except Exception:
                pass
        except Exception:
            pass

        self.experiment_thread.start()

        # -------------------- FSR LEFT --------------------
        self.fsr_left = FSRController('left')
        self.fsr_left.start_in_thread()
        self.fsr_left.updateStatus.connect(lambda s: self.update_status("LEFT: " + s))
        self.fsr_left.updateFSR.connect(self.update_fsr_data_left)
        self.fsr_left.updateConnected.connect(lambda c: self.update_stream(c, side="left"))

        # FSR RIGHT in GUI thread
        self.fsr_right = FSRController("right")
        self.fsr_right.start_in_thread()
        self.fsr_right.updateStatus.connect(lambda s: self.update_status("RIGHT: " + s))
        self.fsr_right.updateFSR.connect(self.update_fsr_data_right)
        self.fsr_right.updateConnected.connect(lambda c: self.update_stream(c, side="right"))

        # Serialize BLE connects across both controllers
        self.ble_busy = False
        self.ble_connect_queue: list[callable] = []
        self.fsr_left.busyChanged.connect(self._on_ble_busy_changed)
        self.fsr_right.busyChanged.connect(self._on_ble_busy_changed)

        # Wire signals
        self.connect_fsr_left_device.connect(self.fsr_left.connect_to_peripheral)
        self.disconnect_fsr_left_device.connect(self.fsr_left.disconnect_from_peripheral)
        self.connect_fsr_right_device.connect(self.fsr_right.connect_to_peripheral)
        self.disconnect_fsr_right_device.connect(self.fsr_right.disconnect_from_peripheral)
        self.fsr_outlet_left: Optional[pylsl.StreamOutlet] = None
        self.fsr_outlet_right: Optional[pylsl.StreamOutlet] = None

        # BLE Scanner in GUI thread (avoid COM-from-worker issues)
        self.ble_scanner = BLEScanner()
        self.ble_scanner.updateStatus.connect(self.update_status)
        self.scan_fsr_btn.clicked.connect(self.ble_scanner.start_scanning)

        # Show main window
        self.show()

    # --- queue helpers (serialize connects) ---
    def _enqueue_ble(self, fn):
        if self.ble_busy:
            self.ble_connect_queue.append(fn)
            self.update_status("BLE busy: queued connect.")
        else:
            self.ble_busy = True
            fn()

    @Slot(bool)
    def _on_ble_busy_changed(self, busy: bool):
        if busy:
            self.ble_busy = True
            return
        # busy released by a controller; run next queued connect if any
        if self.ble_connect_queue:
            fn = self.ble_connect_queue.pop(0)
            self.ble_busy = True
            QTimer.singleShot(0, fn)
        else:
            self.ble_busy = False

    # -------------------- BUTTONS & LEFT MENU --------------------
    def btn_clicked(self):
        btn = SetupMainWindow.setup_btns(self)
        top_settings = MainFunctions.get_title_bar_btn(self, "btn_top_settings")
        top_settings.set_active(False)

        if btn.objectName() == "btn_home":
            self.ui.left_menu.select_only_one(btn.objectName())
            MainFunctions.set_page(self, self.ui.load_pages.page_01)

        elif btn.objectName() == "btn_subject_info":
            self.ui.left_menu.select_only_one(btn.objectName())
            MainFunctions.set_page(self, self.ui.load_pages.page_02)

        elif btn.objectName() == "btn_task_info":
            self.ui.left_menu.select_only_one(btn.objectName())
            MainFunctions.set_page(self, self.ui.load_pages.page_03)

        elif btn.objectName() == "btn_stimulation":
            self.ui.left_menu.select_only_one(btn.objectName())
            MainFunctions.set_page(self, self.ui.load_pages.page_05)

        elif btn.objectName() == "btn_save_load":
            if not MainFunctions.left_column_is_visible(self):
                self.ui.left_menu.select_only_one_tab(btn.objectName())
                MainFunctions.toggle_left_column(self)
            elif btn.is_active_tab():
                self.ui.left_menu.deselect_all_tab()
                MainFunctions.toggle_left_column(self)
            else:
                self.ui.left_menu.select_only_one_tab(btn.objectName())
            MainFunctions.set_left_column_menu(
                self, menu=self.ui.left_column.menus.menu_2, title="Save / Load",
                icon_path=Functions.set_svg_icon("icon_save_load.svg")
            )

        elif btn.objectName() == "btn_settings":
            if not MainFunctions.left_column_is_visible(self):
                self.ui.left_menu.select_only_one_tab(btn.objectName())
                MainFunctions.toggle_left_column(self)
            elif btn.is_active_tab():
                self.ui.left_menu.deselect_all_tab()
                MainFunctions.toggle_left_column(self)
            else:
                self.ui.left_menu.select_only_one_tab(btn.objectName())
            MainFunctions.set_left_column_menu(
                self, menu=self.ui.left_column.menus.menu_1, title="Settings Left Column",
                icon_path=Functions.set_svg_icon("icon_settings.svg")
            )

        elif btn.objectName() == "btn_close_left_column":
            self.ui.left_menu.deselect_all_tab()
            MainFunctions.toggle_left_column(self)

        elif btn.objectName() == "btn_top_settings":
            if not MainFunctions.right_column_is_visible(self):
                btn.set_active(True)
                MainFunctions.toggle_right_column(self)
            else:
                btn.set_active(False)
                MainFunctions.toggle_right_column(self)
            top_settings = MainFunctions.get_left_menu_btn(self, "btn_settings")
            top_settings.set_active_tab(False)

    def btn_released(self):
        pass

    # -------------------- WINDOW EVENTS --------------------
    def resizeEvent(self, event):
        SetupMainWindow.resize_grips(self)

    def mousePressEvent(self, event: QMouseEvent):
        self.dragPos = event.globalPosition().toPoint()

    def closeEvent(self, event):
        self.close_threads()
        if hasattr(self, "angle_calibrator"):
            self.angle_calibrator.stop()
        if self.stopwatch.isActive():
            self.stopwatch.stop()
        SetupMainWindow.close_processes(self)
        event.accept()

    # -------------------- THREAD MANAGEMENT --------------------
    def close_threads(self):
        for thread in [self.fsr_left_thread, self.fsr_right_thread, self.experiment_thread, self.ble_thread]:
            if thread is not None:
                thread.quit()
                thread.wait()
                thread.deleteLater()

    # -------------------- STEP COUNTER SLOTS -----------------
    @Slot(int)
    def on_step_count_changed(self, count: int):
        # Update Page 10 cell (if created in SetupMainWindow)
        if hasattr(self, "page10_step_counter_value") and self.page10_step_counter_value:
            self.page10_step_counter_value.setText(str(int(count)))

    @Slot(int)
    def on_left_step_count_changed(self, count: int):
        try:
            if hasattr(self, "page10_step_left_value") and self.page10_step_left_value:
                self.page10_step_left_value.setText(str(int(count)))
        except Exception:
            pass

    @Slot(int)
    def on_right_step_count_changed(self, count: int):
        try:
            if hasattr(self, "page10_step_right_value") and self.page10_step_right_value:
                self.page10_step_right_value.setText(str(int(count)))
        except Exception:
            pass

    # Keep backward-compat slots by forwarding to the unified ones
    @Slot(int)
    def on_imu_left_step_count_changed(self, count: int):
        self.on_left_step_count_changed(count)

    @Slot(int)
    def on_imu_right_step_count_changed(self, count: int):
        self.on_right_step_count_changed(count)

    @Slot(int)
    def on_fsr_left_step_count_changed(self, count: int):
        self.on_left_step_count_changed(count)

    @Slot(int)
    def on_fsr_right_step_count_changed(self, count: int):
        self.on_right_step_count_changed(count)

    # -------------------- Phase change SLOTS --------------------
    @Slot(int)
    def on_imu_left_phase_changed(self, val: int):
        try:
            name = Phase(val).name.replace("_", " ").title()
        except Exception:
            name = str(val)
        try:
            if hasattr(self, "phase_left_value_label") and self.phase_left_value_label:
                self.phase_left_value_label.setText(name)
        except Exception:
            pass
        # Update Page 10 Active Phase field if present
        try:
            if hasattr(self, "page10_phase_left_value") and self.page10_phase_left_value:
                self.page10_phase_left_value.setText(name)
        except Exception:
            pass

    @Slot(int)
    def on_imu_right_phase_changed(self, val: int):
        try:
            name = Phase(val).name.replace("_", " ").title()
        except Exception:
            name = str(val)
        try:
            if hasattr(self, "phase_right_value_label") and self.phase_right_value_label:
                self.phase_right_value_label.setText(name)
        except Exception:
            pass
        # Update Page 10 Active Phase field if present
        try:
            if hasattr(self, "page10_phase_right_value") and self.page10_phase_right_value:
                self.page10_phase_right_value.setText(name)
        except Exception:
            pass
    # -------------------- FSR DATA SLOTS --------------------
    def get_cop_coordinates(self):
        size = self.ui.load_pages.insole_size_combobox.currentText()
        if size == "S":
            return 8.7, 2.35, -7.9
        elif size == "M":
            return 9.05, 2.525, -9.1
        elif size == "L":
            return 9.35, 2.6, -10.4
        elif size == "XL":
            # TODO: replace with exact XL values once available
            return 9.35, 2.6, -10.4
        else:
            return 9.05, 2.525, -9.1

    @Slot(list)
    def update_fsr_data_left(self, data):
        self.ui.load_pages.ff_value_left.setText(str(data[0]))
        self.ui.load_pages.mf_value_left.setText(str(data[1]))
        self.ui.load_pages.bf_value_left.setText(str(data[2]))

        yff, ymf, ybf = self.get_cop_coordinates()
        ff, mf, bf = data[0], data[1], data[2]
        total_force = ff + mf + bf
        cop_y = (ff * yff + mf * ymf + bf * ybf) / total_force if total_force > 0 else 0.0
        extended_data = [float(ff), float(mf), float(bf), 0.0, float(cop_y)]

        if self.fsr_outlet_left:
            self.fsr_outlet_left.push_sample(extended_data)

    @Slot(list)
    def update_fsr_data_right(self, data):
        self.ui.load_pages.ff_value_right.setText(str(data[0]))
        self.ui.load_pages.mf_value_right.setText(str(data[1]))
        self.ui.load_pages.bf_value_right.setText(str(data[2]))

        yff, ymf, ybf = self.get_cop_coordinates()
        ff, mf, bf = data[0], data[1], data[2]
        total_force = ff + mf + bf
        cop_y = (ff * yff + mf * ymf + bf * ybf) / total_force if total_force > 0 else 0.0
        extended_data = [float(ff), float(mf), float(bf), 0.0, float(cop_y)]

        if self.fsr_outlet_right:
            self.fsr_outlet_right.push_sample(extended_data)

    @Slot(bool)
    def update_stream(self, connected: bool, side: str):
        if side == "left":
            self.left_connected_checkbox.setChecked(connected)
            if connected:
                self.fsr_outlet_left = pylsl.StreamOutlet(
                    pylsl.StreamInfo("FSR_Left", "Motion Data", 5, pylsl.IRREGULAR_RATE, pylsl.cf_float32)
                )
            else:
                self.fsr_outlet_left = None
        else:
            self.right_connected_checkbox.setChecked(connected)
            if connected:
                self.fsr_outlet_right = pylsl.StreamOutlet(
                    pylsl.StreamInfo("FSR_Right", "Motion Data", 5, pylsl.IRREGULAR_RATE, pylsl.cf_float32)
                )
            else:
                self.fsr_outlet_right = None

    # -------------------- FSR CONNECT/DISCONNECT --------------------
    def connect_left_fsr(self):
        self._enqueue_ble(lambda: self.connect_fsr_left_device.emit(DEVICE_ADDRESS_LEFT, self.ble_scanner.get_devices()))

    def connect_right_fsr(self):
        self._enqueue_ble(lambda: self.connect_fsr_right_device.emit(DEVICE_ADDRESS_RIGHT, self.ble_scanner.get_devices()))

    def disconnect_left_fsr(self):
        self.disconnect_fsr_left_device.emit()

    def disconnect_right_fsr(self):
        self.disconnect_fsr_right_device.emit()

    def scan_left_fsr(self):
        self._enqueue_ble(lambda: self.connect_fsr_left_device.emit("FSR_Left", self.ble_scanner.get_devices()))

    def scan_right_fsr(self):
        self._enqueue_ble(lambda: self.connect_fsr_right_device.emit("FSR_Right", self.ble_scanner.get_devices()))

    # -------------------- THREAD MANAGEMENT --------------------
    def close_threads(self):
        # Only stop experiment thread here; BLE runs in GUI thread now
        for thread in [self.experiment_thread]:
            if thread and thread.isRunning():
                thread.quit()
                thread.wait()
    # -------------------- STOPWATCH & TIMER --------------------
    @Slot()
    def start_timer(self):
        # Backend is source of truth → ensure local stopwatch is OFF
        try:
            if self.stopwatch.isActive():
                self.stopwatch.stop()
        except Exception:
            pass
        # Prevent later accidental starts
        try:
            if hasattr(self.stopwatch, "timeout"):
                self.stopwatch.stop()
        except Exception:
            pass

        self._paused = False
        self._elapsed_ms_before_pause = 0

        # Hide legacy label
        try:
            self.ui.load_pages.time_label.setVisible(False)
        except Exception:
            pass
        # Reset Page 10 display
        try:
            if hasattr(self, "page10_timer_value") and self.page10_timer_value is not None:
                self.page10_timer_value.setText("00:00:00")
        except Exception:
            pass

        # reset UI and visuals
        try:
            if hasattr(self, "page10_timer_value") and self.page10_timer_value is not None:
                self.page10_timer_value.setText("00:00:00")
        except Exception:
            pass
        # -- visual feedback: mark status/log frame as "running" (red border) --
        try:
            # store original style once
            if not hasattr(self, "_page10_status_log_frame_orig_style"):
                self._page10_status_log_frame_orig_style = self.page10_status_log_frame.styleSheet()

            # prefer theme color if available, fallback to hardcoded red
            try:
                red_color = self.themes["app_color"].get("red", "#C41E3A")
            except Exception:
                red_color = "#C41E3A"

            # try to reuse original stylesheet replacing the bg_two color if present
            try:
                new_style = self._page10_status_log_frame_orig_style.replace(
                    self.themes["app_color"]["bg_two"], red_color
                )
            except Exception:
                new_style = f"QFrame#page10_status_log_frame {{ border: 2px solid {red_color}; border-radius: 6px; }}"

            self.page10_status_log_frame.setStyleSheet(new_style)
        except Exception:
            # don't break timer on UI update failure
            pass
        # Mark experiment running
        self._experiment_running = True
        # Hard‑disable Pause for first 11 s
        try:
            if hasattr(self, "page10_pause_btn"):
                self.page10_pause_btn.setEnabled(False)
                self.page10_pause_btn.setText("Pause")
        except Exception:
            pass
        # Arm single-shot to re-enable after 11 s
        try:
            if self._pause_enable_delay.isActive():
                self._pause_enable_delay.stop()
            self._pause_enable_delay.start(11000)  # 11 seconds
        except Exception:
            pass

    @Slot()
    def update_time(self):
        if not self.stopwatch.isActive():
            raise RuntimeError("Stopwatch timer is not running")
        elapsed_time = self.start_time.secsTo(QTime.currentTime())
        hours = elapsed_time // 3600
        minutes = (elapsed_time % 3600) // 60
        seconds = elapsed_time % 60
        time_text = f"{hours:02}:{minutes:02}:{seconds:02}"
        # Update both the page label and Page 10 timer cell
        if hasattr(self, "page10_timer_value") and self.page10_timer_value is not None:
            self.page10_timer_value.setText(time_text)

    @staticmethod
    def _fmt_live_angle(val) -> str:
        """Format a calibrator angle (numpy scalar / array / float) as ``+12.3°`` or ``--``."""
        try:
            if val is None:
                return "--"
            if hasattr(val, "size") and val.size == 0:
                return "--"
            v = float(val.item()) if hasattr(val, "item") else float(val)
            return f"{v:+6.1f}°"
        except Exception:
            return "--"

    @Slot()
    def _update_page10_angle_readouts(self):
        """Refresh the live numeric readouts next to each Page-10 plot legend.

        Driven by ``page10_plot_timer`` at 20 Hz. Reads the latest angle samples
        from ``self.angle_calibrator`` and writes them into the small per-leg
        labels under the Knee/Ankle/Hip plots.  Silent on errors so a transient
        calibrator hiccup never breaks the timer chain.
        """
        cal = getattr(self, "angle_calibrator", None)
        if cal is None:
            return
        try:
            lk, rk = cal.get_latest_data()
            la, ra = cal.get_latest_ankle_data()
            lh, rh = cal.get_latest_hip_data()
            if hasattr(self, "page10_knee_lvalue"):
                self.page10_knee_lvalue.setText(self._fmt_live_angle(lk))
                self.page10_knee_rvalue.setText(self._fmt_live_angle(rk))
                self.page10_ankle_lvalue.setText(self._fmt_live_angle(la))
                self.page10_ankle_rvalue.setText(self._fmt_live_angle(ra))
                self.page10_hip_lvalue.setText(self._fmt_live_angle(lh))
                self.page10_hip_rvalue.setText(self._fmt_live_angle(rh))
        except Exception:
            pass

    @Slot(float)
    def on_active_run_seconds_changed(self, secs: float):
        # During pause backend stops emitting; no change shown
        total = int(secs)
        h = total // 3600
        m = (total % 3600) // 60
        s = total % 60
        text = f"{h:02}:{m:02}:{s:02}"
        try:
            if hasattr(self, "page10_timer_value") and self.page10_timer_value is not None:
                self.page10_timer_value.setText(text)
        except Exception:
            pass

    # -------------------- POST-TEST PLOT SAVE --------------------
    @Slot(tuple)
    def _save_plot_pkl_after_test(self, _results=None):
        """Dump the AngleCalibrator buffers next to the master .pkl, and
        write a companion ``<base>_plot.xlsx`` with the dense (60 Hz) joint
        angles. The stim-side ``<base>.xlsx`` pulls angles from the ROM
        objects which are only updated when the gait state machine needs
        them -- hip gets refreshed rarely, so its column in the stim xlsx
        is mostly empty. The plot xlsx fixes that by pulling from the
        AngleCalibrator buffers, where every joint is sampled at 60 Hz on
        a shared timer.
        """
        try:
            base_path = getattr(self, "_last_experiment_save_path", None)
            calibrator = getattr(self, "angle_calibrator", None)
            if not base_path or calibrator is None:
                return
            import os
            base_dir = os.path.dirname(base_path)
            base_name = os.path.splitext(os.path.basename(base_path))[0]
            plot_path  = os.path.join(base_dir, f"{base_name}_plot.pkl")
            xlsx_path  = os.path.join(base_dir, f"{base_name}_plot.xlsx")
            ok = calibrator.save_data(plot_path)
            if ok:
                print(f"Calibrator plot data saved to {plot_path}")
            else:
                print("Calibrator plot data NOT saved (see previous errors).")

            try:
                self._export_plot_xlsx(plot_path, xlsx_path)
                print(f"Dense joint-angle xlsx saved to {xlsx_path}")
            except Exception as ee:
                print(f"Failed to export plot xlsx: {ee}")
        except Exception as e:
            print(f"Failed to save calibrator plot pkl: {e}")

    @staticmethod
    def _export_plot_xlsx(plot_pkl_path: str, xlsx_path: str) -> None:
        """Read the calibrator plot pkl and write a 60 Hz joint-angle xlsx.

        Output sheets:
          - ``Joint_Angles_Native``: each joint at its native sample rate,
            with one timestamp column per joint (sparse columns padded with
            blanks).
          - ``Joint_Angles_Resampled``: every joint interpolated onto a
            single 60 Hz grid spanning the trial window; one row per
            timestamp; identical column lengths.
          - ``Raw_<segment>``: raw quaternion + accel + gyro logs.
          - ``Calibration``: offsets, SVD hinge axes, reference quaternions.
        """
        import pickle
        import numpy as np
        import pandas as pd

        with open(plot_pkl_path, "rb") as f:
            d = pickle.load(f)

        sheets: dict[str, pd.DataFrame] = {}

        # Native (per-joint) angle columns -- same shape as the historical
        # stim xlsx but populated from dense AngleCalibrator buffers.
        joint_keys = [
            ("LeftHip",    "left_hip_angles",    "left_hip_timestamps"),
            ("LeftKnee",   "left_knee_angles",   "left_knee_timestamps"),
            ("LeftAnkle",  "left_ankle_angles",  "left_ankle_timestamps"),
            ("RightHip",   "right_hip_angles",   "right_hip_timestamps"),
            ("RightKnee",  "right_knee_angles",  "right_knee_timestamps"),
            ("RightAnkle", "right_ankle_angles", "right_ankle_timestamps"),
        ]
        native_cols: dict[str, list] = {}
        max_len = 0
        for label, ang_k, ts_k in joint_keys:
            ang = np.asarray(d.get(ang_k, np.array([])))
            ts  = np.asarray(d.get(ts_k,  np.array([])))
            n   = min(ang.size, ts.size)
            native_cols[f"Timestamp_{label}"] = ts[:n].tolist()
            native_cols[f"{label}"]           = ang[:n].tolist()
            max_len = max(max_len, n)
        if max_len > 0:
            padded = {k: list(v) + [None] * (max_len - len(v))
                      for k, v in native_cols.items()}
            sheets["Joint_Angles_Native"] = pd.DataFrame(padded)

        # Resampled (uniform 60 Hz) angle columns -- one row per tick, every
        # joint interpolated to that tick. Solves the "hip column ends
        # early" complaint by giving every joint identical length.
        all_ts = []
        for _, _, ts_k in joint_keys:
            ts = np.asarray(d.get(ts_k, np.array([])))
            if ts.size > 0:
                all_ts.append(ts)
        if all_ts:
            t_lo = min(float(a.min()) for a in all_ts)
            t_hi = max(float(a.max()) for a in all_ts)
            grid = np.arange(t_lo, t_hi, 1.0 / 60.0)
            resampled: dict[str, list] = {"Timestamp": grid.tolist()}
            for label, ang_k, ts_k in joint_keys:
                ang = np.asarray(d.get(ang_k, np.array([])))
                ts  = np.asarray(d.get(ts_k,  np.array([])))
                n   = min(ang.size, ts.size)
                if n < 2 or (ts[:n].max() - ts[:n].min()) <= 0:
                    resampled[label] = [None] * grid.size
                    continue
                # Mask grid points outside the joint's recorded window so we
                # don't fabricate extrapolated angles.
                in_window = (grid >= ts[:n].min()) & (grid <= ts[:n].max())
                col = np.full(grid.size, np.nan)
                col[in_window] = np.interp(grid[in_window], ts[:n], ang[:n])
                resampled[label] = [None if np.isnan(v) else float(v) for v in col]
            # ``is_walking`` flag = 1 inside the detected walk window (between
            # shank-gyro motion-on and motion-off), 0 during pre-walk standing
            # / post-walk standing. Lets the analyst filter the resampled rows
            # to the walking-only window without touching the timestamps.
            ws = d.get("walk_start_ts"); we = d.get("walk_end_ts")
            if ws is not None and we is not None:
                resampled["is_walking"] = ((grid >= ws) & (grid <= we)).astype(int).tolist()
            else:
                resampled["is_walking"] = [0] * grid.size
            sheets["Joint_Angles_Resampled"] = pd.DataFrame(resampled)

        # Raw per-segment IMU logs.
        for seg in ("pelvis", "left_thigh", "left_shank", "left_foot",
                    "right_thigh", "right_shank", "right_foot"):
            q  = np.asarray(d.get(f"raw_{seg}_quat",       np.empty((0, 4))))
            ts = np.asarray(d.get(f"raw_{seg}_timestamps", np.empty((0,))))
            if q.size == 0 or ts.size == 0:
                continue
            n = min(q.shape[0], ts.size)
            cols = {
                "Timestamp": ts[:n].tolist(),
                "QuatW": q[:n, 0].tolist(),
                "QuatX": q[:n, 1].tolist(),
                "QuatY": q[:n, 2].tolist(),
                "QuatZ": q[:n, 3].tolist(),
            }
            sheets[f"Raw_{seg}"[:31]] = pd.DataFrame(cols)

        # Calibration metadata so the offline analyst knows whether each
        # joint actually used the SVD hinge path or fell back to cardinal.
        calib_rows = []
        for j in ("left_hip", "right_hip", "left_knee", "right_knee",
                  "left_ankle", "right_ankle"):
            off  = d.get(f"{j}_offset", None)
            hinge = d.get(f"{j}_hinge_axis", None)
            if "knee" in j:
                ref_p = d.get(f"{j.split('_')[0]}_knee_qthigh_ref")
                ref_d = d.get(f"{j.split('_')[0]}_knee_qshank_ref")
            elif "hip" in j:
                ref_p = d.get(f"{j.split('_')[0]}_hip_qpelvis_ref")
                ref_d = d.get(f"{j.split('_')[0]}_hip_qthigh_ref")
            else:  # ankle
                ref_p = d.get(f"{j.split('_')[0]}_ankle_qshank_ref")
                ref_d = d.get(f"{j.split('_')[0]}_ankle_qfoot_ref")
            method = "SVD" if (ref_p is not None and ref_d is not None
                               and hinge is not None) else "CARD"
            calib_rows.append({
                "joint": j,
                "method": method,
                "offset_deg": float(off) if off is not None else None,
                "hinge_axis": (np.array(hinge).tolist()
                               if hinge is not None else None),
                "qref_proximal": (np.array(ref_p).tolist()
                                  if ref_p is not None else None),
                "qref_distal":   (np.array(ref_d).tolist()
                                  if ref_d is not None else None),
            })
        sheets["Calibration"] = pd.DataFrame(calib_rows)

        # ``Walk_Window`` sheet: motion-on / motion-off markers detected by
        # the AngleCalibrator (shank gyro magnitude > 30 deg/s, held 0.4 s).
        # All recorded samples are still in the workbook -- this sheet just
        # tells the analyst which time range was actual walking vs pre/post
        # standing.
        walk_rows = [{
            "side":            "global",
            "walk_start_ts":   d.get("walk_start_ts"),
            "walk_end_ts":     d.get("walk_end_ts"),
            "walk_duration_s": d.get("walk_duration_s"),
        }]
        for side in ("right", "left"):
            walk_rows.append({
                "side":            side,
                "walk_start_ts":   d.get(f"walk_start_ts_{side}"),
                "walk_end_ts":     d.get(f"walk_end_ts_{side}"),
                "walk_duration_s": d.get(f"walk_duration_s_{side}"),
            })
        params = d.get("walk_detect_params") or {}
        for k, v in params.items():
            walk_rows.append({"side": f"param:{k}", "walk_start_ts": v,
                              "walk_end_ts": None, "walk_duration_s": None})
        sheets["Walk_Window"] = pd.DataFrame(walk_rows)

        with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
            for name, df in sheets.items():
                df.to_excel(writer, sheet_name=name[:31], index=False)

    # -------------------- EXPERIMENT RESULTS --------------------
    @Slot(tuple)
    def show_results(self, results: tuple[dict[str, int], dict[str, int], dict[str, int], dict[str, int]]):
        if not results:
            QMessageBox.information(self, "Experiment Results", "No results to display.")
            return
         # Handle dict or tuple
        if isinstance(results, dict):
            # Show all key-value pairs in a single column
            for phase, count in results.items():
                line_edit = SetupMainWindow.create_std_line_edit(self.themes, f"{phase}: {count}")
                line_edit.setReadOnly(True)
                line_edit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                self.ui.load_pages.phase_right_layout.addWidget(line_edit)
            return
        for phase, count in results[0].items():
            line_edit = SetupMainWindow.create_std_line_edit(self.themes, f"{phase}: {count}")
            line_edit.setReadOnly(True)
            line_edit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.ui.load_pages.phase_right_layout.addWidget(line_edit)
        for phase, count in results[1].items():
            line_edit = SetupMainWindow.create_std_line_edit(self.themes, f"{phase}: {count}")
            line_edit.setReadOnly(True)
            line_edit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.ui.load_pages.subphase_right_layout.addWidget(line_edit)
        for phase, count in results[2].items():
            line_edit = SetupMainWindow.create_std_line_edit(self.themes, f"{phase}: {count}")
            line_edit.setReadOnly(True)
            line_edit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.ui.load_pages.phase_left_layout.addWidget(line_edit)
        for phase, count in results[3].items():
            line_edit = SetupMainWindow.create_std_line_edit(self.themes, f"{phase}: {count}")
            line_edit.setReadOnly(True)
            line_edit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.ui.load_pages.subphase_left_layout.addWidget(line_edit)
        self.ui.load_pages.pages.setCurrentWidget(self.ui.load_pages.page_07)
        self.ui.left_menu.deselect_all()
        self.ui.left_menu.top_frame.setEnabled(False)

    @Slot(str)
    def error_handler(self, message: str):
        QMessageBox.critical(self, "Experiment Error", message)
        self.stop_clicked()

    @Slot(str)
    def update_status(self, status):
        self.fsr_status_box.append(status)

    def stop_clicked(self):
        self.ui.load_pages.stop_btn_widget.setVisible(False)
        self.ui.load_pages.start_btn_widget.setVisible(True)
        self.ui.load_pages.selection_btn_widget.setVisible(True)
        self.ui.load_pages.stimulator_frame.setVisible(True)
        if self.stopwatch.isActive():
            self.stopwatch.stop()
            self.ui.load_pages.time_label.setText("00:00:00")
        self.ui.load_pages.time_label.setVisible(False)
        self.ui.left_menu.top_frame.setVisible(True)
        self.ui.load_pages.title_label.setText(self.title_label)
        # Ensure GUI stopwatch fully stopped
        try:
            if self.stopwatch.isActive():
                self.stopwatch.stop()
        except Exception:
            pass
        try:
            self.ui.load_pages.time_label.setVisible(False)
        except Exception:
            pass
        try:
            if hasattr(self, "page10_timer_value") and self.page10_timer_value is not None:
                self.page10_timer_value.setText("00:00:00")
        except Exception:
            pass
        # Restore the original status/log frame style
        try:
            if hasattr(self, "_page10_status_log_frame_orig_style"):
                self.page10_status_log_frame.setStyleSheet(self._page10_status_log_frame_orig_style)
        except Exception:
            pass
        # Reset Pause button
        try:
            self._paused = False
            self._elapsed_ms_before_pause = 0
            self.page10_pause_btn.setEnabled(False)
            self.page10_pause_btn.setText("Pause")
        except Exception:
            pass
        # Clear running flag and cancel pause delay timer
        try:
            self._experiment_running = False
            if self._pause_enable_delay.isActive():
                self._pause_enable_delay.stop()
        except Exception:
            pass
        # Stop experiment
        self.stop_experiment.emit()

    @Slot()
    def pause_clicked(self):
        if not hasattr(self, "page10_pause_btn"):
            return
        if not getattr(self, "_paused", False):
            self._paused = True
            try:
                self.page10_pause_btn.setText("Resume")
                self.page10_log_box.append("Paused.")
            except Exception:
                pass
            # HARD stop GUI stopwatch to avoid updates
            try:
                if self.stopwatch.isActive():
                    self.stopwatch.stop()
            except Exception:
                pass
            self.pause_experiment.emit()
        else:
            self._paused = False
            try:
                self.page10_pause_btn.setText("Pause")
                self.page10_log_box.append("Resumed.")
            except Exception:
                pass
            # DO NOT restart GUI stopwatch (backend handles time)
            self.resume_experiment.emit()

    @Slot()
    def _enable_page10_pause_btn(self):
        """Enable the Pause button after the 11 s lockout if experiment still running."""
        if not self._experiment_running:
            return
        try:
            if hasattr(self, "page10_pause_btn"):
                self.page10_pause_btn.setEnabled(True)
        except Exception:
            pass
