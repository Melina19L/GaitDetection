from collections import deque
from pylsl import StreamInlet, resolve_byprop
from qt_core import *
from enum import Enum
import numpy as np
from stimulator.closed_loop import ROM
import time
from typing import Optional

TIMEOUT = 3.0  # seconds


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
        self.left_angle_data = np.array([])
        self.right_angle_data = np.array([])

        self.left_angle_offset = 0.0
        self.right_angle_offset = 0.0

        # Setup timer
        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.record_data)

        # Setup thread for resolving streams
        self.stream_resolver = LSLStreamResolver()
        self.worker_thread: Optional[QThread] = None
        self.stream_resolver.found_inlets.connect(self.handle_found_inlets)
        self.stream_resolver.message_signal.connect(self.message_signal.emit)
        self.resolving = SIDE.NONE

    def stop(self):
        """Stop the angle calibration and disconnect from all streams."""
        self.timer.stop()
        if self.left_shank_inlet:
            self.__disconnect_from_streams_left()
        if self.right_shank_inlet:
            self.__disconnect_from_streams_right()
        if self.worker_thread:
            # If a worker thread is running, stop it
            self.worker_thread.quit()
            self.worker_thread.wait()
            self.worker_thread.deleteLater()
        self.message_signal.emit("Angle calibration stopped.")

    def calibration(self):
        # Start the calibration if the calibration step is START
        if self.calibration_step == CalibrationStep.READY:
            # Disable the checkboxes to prevent multiple clicks
            self.__set_checkboxes_enabled(False)
            self.__start_calibration()

        # If in neutral pose, proceed to functional calibration
        elif self.calibration_step == CalibrationStep.NEUTRAL_POSE:
            self.calibration_step = CalibrationStep.COLLECT_DATA
            self.message_signal.emit("Collecting data for functional calibration...")
            self.__functional_calibration()
            # After finishing the functional calibration, re-enable the checkboxes and the calibration
            self.message_signal.emit("Functional calibration completed.")
            self.calibration_step = CalibrationStep.READY
            self.__set_checkboxes_enabled(True)

        elif self.calibration_step == CalibrationStep.COLLECT_DATA:
            self.message_signal.emit("Collecting data, please wait...")

    def get_offset(self) -> tuple[float, float]:
        """Return the angle offsets for both legs.

        :return: Left and right angle offsets
        :rtype: tuple[float, float]
        """
        return self.left_angle_offset, self.right_angle_offset

    def get_angle_data(self) -> tuple[np.ndarray, np.ndarray]:
        """Return the angle data for both legs.

        :return: Left and right angle data
        :rtype: tuple[np.ndarray, np.ndarray]
        """
        return self.left_angle_data, self.right_angle_data

    def get_latest_data(self) -> tuple[np.ndarray, np.ndarray]:
        """Return the latest angle data for both legs.

        :return: Latest left and right angle data
        :rtype: tuple[np.ndarray, np.ndarray]
        """
        left_angle = self.left_angle_data[-1] if self.left_angle_data.size > 0 else np.array([])
        right_angle = self.right_angle_data[-1] if self.right_angle_data.size > 0 else np.array([])
        return left_angle, right_angle

    @Slot(bool)
    def handle_left_inlet(self, checked: bool):
        if checked:
            self.message_signal.emit("Connecting to left leg streams...")
            self.__connect_to_streams_for_left()
            # Disable the checkboxes to prevent multiple clicks
            self.__set_checkboxes_enabled(False)
        else:
            self.message_signal.emit("Disconnecting from left leg streams...")
            self.__disconnect_from_streams_left()
            # Stop the timer if both checkboxes are unchecked
            if not self.right_checkbox.isChecked():
                self.timer.stop()

    @Slot(bool)
    def handle_right_inlet(self, checked: bool):
        if checked:
            self.message_signal.emit("Connecting to right leg streams...")
            self.__connect_to_streams_for_right()
            # Disable the checkboxes to prevent multiple clicks
            self.__set_checkboxes_enabled(False)
        else:
            self.message_signal.emit("Disconnecting from right leg streams...")
            self.__disconnect_from_streams_right()
            # Stop the timer if both checkboxes are unchecked
            if not self.left_checkbox.isChecked():
                self.timer.stop()

    @Slot()
    def record_data(self):
        if self.left_shank_inlet and self.left_thigh_inlet:
            angles = self.__calculate_angles(self.left_shank_inlet, self.left_thigh_inlet, self.left_angle_offset)
            self.left_angle_data = np.append(self.left_angle_data, angles)
        if self.right_shank_inlet and self.right_thigh_inlet:
            angles = self.__calculate_angles(self.right_shank_inlet, self.right_thigh_inlet, self.right_angle_offset)
            self.right_angle_data = np.append(self.right_angle_data, angles)

    @Slot(tuple)
    def handle_found_inlets(self, inlets: tuple[StreamInlet, StreamInlet]):
        """Handle the found inlets from the stream resolver."""
        # Clean up the worker thread
        self.worker_thread.quit()
        self.worker_thread.wait()
        self.worker_thread.deleteLater()
        self.worker_thread = None
        
        # Re-enable the checkboxes
        self.__set_checkboxes_enabled(True)

        if inlets[0] is None or inlets[1] is None:
            # Message is handeled in the LSLStreamResolver
            return

        if self.resolving == SIDE.LEFT:
            # Store the inlets and start the timer
            self.left_shank_inlet, self.left_thigh_inlet = inlets
            self.message_signal.emit("Left leg streams connected successfully.")
            self.timer.start()

        elif self.resolving == SIDE.RIGHT:
            # Store the inlets and start the timer
            self.right_shank_inlet, self.right_thigh_inlet = inlets
            self.message_signal.emit("Right leg streams connected successfully.")
            self.timer.start()
        
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
        def _one_side(shank_inlet, thigh_inlet, target_spinbox):
            if not (shank_inlet and thigh_inlet):
                return None
            max_tries = 10  # retry up to ~10×timeout
            for _ in range(max_tries):
                q_shank = self.__get_latest_quaternion_nonblocking(shank_inlet)
                q_thigh = self.__get_latest_quaternion_nonblocking(thigh_inlet)
                if q_shank is not None and q_thigh is not None:
                    return ROM.functional_calibration(q_thigh, q_shank) - target_spinbox.value()
                QCoreApplication.processEvents()  # keep UI alive
            return None

        if self.left_checkbox.isChecked():
            off = _one_side(self.left_shank_inlet, self.left_thigh_inlet, self.extension_target_left)
            if off is not None:
                self.left_angle_offset = off
            else:
                self.message_signal.emit("Left: no data yet. Try again when streams are active.")

        if self.right_checkbox.isChecked():
            off = _one_side(self.right_shank_inlet, self.right_thigh_inlet, self.extension_target_right)
            if off is not None:
                self.right_angle_offset = off
            else:
                self.message_signal.emit("Right: no data yet. Try again when streams are active.")
    

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

    def __calculate_angles(self, shank_inlet: StreamInlet, thigh_inlet: StreamInlet, angle_offset: float) -> np.ndarray:
        # Get the latest samples from the inlets
        angle = None
        samples_thigh, ts_thigh = thigh_inlet.pull_chunk()
        samples_shank, ts_shank = shank_inlet.pull_chunk()
        # if thigh_inlet.samples_available() > 0 and shank_inlet.samples_available() > 0:
        #     samples_thigh, ts_thigh = thigh_inlet.pull_chunk(timeout=0.0, max_samples=64)
        #     samples_shank, ts_shank = shank_inlet.pull_chunk(timeout=0.0, max_samples=64)
        # else:
        #     return np.array([])

        quat_thigh = deque(maxlen=10)
        quat_shank = deque(maxlen=10)
        # Check if both samples are available
        if samples_thigh and samples_shank:
            # Take the smallest sample size to avoid index errors
            min_samples = min(len(samples_thigh), len(samples_shank))
            samples_shank = samples_shank[-min_samples:]
            samples_thigh = samples_thigh[-min_samples:]
            quat_shank.extend([timestamp] + sample[6:10] for sample, timestamp in zip(samples_shank, ts_shank))
            quat_thigh.extend([timestamp] + sample[6:10] for sample, timestamp in zip(samples_thigh, ts_thigh))
            # Calculate the angle and append to the angles array
            angle = ROM.static_compute_from_list(np.array(quat_thigh), np.array(quat_shank), angle_offset)

        return np.array(angle) if angle is not None else np.array([])
    
    
    def __calculate_angles_old(self, shank_inlet: StreamInlet, thigh_inlet: StreamInlet, angle_offset: float) -> np.ndarray:
        angles = np.array([])
        # Get the latest samples from the inlets
        samples_thigh, _ = thigh_inlet.pull_chunk()
        samples_shank, _ = shank_inlet.pull_chunk()
        # Check if both samples are available
        if samples_thigh and samples_shank:
            # Take the smallest sample size to avoid index errors
            min_samples = min(len(samples_thigh), len(samples_shank))
            samples_shank = samples_shank[-min_samples:]
            samples_thigh = samples_thigh[-min_samples:]
            for i in range(min_samples):
                # Extract the quaternion data from the samples
                q_shank = np.array(samples_shank[i][6:10])
                q_thigh = np.array(samples_thigh[i][6:10])
                # Calculate the angle and append to the angles array
                angle = ROM.calculate_joint_angle(q_thigh, q_shank, angle_offset)
                angles = np.append(angles, angle)

        return angles


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
        # Resolve the LSL streams for the left leg
        stream_shank = resolve_byprop("name", "Left Shank", timeout=TIMEOUT)
        stream_thigh = resolve_byprop("name", "Left Thigh", timeout=TIMEOUT)
        if not stream_shank or not stream_thigh:
            self.message_signal.emit("Left leg streams not found. Please check the LSL streams.")
            self.found_inlets.emit((None, None))
        else:
            self.message_signal.emit("Left leg streams found. Connecting...")
            # Create StreamInlets for the left leg streams and emit them for the AngleCalibrator
            self.found_inlets.emit((StreamInlet(stream_shank[0]), StreamInlet(stream_thigh[0])))

    @Slot()
    def resolve_streams_for_right(self):
        print("Resolving streams for right leg...")
        # Resolve the LSL streams for the right leg
        stream_shank = resolve_byprop("name", "Right Shank", timeout=TIMEOUT)
        stream_thigh = resolve_byprop("name", "Right Thigh", timeout=TIMEOUT)
        if not stream_shank or not stream_thigh:
            self.message_signal.emit("Right leg streams not found. Please check the LSL streams.")
            self.found_inlets.emit((None, None))
        else:
            self.message_signal.emit("Right leg streams found. Connecting...")
            # Create StreamInlets for the right leg streams and emit them for the AngleCalibrator
            self.found_inlets.emit((StreamInlet(stream_shank[0]), StreamInlet(stream_thigh[0])))
            
    @Slot()            
    def move_to_main(self):
        """Move the resolver to the main thread to avoid threading issues."""
        if self.thread() is not QApplication.instance().thread():
            self.moveToThread(QApplication.instance().thread())
