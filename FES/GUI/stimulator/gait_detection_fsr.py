import numpy as np
from pylsl import StreamInlet
from collections import deque
from enum import Enum
from .gait_phases import Phase
from PySide6.QtCore import QTimer, Qt, QObject, Slot, SLOT, Signal


class FirstStep(Enum):
    DETECTING_HEEL_STRIKE = 1
    DETECTING_TOE_OFF = 2
    DETECTED = 3


class FSRGaitFSM(QObject):
    # initialize the class and phase counters
    steps_changed = Signal(int)
    # emit when active phase changes (value is Phase enum value -> int)
    phase_changed = Signal(int)

    # initialize the class and phase counters
    def __init__(self, inlet: StreamInlet, threshold: int = 20):
        super().__init__()  # required for Qt signals to work
        self.inlet = inlet
        self.threshold = threshold  # Threshold for phase detection

        self.active_phase = Phase.UNKNOWN  # Initial state
        self.previous_phase = Phase.UNKNOWN  # Previous state
        self.phase_counters = {Phase.LOADING_RESPONSE: 0, Phase.MID_STANCE: 0, Phase.SWING: 0, Phase.UNKNOWN: 0}
        self.phase_timestamps = {
            Phase.LOADING_RESPONSE: np.array([]),
            Phase.MID_STANCE: np.array([]),
            Phase.SWING: np.array([]),
            Phase.UNKNOWN: np.array([]),
        }

        self.heel_strike = np.array([])
        self.toe_off = np.array([])
        self.mid_stance = np.array([])

        self.heel_strike_timestamps = np.array([])
        self.toe_off_timestamps = np.array([])
        self.mid_stance_timestamps = np.array([])

        self.data_ff = deque(maxlen=1000)  # Data for the front foot sensor
        self.data_mf = deque(maxlen=1000)  # Data for the middle foot sensor
        self.data_bf = deque(maxlen=1000)  # Data for the back foot sensor
        self.timestamps = deque(maxlen=1000)

        # Data for the offline analysis
        self.data_ff_offline = np.array([])
        self.data_mf_offline = np.array([])
        self.data_bf_offline = np.array([])
        self.timestamps_offline = np.array([])

        self.first_step_detected = FirstStep.DETECTING_HEEL_STRIKE  # Initial state for first step detection

    ###############################
    # Public methods
    ###############################

    def is_phase_unknown(self) -> bool:
        # Check if the current phase is "UNKNOWN"
        return self.active_phase == Phase.UNKNOWN

    def changed_phase(self) -> bool:
        # Check if the current phase has changed from the previous one
        return self.active_phase != self.previous_phase

    def update_previous_phase(self):
        # Update the previous phase to the current one
        self.previous_phase = self.active_phase

    def update_fsr(self):
        """Update the FSR data by pulling a chunk of samples from the LSL stream."""
        # Pull data from lsl stream
        samples, timestamps = self.inlet.pull_chunk(timeout=0.001, max_samples=1000)

        if timestamps:
            # Extend deque with new data, data_gx is the only one used online
            self.data_ff.extend(sample[0] for sample in samples)
            self.data_mf.extend(sample[1] for sample in samples)
            self.data_bf.extend(sample[2] for sample in samples)
            self.timestamps.extend(timestamps)
            
            # Print streaming FSR data in the terminal (Front, Middle, Back foot)
            print(f"FSR Stream -> Front: {self.data_ff[-1]:.2f}, Middle: {self.data_mf[-1]:.2f}, Back: {self.data_bf[-1]:.2f}")


            # For offline analysis, store the data in numpy arrays
            self.data_ff_offline = np.append(self.data_ff_offline, np.array([sample[0] for sample in samples]))
            self.data_mf_offline = np.append(self.data_mf_offline, np.array([sample[1] for sample in samples]))
            self.data_bf_offline = np.append(self.data_bf_offline, np.array([sample[2] for sample in samples]))
            self.timestamps_offline = np.append(self.timestamps_offline, np.array(timestamps))

    def fsr_phase_detection(self):
        """Detect the gait phase based on the IMU data."""
        # Ensure we have enough data points to update the plot
        # (changing this parameter would not affect the phase counters result but only the plots' starting point)
        if len(self.data_ff) <= 100:
            return

        # TODO Detect heel strike and toe off from fsr values
        # Heel strike is when the latest backfoot data is above a certain threshold
        # Mid stance is when the latest midfoot data is above the latest backfoot data
        # Toe off is when the latest frontfoot and midfoot data are below a certain threshold

        # Detect swing if phase is unknown
        if (
            self.active_phase == Phase.UNKNOWN
            and self.data_bf[-1] < self.threshold
            and self.data_mf[-1] < self.threshold
            and self.data_ff[-1] < self.threshold
        ):
            self.__transition_to(Phase.SWING)

        # Detect heel strike
        if self.data_bf[-1] > self.threshold and self.active_phase == Phase.SWING:
            self.__record_heel_strike(self.timestamps[-1])
            self.__transition_to(Phase.LOADING_RESPONSE)

        # Detect mid stance
        elif self.data_mf[-1] > self.data_bf[-1] and self.active_phase == Phase.LOADING_RESPONSE:
            self.__record_mid_stance(self.timestamps[-1])
            self.__transition_to(Phase.MID_STANCE)

        # Detect toe off
        elif self.data_ff[-1] < self.threshold and self.data_mf[-1] < self.threshold and self.active_phase == Phase.MID_STANCE:
            self.__record_toe_off(self.timestamps[-1])
            self.__transition_to(Phase.SWING)

        # Separate case to detect the first step
        if self.first_step_detected is not FirstStep.DETECTED:
            
            # TODO Detect first step from fsr values
            pass

        # For the steps after the first step
        else:
            # TODO Detect steps from fsr values
            pass

        # Public helper for counting steps
    def get_step_count(self) -> int:
        try:
            # Prefer heel-strike timestamps if present
            return int(len(self.heel_strike_timestamps))
        except Exception:
            # Fallback to phase counters if you store HS there
            try:
                return int(self.phase_counters.get(Phase.LOADING_RESPONSE, 0))
            except Exception:
                return 0

    ###############################
    # Private methods
    ###############################

    def __transition_to(self, next_phase: Phase) -> None:
        """Transition to the next phase of the gait cycle and record the timestamp.

        :param next_phase: The next phase to transition to.
        :type next_phase: Phase
        :raises ValueError: If next_phase is not an instance of the Phase Enum.
        """
        if not isinstance(next_phase, Phase):
            raise ValueError("next_phase must be an instance of the Phase Enum")
        # Update counter and current state
        if next_phase != self.active_phase:
            # print(f"Transitioning from {self.current_phase} to {next_phase}")  # print for debugging
            self.phase_counters[next_phase] += 1
            self.active_phase = next_phase
            self.phase_timestamps[next_phase] = np.append(self.phase_timestamps[next_phase], self.timestamps[-1])
            try:
                # emit numeric Phase so Qt signals are simple to forward
                self.phase_changed.emit(int(self.active_phase.value))
            except Exception:
                pass
            # Emit on heel-strike phase if applicable
            if next_phase == Phase.LOADING_RESPONSE:
                self.steps_changed.emit(self.get_step_count())

    def __detect_steps(self, timestamp: float) -> None:
        """Detect and handle phase transitions of the gait based on the peak timestamp.\n

        UPDATE THIS PLEASE
        This function classifies the detected peak as either a heel strike or a toe off based on the distance to the last valley and the last peak.
        The peak is classified as a heel strike if the distance to the last valley is less than the distance to the last recorded peak, and as a toe off otherwise.

        For the detection of the first step, another function is used.

        :param peak_timestamp: The timestamp of the detected peak.
        :type peak_timestamp: float
        """
        # TODO Detect heel strike and toe off from fsr values

        if True:  # TODO: Replace with actual condition to check if toe off
            self.__record_toe_off(timestamp)
            self.__transition_to(Phase.SWING)

        # Otherwise, heel strike
        else:
            self.__record_heel_strike(timestamp)
            # Transition to STANCE phase
            self.__transition_to(Phase.STANCE)

    def __detect_first_step(self, valley_timestamp: float, peak_timestamp: float) -> None:
        """Detect the first step of the gait cycle based on the peak and valley timestamps.\n
        This function is only called for the first step of the gait cycle and is not called again after the first step is detected.

        This function waits for the first valley to be detected and then starts detecting the first step.\n
        Valley -> Peak (Heel Strike) -> Peak (Toe Off) -> First Step Detected.

        :param valley_timestamp: The timestamp of the detected valley.
        :type valley_timestamp: float
        :param peak_timestamp: The timestamp of the detected peak.
        :type peak_timestamp: float
        """
        # The first peak after the valley is detected (short peak)
        if self.first_step_detected == FirstStep.DETECTING_HEEL_STRIKE:
            # Ensure the "long" peak is not the same as the "short" peak
            if peak_timestamp > self.heel_strike_timestamps[-1]:
                self.__record_toe_off(peak_timestamp)
                self.__transition_to(Phase.SWING)
                # Update the last peak type -> first step fully detected, this function should not be called anymore
                self.first_step_detected = FirstStep.DETECTED

        # Check if a valley was detected before the latest peak
        elif peak_timestamp > valley_timestamp:
            if peak_timestamp - valley_timestamp < 0.5:  # 0.5 seconds
                self.__record_heel_strike(peak_timestamp)
                self.__transition_to(Phase.STANCE)
                # Update the last peak type
                self.first_step_detected = FirstStep.DETECTING_TOE_OFF

    def __record_heel_strike(self, timestamp: float) -> None:
        """Record the time of the detected and classified heel strike."""
        self.heel_strike_timestamps = np.append(self.heel_strike_timestamps, timestamp)
        self.heel_strike = np.append(self.heel_strike, self.data_bf[-1])

    def __record_toe_off(self, timestamp: float) -> None:
        """Record the time of the detected and classified toe off."""
        self.toe_off_timestamps = np.append(self.toe_off_timestamps, timestamp)
        self.toe_off = np.append(self.toe_off, self.data_ff[-1])

    def __record_mid_stance(self, timestamp: float) -> None:
        """Record the time of the detected and classified mid stance."""
        self.mid_stance_timestamps = np.append(self.mid_stance_timestamps, timestamp)
        self.mid_stance = np.append(self.mid_stance, self.data_mf[-1])
        
        
