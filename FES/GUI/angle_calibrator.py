from collections import deque
from pylsl import StreamInlet, resolve_byprop
from qt_core import *
from enum import Enum
import numpy as np
from stimulator.closed_loop import ROM, TIME_TOLERANCE, sensor_axes_diagnostic
import time
from typing import Optional

TIMEOUT = 3.0  # seconds
MAX_BUFFER = 5000  # max samples kept in memory per channel (≈50 s at 100 Hz)


class CalibrationStep(Enum):
    READY = 0
    NEUTRAL_POSE = 1
    COLLECT_DATA = 2


class SIDE(Enum):
    LEFT = 0
    RIGHT = 1
    NONE = 2


class AngleCalibrator(QObject):
    message_signal = Signal(str)
    error_signal = Signal(str)
    # Carries HTML-formatted diagnostic lines for display in the status box
    diagnostic_signal = Signal(str)
    # Emitted once when calibration completes — HTML banner with offset values
    calibration_done_signal = Signal(str)
    # Emitted with full axis diagnostic — connects to a dedicated popup window
    axis_diagnostic_signal = Signal(str)

    def __init__(self, left_checkbox: QCheckBox, right_checkbox: QCheckBox, extension_target_left: QSpinBox, extension_target_right: QSpinBox, parent=None):
        super().__init__(parent)
        self.left_checkbox = left_checkbox
        self.right_checkbox = right_checkbox
        self.extension_target_left = extension_target_left
        self.extension_target_right = extension_target_right
        self.calibration_step = CalibrationStep.READY
        self.left_shank_inlet = None
        self.right_shank_inlet = None
        self.left_thigh_inlet = None
        self.right_thigh_inlet = None
        self.left_foot_inlet = None
        self.right_foot_inlet = None
        self.left_angle_data = np.array([])
        self.right_angle_data = np.array([])
        self.left_ankle_data = np.array([])
        self.right_ankle_data = np.array([])

        # Timestamps (wall-clock seconds, time.time()) aligned sample-by-sample
        # with the four angle arrays above.  Populated in record_data.
        self.left_angle_timestamps  = np.array([])
        self.right_angle_timestamps = np.array([])
        self.left_ankle_timestamps  = np.array([])
        self.right_ankle_timestamps = np.array([])

        # Session bookkeeping
        self._session_start: float | None = None

        self.left_angle_offset = 0.0
        self.right_angle_offset = 0.0
        self.left_ankle_offset = 0.0
        self.right_ankle_offset = 0.0

        # Setup timer — 20 ms (50 Hz) so the buffer fills fast enough
        # for the 50 ms plot refresh to always have fresh data.
        self.timer = QTimer(self)
        self.timer.setInterval(20)
        self.timer.timeout.connect(self.record_data)

        # ── Per-inlet sample counters for diagnostic rate measurement ──
        # Each entry is [total_samples_in_window, last_chunk_timestamp]
        self._diag: dict[str, dict] = {
            name: {"count": 0, "last_ts": 0.0, "sync_gap_sum": 0.0, "sync_gap_n": 0}
            for name in ("left_shank", "left_thigh", "left_foot",
                          "right_shank", "right_thigh", "right_foot")
        }

        # ── Per-inlet accumulation buffers ────────────────────────────────────
        # BLE delivers shank and foot samples at different host-clock times.
        # Accumulating independently and matching when both have data ensures we
        # never miss a pair just because they didn't arrive in the same 20 ms tick.
        # Max 300 samples ≈ 3 s at 100 Hz — enough headroom without memory risk.
        _BUF = 300
        self._acc = {
            name: deque(maxlen=_BUF)
            for name in ("left_thigh", "left_shank", "left_foot",
                          "right_thigh", "right_shank", "right_foot")
        }

        # Diagnostic timer — fires every 2 s, reads the counters and emits
        self._diag_timer = QTimer(self)
        self._diag_timer.setInterval(2000)
        self._diag_timer.timeout.connect(self._run_diagnostics)

        # Setup thread for resolving streams
        self.stream_resolver = LSLStreamResolver()
        self.worker_thread: Optional[QThread] = None
        self.stream_resolver.found_inlets.connect(self.handle_found_inlets)
        self.stream_resolver.message_signal.connect(self.message_signal.emit)
        self.resolving = SIDE.NONE

    def has_any_sensor(self) -> bool:
        """Return True if at least one sensor pair is connected."""
        left_knee = self.left_shank_inlet is not None and self.left_thigh_inlet is not None
        right_knee = self.right_shank_inlet is not None and self.right_thigh_inlet is not None
        left_ankle = self.left_shank_inlet is not None and self.left_foot_inlet is not None
        right_ankle = self.right_shank_inlet is not None and self.right_foot_inlet is not None
        return left_knee or right_knee or left_ankle or right_ankle

    def stop(self):
        """Stop the angle calibration and disconnect from all streams."""
        self.timer.stop()
        self._diag_timer.stop()
        if self.left_shank_inlet:
            self.__disconnect_from_streams_left()
        if self.right_shank_inlet:
            self.__disconnect_from_streams_right()
        if self.worker_thread:
            # If a worker thread is running, stop it
            self.worker_thread.quit()
            self.worker_thread.wait()
            self.worker_thread.deleteLater()
        self.message_signal.emit("Angle calibration stopped (knee + ankle).")

    def calibration(self):
        """Single-press calibration: reads current sensor pose as the zero reference."""
        # Guard: refuse if no sensors are connected
        if not self.has_any_sensor():
            self.error_signal.emit("Calibration failed: no sensors connected.")
            return

        if self.calibration_step == CalibrationStep.COLLECT_DATA:
            self.message_signal.emit("Calibration already in progress, please wait...")
            return

        # Disable toggles while calibrating
        self.__set_checkboxes_enabled(False)
        self.calibration_step = CalibrationStep.COLLECT_DATA
        self.diagnostic_signal.emit(
            '<p style="color:#f39c12; font-weight:bold;">'
            '&#9203; Calibrating&hellip; Please stand still in neutral position.</p>'
        )
        QCoreApplication.processEvents()  # let the UI show the message immediately

        # Run the functional calibration (reads current pose as offset)
        self.__functional_calibration()

        # Re-enable toggles
        self.calibration_step = CalibrationStep.READY
        self.__set_checkboxes_enabled(True)

        # Build a clear success banner with the actual offset values
        kl, kr = self.left_angle_offset, self.right_angle_offset
        al, ar = self.left_ankle_offset, self.right_ankle_offset
        banner = (
            '<hr/>'
            '<p style="color:#27ae60; font-size:13px; font-weight:bold;">'
            '&#10003;&#10003; OFFSET CALIBRATION COMPLETED SUCCESSFULLY &#10003;&#10003;</p>'
            '<table style="color:#ecf0f1; font-family:monospace;">'
            f'<tr><td>Knee &nbsp;Left&nbsp;</td><td><b>{kl:+.2f}&deg;</b></td></tr>'
            f'<tr><td>Knee &nbsp;Right</td><td><b>{kr:+.2f}&deg;</b></td></tr>'
            f'<tr><td>Ankle Left&nbsp;</td><td><b>{al:+.2f}&deg;</b></td></tr>'
            f'<tr><td>Ankle Right</td><td><b>{ar:+.2f}&deg;</b></td></tr>'
            '</table><hr/>'
        )
        self.calibration_done_signal.emit(banner)


    def get_offset(self) -> tuple[float, float]:
        """Return the knee angle offsets for both legs.

        :return: Left and right knee angle offsets
        :rtype: tuple[float, float]
        """
        return self.left_angle_offset, self.right_angle_offset

    def get_ankle_offset(self) -> tuple[float, float]:
        """Return the ankle angle offsets for both legs.

        :return: Left and right ankle angle offsets
        :rtype: tuple[float, float]
        """
        return self.left_ankle_offset, self.right_ankle_offset

    def get_ankle_reference(self):
        """Return the calibration quaternions (q_shank_ref, q_foot_ref) for each leg.

        Used to pass the reference quaternions to ROM.set_ankle_reference() so that
        the stable relative-quaternion ankle angle algorithm can be used at runtime.

        :return: (left_qs, left_qf, right_qs, right_qf) or (None, None, None, None)
                 when no ankle calibration has been performed yet.
        """
        left_qs  = getattr(self, 'left_ankle_qshank_ref',  None)
        left_qf  = getattr(self, 'left_ankle_qfoot_ref',   None)
        right_qs = getattr(self, 'right_ankle_qshank_ref', None)
        right_qf = getattr(self, 'right_ankle_qfoot_ref',  None)
        return left_qs, left_qf, right_qs, right_qf

    def get_angle_data(self) -> tuple[np.ndarray, np.ndarray]:
        """Return the knee angle data for both legs.

        :return: Left and right knee angle data
        :rtype: tuple[np.ndarray, np.ndarray]
        """
        return self.left_angle_data, self.right_angle_data

    def get_ankle_data(self) -> tuple[np.ndarray, np.ndarray]:
        """Return the ankle angle data for both legs.

        :return: Left and right ankle angle data
        :rtype: tuple[np.ndarray, np.ndarray]
        """
        return self.left_ankle_data, self.right_ankle_data

    def get_latest_data(self) -> tuple[np.ndarray, np.ndarray]:
        """Return the latest knee angle data for both legs.

        :return: Latest left and right knee angle data
        :rtype: tuple[np.ndarray, np.ndarray]
        """
        left_angle = self.left_angle_data[-1] if self.left_angle_data.size > 0 else np.array([])
        right_angle = self.right_angle_data[-1] if self.right_angle_data.size > 0 else np.array([])
        return left_angle, right_angle

    def get_latest_ankle_data(self) -> tuple[np.ndarray, np.ndarray]:
        """Return the latest ankle angle data for both legs.

        :return: Latest left and right ankle angle data
        :rtype: tuple[np.ndarray, np.ndarray]
        """
        left_ankle = self.left_ankle_data[-1] if self.left_ankle_data.size > 0 else np.array([])
        right_ankle = self.right_ankle_data[-1] if self.right_ankle_data.size > 0 else np.array([])
        return left_ankle, right_ankle

    @Slot(bool)
    def handle_left_inlet(self, checked: bool):
        if checked:
            self.message_signal.emit("Connecting to left leg sensors...")
            self.__connect_to_streams_for_left()
            # Disable only the Left checkbox during connection
            self.left_checkbox.setEnabled(False)
        else:
            self.message_signal.emit("Disconnecting from left leg sensors...")
            self.__disconnect_from_streams_left()
            # Stop the timer if both checkboxes are unchecked
            if not self.right_checkbox.isChecked():
                self.timer.stop()

    @Slot(bool)
    def handle_right_inlet(self, checked: bool):
        if checked:
            self.message_signal.emit("Connecting to right leg sensors...")
            self.__connect_to_streams_for_right()
            # Disable only the Right checkbox during connection
            self.right_checkbox.setEnabled(False)
        else:
            self.message_signal.emit("Disconnecting from right leg sensors...")
            self.__disconnect_from_streams_right()
            # Stop the timer if both checkboxes are unchecked
            if not self.left_checkbox.isChecked():
                self.timer.stop()

    @Slot()
    def record_data(self):
        """Accumulate raw samples from every inlet and drain matched pairs.

        Each inlet has an independent ``deque`` (``self._acc[key]``).  New samples
        are appended on every 20 ms tick.  Angle computation only runs when BOTH
        paired inlets have data — but because the deques persist between ticks, a
        sample that arrived without its partner will still be used on the next tick.

        Shank data is needed for BOTH knee (thigh↔shank) and ankle (shank↔foot).
        To avoid double-consuming the deque, we keep a **separate copy** of the
        shank samples drained for knee matching and reuse them for ankle matching.
        """
        now = time.time()

        # ── 1. Pull each inlet once and push into accumulation deques ──────────
        for inlet, key in (
            (self.left_thigh_inlet,  "left_thigh"),
            (self.left_shank_inlet,  "left_shank"),
            (self.left_foot_inlet,   "left_foot"),
            (self.right_thigh_inlet, "right_thigh"),
            (self.right_shank_inlet, "right_shank"),
            (self.right_foot_inlet,  "right_foot"),
        ):
            if inlet is None:
                continue
            samples, _ = inlet.pull_chunk(timeout=0.0, max_samples=128)
            if samples:
                self._acc[key].extend(samples)
                self._diag[key]["count"]  += len(samples)
                self._diag[key]["last_ts"] = now

        # ── 2. helper: drain N matched pairs from two deques ───────────────────
        def _drain_pairs(deq_a, deq_b):
            """Pop min(len(a), len(b)) items from both deques and return as lists."""
            n = min(len(deq_a), len(deq_b))
            a = [deq_a.popleft() for _ in range(n)]
            b = [deq_b.popleft() for _ in range(n)]
            return a, b

        # ── 3. Knee LEFT: thigh ↔ shank ────────────────────────────────────────
        if self.left_thigh_inlet and self.left_shank_inlet:
            l_thigh_s, l_shank_for_knee = _drain_pairs(
                self._acc["left_thigh"], self._acc["left_shank"]
            )
            angles = self.__compute_angles_from_data(
                l_thigh_s, [], l_shank_for_knee, [],
                self.left_angle_offset, self._diag["left_thigh"],
            )
            self.left_angle_data = np.append(self.left_angle_data, angles)
            if len(angles):
                self.left_angle_timestamps = np.append(
                    self.left_angle_timestamps,
                    np.full(len(angles), now)
                )

            # Ankle LEFT: re-use the same shank samples (already drained from deque)
            if self.left_foot_inlet:
                n_ankle = min(len(l_shank_for_knee), len(self._acc["left_foot"]))
                l_foot_s = [self._acc["left_foot"].popleft() for _ in range(n_ankle)]
                ankle_angles = self.__compute_angles_from_data(
                    l_shank_for_knee[:n_ankle], [], l_foot_s, [],
                    self.left_ankle_offset, self._diag["left_shank"],
                )
                self.left_ankle_data = np.append(self.left_ankle_data, ankle_angles)
                if len(ankle_angles):
                    self.left_ankle_timestamps = np.append(
                        self.left_ankle_timestamps,
                        np.full(len(ankle_angles), now)
                    )

        elif self.left_shank_inlet and self.left_foot_inlet:
            # No thigh — only ankle
            l_shank_s, l_foot_s = _drain_pairs(
                self._acc["left_shank"], self._acc["left_foot"]
            )
            ankle_angles = self.__compute_angles_from_data(
                l_shank_s, [], l_foot_s, [],
                self.left_ankle_offset, self._diag["left_shank"],
            )
            self.left_ankle_data = np.append(self.left_ankle_data, ankle_angles)
            if len(ankle_angles):
                self.left_ankle_timestamps = np.append(
                    self.left_ankle_timestamps,
                    np.full(len(ankle_angles), now)
                )

        # ── 4. Knee RIGHT: thigh ↔ shank ───────────────────────────────────────
        if self.right_thigh_inlet and self.right_shank_inlet:
            r_thigh_s, r_shank_for_knee = _drain_pairs(
                self._acc["right_thigh"], self._acc["right_shank"]
            )
            angles = self.__compute_angles_from_data(
                r_thigh_s, [], r_shank_for_knee, [],
                self.right_angle_offset, self._diag["right_thigh"],
            )
            self.right_angle_data = np.append(self.right_angle_data, angles)
            if len(angles):
                self.right_angle_timestamps = np.append(
                    self.right_angle_timestamps,
                    np.full(len(angles), now)
                )

            # Ankle RIGHT: re-use the same shank samples
            if self.right_foot_inlet:
                n_ankle = min(len(r_shank_for_knee), len(self._acc["right_foot"]))
                r_foot_s = [self._acc["right_foot"].popleft() for _ in range(n_ankle)]
                ankle_angles = self.__compute_angles_from_data(
                    r_shank_for_knee[:n_ankle], [], r_foot_s, [],
                    self.right_ankle_offset, self._diag["right_shank"],
                )
                self.right_ankle_data = np.append(self.right_ankle_data, ankle_angles)
                if len(ankle_angles):
                    self.right_ankle_timestamps = np.append(
                        self.right_ankle_timestamps,
                        np.full(len(ankle_angles), now)
                    )

        elif self.right_shank_inlet and self.right_foot_inlet:
            # No thigh — only ankle
            r_shank_s, r_foot_s = _drain_pairs(
                self._acc["right_shank"], self._acc["right_foot"]
            )
            ankle_angles = self.__compute_angles_from_data(
                r_shank_s, [], r_foot_s, [],
                self.right_ankle_offset, self._diag["right_shank"],
            )
            self.right_ankle_data = np.append(self.right_ankle_data, ankle_angles)
            if len(ankle_angles):
                self.right_ankle_timestamps = np.append(
                    self.right_ankle_timestamps,
                    np.full(len(ankle_angles), now)
                )

        if self.left_angle_data.size > MAX_BUFFER:
            self.left_angle_data       = self.left_angle_data[-MAX_BUFFER:]
            self.left_angle_timestamps = self.left_angle_timestamps[-MAX_BUFFER:]
        if self.right_angle_data.size > MAX_BUFFER:
            self.right_angle_data       = self.right_angle_data[-MAX_BUFFER:]
            self.right_angle_timestamps = self.right_angle_timestamps[-MAX_BUFFER:]
        if self.left_ankle_data.size > MAX_BUFFER:
            self.left_ankle_data       = self.left_ankle_data[-MAX_BUFFER:]
            self.left_ankle_timestamps = self.left_ankle_timestamps[-MAX_BUFFER:]
        if self.right_ankle_data.size > MAX_BUFFER:
            self.right_ankle_data       = self.right_ankle_data[-MAX_BUFFER:]
            self.right_ankle_timestamps = self.right_ankle_timestamps[-MAX_BUFFER:]


    def save_data(self, path: str) -> bool:
        """Save all angle data and metadata to a .pkl file.

        The file contains a single dict with keys:

        Angles (numpy arrays, degrees)
        ──────────────────────────────
        left_knee_angles, right_knee_angles   — knee flexion/extension
        left_ankle_angles, right_ankle_angles — ankle dorsi/plantar-flexion

        Timestamps (numpy arrays, wall-clock seconds from time.time())
        ──────────────────────────────────────────────────────────────
        left_knee_timestamps, right_knee_timestamps
        left_ankle_timestamps, right_ankle_timestamps

        Calibration
        ───────────
        left_knee_offset, right_knee_offset   — subtracted angle at neutral pose
        left_ankle_offset, right_ankle_offset

        Session metadata
        ────────────────
        session_start_unix, session_end_unix  — float seconds
        session_start_iso, session_end_iso    — ISO-8601 strings
        session_duration_s                    — total wall-clock seconds

        :param path: Full path to destination file (should end in .pkl).
        :returns: True on success, False on IOError.
        """
        import pickle
        from datetime import datetime

        now = time.time()
        start = self._session_start if self._session_start is not None else now

        def _iso(ts):
            return datetime.fromtimestamp(ts).isoformat(timespec="seconds")

        data = {
            # ── Angles ───────────────────────────────────────────────────────
            "left_knee_angles":    self.left_angle_data.copy(),
            "right_knee_angles":   self.right_angle_data.copy(),
            "left_ankle_angles":   self.left_ankle_data.copy(),
            "right_ankle_angles":  self.right_ankle_data.copy(),
            # ── Timestamps ───────────────────────────────────────────────────
            "left_knee_timestamps":   self.left_angle_timestamps.copy(),
            "right_knee_timestamps":  self.right_angle_timestamps.copy(),
            "left_ankle_timestamps":  self.left_ankle_timestamps.copy(),
            "right_ankle_timestamps": self.right_ankle_timestamps.copy(),
            # ── Calibration offsets ──────────────────────────────────────────
            "left_knee_offset":   self.left_angle_offset,
            "right_knee_offset":  self.right_angle_offset,
            "left_ankle_offset":  self.left_ankle_offset,
            "right_ankle_offset": self.right_ankle_offset,
            # ── Session metadata ─────────────────────────────────────────────
            "session_start_unix": start,
            "session_end_unix":   now,
            "session_start_iso":  _iso(start),
            "session_end_iso":    _iso(now),
            "session_duration_s": now - start,
        }
        try:
            with open(path, "wb") as f:
                pickle.dump(data, f)
            return True
        except Exception as e:
            print(f"[AngleCalibrator] save_data failed: {e}")
            return False


    @Slot(tuple)
    def handle_found_inlets(self, inlets: tuple):
        """Handle the found inlets from the stream resolver.
        inlets is a tuple of (shank_inlet, thigh_inlet, foot_inlet).
        foot_inlet may be None if no foot IMU is available.
        """
        # Clean up the worker thread
        self.worker_thread.quit()
        self.worker_thread.wait()
        self.worker_thread.deleteLater()
        self.worker_thread = None
        
        # Re-enable the checkbox that was being connected
        if self.resolving == SIDE.LEFT:
            self.left_checkbox.setEnabled(True)
        elif self.resolving == SIDE.RIGHT:
            self.right_checkbox.setEnabled(True)

        if inlets[0] is None or inlets[1] is None:
            # Connection failed — uncheck the toggle that was trying to connect
            self.error_signal.emit("Connection failed: sensors not found.")
            if self.resolving == SIDE.LEFT:
                self.left_checkbox.setChecked(False)
            elif self.resolving == SIDE.RIGHT:
                self.right_checkbox.setChecked(False)
            self.resolving = SIDE.NONE
            return

        # Extract foot inlet (may be None)
        foot_inlet = inlets[2] if len(inlets) > 2 else None

        if self.resolving == SIDE.LEFT:
            # Store the inlets and start the timer
            self.left_shank_inlet, self.left_thigh_inlet = inlets[0], inlets[1]
            self.left_foot_inlet = foot_inlet
            self.message_signal.emit("Left leg streams connected successfully.")
            if foot_inlet:
                self.message_signal.emit("Left foot IMU connected (ankle angle enabled).")
            else:
                self.message_signal.emit("Left foot IMU not found (ankle angle disabled).")
            self.timer.start()
            self.start_diagnostics()   # start live stream-quality monitor

        elif self.resolving == SIDE.RIGHT:
            # Store the inlets and start the timer
            self.right_shank_inlet, self.right_thigh_inlet = inlets[0], inlets[1]
            self.right_foot_inlet = foot_inlet
            self.message_signal.emit("Right leg streams connected successfully.")
            if foot_inlet:
                self.message_signal.emit("Right foot IMU connected (ankle angle enabled).")
            else:
                self.message_signal.emit("Right foot IMU not found (ankle angle disabled).")
            self.timer.start()
            self.start_diagnostics()   # start live stream-quality monitor

        self.resolving = SIDE.NONE


    ################################
    """ PRIVATE METHODS """
    ################################

    # --------------------
    # Calibration Methods
    # --------------------

    def __start_calibration(self):
        #--------------OLD VERSION-------------
        # If neither is checked, ask the user to check at least one and try again
        # if not self.left_checkbox.isChecked() and not self.right_checkbox.isChecked():
        #     self.message_signal.emit("Please select at least one leg for calibration.")
        #     # Re-enable the checkboxes
        #     self.__set_checkboxes_enabled(True)
        #     return

        # # Connect to lsl streams if the inlets are not already connected
        # if (self.left_shank_inlet is None or self.left_thigh_inlet is None) and self.left_checkbox.isChecked():
        #     self.message_signal.emit("Connecting to left leg streams...")
        #     self.__connect_to_streams_for_left()
        #     # Stop if no streams are found
        #     if self.left_shank_inlet is None or self.left_thigh_inlet is None:
        #         self.__set_checkboxes_enabled(True)
        #         return
        # if (self.right_shank_inlet is None or self.right_thigh_inlet is None) and self.right_checkbox.isChecked():
        #     self.message_signal.emit("Connecting to right leg streams...")
        #     self.__connect_to_streams_for_right()
        #     # Stop if no streams are found
        #     if self.right_shank_inlet is None or self.right_thigh_inlet is None:
        #         self.__set_checkboxes_enabled(True)
        #         return

        # # Else ask the user to stand in neutral position and press "Calibrate Offset" once ready
        # self.message_signal.emit("Please stand in a neutral position and press 'Calibrate Offset' when ready.")
        # self.calibration_step = CalibrationStep.NEUTRAL_POSE
        
        if self.left_checkbox.isChecked() and (self.left_shank_inlet is None or self.left_thigh_inlet is None):
            self.message_signal.emit("Connecting to left leg streams...")
            self.__connect_to_streams_for_left()

        if self.right_checkbox.isChecked() and (self.right_shank_inlet is None or self.right_thigh_inlet is None):
            self.message_signal.emit("Connecting to right leg streams...")
            self.__connect_to_streams_for_right()

        # Don't block — let handle_found_inlets start the timer when ready
        self.message_signal.emit("Please stand in a neutral position and press 'Calibrate Offset' when ready.")
        self.calibration_step = CalibrationStep.NEUTRAL_POSE


    # def __functional_calibration(self):
    #     if self.left_checkbox.isChecked():
    #         q_shank = self.__get_latest_quaternion(self.left_shank_inlet)
    #         q_thigh = self.__get_latest_quaternion(self.left_thigh_inlet)

    #         # Pull samples until valid quaternions are received
    #         while q_shank is None or q_thigh is None:
    #             q_shank = self.__get_latest_quaternion(self.left_shank_inlet)
    #             q_thigh = self.__get_latest_quaternion(self.left_thigh_inlet)

    #         # Calcultes the offset for the left leg
    #         self.left_angle_offset = ROM.functional_calibration(q_thigh, q_shank) - self.extension_target_left.value()

    #     if self.right_checkbox.isChecked():
    #         q_shank = self.__get_latest_quaternion(self.right_shank_inlet)
    #         q_thigh = self.__get_latest_quaternion(self.right_thigh_inlet)

    #         # Pull samples until valid quaternions are received
    #         while q_shank is None or q_thigh is None:
    #             q_shank = self.__get_latest_quaternion(self.right_shank_inlet)
    #             q_thigh = self.__get_latest_quaternion(self.right_thigh_inlet)

    #         # Calcultes the offset for the right leg
    #         self.right_angle_offset = ROM.functional_calibration(q_thigh, q_shank) - self.extension_target_right.value()

    def __functional_calibration(self):
        def _one_side_knee(shank_inlet, thigh_inlet, target_spinbox):
            if not (shank_inlet and thigh_inlet):
                return None
            max_tries = 10
            for _ in range(max_tries):
                q_shank = self.__get_latest_quaternion_nonblocking(shank_inlet)
                q_thigh = self.__get_latest_quaternion_nonblocking(thigh_inlet)
                if q_shank is not None and q_thigh is not None:
                    return ROM.functional_calibration(q_thigh, q_shank) - target_spinbox.value()
                QCoreApplication.processEvents()
            return None

        def _one_side_ankle(shank_inlet, foot_inlet):
            """Return (offset, q_shank, q_foot) or (None, None, None) on failure."""
            if not (shank_inlet and foot_inlet):
                return None, None, None
            max_tries = 10
            for _ in range(max_tries):
                q_shank = self.__get_latest_quaternion_nonblocking(shank_inlet)
                q_foot  = self.__get_latest_quaternion_nonblocking(foot_inlet)
                if q_shank is not None and q_foot is not None:
                    offset = ROM.ankle_functional_calibration(q_shank, q_foot)
                    return offset, q_shank, q_foot
                QCoreApplication.processEvents()
            return None, None, None

        # Collect quaternions for combined axis diagnostic emitted once at end
        diag_sections = []
        if self.left_checkbox.isChecked():
            # Knee calibration
            off = _one_side_knee(self.left_shank_inlet, self.left_thigh_inlet, self.extension_target_left)
            if off is not None:
                self.left_angle_offset = off
            else:
                self.message_signal.emit("Left knee: no data yet. Try again when streams are active.")
            ankle_off, q_sh_l, q_ft_l = _one_side_ankle(self.left_shank_inlet, self.left_foot_inlet)
            if ankle_off is not None:
                self.left_ankle_offset = ankle_off
                # Store reference quaternions for the stable relative-quat path
                self.left_ankle_qshank_ref = q_sh_l
                self.left_ankle_qfoot_ref  = q_ft_l
                print(f"[CalibAnkle LEFT] offset={ankle_off:.2f}°  q_shank={q_sh_l}  q_foot={q_ft_l}")
                self.message_signal.emit("Left ankle offset calibrated.  ✔ Reference quaternions saved.")
                diag_sections.append(("LEFT LEG", q_sh_l, q_ft_l))
            elif self.left_foot_inlet:
                self.message_signal.emit("Left ankle: no data yet. Try again when streams are active.")
            else:
                # foot_inlet is None — ankle calibration cannot proceed
                self.message_signal.emit(
                    "⚠️ Left ankle: foot sensor not connected to calibrator. "
                    "Connect the Left Foot stream before calibrating."
                )
                print("[CalibAnkle LEFT] left_foot_inlet is None — ankle calibration skipped.")

        if self.right_checkbox.isChecked():
            # Knee calibration
            off = _one_side_knee(self.right_shank_inlet, self.right_thigh_inlet, self.extension_target_right)
            if off is not None:
                self.right_angle_offset = off
            else:
                self.message_signal.emit("Right knee: no data yet. Try again when streams are active.")
            ankle_off, q_sh_r, q_ft_r = _one_side_ankle(self.right_shank_inlet, self.right_foot_inlet)
            if ankle_off is not None:
                self.right_ankle_offset = ankle_off
                # Store reference quaternions for the stable relative-quat path
                self.right_ankle_qshank_ref = q_sh_r
                self.right_ankle_qfoot_ref  = q_ft_r
                print(f"[CalibAnkle RIGHT] offset={ankle_off:.2f}°  q_shank={q_sh_r}  q_foot={q_ft_r}")
                self.message_signal.emit("Right ankle offset calibrated.  ✔ Reference quaternions saved.")
                diag_sections.append(("RIGHT LEG", q_sh_r, q_ft_r))
            elif self.right_foot_inlet:
                self.message_signal.emit("Right ankle: no data yet. Try again when streams are active.")
            else:
                # foot_inlet is None — ankle calibration cannot proceed
                self.message_signal.emit(
                    "⚠️ Right ankle: foot sensor not connected to calibrator. "
                    "Connect the Right Foot stream before calibrating."
                )
                print("[CalibAnkle RIGHT] right_foot_inlet is None — ankle calibration skipped.")

        # Emit single combined HTML → dedicated popup window (axis_diagnostic_signal)
        if diag_sections:
            combined = ""
            for leg_label, q_sh, q_ft in diag_sections:
                combined += (
                    f'<h3 style="color:#9b59b6; margin-top:12px;">{leg_label}</h3>'
                    + sensor_axes_diagnostic(q_sh, q_ft)
                )
            self.axis_diagnostic_signal.emit(combined)



    def __set_checkboxes_enabled(self, enabled: bool):
        """Enable or disable the checkboxes."""
        self.left_checkbox.setEnabled(enabled)
        self.right_checkbox.setEnabled(enabled)

    # ------------------------
    # Data Collection Methods
    # ------------------------

    def __get_latest_quaternion(self, inlet: StreamInlet):
        inlet.flush()
        sample, _ = inlet.pull_sample(timeout=TIMEOUT)
        return np.array(sample[6:10]) if sample else None
    
    def __get_latest_quaternion_nonblocking(self, inlet: StreamInlet, max_wait=2.0, poll_interval=0.05):
        """Try to read one quaternion sample with short polling intervals (non-blocking to GUI).
        Returns None if no data after max_wait seconds."""
        t_start = time.time()
        while time.time() - t_start < max_wait:
            if inlet.samples_available() > 0:
                sample, _ = inlet.pull_sample(timeout=0.0)
                return np.array(sample[6:10]) if sample else None
            QCoreApplication.processEvents()
            time.sleep(poll_interval)  # small delay to prevent CPU spinning
        return None


    def __connect_to_streams_for_left(self):
        # Create a worker thread to resolve the streams
        self.worker_thread = QThread()
        self.stream_resolver.moveToThread(self.worker_thread)

        # Connect the correct function to resolve the streams
        self.worker_thread.started.connect(self.stream_resolver.resolve_streams_for_left)
        self.resolving = SIDE.LEFT

        # Start the worker thread
        self.worker_thread.start()

    def __connect_to_streams_for_right(self):
        # Create a worker thread to resolve the streams
        self.worker_thread = QThread()
        self.stream_resolver.moveToThread(self.worker_thread)

        # Connect the correct function to resolve the streams
        self.worker_thread.started.connect(self.stream_resolver.resolve_streams_for_right)
        self.resolving = SIDE.RIGHT

        # Start the worker thread
        self.worker_thread.start()

    def __disconnect_from_streams_left(self):
        # Close the streams for the left leg
        if self.left_shank_inlet is not None:
            self.left_shank_inlet.close_stream()
            del self.left_shank_inlet
            self.left_shank_inlet = None
        if self.left_thigh_inlet is not None:
            self.left_thigh_inlet.close_stream()
            del self.left_thigh_inlet
            self.left_thigh_inlet = None
        if self.left_foot_inlet is not None:
            self.left_foot_inlet.close_stream()
            del self.left_foot_inlet
            self.left_foot_inlet = None

    def __disconnect_from_streams_right(self):
        # Close the streams for the right leg
        if self.right_shank_inlet is not None:
            self.right_shank_inlet.close_stream()
            del self.right_shank_inlet
            self.right_shank_inlet = None
        if self.right_thigh_inlet is not None:
            self.right_thigh_inlet.close_stream()
            del self.right_thigh_inlet
            self.right_thigh_inlet = None
        if self.right_foot_inlet is not None:
            self.right_foot_inlet.close_stream()
            del self.right_foot_inlet
            self.right_foot_inlet = None

    def __calculate_angles(self, shank_inlet: StreamInlet, thigh_inlet: StreamInlet, angle_offset: float) -> np.ndarray:
        """Compute joint angles for ALL synchronized sample pairs in the current chunk.

        Pulls the latest chunk from both inlets and returns one angle value per
        matching sample pair.  Using all pairs (instead of just the latest one)
        ensures the data buffer in the calibrator updates at the full IMU sample
        rate rather than once-per-timer-tick.

        NOTE: the argument order matches the call sites — ``shank_inlet`` is the
        *distal* segment and ``thigh_inlet`` is the *proximal* one for the knee,
        OR *shank* / *foot* for the ankle.  ``static_compute_from_list`` already
        handles this correctly.
        """
        # Pull with timeout=0.0 so we never block the main Qt thread
        samples_thigh, ts_thigh = thigh_inlet.pull_chunk(timeout=0.0, max_samples=128)
        samples_shank, ts_shank = shank_inlet.pull_chunk(timeout=0.0, max_samples=128)

        if not samples_thigh or not samples_shank:
            return np.array([])

        # Convert timestamp lists to numpy once for vectorised nearest-neighbour search
        ts_shank_arr = np.array(ts_shank, dtype=np.float64)

        angles = []
        for sample_thigh, t_thigh in zip(samples_thigh, ts_thigh):
            # Find the shank sample whose timestamp is closest to this thigh timestamp
            closest_idx = int(np.argmin(np.abs(ts_shank_arr - t_thigh)))
            if np.abs(ts_shank_arr[closest_idx] - t_thigh) < TIME_TOLERANCE:
                q_thigh = np.array(sample_thigh[6:10], dtype=np.float64)
                q_shank = np.array(samples_shank[closest_idx][6:10], dtype=np.float64)
                try:
                    angle = ROM.calculate_joint_angle(q_thigh, q_shank, angle_offset)
                    angles.append(float(angle))
                except Exception:
                    pass  # skip numerically degenerate quaternions

        return angles

    # ─────────────────────────────────────────────────
    # Diagnostics / angle computation helpers
    # ─────────────────────────────────────────────────

    def __compute_angles_from_data(
        self,
        samples_proximal: list,
        ts_proximal: list,
        samples_distal: list,
        ts_distal: list,
        angle_offset: float,
        diag_proximal: dict,
    ) -> np.ndarray:
        """Compute joint angles from pre-fetched sample lists using index-based matching.

        Since Xsens Dot sensors are hardware-synchronized (same BLE clock, same
        sample rate), the Nth sample from the proximal sensor corresponds to the
        Nth sample from the distal sensor BY CONSTRUCTION — no timestamp matching
        is needed, and in fact timestamp matching is unreliable because LSL applies
        host-clock timestamps on BLE reception, which can vary per device by more
        than the TIME_TOLERANCE threshold.

        Timestamps are still compared and reported in the diagnostic for monitoring
        sync quality, but are NOT used as a filter for angle computation.
        """
        if not samples_proximal or not samples_distal:
            return np.array([])

        # Pair samples by index (hardware-synced sensors: same position = same time)
        n_pairs = min(len(samples_proximal), len(samples_distal))
        ts_prox_arr = np.array(ts_proximal[:n_pairs], dtype=np.float64)
        ts_dist_arr = np.array(ts_distal[:n_pairs],   dtype=np.float64)

        # Record average timestamp gap for diagnostics (informational only)
        gaps = np.abs(ts_prox_arr - ts_dist_arr)
        if gaps.size > 0:
            diag_proximal["sync_gap_sum"] += float(gaps.mean())
            diag_proximal["sync_gap_n"]   += 1

        angles = []
        for i in range(n_pairs):
            q_prox = np.array(samples_proximal[i][6:10], dtype=np.float64)
            q_dist = np.array(samples_distal[i][6:10],   dtype=np.float64)
            try:
                angle = ROM.calculate_joint_angle(q_prox, q_dist, angle_offset)
                angles.append(float(angle))
            except Exception:
                pass  # skip numerically degenerate quaternions

        return np.array(angles) if angles else np.array([])





    @Slot()
    def _run_diagnostics(self):
        """Called every 2 s — measures sample rate, sync quality and dropout.

        Emits ``diagnostic_signal`` with an HTML summary string.
        Resets the per-inlet counters after reading them.

        Thresholds
        ----------
        Sample rate   good ≥ 60 Hz | warning 30–60 Hz | error < 30 Hz (or 0 = stream frozen)
        Sync gap      good < 2 ms  | warning 2–10 ms  | error > 10 ms (likely not synced)
        Dropout       error if last sample > 500 ms ago
        """
        WINDOW = 2.0   # diagnostic timer interval (seconds)
        MIN_HZ_GOOD    = 60
        MIN_HZ_WARN    = 30
        MAX_GAP_GOOD   = 0.002   # 2 ms
        MAX_GAP_WARN   = 0.010   # 10 ms
        DROPOUT_THRESH = 0.500   # 500 ms

        now = time.time()

        # Map (label, diag_key, is_connected)
        sensors = [
            ("L-Thigh",  "left_thigh",  self.left_thigh_inlet  is not None),
            ("L-Shank",  "left_shank",  self.left_shank_inlet  is not None),
            ("L-Foot",   "left_foot",   self.left_foot_inlet   is not None),
            ("R-Thigh",  "right_thigh", self.right_thigh_inlet is not None),
            ("R-Shank",  "right_shank", self.right_shank_inlet is not None),
            ("R-Foot",   "right_foot",  self.right_foot_inlet  is not None),
        ]

        # ── Pairing for sync-gap check (proximal diag key → label) ──
        pairs = [
            ("left_thigh",  "left_shank",  "L Knee"),
            ("left_shank",  "left_foot",   "L Ankle"),
            ("right_thigh", "right_shank", "R Knee"),
            ("right_shank", "right_foot",  "R Ankle"),
        ]

        lines = ["<b>─── IMU Stream Diagnostic ───</b>"]

        any_active = False
        for label, key, connected in sensors:
            if not connected:
                continue
            any_active = True
            d = self._diag[key]
            hz = d["count"] / WINDOW

            if hz == 0:
                col = "#ff5555"
                tag = "FROZEN / BLE LOST"
            elif hz < MIN_HZ_WARN:
                col = "#ff5555"
                tag = f"{hz:.0f} Hz ⚠ too low"
            elif hz < MIN_HZ_GOOD:
                col = "#ffb86c"
                tag = f"{hz:.0f} Hz (warn: < {MIN_HZ_GOOD} Hz)"
            else:
                col = "#50fa7b"
                tag = f"{hz:.0f} Hz ✓"

            # Dropout check
            dropout = ""
            if d["last_ts"] > 0 and (now - d["last_ts"]) > DROPOUT_THRESH:
                dropout = f' <span style="color:#ff5555;">⚠ DROPOUT {(now - d["last_ts"])*1000:.0f} ms</span>'

            lines.append(
                f'<span style="color:{col};">[{label}] {tag}</span>{dropout}'
            )

            # Reset counter for next window
            d["count"] = 0

        if not any_active:
            return  # nothing connected yet

        # ── Synchronisation quality ──
        lines.append("<b>─── Sync quality ───</b>")
        for prox_key, dist_key, pair_label in pairs:
            dp = self._diag[prox_key]
            if dp["sync_gap_n"] == 0:
                continue
            avg_gap_ms = (dp["sync_gap_sum"] / dp["sync_gap_n"]) * 1000
            if avg_gap_ms < MAX_GAP_GOOD * 1000:
                col = "#50fa7b"
                tag = f"{avg_gap_ms:.1f} ms ✓ synced"
            elif avg_gap_ms < MAX_GAP_WARN * 1000:
                col = "#ffb86c"
                tag = f"{avg_gap_ms:.1f} ms ⚠ marginal sync"
            else:
                col = "#ff5555"
                tag = f"{avg_gap_ms:.1f} ms ✗ NOT SYNCED — re-sync sensors"
            lines.append(f'<span style="color:{col};">[{pair_label}] Δts avg: {tag}</span>')
            # Reset
            dp["sync_gap_sum"] = 0.0
            dp["sync_gap_n"] = 0

        self.diagnostic_signal.emit("<br>".join(lines))

    def start_diagnostics(self):
        """Start the 2-second diagnostic loop. Call after sensors are connected."""
        self._diag_timer.start()

    def stop_diagnostics(self):
        """Stop the diagnostic loop."""
        self._diag_timer.stop()


