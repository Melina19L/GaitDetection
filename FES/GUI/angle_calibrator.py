from collections import deque
from pylsl import StreamInlet, resolve_byprop
from qt_core import *
from enum import Enum
import numpy as np
from stimulator.closed_loop import (
    ROM, TIME_TOLERANCE, sensor_axes_diagnostic,
    detect_most_vertical_axis, detect_most_horizontal_axis,
    detect_foot_medio_lateral_axis,
    identify_hinge_axis, extract_joint_angle_with_axis,
    # ── Paper algorithm (Hoegberg, Donahue, Major — Sensors 2025, 25, 2931) ──
    quaternion_average,
    paper_compute_q_g,
    paper_compute_q_PCA,
    paper_finalize_q0,
    paper_joint_angle_deg,
)
import time
from typing import Optional

TIMEOUT = 3.0  # seconds
MAX_BUFFER = 5000  # max samples kept in memory per channel (≈50 s at 100 Hz)


class CalibrationStep(Enum):
    READY = 0
    NEUTRAL_POSE = 1
    COLLECT_DATA = 2
    ANKLE_CALIBRATION = 3


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

    def __init__(self, left_checkbox: QCheckBox, right_checkbox: QCheckBox, extension_target_left: QSpinBox, extension_target_right: QSpinBox, parent=None, hip_target_left: QSpinBox=None, hip_target_right: QSpinBox=None):
        super().__init__(parent)
        self.left_checkbox = left_checkbox
        self.right_checkbox = right_checkbox
        self.extension_target_left = extension_target_left
        self.extension_target_right = extension_target_right
        self.hip_target_left = hip_target_left
        self.hip_target_right = hip_target_right
        self.calibration_step = CalibrationStep.READY
        self.left_shank_inlet = None
        self.right_shank_inlet = None
        self.left_thigh_inlet = None
        self.right_thigh_inlet = None
        self.left_foot_inlet = None
        self.right_foot_inlet = None
        # Single pelvis sensor (replaces the previous left/right trunk pair).
        # Shared between left and right hip computations.
        self.pelvis_inlet = None
        self.left_angle_data = np.array([])
        self.right_angle_data = np.array([])
        self.left_ankle_data = np.array([])
        self.right_ankle_data = np.array([])
        self.left_hip_data = np.array([])
        self.right_hip_data = np.array([])

        # Timestamps (wall-clock seconds, time.time()) aligned sample-by-sample
        # with the four angle arrays above.  Populated in record_data.
        self.left_angle_timestamps  = np.array([])
        self.right_angle_timestamps = np.array([])
        self.left_ankle_timestamps  = np.array([])
        self.right_ankle_timestamps = np.array([])
        self.left_hip_timestamps  = np.array([])
        self.right_hip_timestamps = np.array([])

        # Session bookkeeping
        self._session_start: float | None = None

        self.left_angle_offset = 0.0
        self.right_angle_offset = 0.0
        self.left_ankle_offset = 0.0
        self.right_ankle_offset = 0.0
        self.left_hip_offset = 0.0
        self.right_hip_offset = 0.0

        # Per-side ankle axes (auto-detected at functional calibration so the
        # algorithm picks the longitudinal axis of each Movella DOT regardless
        # of strap orientation). Defaults preserve the historic X/X behaviour.
        self.left_ankle_shank_axis  = 'X'
        self.left_ankle_foot_axis   = 'X'
        self.right_ankle_shank_axis = 'X'
        self.right_ankle_foot_axis  = 'X'

        self.left_ankle_hinge_axis = None
        self.right_ankle_hinge_axis = None

        # Knee hinge axes + reference quaternions (from dynamic calibration)
        self.left_knee_hinge_axis = None
        self.right_knee_hinge_axis = None
        self.left_knee_qthigh_ref = None
        self.left_knee_qshank_ref = None
        self.right_knee_qthigh_ref = None
        self.right_knee_qshank_ref = None

        # Hip hinge axes + reference quaternions (from dynamic calibration)
        self.left_hip_hinge_axis = None
        self.right_hip_hinge_axis = None
        self.left_hip_qpelvis_ref = None
        self.left_hip_qthigh_ref = None
        self.right_hip_qpelvis_ref = None
        self.right_hip_qthigh_ref = None

        # ── Paper-style per-segment calibration (Hoegberg 2025 ReBAIT) ─────────
        # Each entry, when complete, has keys
        #   'q_g'            : gravity-alignment quaternion (Eq. 2-4)
        #   'q_PCA'          : medio-lateral alignment quaternion (Eq. 5-7+9)
        #   'q_0'            : conjugate of full neutral orientation (Eq. 10)
        #   'q_static_avg'   : average q_IMU during quiet stance
        #   'accel_static_avg': average linear accel during quiet stance
        # Calibrate Offsets fills q_static_avg, accel_static_avg, q_g.
        # Functional Calibration fills q_PCA and finalises q_0.
        # When BOTH segments of a joint have complete cal, the paper algorithm
        # is used at runtime instead of the legacy offset-subtraction path.
        self._paper_cal: dict[str, dict] = {}

        # Raw data logging for debugging time-sync issues
        self._raw_log = {'left_shank': [], 'left_foot': [], 'right_shank': [], 'right_foot': []}

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
                          "right_shank", "right_thigh", "right_foot",
                          "pelvis")
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
                          "right_thigh", "right_shank", "right_foot",
                          "pelvis")
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
        left_hip = self.left_thigh_inlet is not None and self.pelvis_inlet is not None
        right_hip = self.right_thigh_inlet is not None and self.pelvis_inlet is not None
        return left_knee or right_knee or left_ankle or right_ankle or left_hip or right_hip

    def _connected_inlets(self) -> list:
        """Return the list of ``(display_name, inlet, diag_key)`` for inlets the
        operator has currently connected. Used by the readiness gate so it only
        waits on sensors that are actually expected to stream."""
        candidates = (
            ("Left Thigh",  self.left_thigh_inlet,  "left_thigh"),
            ("Left Shank",  self.left_shank_inlet,  "left_shank"),
            ("Left Foot",   self.left_foot_inlet,   "left_foot"),
            ("Right Thigh", self.right_thigh_inlet, "right_thigh"),
            ("Right Shank", self.right_shank_inlet, "right_shank"),
            ("Right Foot",  self.right_foot_inlet,  "right_foot"),
            ("Pelvis",      self.pelvis_inlet,      "pelvis"),
        )
        return [(n, i, k) for n, i, k in candidates if i is not None]

    def is_all_sensors_streaming(self, freshness_s: float = 0.5) -> tuple[bool, dict]:
        """Return ``(all_ready, status_per_sensor)``.

        A sensor is "ready" when its diagnostic counter reports a sample within
        the last ``freshness_s`` seconds. Sensors that are not connected are
        skipped — they don't block the gate.

        Used by the SensorReadinessDialog to wait for all connected Movella DOTs
        to actually stream before the test starts, so the recording doesn't
        contain the BLE warm-up transient.
        """
        now = time.time()
        status: dict[str, bool] = {}
        all_ready = True
        for name, _inlet, key in self._connected_inlets():
            last_ts = self._diag.get(key, {}).get("last_ts", 0.0)
            is_fresh = (last_ts > 0.0) and (now - last_ts < freshness_s)
            status[name] = is_fresh
            if not is_fresh:
                all_ready = False
        return all_ready, status

    def flush_buffers(self) -> None:
        """Drop everything currently buffered: deques, computed angle arrays,
        and the diagnostic counters. Called right before the test starts so
        the recording (and the live plot) begin from a clean baseline,
        without the warm-up transient that BLE often produces in the first
        seconds after sensors come online.
        """
        # 1. Drop any sample backlog in the per-inlet deques. We can't iterate
        #    while clearing, so use a snapshot of the keys.
        for key in list(self._acc.keys()):
            try:
                self._acc[key].clear()
            except Exception:
                pass

        # 2. Reset all computed-angle arrays + their timestamp arrays so the
        #    plot widgets repaint from scratch.
        self.left_angle_data       = np.array([])
        self.right_angle_data      = np.array([])
        self.left_ankle_data       = np.array([])
        self.right_ankle_data      = np.array([])
        self.left_hip_data         = np.array([])
        self.right_hip_data        = np.array([])
        self.left_angle_timestamps  = np.array([])
        self.right_angle_timestamps = np.array([])
        self.left_ankle_timestamps  = np.array([])
        self.right_ankle_timestamps = np.array([])
        self.left_hip_timestamps    = np.array([])
        self.right_hip_timestamps   = np.array([])

        # 3. Drop any pending samples sitting on the LSL inlet socket buffers
        #    (each pull_chunk after this returns only freshly arrived samples).
        for _name, inlet, _key in self._connected_inlets():
            try:
                inlet.flush()
            except Exception:
                pass

        # 4. Reset diagnostic windowing (rate counters + sync-gap accumulators)
        for key in list(self._diag.keys()):
            d = self._diag[key]
            d["count"] = 0
            d["sync_gap_sum"] = 0.0
            d["sync_gap_n"] = 0
            # NOTE: we keep last_ts so is_all_sensors_streaming() still reports
            # recently-arrived sensors as "ready"; record_data will refresh it
            # on the very next tick.

        # 5. Mark a new session start for offline saving / plot pkl naming.
        self._session_start = time.time()

    def stop(self):
        """Stop the angle calibration and disconnect from all streams."""
        self.timer.stop()
        self._diag_timer.stop()
        if self.left_shank_inlet or self.left_thigh_inlet or self.left_foot_inlet:
            self.__disconnect_from_streams_left()
        if self.right_shank_inlet or self.right_thigh_inlet or self.right_foot_inlet:
            self.__disconnect_from_streams_right()
        # Pelvis is shared — close once if no leg side keeps it alive
        self.__disconnect_pelvis_if_idle()
        if self.worker_thread:
            # If a worker thread is running, stop it
            self.worker_thread.wait()
            self.worker_thread.deleteLater()
            
        self.save_raw_data()
        self.message_signal.emit("Angle calibration stopped (knee + ankle + hip).")

    def save_raw_data(self):
        """Save raw LSL data for debugging time sync."""
        try:
            import numpy as np
            raw_file = "raw_imu_data_from_gui.npz"
            np.savez(raw_file, 
                     left_shank=np.array(self._raw_log['left_shank']),
                     left_foot=np.array(self._raw_log['left_foot']),
                     right_shank=np.array(self._raw_log['right_shank']),
                     right_foot=np.array(self._raw_log['right_foot']))
            print(f"Raw LSL data saved to {raw_file}")
        except Exception as e:
            print(f"Failed to save raw data: {e}")

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

        # Stop the record_data timer so __get_averaged_quaternion has
        # exclusive access to the LSL inlets during calibration.
        # Without this, record_data's pull_chunk and calibration's
        # pull_sample would race for the same packets.
        self.timer.stop()

        # Flush stale samples so calibration averages only fresh data
        for _name, inlet, _key in self._connected_inlets():
            try:
                inlet.flush()
            except Exception:
                pass

        # Run the functional calibration (reads current pose as offset)
        self.__functional_calibration()

        # Restart the record_data timer
        self.timer.start()

        # IMPORTANT: Clear data buffers here!
        # The background timer started logging data the moment the IMUs were toggled ON,
        # using an offset of 0.0 (since calibration had not happened yet).
        # We must discard this pre-calibration "garbage" data so it doesn't show
        # up at the start of the plot or in the saved .pkl file.
        self.left_angle_data = np.array([])
        self.right_angle_data = np.array([])
        self.left_ankle_data = np.array([])
        self.right_ankle_data = np.array([])
        self.left_hip_data = np.array([])
        self.right_hip_data = np.array([])
        self.left_angle_timestamps = np.array([])
        self.right_angle_timestamps = np.array([])
        self.left_ankle_timestamps = np.array([])
        self.right_ankle_timestamps = np.array([])
        self.left_hip_timestamps = np.array([])
        self.right_hip_timestamps = np.array([])

        # Re-enable toggles
        self.calibration_step = CalibrationStep.READY
        self.__set_checkboxes_enabled(True)

        # Build a clear success banner with the actual offset values
        kl, kr = self.left_angle_offset, self.right_angle_offset
        al, ar = self.left_ankle_offset, self.right_ankle_offset
        hl, hr = self.left_hip_offset, self.right_hip_offset
        banner = (
            '<hr/>'
            '<p style="color:#27ae60; font-size:13px; font-weight:bold;">'
            '&#10003;&#10003; OFFSET CALIBRATION COMPLETED SUCCESSFULLY &#10003;&#10003;</p>'
            '<table style="color:#ecf0f1; font-family:monospace;">'
            f'<tr><td>Knee &nbsp;Left&nbsp;</td><td><b>{kl:+.2f}&deg;</b></td></tr>'
            f'<tr><td>Knee &nbsp;Right</td><td><b>{kr:+.2f}&deg;</b></td></tr>'
            f'<tr><td>Ankle Left&nbsp;</td><td><b>{al:+.2f}&deg;</b></td></tr>'
            f'<tr><td>Ankle Right</td><td><b>{ar:+.2f}&deg;</b></td></tr>'
            f'<tr><td>Hip &nbsp;&nbsp;Left&nbsp;</td><td><b>{hl:+.2f}&deg;</b></td></tr>'
            f'<tr><td>Hip &nbsp;&nbsp;Right</td><td><b>{hr:+.2f}&deg;</b></td></tr>'
            '</table><hr/>'
        )
        self.calibration_done_signal.emit(banner)

    def ankle_functional_calibration(self):
        """Dynamic functional calibration for ALL joints (hip, knee, ankle).

        The user should walk normally for 5 seconds. The system records
        quaternion data from all connected sensors and uses SVD to identify
        the principal rotation (hinge) axis of each joint. This axis is then
        used at runtime via swing-twist decomposition to extract only the
        sagittal-plane angle, decoupling each joint from out-of-plane motion.

        Based on the PCA/SVD approach from Donahue et al. (2025) / Seel et al. (2014).
        """
        if not self.has_any_sensor():
            self.error_signal.emit("Functional Calibration failed: no sensors connected.")
            return

        if self.calibration_step != CalibrationStep.READY:
            self.message_signal.emit("System is busy, please wait...")
            return

        self.__set_checkboxes_enabled(False)
        self.calibration_step = CalibrationStep.ANKLE_CALIBRATION
        
        self.diagnostic_signal.emit(
            '<p style="color:#3498db; font-weight:bold;">'
            '&#128694; Full Functional Calibration (10 s)&hellip;<br/>'
            '<b>Do all of these in any order:</b><br/>'
            '&nbsp;&nbsp;• 4-5 <b>toe-touches</b> (rise on toes / heel raises) — excites the ankle axis<br/>'
            '&nbsp;&nbsp;• 4-5 <b>steps in place</b> (lift each knee high) — excites knee + hip<br/>'
            '&nbsp;&nbsp;• 2-3 slow <b>trunk bows</b> (lean forward and back at the waist) — excites pelvis<br/>'
            'PCA needs strong, clean motion in each anatomical axis.</p>'
        )
        QCoreApplication.processEvents()

        self.timer.stop()

        for _name, inlet, _key in self._connected_inlets():
            try:
                inlet.flush()
            except Exception:
                pass

        import time

        # 10 s gives the user enough time to do the 3-movement protocol the
        # paper recommends ("5-10 toe-touches and steady-state walking" —
        # Hoegberg 2025 §2.3.3) plus the trunk bows we add to excite the
        # pelvis sagittal axis (which pure walking doesn't excite enough,
        # so its PCA eig-ratio stays below 2.0).
        duration = 10.0
        start_t = time.time()
        
        # Accumulate data from ALL sensors
        buffers = {
            'left_pelvis': [], 'left_thigh': [], 'left_shank': [], 'left_foot': [],
            'right_pelvis': [], 'right_thigh': [], 'right_shank': [], 'right_foot': [],
        }
        
        inlet_map = {}
        if self.left_checkbox.isChecked():
            if self.pelvis_inlet:    inlet_map['left_pelvis'] = self.pelvis_inlet
            if self.left_thigh_inlet: inlet_map['left_thigh'] = self.left_thigh_inlet
            if self.left_shank_inlet: inlet_map['left_shank'] = self.left_shank_inlet
            if self.left_foot_inlet:  inlet_map['left_foot'] = self.left_foot_inlet
        if self.right_checkbox.isChecked():
            if self.pelvis_inlet:     inlet_map['right_pelvis'] = self.pelvis_inlet
            if self.right_thigh_inlet: inlet_map['right_thigh'] = self.right_thigh_inlet
            if self.right_shank_inlet: inlet_map['right_shank'] = self.right_shank_inlet
            if self.right_foot_inlet:  inlet_map['right_foot'] = self.right_foot_inlet
        
        while time.time() - start_t < duration:
            for key, inlet in inlet_map.items():
                chunk, _ = inlet.pull_chunk(timeout=0.0)
                if chunk:
                    buffers[key].extend(chunk)
            QCoreApplication.processEvents()
            time.sleep(0.02)
        
        def _extract_quats(samples):
            """Extract and normalize quaternions [w,x,y,z] from LSL samples."""
            if not samples:
                return None
            arr = np.array([s[6:10] for s in samples], dtype=np.float64)
            norms = np.linalg.norm(arr, axis=1, keepdims=True)
            norms[norms < 1e-9] = 1.0
            return arr / norms

        def _extract_gyros(samples):
            """Extract angular velocity vectors (cols 3:6) from LSL samples."""
            if not samples:
                return None
            return np.array([s[3:6] for s in samples], dtype=np.float64)

        def _finalise_paper_segment(seg_name: str, samples: list) -> bool:
            """Compute q_PCA + q_0 for a single segment (paper Step 2 / Eq.5-7+9).

            Requires that q_g and q_static_avg were already stored for this
            segment by Calibrate Offsets. Returns True on success.
            """
            cal = self._paper_cal.get(seg_name)
            if cal is None or 'q_g' not in cal or 'q_static_avg' not in cal:
                # Static cal hasn't run yet — paper algo can't be activated.
                return False
            q_d = _extract_quats(samples)
            g_d = _extract_gyros(samples)
            if q_d is None or g_d is None:
                return False
            n = min(len(q_d), len(g_d))
            if n < 50:
                return False
                
            try:
                q_PCA, ratio = paper_compute_q_PCA(g_d[:n], q_d[:n], cal['q_g'])
            except Exception as e:
                self.error_signal.emit(f"PCA Math Error on {seg_name}: {e}")
                return False
                
            cal['pca_ratio'] = float(ratio)

            # Hard threshold: only commit q_PCA + q_0 (= activate paper path
            # at runtime) when the principal axis is at least 1.5× stronger
            # than the second axis. Below that the PCA pointed somewhere
            # random and using it forces q_joint into the Eq.11 wrap-around
            # zone (±180°).
            PCA_MIN_RATIO = 1.5
            if ratio < PCA_MIN_RATIO:
                # Drop any previously stored q_PCA/q_0 so the dispatcher in
                # __compute_angles_from_data falls back to the legacy path.
                cal.pop('q_PCA', None)
                cal.pop('q_0',   None)
                self.message_signal.emit(
                    f"[paper] {seg_name}: ratio {ratio:.2f} < {PCA_MIN_RATIO} — "
                    f"REJECTED, falling back to legacy. Redo Functional Calibration "
                    f"with stronger {seg_name}-specific motion."
                )
                return False
            cal['q_PCA'] = q_PCA
            cal['q_0']   = paper_finalize_q0(cal['q_g'], q_PCA, cal['q_static_avg'])
            tag = "clean ✓" if ratio >= 2.0 else "acceptable ✓"
            self.message_signal.emit(
                f"[paper] {seg_name}: PCA eig-ratio {ratio:.2f} ({tag}, n={n})"
            )
            return True

        def _identify_axis(prox_samples, dist_samples, joint_name):
            """Run SVD hinge axis identification for a joint pair (legacy path).
            Returns hinge_axis or None.
            """
            q_prox = _extract_quats(prox_samples)
            q_dist = _extract_quats(dist_samples)
            if q_prox is None or q_dist is None:
                return None
            n_min = min(len(q_prox), len(q_dist))
            if n_min < 50:
                self.error_signal.emit(f"Not enough data for {joint_name} ({n_min} samples).")
                return None
            q_prox = q_prox[:n_min]
            q_dist = q_dist[:n_min]
            axis = identify_hinge_axis(q_prox, q_dist)
            self.message_signal.emit(
                f"{joint_name}: axis=[{axis[0]:+.3f}, {axis[1]:+.3f}, {axis[2]:+.3f}] "
                f"({n_min} samples)"
            )
            return axis
        
        results = []

        # ── PAPER ALGORITHM: per-segment q_PCA + q_0 (Hoegberg 2025) ──────────
        # Compute medio-lateral alignment (Eq. 5-7+9) for every segment that
        # already has q_g from Calibrate Offsets. The buffers above are
        # JOINT-keyed (e.g. 'left_pelvis' = pelvis samples gathered while the
        # left side was active) — pelvis samples are the same on both sides
        # since the inlet is shared, so we just pick one.
        paper_segments = []
        if self.left_checkbox.isChecked():
            paper_segments += [
                ('left_thigh', buffers['left_thigh']),
                ('left_shank', buffers['left_shank']),
                ('left_foot',  buffers['left_foot']),
            ]
        if self.right_checkbox.isChecked():
            paper_segments += [
                ('right_thigh', buffers['right_thigh']),
                ('right_shank', buffers['right_shank']),
                ('right_foot',  buffers['right_foot']),
            ]
        # Pelvis: pick whichever side was sampled (or merge both)
        pelvis_samples = (buffers.get('left_pelvis') or []) + (buffers.get('right_pelvis') or [])
        if self.pelvis_inlet is not None and pelvis_samples:
            paper_segments.append(('pelvis', pelvis_samples))

        for seg_name, segs in paper_segments:
            if not segs:
                continue
            ok = _finalise_paper_segment(seg_name, segs)
            if ok:
                results.append(f'{seg_name} ✓')
            else:
                results.append(f'{seg_name} ✗ (need static cal first)')

        # ── LEGACY: SVD hinge axis (kept as fallback for joints without paper cal) ──
        if self.left_checkbox.isChecked():
            ax = _identify_axis(
                buffers['left_pelvis'], buffers['left_thigh'], 'Left Hip (SVD)')
            if ax is not None:
                self.left_hip_hinge_axis = ax
            ax = _identify_axis(
                buffers['left_thigh'], buffers['left_shank'], 'Left Knee (SVD)')
            if ax is not None:
                self.left_knee_hinge_axis = ax
            ax = _identify_axis(
                buffers['left_shank'], buffers['left_foot'], 'Left Ankle (SVD)')
            if ax is not None:
                self.left_ankle_hinge_axis = ax

        if self.right_checkbox.isChecked():
            ax = _identify_axis(
                buffers['right_pelvis'], buffers['right_thigh'], 'Right Hip (SVD)')
            if ax is not None:
                self.right_hip_hinge_axis = ax
            ax = _identify_axis(
                buffers['right_thigh'], buffers['right_shank'], 'Right Knee (SVD)')
            if ax is not None:
                self.right_knee_hinge_axis = ax
            ax = _identify_axis(
                buffers['right_shank'], buffers['right_foot'], 'Right Ankle (SVD)')
            if ax is not None:
                self.right_ankle_hinge_axis = ax
        
        self.timer.start()
        self.calibration_step = CalibrationStep.READY
        self.__set_checkboxes_enabled(True)
        
        summary = ', '.join(results) if results else 'No joints calibrated'
        self.diagnostic_signal.emit(
            f'<p style="color:#2ecc71; font-weight:bold;">'
            f'&#10004; Functional Calibration Complete: {summary}</p>'
        )


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
        """Return the calibration quaternions (q_shank_ref, q_foot_ref) and
        hinge axes for each leg.

        Used to pass the reference quaternions to ROM.set_ankle_reference() so that
        the stable relative-quaternion ankle angle algorithm can be used at runtime.

        :return: (left_qs, left_qf, right_qs, right_qf, left_axis, right_axis)
        """
        left_qs  = getattr(self, 'left_ankle_qshank_ref',  None)
        left_qf  = getattr(self, 'left_ankle_qfoot_ref',   None)
        right_qs = getattr(self, 'right_ankle_qshank_ref', None)
        right_qf = getattr(self, 'right_ankle_qfoot_ref',  None)
        left_axis = getattr(self, 'left_ankle_hinge_axis', None)
        right_axis = getattr(self, 'right_ankle_hinge_axis', None)
        return left_qs, left_qf, right_qs, right_qf, left_axis, right_axis

    def get_knee_reference(self):
        """Return the calibration quaternions (q_thigh_ref, q_shank_ref) and
        hinge axes for each knee.
        """
        left_qt  = getattr(self, 'left_knee_qthigh_ref',  None)
        left_qs  = getattr(self, 'left_knee_qshank_ref',   None)
        right_qt = getattr(self, 'right_knee_qthigh_ref', None)
        right_qs = getattr(self, 'right_knee_qshank_ref',  None)
        left_axis = getattr(self, 'left_knee_hinge_axis', None)
        right_axis = getattr(self, 'right_knee_hinge_axis', None)
        return left_qt, left_qs, right_qt, right_qs, left_axis, right_axis

    def get_hip_reference(self):
        """Return the calibration quaternions (q_pelvis_ref, q_thigh_ref) and
        hinge axes for each hip.
        """
        left_qp  = getattr(self, 'left_hip_qpelvis_ref',  None)
        left_qt  = getattr(self, 'left_hip_qthigh_ref',   None)
        right_qp = getattr(self, 'right_hip_qpelvis_ref', None)
        right_qt = getattr(self, 'right_hip_qthigh_ref',  None)
        left_axis = getattr(self, 'left_hip_hinge_axis', None)
        right_axis = getattr(self, 'right_hip_hinge_axis', None)
        return left_qp, left_qt, right_qp, right_qt, left_axis, right_axis

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

    def get_hip_data(self) -> tuple[np.ndarray, np.ndarray]:
        """Return the hip angle data for both legs.

        :return: Left and right hip angle data
        :rtype: tuple[np.ndarray, np.ndarray]
        """
        return self.left_hip_data, self.right_hip_data

    def get_latest_hip_data(self) -> tuple[np.ndarray, np.ndarray]:
        """Return the latest hip angle data for both legs.

        :return: Latest left and right hip angle data
        :rtype: tuple[np.ndarray, np.ndarray]
        """
        left_hip = self.left_hip_data[-1] if self.left_hip_data.size > 0 else np.array([])
        right_hip = self.right_hip_data[-1] if self.right_hip_data.size > 0 else np.array([])
        return left_hip, right_hip

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

    def _match_snapshots(self, snap_prox: list, snap_dist: list, tolerance: float = 0.05) -> tuple:
        """Match two lists of (timestamp, sample) tuples by timestamp.
        Returns:
            matched_prox (list): matched proximal samples
            matched_dist (list): matched distal samples
            ts_prox_out (list): timestamps for proximal
            ts_dist_out (list): timestamps for distal
            consumed_prox (int): number of proximal items to pop from queue
            consumed_dist (int): number of distal items to pop from queue
        """
        matched_prox, matched_dist = [], []
        ts_prox_out, ts_dist_out = [], []
        i, j = 0, 0
        while i < len(snap_prox) and j < len(snap_dist):
            ts_p, s_p = snap_prox[i]
            ts_d, s_d = snap_dist[j]
            diff = ts_p - ts_d
            if abs(diff) <= tolerance:
                matched_prox.append(s_p)
                matched_dist.append(s_d)
                ts_prox_out.append(ts_p)
                ts_dist_out.append(ts_d)
                i += 1
                j += 1
            elif diff > tolerance:
                # ts_p is newer than ts_d by more than tolerance.
                # s_d is too old, discard it.
                j += 1
            else:
                # ts_d is newer than ts_p. s_p is too old, discard it.
                i += 1
        return matched_prox, ts_prox_out, matched_dist, ts_dist_out, i, j

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
            (self.pelvis_inlet,      "pelvis"),
        ):
            if inlet is None:
                continue
            samples, timestamps = inlet.pull_chunk(timeout=0.0, max_samples=128)
            if samples:
                # Store as (timestamp, sample) tuples to allow time-sync matching
                paired = list(zip(timestamps, samples))
                self._acc[key].extend(paired)
                self._diag[key]["count"]  += len(samples)
                self._diag[key]["last_ts"] = now
                if hasattr(self, '_raw_log') and key in self._raw_log:
                    # Save raw samples with arrival timestamp for debugging
                    for ts, s in paired:
                        self._raw_log[key].append([ts] + list(s))

        # ── 2. Snapshot pelvis (shared between both hips) ─────────────────────
        # Pelvis samples feed BOTH left and right hip computations, so they are
        # NOT included in the per-leg `min` and we don't pop them per-leg either.
        # Instead we take a snapshot, peek for hip math on each side, then pop
        # only the maximum count actually used by either side.
        pelvis_snapshot = list(self._acc["pelvis"]) if self.pelvis_inlet else []
        pelvis_used = 0

        # ── 3. Process LEFT LEG ───────────────────────────────────────────────
        l_thigh_q = list(self._acc["left_thigh"]) if self.left_thigh_inlet else []
        l_shank_q = list(self._acc["left_shank"]) if self.left_shank_inlet else []
        l_foot_q  = list(self._acc["left_foot"]) if self.left_foot_inlet else []

        l_thigh_used = 0
        l_shank_used = 0
        l_foot_used  = 0

        # Hip LEFT
        if self.pelvis_inlet and self.left_thigh_inlet:
            p_s, p_ts, t_s, t_ts, c_p, c_t = self._match_snapshots(pelvis_snapshot, l_thigh_q)
            if p_s:
                hip_angles = self.__compute_angles_from_data(
                    p_s, p_ts, t_s, t_ts,
                    self.left_hip_offset, self._diag["pelvis"],
                    q_proximal_ref=getattr(self, 'left_hip_qpelvis_ref', None),
                    q_distal_ref=getattr(self, 'left_hip_qthigh_ref', None),
                    hinge_axis=getattr(self, 'left_hip_hinge_axis', None),
                    cal_proximal=self._paper_cal.get('pelvis'),
                    cal_distal=self._paper_cal.get('left_thigh'),
                )
                self.left_hip_data = np.append(self.left_hip_data, hip_angles)
                self.left_hip_timestamps = np.append(self.left_hip_timestamps, t_ts)
                pelvis_used = max(pelvis_used, c_p)
                l_thigh_used = max(l_thigh_used, c_t)

        # Knee LEFT
        if self.left_thigh_inlet and self.left_shank_inlet:
            t_s, t_ts, s_s, s_ts, c_t, c_s = self._match_snapshots(l_thigh_q, l_shank_q)
            if t_s:
                angles = self.__compute_angles_from_data(
                    t_s, t_ts, s_s, s_ts,
                    self.left_angle_offset, self._diag["left_thigh"],
                    q_proximal_ref=getattr(self, 'left_knee_qthigh_ref', None),
                    q_distal_ref=getattr(self, 'left_knee_qshank_ref', None),
                    hinge_axis=getattr(self, 'left_knee_hinge_axis', None),
                    cal_proximal=self._paper_cal.get('left_thigh'),
                    cal_distal=self._paper_cal.get('left_shank'),
                )
                self.left_angle_data = np.append(self.left_angle_data, angles)
                self.left_angle_timestamps = np.append(self.left_angle_timestamps, s_ts)
                l_thigh_used = max(l_thigh_used, c_t)
                l_shank_used = max(l_shank_used, c_s)

        # Ankle LEFT
        if self.left_shank_inlet and self.left_foot_inlet:
            s_s, s_ts, f_s, f_ts, c_s, c_f = self._match_snapshots(l_shank_q, l_foot_q)
            if s_s:
                ankle_angles = self.__compute_angles_from_data(
                    s_s, s_ts, f_s, f_ts,
                    self.left_ankle_offset, self._diag["left_shank"],
                    is_ankle=True,
                    proximal_axis=self.left_ankle_shank_axis,
                    distal_axis=self.left_ankle_foot_axis,
                    q_proximal_ref=getattr(self, 'left_ankle_qshank_ref', None),
                    q_distal_ref=getattr(self, 'left_ankle_qfoot_ref', None),
                    hinge_axis=getattr(self, 'left_ankle_hinge_axis', None),
                    cal_proximal=self._paper_cal.get('left_shank'),
                    cal_distal=self._paper_cal.get('left_foot'),
                )
                self.left_ankle_data = np.append(self.left_ankle_data, ankle_angles)
                self.left_ankle_timestamps = np.append(self.left_ankle_timestamps, f_ts)
                l_shank_used = max(l_shank_used, c_s)
                l_foot_used = max(l_foot_used, c_f)

        # ── 4. Process RIGHT LEG ──────────────────────────────────────────────
        r_thigh_q = list(self._acc["right_thigh"]) if self.right_thigh_inlet else []
        r_shank_q = list(self._acc["right_shank"]) if self.right_shank_inlet else []
        r_foot_q  = list(self._acc["right_foot"]) if self.right_foot_inlet else []

        r_thigh_used = 0
        r_shank_used = 0
        r_foot_used  = 0

        # Hip RIGHT
        if self.pelvis_inlet and self.right_thigh_inlet:
            p_s, p_ts, t_s, t_ts, c_p, c_t = self._match_snapshots(pelvis_snapshot, r_thigh_q)
            if p_s:
                hip_angles = self.__compute_angles_from_data(
                    p_s, p_ts, t_s, t_ts,
                    self.right_hip_offset, self._diag["pelvis"],
                    q_proximal_ref=getattr(self, 'right_hip_qpelvis_ref', None),
                    q_distal_ref=getattr(self, 'right_hip_qthigh_ref', None),
                    hinge_axis=getattr(self, 'right_hip_hinge_axis', None),
                    cal_proximal=self._paper_cal.get('pelvis'),
                    cal_distal=self._paper_cal.get('right_thigh'),
                )
                self.right_hip_data = np.append(self.right_hip_data, hip_angles)
                self.right_hip_timestamps = np.append(self.right_hip_timestamps, t_ts)
                pelvis_used = max(pelvis_used, c_p)
                r_thigh_used = max(r_thigh_used, c_t)

        # Knee RIGHT
        if self.right_thigh_inlet and self.right_shank_inlet:
            t_s, t_ts, s_s, s_ts, c_t, c_s = self._match_snapshots(r_thigh_q, r_shank_q)
            if t_s:
                angles = self.__compute_angles_from_data(
                    t_s, t_ts, s_s, s_ts,
                    self.right_angle_offset, self._diag["right_thigh"],
                    q_proximal_ref=getattr(self, 'right_knee_qthigh_ref', None),
                    q_distal_ref=getattr(self, 'right_knee_qshank_ref', None),
                    hinge_axis=getattr(self, 'right_knee_hinge_axis', None),
                    cal_proximal=self._paper_cal.get('right_thigh'),
                    cal_distal=self._paper_cal.get('right_shank'),
                )
                self.right_angle_data = np.append(self.right_angle_data, angles)
                self.right_angle_timestamps = np.append(self.right_angle_timestamps, s_ts)
                r_thigh_used = max(r_thigh_used, c_t)
                r_shank_used = max(r_shank_used, c_s)

        # Ankle RIGHT
        if self.right_shank_inlet and self.right_foot_inlet:
            s_s, s_ts, f_s, f_ts, c_s, c_f = self._match_snapshots(r_shank_q, r_foot_q)
            if s_s:
                ankle_angles = self.__compute_angles_from_data(
                    s_s, s_ts, f_s, f_ts,
                    self.right_ankle_offset, self._diag["right_shank"],
                    is_ankle=True,
                    proximal_axis=self.right_ankle_shank_axis,
                    distal_axis=self.right_ankle_foot_axis,
                    q_proximal_ref=getattr(self, 'right_ankle_qshank_ref', None),
                    q_distal_ref=getattr(self, 'right_ankle_qfoot_ref', None),
                    hinge_axis=getattr(self, 'right_ankle_hinge_axis', None),
                    cal_proximal=self._paper_cal.get('right_shank'),
                    cal_distal=self._paper_cal.get('right_foot'),
                )
                self.right_ankle_data = np.append(self.right_ankle_data, ankle_angles)
                self.right_ankle_timestamps = np.append(self.right_ankle_timestamps, f_ts)
                r_shank_used = max(r_shank_used, c_s)
                r_foot_used = max(r_foot_used, c_f)

        # ── 5. Drop the samples consumed by computations ───────────
        if self.pelvis_inlet and pelvis_used > 0:
            for _ in range(min(pelvis_used, len(self._acc["pelvis"]))):
                self._acc["pelvis"].popleft()
        if self.left_thigh_inlet and l_thigh_used > 0:
            for _ in range(min(l_thigh_used, len(self._acc["left_thigh"]))):
                self._acc["left_thigh"].popleft()
        if self.left_shank_inlet and l_shank_used > 0:
            for _ in range(min(l_shank_used, len(self._acc["left_shank"]))):
                self._acc["left_shank"].popleft()
        if self.left_foot_inlet and l_foot_used > 0:
            for _ in range(min(l_foot_used, len(self._acc["left_foot"]))):
                self._acc["left_foot"].popleft()
        if self.right_thigh_inlet and r_thigh_used > 0:
            for _ in range(min(r_thigh_used, len(self._acc["right_thigh"]))):
                self._acc["right_thigh"].popleft()
        if self.right_shank_inlet and r_shank_used > 0:
            for _ in range(min(r_shank_used, len(self._acc["right_shank"]))):
                self._acc["right_shank"].popleft()
        if self.right_foot_inlet and r_foot_used > 0:
            for _ in range(min(r_foot_used, len(self._acc["right_foot"]))):
                self._acc["right_foot"].popleft()

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
        if self.left_hip_data.size > MAX_BUFFER:
            self.left_hip_data       = self.left_hip_data[-MAX_BUFFER:]
            self.left_hip_timestamps = self.left_hip_timestamps[-MAX_BUFFER:]
        if self.right_hip_data.size > MAX_BUFFER:
            self.right_hip_data       = self.right_hip_data[-MAX_BUFFER:]
            self.right_hip_timestamps = self.right_hip_timestamps[-MAX_BUFFER:]


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
            "left_hip_angles":     self.left_hip_data.copy(),
            "right_hip_angles":    self.right_hip_data.copy(),
            # ── Timestamps ───────────────────────────────────────────────────
            "left_knee_timestamps":   self.left_angle_timestamps.copy(),
            "right_knee_timestamps":  self.right_angle_timestamps.copy(),
            "left_ankle_timestamps":  self.left_ankle_timestamps.copy(),
            "right_ankle_timestamps": self.right_ankle_timestamps.copy(),
            "left_hip_timestamps":    self.left_hip_timestamps.copy(),
            "right_hip_timestamps":   self.right_hip_timestamps.copy(),
            # ── Calibration offsets ──────────────────────────────────────────
            "left_knee_offset":   self.left_angle_offset,
            "right_knee_offset":  self.right_angle_offset,
            "left_ankle_offset":  self.left_ankle_offset,
            "right_ankle_offset": self.right_ankle_offset,
            "left_hip_offset":    self.left_hip_offset,
            "right_hip_offset":   self.right_hip_offset,
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

        ``inlets`` is ``(shank_inlet, thigh_inlet, foot_inlet, pelvis_inlet)``.
        The pelvis inlet is shared between sides: the second leg to connect
        receives the same pelvis inlet (or ``None`` if it was already wired up)
        so we never bind two inlets to the same LSL stream.
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

        if not any(inlets):
            # Connection failed — uncheck the toggle that was trying to connect
            self.error_signal.emit("Connection failed: no sensors found.")
            if self.resolving == SIDE.LEFT:
                self.left_checkbox.setChecked(False)
            elif self.resolving == SIDE.RIGHT:
                self.right_checkbox.setChecked(False)
            self.resolving = SIDE.NONE
            return

        # Extract inlets
        shank_inlet, thigh_inlet, foot_inlet, pelvis_inlet = inlets

        # Adopt the pelvis inlet only if we don't already own one for this run
        if pelvis_inlet is not None and self.pelvis_inlet is None:
            self.pelvis_inlet = pelvis_inlet
        elif pelvis_inlet is not None and self.pelvis_inlet is not None:
            # We already have one — close the duplicate stream returned this round
            try:
                pelvis_inlet.close_stream()
            except Exception:
                pass

        pelvis_label = "Pelvis" if self.pelvis_inlet is not None else None

        if self.resolving == SIDE.LEFT:
            self.left_shank_inlet = shank_inlet
            self.left_thigh_inlet = thigh_inlet
            self.left_foot_inlet  = foot_inlet

            connected_names = []
            if shank_inlet: connected_names.append("Shank")
            if thigh_inlet: connected_names.append("Thigh")
            if foot_inlet:  connected_names.append("Foot")
            if pelvis_label: connected_names.append(pelvis_label)
            self.message_signal.emit(f"Left leg streams connected: {', '.join(connected_names)}.")
            self.timer.start()
            self.start_diagnostics()

        elif self.resolving == SIDE.RIGHT:
            self.right_shank_inlet = shank_inlet
            self.right_thigh_inlet = thigh_inlet
            self.right_foot_inlet  = foot_inlet

            connected_names = []
            if shank_inlet: connected_names.append("Shank")
            if thigh_inlet: connected_names.append("Thigh")
            if foot_inlet:  connected_names.append("Foot")
            if pelvis_label: connected_names.append(pelvis_label)
            self.message_signal.emit(f"Right leg streams connected: {', '.join(connected_names)}.")
            self.timer.start()
            self.start_diagnostics()

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
        # All offset captures average ~1 s of samples instead of grabbing a
        # single jittery quaternion. Eliminates the ±10° "standing pose" drift.
        AVG_DURATION_S = 1.0

        # ── Paper-style per-segment static collection (Hoegberg 2025) ────────
        # We collect 1 s of accelerometer + quaternion samples ONCE per unique
        # segment (vs. the previous code which sampled e.g. left_shank twice —
        # once for the knee, once for the ankle). The cached q_avg is then
        # reused below by the legacy knee / ankle / hip offset helpers, and
        # the (q_avg, accel_avg) pair feeds paper_compute_q_g for each segment.
        # ----------------------------------------------------------------------
        seg_inlets = []
        if self.left_checkbox.isChecked():
            seg_inlets += [
                ('left_thigh', self.left_thigh_inlet),
                ('left_shank', self.left_shank_inlet),
                ('left_foot',  self.left_foot_inlet),
            ]
        if self.right_checkbox.isChecked():
            seg_inlets += [
                ('right_thigh', self.right_thigh_inlet),
                ('right_shank', self.right_shank_inlet),
                ('right_foot',  self.right_foot_inlet),
            ]
        # Pelvis is shared between hips
        if self.pelvis_inlet is not None and (
            self.left_checkbox.isChecked() or self.right_checkbox.isChecked()
        ):
            seg_inlets.append(('pelvis', self.pelvis_inlet))

        static_data: dict[str, dict] = {}  # 'left_thigh' → {'q': ..., 'accel': ...}
        for name, inlet in seg_inlets:
            if inlet is None:
                continue
            q_avg, a_avg, _, _ = self.__get_averaged_static_data(
                inlet, duration_s=AVG_DURATION_S,
            )
            if q_avg is None or a_avg is None:
                continue
            static_data[name] = {'q': q_avg, 'accel': a_avg}
            # Seed paper cal with q_g + static data ONLY. q_PCA / q_0 are
            # intentionally *not* stored here — they get filled by Functional
            # Calibration if (and only if) the PCA produces a confident axis.
            # The runtime dispatcher checks for both keys before activating
            # the paper path, so an incomplete cal falls back to legacy.
            q_g = paper_compute_q_g(a_avg, q_avg)
            self._paper_cal[name] = {
                'q_g': q_g,
                'q_static_avg': q_avg,
                'accel_static_avg': a_avg,
            }

        def _one_side_knee(shank_seg, thigh_seg, target_spinbox):
            q_shank = static_data.get(shank_seg, {}).get('q')
            q_thigh = static_data.get(thigh_seg, {}).get('q')
            if q_shank is None or q_thigh is None:
                return None
            return ROM.functional_calibration(q_thigh, q_shank) - target_spinbox.value()

        def _one_side_ankle(shank_seg, foot_seg):
            """Calibrate the ankle joint using auto-detected sensor axes.

            Uses the cached static_data from the paper-collection step above
            (no second 1-second wait per inlet). Behaviour otherwise unchanged.
            """
            q_shank = static_data.get(shank_seg, {}).get('q')
            q_foot  = static_data.get(foot_seg,  {}).get('q')
            if q_shank is None or q_foot is None:
                return None, None, None, 'X', 'X', 'X'

            # Auto-detect axes from the standing-pose quaternions
            shank_vert_axis = detect_most_vertical_axis(q_shank)
            foot_fwd_axis   = detect_most_horizontal_axis(q_foot, q_shank)
            foot_ml_axis    = detect_foot_medio_lateral_axis(q_foot, q_shank)
            foot_grav_axis  = detect_most_vertical_axis(q_foot)

            print(f"[CalibAnkle] Auto-detected axes:")
            print(f"  Shank vertical axis: {shank_vert_axis}")
            print(f"  Foot gravity axis:   {foot_grav_axis}")
            print(f"  Foot forward axis:   {foot_fwd_axis}")
            print(f"  Foot medio-lat axis: {foot_ml_axis}")

            # Use the detected longitudinal axes for the legacy offset calculation
            offset = ROM.ankle_functional_calibration(
                q_shank, q_foot,
                foot_axis=foot_fwd_axis, shank_axis=shank_vert_axis,
            )
            return offset, q_shank, q_foot, shank_vert_axis, foot_fwd_axis, foot_ml_axis

        def _one_side_hip(thigh_seg, offset_val):
            """Calibrate hip using the shared pelvis sensor as the proximal reference."""
            q_pelvis = static_data.get('pelvis',   {}).get('q')
            q_thigh  = static_data.get(thigh_seg,  {}).get('q')
            if q_pelvis is None or q_thigh is None:
                return None
            return ROM.functional_calibration(q_pelvis, q_thigh) - offset_val

        # Collect quaternions for combined axis diagnostic emitted once at end
        diag_sections = []
        if self.left_checkbox.isChecked():
            # Knee calibration
            off = _one_side_knee('left_shank', 'left_thigh', self.extension_target_left)
            if off is not None:
                self.left_angle_offset = off
            else:
                self.message_signal.emit("Left knee: no data yet. Try again when streams are active.")

            # Hip calibration (safe — does not block if pelvis is absent)
            try:
                hip_tgt = self.hip_target_left.value() if self.hip_target_left else 0.0
                hip_off = _one_side_hip('left_thigh', hip_tgt)
                if hip_off is not None:
                    self.left_hip_offset = hip_off
                elif self.pelvis_inlet and self.left_thigh_inlet:
                    self.message_signal.emit("Left hip: no data yet. Try again when streams are active.")
            except Exception as e:
                print(f"[CalibHip LEFT] skipped: {e}")

            ankle_off, q_sh_l, q_ft_l, sh_ax_l, ft_fwd_l, ft_ml_l = _one_side_ankle('left_shank', 'left_foot')
            if ankle_off is not None:
                self.left_ankle_offset = ankle_off
                # Store reference quaternions for sagittal-plane projection
                self.left_ankle_qshank_ref = q_sh_l
                self.left_ankle_qfoot_ref  = q_ft_l
                # Store the axes for the sagittal-plane algorithm:
                #  shank_axis = longitudinal (vertical) axis of the shank
                #  foot_axis  = FORWARD axis of the foot (toward toes)
                self.left_ankle_shank_axis = sh_ax_l     # shank longitudinal axis
                self.left_ankle_foot_axis  = ft_fwd_l    # foot FORWARD axis
                print(f"[CalibAnkle LEFT] offset={ankle_off:.2f}°  shank_axis={sh_ax_l}  foot_fwd={ft_fwd_l}  foot_ml={ft_ml_l}")
                self.message_signal.emit(
                    f"Left ankle calibrated.  offset={ankle_off:+.1f}°  "
                    f"axes: shank_long={sh_ax_l}, foot_fwd={ft_fwd_l}, foot_ml={ft_ml_l}"
                )
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
            off = _one_side_knee('right_shank', 'right_thigh', self.extension_target_right)
            if off is not None:
                self.right_angle_offset = off
            else:
                self.message_signal.emit("Right knee: no data yet. Try again when streams are active.")

            # Hip calibration (safe — does not block if pelvis is absent)
            try:
                hip_tgt_r = self.hip_target_right.value() if self.hip_target_right else 0.0
                hip_off_r = _one_side_hip('right_thigh', hip_tgt_r)
                if hip_off_r is not None:
                    self.right_hip_offset = hip_off_r
                elif self.pelvis_inlet and self.right_thigh_inlet:
                    self.message_signal.emit("Right hip: no data yet. Try again when streams are active.")
            except Exception as e:
                print(f"[CalibHip RIGHT] skipped: {e}")

            ankle_off, q_sh_r, q_ft_r, sh_ax_r, ft_fwd_r, ft_ml_r = _one_side_ankle('right_shank', 'right_foot')
            if ankle_off is not None:
                self.right_ankle_offset = ankle_off
                # Store reference quaternions for sagittal-plane projection
                self.right_ankle_qshank_ref = q_sh_r
                self.right_ankle_qfoot_ref  = q_ft_r
                # Store the axes for the sagittal-plane algorithm:
                #  shank_axis = longitudinal (vertical) axis of the shank
                #  foot_axis  = FORWARD axis of the foot (toward toes)
                self.right_ankle_shank_axis = sh_ax_r    # shank longitudinal axis
                self.right_ankle_foot_axis  = ft_fwd_r   # foot FORWARD axis
                print(f"[CalibAnkle RIGHT] offset={ankle_off:.2f}°  shank_axis={sh_ax_r}  foot_fwd={ft_fwd_r}  foot_ml={ft_ml_r}")
                self.message_signal.emit(
                    f"Right ankle calibrated.  offset={ankle_off:+.1f}°  "
                    f"axes: shank_long={sh_ax_r}, foot_fwd={ft_fwd_r}, foot_ml={ft_ml_r}"
                )
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

    def __get_averaged_static_data(self, inlet: StreamInlet, duration_s: float = 1.0,
                                    poll_interval: float = 0.02):
        """Collect ~``duration_s`` of samples during quiet stance and return
        ``(q_avg, accel_avg, q_buffer, accel_buffer)``.

        Used for paper-style per-segment calibration (Hoegberg 2025): the
        gravity-alignment quaternion ``q_g`` needs the average accelerometer
        vector AND the average orientation quaternion at the same neutral pose.

        Returns ``(None, None, None, None)`` if no samples arrive in time.

        Notes
        -----
        - Quaternion averaging uses the eigendecomposition method
          (`quaternion_average`), which is robust to the q/-q double cover.
        - Accel averaging is element-wise (linear acceleration is a vector).
        - The returned per-sample buffers are kept around in case the caller
          wants the unfiltered samples (currently unused).
        """
        if inlet is None:
            return None, None, None, None
        t_start = time.time()
        q_buf, a_buf = [], []
        while time.time() - t_start < duration_s:
            if inlet.samples_available() > 0:
                sample, _ = inlet.pull_sample(timeout=0.0)
                if sample:
                    q_buf.append(np.asarray(sample[6:10], dtype=np.float64))
                    a_buf.append(np.asarray(sample[0:3],  dtype=np.float64))
            QCoreApplication.processEvents()
            time.sleep(poll_interval)
        if not q_buf:
            return None, None, None, None
        q_arr = np.asarray(q_buf, dtype=np.float64)
        # Drop zero-norm quaternions (BLE warm-up sometimes leaks junk)
        norms = np.linalg.norm(q_arr, axis=1)
        keep = norms > 1e-6
        if not np.any(keep):
            return None, None, None, None
        q_arr = q_arr[keep] / norms[keep, None]
        a_arr = np.asarray(a_buf, dtype=np.float64)[keep]
        q_avg = quaternion_average(q_arr)
        a_avg = a_arr.mean(axis=0)
        return q_avg, a_avg, q_arr, a_arr

    def __get_averaged_quaternion(self, inlet: StreamInlet, duration_s: float = 1.0,
                                  poll_interval: float = 0.02):
        """Collect ~N quaternion samples for ``duration_s`` seconds and return their mean.

        Quaternion-aware averaging: each new sample is sign-flipped if its dot
        product with the running reference is negative (q and -q represent the
        same rotation). The arithmetic mean is renormalised at the end.

        Used for **stable calibration offset capture** — sampling a single
        quaternion produces ±10° jitter at standing, which translates directly
        into a wrong "zero" for the joint angles. Averaging over 1 s gives a
        sub-degree offset.
        """
        if inlet is None:
            return None
        t_start = time.time()
        ref = None
        acc = np.zeros(4, dtype=np.float64)
        n = 0
        while time.time() - t_start < duration_s:
            if inlet.samples_available() > 0:
                sample, _ = inlet.pull_sample(timeout=0.0)
                if sample:
                    q = np.asarray(sample[6:10], dtype=np.float64)
                    if ref is None:
                        ref = q
                    if float(np.dot(q, ref)) < 0:
                        q = -q
                    acc += q
                    n += 1
            QCoreApplication.processEvents()
            time.sleep(poll_interval)
        if n == 0:
            return None
        avg = acc / float(n)
        norm = float(np.linalg.norm(avg))
        if norm < 1e-9:
            return None
        return avg / norm


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
        # Pelvis is shared with the right leg — drop only when both sides are gone.
        self.__disconnect_pelvis_if_idle()

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
        # Pelvis is shared with the left leg — drop only when both sides are gone.
        self.__disconnect_pelvis_if_idle()

    def __disconnect_pelvis_if_idle(self):
        """Close the shared pelvis inlet only when no leg is connected anymore."""
        any_left  = bool(self.left_shank_inlet  or self.left_thigh_inlet  or self.left_foot_inlet)
        any_right = bool(self.right_shank_inlet or self.right_thigh_inlet or self.right_foot_inlet)
        if any_left or any_right:
            return
        if self.pelvis_inlet is not None:
            try:
                self.pelvis_inlet.close_stream()
            except Exception:
                pass
            self.pelvis_inlet = None
            # Allow the resolver to re-bind on the next connect.
            try:
                self.stream_resolver.pelvis_already_bound = False
            except Exception:
                pass

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

        angles = []
        for sample_thigh, sample_shank in zip(samples_thigh, samples_shank):
            q_thigh = np.array(sample_thigh[6:10], dtype=np.float64)
            q_shank = np.array(sample_shank[6:10], dtype=np.float64)
            try:
                angle = ROM.calculate_joint_angle(q_thigh, q_shank, angle_offset)
                angles.append(float(angle))
            except Exception:
                pass  # skip numerically degenerate quaternions

        return np.array(angles)

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
        is_ankle: bool = False,
        proximal_axis: str = 'X',
        distal_axis:   str = 'X',
        q_proximal_ref: np.ndarray = None,
        q_distal_ref:   np.ndarray = None,
        hinge_axis: np.ndarray = None,
        cal_proximal: dict = None,
        cal_distal:   dict = None,
    ) -> np.ndarray:
        """Compute joint angles from pre-matched sample lists.

        The lists `samples_proximal` and `samples_distal` have already been
        aligned by timestamp in `_record_data`, so they are guaranteed to be
        the exact same length and correspond to the same instant in time.

        Algorithm dispatch (highest priority first):
          1. **Paper algorithm** (Hoegberg 2025) — used when both segments
             have a complete cal dict (q_g + q_PCA + q_0). This is the path
             we want once Calibrate Offsets + Functional Calibration have
             both completed successfully.
          2. **Legacy SVD swing-twist** — backward compat for joints whose
             paper cal isn't ready but a hinge_axis was found.
          3. **Static-only ankle / knee / hip** — fallback when neither.
        """
        if not samples_proximal or not samples_distal:
            return np.array([])

        n_pairs = min(len(samples_proximal), len(samples_distal))

        if ts_proximal and ts_distal:
            ts_prox_arr = np.array(ts_proximal[:n_pairs], dtype=np.float64)
            ts_dist_arr = np.array(ts_distal[:n_pairs],   dtype=np.float64)
            # Record average timestamp gap for diagnostics (informational only)
            gaps = np.abs(ts_prox_arr - ts_dist_arr)
            if gaps.size > 0:
                diag_proximal["sync_gap_sum"] += float(gaps.mean())
                diag_proximal["sync_gap_n"]   += 1

        # Decide once per call whether the paper algorithm is available — we
        # need both cal dicts AND each must have all three quaternions.
        paper_ready = (
            cal_proximal is not None and cal_distal is not None
            and all(k in cal_proximal for k in ('q_g', 'q_PCA', 'q_0'))
            and all(k in cal_distal   for k in ('q_g', 'q_PCA', 'q_0'))
        )

        angles = []
        for i in range(n_pairs):
            q_prox = np.array(samples_proximal[i][6:10], dtype=np.float64)
            q_dist = np.array(samples_distal[i][6:10],   dtype=np.float64)
            try:
                if paper_ready:
                    # ── Paper algorithm: ISB-aligned segment frames + Eq. 11 ──
                    angle = paper_joint_angle_deg(
                        q_prox, q_dist, cal_proximal, cal_distal,
                    )
                    if is_ankle:
                        # Anatomic ankle ROM is ~-30° dorsi / +50° plantar.
                        # Clamp to ±50° so a transient sensor-fusion glitch
                        # (rare BLE packet loss → stale q) can't spike the
                        # plot to absurd values during the live test.
                        ANKLE_MIN, ANKLE_MAX = -50.0, 50.0
                        angle = max(ANKLE_MIN, min(ANKLE_MAX, angle))
                elif hinge_axis is not None and q_proximal_ref is not None and q_distal_ref is not None:
                    # ── Legacy SVD swing-twist fallback ──
                    angle = extract_joint_angle_with_axis(
                        q_prox, q_dist,
                        q_proximal_ref, q_distal_ref,
                        hinge_axis,
                    )
                    if is_ankle:
                        ANKLE_MIN, ANKLE_MAX = -50.0, 50.0
                        angle = max(ANKLE_MIN, min(ANKLE_MAX, angle))
                elif is_ankle:
                    angle = ROM.calculate_ankle_angle(
                        q_prox, q_dist, angle_offset,
                        foot_axis=distal_axis, shank_axis=proximal_axis,
                        q_shank_ref=q_proximal_ref, q_foot_ref=q_distal_ref,
                    )
                    ANKLE_MIN, ANKLE_MAX = -50.0, 50.0
                    angle = max(ANKLE_MIN, min(ANKLE_MAX, angle))
                else:
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
        MAX_GAP_GOOD   = 0.020   # 20 ms — BLE at 60 Hz has natural ~16 ms jitter
        MAX_GAP_WARN   = 0.050   # 50 ms
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
            ("Pelvis",   "pelvis",      self.pelvis_inlet      is not None),
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

    # Pelvis is a single shared sensor (replaces the previous left/right trunk pair).
    # Only the FIRST leg to connect resolves it; the second leg sees ``pelvis_already_bound``
    # set to True and skips resolution to avoid binding two inlets to the same stream.
    pelvis_already_bound: bool = False

    def __init__(self, parent=None):
        super().__init__(parent)
        self.found_inlets.connect(self.move_to_main)

    def _resolve_pelvis(self):
        """Resolve the single pelvis sensor stream (``Pelvis`` → fallback ``Custom 1``).

        Returns a ``StreamInlet`` or ``None``.  Resolution is skipped (returns ``None``)
        when ``pelvis_already_bound`` is set, so the second leg connect doesn't try to
        bind a duplicate inlet.
        """
        if self.pelvis_already_bound:
            return None
        PELVIS_TIMEOUT = 1.0
        stream = resolve_byprop("name", "Pelvis", timeout=PELVIS_TIMEOUT)
        if not stream:
            stream = resolve_byprop("name", "Custom 1", timeout=PELVIS_TIMEOUT)
        if not stream:
            return None
        inlet = StreamInlet(stream[0])
        self.pelvis_already_bound = True
        return inlet

    @Slot()
    def resolve_streams_for_left(self):
        print("Resolving streams for left leg...")
        stream_shank = resolve_byprop("name", "Left Shank", timeout=TIMEOUT)
        stream_thigh = resolve_byprop("name", "Left Thigh", timeout=TIMEOUT)
        stream_foot  = resolve_byprop("name", "Left Foot",  timeout=TIMEOUT)

        shank_inlet  = StreamInlet(stream_shank[0]) if stream_shank else None
        thigh_inlet  = StreamInlet(stream_thigh[0]) if stream_thigh else None
        foot_inlet   = StreamInlet(stream_foot[0])  if stream_foot  else None
        pelvis_inlet = self._resolve_pelvis()

        if not any([shank_inlet, thigh_inlet, foot_inlet, pelvis_inlet]):
            self.message_signal.emit("Left leg streams not found. Please check the LSL streams.")
        else:
            self.message_signal.emit("Left leg streams found. Connecting...")

        self.found_inlets.emit((shank_inlet, thigh_inlet, foot_inlet, pelvis_inlet))

    @Slot()
    def resolve_streams_for_right(self):
        print("Resolving streams for right leg...")
        stream_shank = resolve_byprop("name", "Right Shank", timeout=TIMEOUT)
        stream_thigh = resolve_byprop("name", "Right Thigh", timeout=TIMEOUT)
        stream_foot  = resolve_byprop("name", "Right Foot",  timeout=TIMEOUT)

        shank_inlet  = StreamInlet(stream_shank[0]) if stream_shank else None
        thigh_inlet  = StreamInlet(stream_thigh[0]) if stream_thigh else None
        foot_inlet   = StreamInlet(stream_foot[0])  if stream_foot  else None
        pelvis_inlet = self._resolve_pelvis()

        if not any([shank_inlet, thigh_inlet, foot_inlet, pelvis_inlet]):
            self.message_signal.emit("Right leg streams not found. Please check the LSL streams.")
        else:
            self.message_signal.emit("Right leg streams found. Connecting...")

        self.found_inlets.emit((shank_inlet, thigh_inlet, foot_inlet, pelvis_inlet))
            
    @Slot()            
    def move_to_main(self):
        """Move the resolver to the main thread to avoid threading issues."""
        if self.thread() is not QApplication.instance().thread():
            self.moveToThread(QApplication.instance().thread())