class FSRGaitFSM_2(QObject):
    # initialize the class and phase counters
    steps_changed = Signal(int)
    # emit when active phase changes (value is Phase enum value -> int)
    phase_changed = Signal(int)

    # initialize the class and phase counters
    def __init__(self, inlet: StreamInlet, threshold: int = 5 , hysteresis: int = 2, terminal_stance_divider: int = 4 ):
        super().__init__()  # required for Qt signals to work
        self.inlet = inlet
        self.threshold = threshold  # Threshold for phase detection
        self.hysteresis = hysteresis
        self.terminal_stance_divider=terminal_stance_divider


        self.active_phase = Phase.UNKNOWN  # Initial state
        self.previous_phase = Phase.UNKNOWN  # Previous state
        self.phase_counters = {Phase.LOADING_RESPONSE: 0, Phase.MID_STANCE: 0, Phase.TERMINAL_STANCE:0, Phase.PRE_SWING: 0, Phase.SWING: 0, Phase.UNKNOWN: 0}
        self.phase_timestamps = {
            Phase.LOADING_RESPONSE: np.array([]),
            Phase.MID_STANCE: np.array([]),
            Phase.TERMINAL_STANCE: np.array([]),
            Phase.PRE_SWING: np.array([]),
            Phase.SWING: np.array([]),
            Phase.UNKNOWN: np.array([]),
        }

        self.heel_strike = np.array([])
        self.toe_off = np.array([])
        self.mid_stance = np.array([])

        self.heel_strike_timestamps = np.array([])
        self.toe_off_timestamps = np.array([])
        self.mid_stance_timestamps = np.array([])

        self.data_ff = deque(maxlen=1000)  # Data for the front foot sensor
        self.data_mf = deque(maxlen=1000)  # Data for the middle foot sensor
        self.data_bf = deque(maxlen=1000)  # Data for the back foot sensor
        
        self.timestamps = deque(maxlen=1000)

        # Data for the offline analysis
        self.data_ff_offline = np.array([])
        self.data_mf_offline = np.array([])
        self.data_bf_offline = np.array([])
        self.timestamps_offline = np.array([])
        
        #Loading phase info
        self.stance_time=0
        self.FSR2_loading_response_durations = np.array([])
        self.FSR2_mid_stance_durations = np.array([])
        self.FSR2_stance_durations = np.array([])

        self.first_step_detected = FirstStep.DETECTING_HEEL_STRIKE  # Initial state for first step detection

    ###############################
    # Public methods
    ###############################

    def is_phase_unknown(self) -> bool:
        # Check if the current phase is "UNKNOWN"
        return self.active_phase == Phase.UNKNOWN

    def changed_phase(self) -> bool:
        # Check if the current phase has changed from the previous one
        return self.active_phase != self.previous_phase

    def update_previous_phase(self):
        # Update the previous phase to the current one
        self.previous_phase = self.active_phase

    def update_fsr(self):
        """Update the FSR data by pulling a chunk of samples from the LSL stream."""
        # Pull data from lsl stream
        samples, timestamps = self.inlet.pull_chunk(timeout=0.001, max_samples=1000)

        if timestamps:
            # Extend deque with new data, data_gx is the only one used online
            self.data_ff.extend(sample[0] for sample in samples)
            self.data_mf.extend(sample[1] for sample in samples)
            self.data_bf.extend(sample[2] for sample in samples)
            self.timestamps.extend(timestamps)
            
            # Print streaming FSR data in the terminal (Front, Middle, Back foot)
            print(f"FSR Stream -> Front: {self.data_ff[-1]:.2f}, Middle: {self.data_mf[-1]:.2f}, Back: {self.data_bf[-1]:.2f}")
            
            

            # For offline analysis, store the data in numpy arrays
            self.data_ff_offline = np.append(self.data_ff_offline, np.array([sample[0] for sample in samples]))
            self.data_mf_offline = np.append(self.data_mf_offline, np.array([sample[1] for sample in samples]))
            self.data_bf_offline = np.append(self.data_bf_offline, np.array([sample[2] for sample in samples]))
            self.timestamps_offline = np.append(self.timestamps_offline, np.array(timestamps))

    def fsr_phase_detection(self):
        """Detect the gait phase based on the IMU data."""
        # Ensure we have enough data points to update the plot
        # (changing this parameter would not affect the phase counters result but only the plots' starting point)
        if len(self.data_ff) <= 100:
            return
        
        

        ff=np.asarray(self.data_ff)
        mf=np.asarray(self.data_mf)
        bf=np.asarray(self.data_bf)
        
        data_mean = (ff + mf + bf) / 3 

        # Detect swing if phase is unknown
        if (
            self.active_phase == Phase.UNKNOWN
            and data_mean[-1] <  self.threshold  
        ):
            self.__transition_to(Phase.SWING)

        # Detect heel strike
        if data_mean[-1] > abs(self.threshold + self.hysteresis) and self.active_phase == Phase.SWING:
            self.__record_heel_strike(self.timestamps[-1])
            self.__transition_to(Phase.LOADING_RESPONSE)
            if self.heel_strike_timestamps.size < 2:
                # Transition to mid stance after 100 ms
                            QTimer.singleShot(100, Qt.TimerType.PreciseTimer, self, SLOT("_mid_stance_transition()"))
                            QTimer.singleShot(300, Qt.TimerType.PreciseTimer, self, SLOT("_terminal_stance_transition()"))
                            QTimer.singleShot(500, Qt.TimerType.PreciseTimer, self, SLOT("_pre_swing_transition()"))
            else: 
                # compute loading response duration as 1/6 of stance, convert seconds -> milliseconds
                LR_time_ms = max(100, int((self.stance_time / 6.0) * 1000.0)) # always stimulate at least for 100 ms 
                self.FSR2_loading_response_durations = np.append(self.FSR2_loading_response_durations, LR_time_ms)
                QTimer.singleShot(LR_time_ms, Qt.TimerType.PreciseTimer, self, SLOT("_mid_stance_transition()"))
                
                # compute mid stance duration as 1/3 of stance, convert seconds -> milliseconds
                MST_time_ms = max(200, int((self.stance_time / 3.0) * 1000.0)) # always stimulate at least for 100 ms 
                self.FSR2_mid_stance_durations = np.append(self.FSR2_mid_stance_durations, MST_time_ms)
                delay_MST= LR_time_ms + MST_time_ms
                QTimer.singleShot(delay_MST, Qt.TimerType.PreciseTimer, self, SLOT("_terminal_stance_transition()"))

                # compute terminal stance duration , convert seconds -> milliseconds
                TST_time_ms = max(200, int((self.stance_time / self.terminal_stance_divider) * 1000.0)) # always stimulate at least for 300 ms 
                delay_TST= delay_MST + TST_time_ms
                print(f"DEBUG: Terminal stance duration = {TST_time_ms} ms, divider = {self.terminal_stance_divider}")
                QTimer.singleShot(delay_TST, Qt.TimerType.PreciseTimer, self, SLOT("_pre_swing_transition()"))
    


        # Detect toe off
        elif data_mean[-1] < abs(self.threshold - self.hysteresis) and self.active_phase == Phase.MID_STANCE:
            self.__record_toe_off(self.timestamps[-1])
            self.__transition_to(Phase.SWING)
            
            if self.heel_strike_timestamps.size == 0 or self.toe_off_timestamps.size == 0:
                # not enough data yet to compute stance_time
                pass
            
            else:
                dt = float(self.toe_off_timestamps[-1] - self.heel_strike_timestamps[-1])
                self.FSR2_stance_durations = np.append(self.FSR2_stance_durations, dt)
                if self.stance_time == 0:
                    self.stance_time = dt
                else:
                   # smoother update (alpha controls responsiveness), if we averaged the mean and new, 50% of the value will depend on the new 
                    alpha = 0.2
                    self.stance_time = alpha * dt + (1.0 - alpha) * self.stance_time

        # Separate case to detect the first step
        if self.first_step_detected is not FirstStep.DETECTED:
            
            # TODO Detect first step from fsr values
            pass

        # For the steps after the first step
        else:
            # TODO Detect steps from fsr values
            pass

        # Public helper for counting steps
    def get_step_count(self) -> int:
        try:
            # Prefer heel-strike timestamps if present
            return int(len(self.heel_strike_timestamps))
        except Exception:
            # Fallback to phase counters if you store HS there
            try:
                return int(self.phase_counters.get(Phase.LOADING_RESPONSE, 0))
            except Exception:
                return 0

    ###############################
    # Private methods
    ###############################

    def __transition_to(self, next_phase: Phase) -> None:
        """Transition to the next phase of the gait cycle and record the timestamp.

        :param next_phase: The next phase to transition to.
        :type next_phase: Phase
        :raises ValueError: If next_phase is not an instance of the Phase Enum.
        """
        if not isinstance(next_phase, Phase):
            raise ValueError("next_phase must be an instance of the Phase Enum")
        # Update counter and current state
        if next_phase != self.active_phase:
            # print(f"Transitioning from {self.current_phase} to {next_phase}")  # print for debugging
            self.phase_counters[next_phase] += 1
            self.active_phase = next_phase
            self.phase_timestamps[next_phase] = np.append(self.phase_timestamps[next_phase], self.timestamps[-1])
            try:
                # emit numeric Phase so Qt signals are simple to forward
                self.phase_changed.emit(int(self.active_phase.value))
            except Exception:
                pass
            # Emit on heel-strike phase if applicable
            if next_phase == Phase.LOADING_RESPONSE:
                self.steps_changed.emit(self.get_step_count())
                
    @Slot()
    def _mid_stance_transition(self) -> None:
        """Transition to the mid stance phase of the gait cycle and record the timestamp.
        This function is used for QTimer.singleShot as it requires a member function as a string (slot) -> no arguments are passed.
        """
        self.__transition_to(Phase.MID_STANCE)
        
    @Slot()
    def _terminal_stance_transition(self) -> None:
        """Transition to the pre swing phase of the gait cycle and record the timestamp.
        This function is used for QTimer.singleShot as it requires a member function as a string (slot) -> no arguments are passed.
        """
        self.__transition_to(Phase.TERMINAL_STANCE)
        
    @Slot()
    def _pre_swing_transition(self) -> None:
        """Transition to the pre swing phase of the gait cycle and record the timestamp.
        This function is used for QTimer.singleShot as it requires a member function as a string (slot) -> no arguments are passed.
        """
        self.__transition_to(Phase.PRE_SWING)

    def __detect_steps(self, timestamp: float) -> None:
        """Detect and handle phase transitions of the gait based on the peak timestamp.\n

        UPDATE THIS PLEASE
        This function classifies the detected peak as either a heel strike or a toe off based on the distance to the last valley and the last peak.
        The peak is classified as a heel strike if the distance to the last valley is less than the distance to the last recorded peak, and as a toe off otherwise.

        For the detection of the first step, another function is used.

        :param peak_timestamp: The timestamp of the detected peak.
        :type peak_timestamp: float
        """
        # TODO Detect heel strike and toe off from fsr values

        if True:  # TODO: Replace with actual condition to check if toe off
            self.__record_toe_off(timestamp)
            self.__transition_to(Phase.SWING)

        # Otherwise, heel strike
        else:
            self.__record_heel_strike(timestamp)
            # Transition to STANCE phase
            self.__transition_to(Phase.STANCE)

    def __detect_first_step(self, valley_timestamp: float, peak_timestamp: float) -> None:
        """Detect the first step of the gait cycle based on the peak and valley timestamps.\n
        This function is only called for the first step of the gait cycle and is not called again after the first step is detected.

        This function waits for the first valley to be detected and then starts detecting the first step.\n
        Valley -> Peak (Heel Strike) -> Peak (Toe Off) -> First Step Detected.

        :param valley_timestamp: The timestamp of the detected valley.
        :type valley_timestamp: float
        :param peak_timestamp: The timestamp of the detected peak.
        :type peak_timestamp: float
        """
        # The first peak after the valley is detected (short peak)
        if self.first_step_detected == FirstStep.DETECTING_HEEL_STRIKE:
            # Ensure the "long" peak is not the same as the "short" peak
            if peak_timestamp > self.heel_strike_timestamps[-1]:
                self.__record_toe_off(peak_timestamp)
                self.__transition_to(Phase.SWING)
                # Update the last peak type -> first step fully detected, this function should not be called anymore
                self.first_step_detected = FirstStep.DETECTED

        # Check if a valley was detected before the latest peak
        elif peak_timestamp > valley_timestamp:
            if peak_timestamp - valley_timestamp < 0.5:  # 0.5 seconds
                self.__record_heel_strike(peak_timestamp)
                self.__transition_to(Phase.STANCE)
                # Update the last peak type
                self.first_step_detected = FirstStep.DETECTING_TOE_OFF

    def __record_heel_strike(self, timestamp: float) -> None:
        """Record the time of the detected and classified heel strike."""
        self.heel_strike_timestamps = np.append(self.heel_strike_timestamps, timestamp)
        self.heel_strike = np.append(self.heel_strike, self.data_bf[-1])

    def __record_toe_off(self, timestamp: float) -> None:
        """Record the time of the detected and classified toe off."""
        self.toe_off_timestamps = np.append(self.toe_off_timestamps, timestamp)
        self.toe_off = np.append(self.toe_off, self.data_ff[-1])

    def __record_mid_stance(self, timestamp: float) -> None:
        """Record the time of the detected and classified mid stance."""
        self.mid_stance_timestamps = np.append(self.mid_stance_timestamps, timestamp)
        self.mid_stance = np.append(self.mid_stance, self.data_mf[-1])
        
        
        
        