class LSLStreamResolver(QObject):

    """A class to resolve LSL streams for angle calibration in a separate thread."""

    message_signal = Signal(str)
    found_inlets = Signal(tuple)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.found_inlets.connect(self.move_to_main)

    @Slot()
    def resolve_streams_for_left(self):
        print("Resolving streams for left leg...")
        # Resolve the LSL streams for the left leg (shank + thigh + foot)
        stream_shank = resolve_byprop("name", "Left Shank", timeout=TIMEOUT)
        stream_thigh = resolve_byprop("name", "Left Thigh", timeout=TIMEOUT)
        if not stream_shank or not stream_thigh:
            self.message_signal.emit("Left leg streams not found. Please check the LSL streams.")
            self.found_inlets.emit((None, None, None))
        else:
            self.message_signal.emit("Left leg streams found. Connecting...")
            shank_inlet = StreamInlet(stream_shank[0])
            thigh_inlet = StreamInlet(stream_thigh[0])
            # Try to resolve foot stream (optional — ankle angle)
            stream_foot = resolve_byprop("name", "Left Foot", timeout=TIMEOUT)
            foot_inlet = StreamInlet(stream_foot[0]) if stream_foot else None
            self.found_inlets.emit((shank_inlet, thigh_inlet, foot_inlet))

    @Slot()
    def resolve_streams_for_right(self):
        print("Resolving streams for right leg...")
        # Resolve the LSL streams for the right leg (shank + thigh + foot)
        stream_shank = resolve_byprop("name", "Right Shank", timeout=TIMEOUT)
        stream_thigh = resolve_byprop("name", "Right Thigh", timeout=TIMEOUT)
        if not stream_shank or not stream_thigh:
            self.message_signal.emit("Right leg streams not found. Please check the LSL streams.")
            self.found_inlets.emit((None, None, None))
        else:
            self.message_signal.emit("Right leg streams found. Connecting...")
            shank_inlet = StreamInlet(stream_shank[0])
            thigh_inlet = StreamInlet(stream_thigh[0])
            # Try to resolve foot stream (optional — ankle angle)
            stream_foot = resolve_byprop("name", "Right Foot", timeout=TIMEOUT)
            foot_inlet = StreamInlet(stream_foot[0]) if stream_foot else None
            self.found_inlets.emit((shank_inlet, thigh_inlet, foot_inlet))
            
    @Slot()            
    def move_to_main(self):
        """Move the resolver to the main thread to avoid threading issues."""
        if self.thread() is not QApplication.instance().thread():
            self.moveToThread(QApplication.instance().thread())