class FSRGaitFSM_DUMMY(QObject):
    # initialize the class and phase counters
    steps_changed = Signal(int)
    # emit when active phase changes (value is Phase enum value -> int)
    phase_changed = Signal(int)

    # initialize the class and phase counters
    def __init__(self):
        super().__init__()  # required for Qt signals to work

        self.active_phase = Phase.UNKNOWN  # Initial state
        self.previous_phase = Phase.UNKNOWN  # Previous state
        self.phase_counters = {Phase.LOADING_RESPONSE: 0, Phase.MID_STANCE: 0, Phase.PRE_SWING: 0, Phase.SWING: 0, Phase.UNKNOWN: 0}
        self.phase_timestamps = {
            Phase.LOADING_RESPONSE: np.array([]),
            Phase.MID_STANCE: np.array([]),
            Phase.PRE_SWING: np.array([]),
            Phase.SWING: np.array([]),
            Phase.UNKNOWN: np.array([]),
        }
        self.active_phase = Phase.UNKNOWN  # Initial state
        self.previous_phase = Phase.UNKNOWN  # Previous state
        self.phase_counters = {Phase.LOADING_RESPONSE: 0, Phase.MID_STANCE: 0, Phase.TERMINAL_STANCE:0, Phase.PRE_SWING: 0, Phase.SWING: 0, Phase.UNKNOWN: 0}
        self.phase_timestamps = {
            Phase.LOADING_RESPONSE: np.array([]),
            Phase.MID_STANCE: np.array([]),
            Phase.TERMINAL_STANCE: np.array([]),
            Phase.PRE_SWING: np.array([]),
            Phase.SWING: np.array([]),
            Phase.UNKNOWN: np.array([]),
        }

        self.heel_strike = np.array([])
        self.toe_off = np.array([])
        self.mid_stance = np.array([])

        self.heel_strike_timestamps = np.array([])
        self.toe_off_timestamps = np.array([])
        self.mid_stance_timestamps = np.array([])

        self.data_ff = deque(maxlen=1000)  # Data for the front foot sensor
        self.data_mf = deque(maxlen=1000)  # Data for the middle foot sensor
        self.data_bf = deque(maxlen=1000)  # Data for the back foot sensor
        
        self.timestamps = deque(maxlen=1000)

        # Data for the offline analysis
        self.data_ff_offline = np.array([])
        self.data_mf_offline = np.array([])
        self.data_bf_offline = np.array([])
        self.timestamps_offline = np.array([])
        
        #Loading phase info
        self.stance_time=0
        self.FSR2_loading_response_durations = np.array([])
        self.FSR2_mid_stance_durations = np.array([])
        self.FSR2_stance_durations = np.array([])
        
        self.timestamps_fsr = deque(maxlen=1000)

        # Data for the offline analysis
        self.data_ff_offline = np.array([])
        self.data_mf_offline = np.array([])
        self.data_bf_offline = np.array([])
        self.timestamps_fsr_offline = np.array([])
        
        # IMU DATA
        self.data_gy = deque(maxlen=1000)
        self.data_gy_rom = []
        self.timestamps_imu =deque(maxlen=1000)
        self.timestamps_rom_imu = []
        self._deg = 180.0 / np.pi
        self.valley_height = 0.5
        self.distance_valleys = 45
        self.min_distance_between_valleys = 50
        self._last_valley_ts = None
        self.valleys = np.array([])                # move/create outside the FES-guard
        self.valleys_timestamps = np.array([])
        # optionally make window/threshold configurable
        self.valley_search_window_s = 0.6
        self._midswing_start_imu_ts = None
        

        
        #Loading phase info
        self.stance_time=0
        self.FSR2_loading_response_durations = np.array([])
        self.FSR2_mid_stance_durations = np.array([])
        self.FSR2_stance_durations = np.array([])


    ###############################
    # Public methods
    ###############################

    def is_phase_unknown(self) -> bool:
        # Check if the current phase is "UNKNOWN"
        return self.active_phase == Phase.UNKNOWN

    def changed_phase(self) -> bool:
        # Check if the current phase has changed from the previous one
        return False

    def update_previous_phase(self):
        # Update the previous phase to the current one
        self.previous_phase = self.active_phase

    def update_fsr(self):
        """Update the FSR data by pulling a chunk of samples from the LSL stream."""
        # Pull data from lsl stream
        pass
    
    def update_fsr_imu(self):
        """Update the FSR data by pulling a chunk of samples from the LSL stream."""
        # Pull data from lsl stream
        pass
    
    def fsr_phase_detection(self):
        """Detect the gait phase based on the IMU data."""
        pass

        # Public helper for counting steps
    def get_step_count(self) -> int:
        try:
            # Prefer heel-strike timestamps if present
            return int(len(self.heel_strike_timestamps))
        except Exception:
            # Fallback to phase counters if you store HS there
            try:
                return int(self.phase_counters.get(Phase.LOADING_RESPONSE, 0))
            except Exception:
                return 0

    ###############################
    # Private methods
    ###############################

    def __transition_to(self, next_phase: Phase) -> None:
        pass
                
    @Slot()
    def _mid_stance_transition(self) -> None:
        """Transition to the mid stance phase of the gait cycle and record the timestamp.
        This function is used for QTimer.singleShot as it requires a member function as a string (slot) -> no arguments are passed.
        """
        pass
        
    @Slot()
    def _pre_swing_transition(self) -> None:
        """Transition to the pre swing phase of the gait cycle and record the timestamp.
        This function is used for QTimer.singleShot as it requires a member function as a string (slot) -> no arguments are passed.
        """
        pass

    def __detect_steps(self, timestamp: float) -> None:
        pass

    def __detect_first_step(self, valley_timestamp: float, peak_timestamp: float) -> None:
       
        pass

    def __record_heel_strike(self, timestamp: float) -> None:
        pass

    def __record_toe_off(self, timestamp: float) -> None:
        pass

    def __record_mid_stance(self, timestamp: float) -> None:
        pass