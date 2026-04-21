import numpy as np
from scipy.signal import find_peaks
from pylsl import StreamInlet
from collections import deque
from enum import Enum
from PySide6.QtCore import QTimer, Qt, QObject, Slot, SLOT, Signal
from .gait_phases import Phase

#PEAK_DETECTION_DEADZONE = 0.25  # seconds
#HEEL_STRIKE_PEAK_RANGE = 0.5  # seconds

######################################################################
""" Parameters for gait phase and peak detection """
######################################################################

# DISTANCE
# we search the higher peak in this distance from the detected peak (search space). if its high it helps in detecting only the higher peak.
# we need it pretty small because for HS: the two small peaks ("HS1, HS2") for HS are both detected (if initial_distance < distance btw HS1 and HS2),
# but the second one is discarded since min_distance_between peaks < distance btw HS1 and HS2.
# set to this value that is less than half of the distance btw the two short peaks at HS (i.e. 40/2)

# MIN_DISTANCE_BETWEEN PEAKS
# this should be pretty high (if the signal range is small is modified to be higher), it helps in removing the unwanted misdetection for the same class of peaks.
# short and long peaks are discriminated before in the function and then the filtering action based on this parameter happens, so it prevents to detect multiple
# times HS or TO events (e.g. HS[-2] - HS[-1] should be > initial_min_distance_between_peaks )
# in small valocities scenario increasing it helps to prevent detecting TO as HS, indeed 200*1.65 = 330, that is the length of the step (from short to long 300-320) + half valley (70/2 = 35)

# INITIAL_PROMINENCE
# set really small, can help in detecting peaks, should not be set too high to avoid discarding useful short peaks in small velocity regimes
# with this value it doesnt affect higher speed regimes

parameters = {
    "peak_threshold": 0.25,  # pretty small for 3km/h but for smaller velocities is necessary to be like this (from 1.5 km/h on we lose HS peaks otherwise)
    "distance": 25,  # Required minimal horizontal distance (>= 1) in samples between neighboring peaks. Smaller peaks are removed first until the condition is fulfilled for all remaining peaks.
    "min_distance_between_peaks": 25,  # of the same type (e.g., min distance between short_a and short_a...) --> OK (can be more)
    "valley_height": 0.5,  # height for valleys (maximum negative value -> peak has to be lower than -this value)
    "distance_valleys": 45,  # to check
    "min_distance_between_valleys": 50,  # minimum distance between valleys
    "prominence": 0.25,  # prominence threshold for peaks
    "peak_detection_deadzone": 0.25 , # in seconds
    "heel_strike_peak_range" : 1 ,# in seconds

}

class FirstStep(Enum):
    DETECTING_HEEL_STRIKE = 1
    DETECTING_TOE_OFF = 2
    DETECTED = 3


def filter_peaks_by_min_distance(peaks, min_distance) -> np.ndarray:
    # No filtering required if there is only one peak or none
    if len(peaks) < 2:
        return peaks

    # Filter by taking the first peak and then checking the distance to the next peaks
    # If the distance is greater than min_distance, add the peak to the filtered list
    filtered_peaks = [peaks[0]]
    for i in range(1, len(peaks)):
        if peaks[i] - filtered_peaks[-1] >= min_distance:
            filtered_peaks.append(peaks[i])
    return np.array(filtered_peaks)


# Identification of heel strike and toe off
def identify_gait_phases(
    data: np.ndarray,
    peak_threshold: float,
    distance: float,
    min_distance_between_peaks: float,
    prominence: float,
) -> tuple[np.ndarray, np.ndarray]:
    # Prominence can be useful in the slow speed regime
    peaks, _ = find_peaks(data, height=peak_threshold, prominence=prominence, distance=distance)

    # Filter the detected peaks by a minimum distance
    peaks = filter_peaks_by_min_distance(peaks, min_distance_between_peaks)

    height_peaks = data[peaks]

    return peaks, height_peaks


def identify_valleys(data: np.ndarray, valley_height: float, distance_valleys: float, min_distance_between_valleys: float) -> np.ndarray:
    # Find valleys in the data, by finding peaks of the inverted signal
    valleys, _ = find_peaks(-data, height=valley_height, distance=distance_valleys)
    valleys = filter_peaks_by_min_distance(valleys, min_distance_between_valleys)
    return valleys


class IMUGaitFSM(QObject):
    # initialize the class and phase counters
    steps_changed = Signal(int)
    phase_changed = Signal(int)
    # initialize the class and phase counters
    def __init__(self, inlet: StreamInlet, speed: float, terminal_stance_divider: int, split_stance: bool = True, FES: bool =False, both_imu_methods: bool = False, do_closed_loop: bool = False):
        """Initialize the IMU Gait Finite State Machine

        :param inlet: The LSL inlet for receiving IMU data
        :type inlet: StreamInlet
        :param split_stance: The flag to indicate whether to split the stance phase into loading response and mid stance, defaults to True
        :type split_stance: bool, optional
        :param fast_walking: Flag to indicate if the gait is fast walking, defaults to False
        :type fast_walking: bool, optional
        """
        super().__init__()
        self.inlet = inlet
        self.split_stance = split_stance  # Flag to indicate whether to split the stance phase
        self.active_phase = Phase.UNKNOWN  # Initial state
        self.previous_phase = Phase.UNKNOWN  # Previous state
        self.phase_counters = {Phase.STANCE: 0, Phase.SWING: 0, Phase.UNKNOWN: 0}
        self.phase_timestamps = {Phase.STANCE: np.array([]), Phase.SWING: np.array([]), Phase.UNKNOWN: np.array([])}
        self.speed = speed
        self.both_imu_methods = both_imu_methods
        self.terminal_stance_divider=terminal_stance_divider
        
        self.FES=FES
        self.do_closed_loop=do_closed_loop
        # helper used when splitting SWING into MID_SWING -> TERMINAL_SWING
        self._awaiting_terminal_swing = False
        self._last_toe_off_ts = None
        
        if FES: #If FES is true we will split swing
            self.phase_counters[Phase.MID_SWING] = 0
            self.phase_counters[Phase.TERMINAL_SWING] = 0
            self.phase_timestamps[Phase.MID_SWING] = np.array([])
            self.phase_timestamps[Phase.TERMINAL_SWING] = np.array([])
            self.valleys = np.array([])                # ensure valleys exist
            self.valleys_timestamps = np.array([])     # ensure valley timestamps exist

        
        # Add loading response and mid stance to the phase counters and timestamps if the stance phase is split
        if split_stance:
            self.phase_counters[Phase.LOADING_RESPONSE] = 0
            self.phase_counters[Phase.MID_STANCE] = 0
            self.phase_counters[Phase.TERMINAL_STANCE]= 0
            self.phase_counters[Phase.PRE_SWING] = 0
            self.phase_timestamps[Phase.LOADING_RESPONSE] = np.array([])
            self.phase_timestamps[Phase.MID_STANCE] = np.array([])
            self.phase_timestamps[Phase.TERMINAL_STANCE] = np.array([])
            self.phase_timestamps[Phase.PRE_SWING] = np.array([])

        self.heel_strike_peaks = np.array([])
        self.toe_off_peaks = np.array([])
        self.peaks = np.array([])
        self.valleys = np.array([])
        self.height_toe_off = np.array([])
        self.height_heel_strike = np.array([])
        self.height_peaks = np.array([])

        self.heel_strike_peaks_timestamps = np.array([])
        self.toe_off_peaks_timestamps = np.array([])
        self.valleys_timestamps = np.array([])
        self.height_toe_off = np.array([])
        self.height_heel_strike = np.array([])

        self.data_gy = deque(maxlen=1000)
        self.timestamps = deque(maxlen=1000)
        self.quaternion = deque(maxlen=10)  # Quaternion data for IMU
        self.data_gx_rom = []
        self.data_gy_rom = []
        self.data_gz_rom = []
        self.data_accx_rom = []
        self.data_accy_rom = []
        self.data_accz_rom = []
        self.data_quatw_rom = []
        self.data_quatx_rom = []
        self.data_quaty_rom = []
        self.data_quatz_rom = []
        # self.data_magx_rom = [] we dont send magnetometer data :(
        # self.data_magy_rom = []
        # self.data_magz_rom = []
        self.timestamps_rom = []

        self.first_step_detected = FirstStep.DETECTING_HEEL_STRIKE  # Initial state for first step detection
        
        # Increase the number of samples between two peaks, if the gait is slow (e.g., walking at 1 km/h)
        
        self.stream_name = self.inlet.info().name() # extract name of stream 
        
        if speed > 1.5:
            fast_walking= True
        else:
            fast_walking = False
        
        if self.stream_name in ("Right Shank", "Left Shank"): # method S1
            if fast_walking:
                parameters['min_distance_between_peaks'] = 15
                parameters['prominence'] = 0.5
                parameters['valley_height'] = 1.5
            else:
                if speed <= 0.4:
                    parameters['peak_threshold'] = 0.14
                    parameters['distance'] = 75
                    parameters['min_distance_between_peaks'] = 75
                    parameters['prominence'] = 0.12
                    parameters['valley_height'] = 0.5
                    parameters['distance_valleys'] = 45
                    parameters['min_distance_between_valleys'] = 50
                    parameters['peak_detection_deadzone'] = 0.25
                    parameters['heel_strike_peak_range'] = 2.5

                elif 0.4 < speed <= 0.8: 
                    parameters['peak_threshold'] = 0.20
                    parameters['distance'] = 25
                    parameters['min_distance_between_peaks'] = 25
                    parameters['prominence'] = 0.20
                    parameters['valley_height'] = 0.5
                    parameters['distance_valleys'] = 45
                    parameters['min_distance_between_valleys'] = 50
                    parameters['peak_detection_deadzone'] = 0.25
                    parameters['heel_strike_peak_range'] = 1
                    
                else:
                    # 0.8 – 1.5 km/h shank: the default 0.25 threshold is tuned for
                    # 3 km/h and is too high for the shank gyroscope at moderate speed.
                    # Use lower initial values so the adaptive algorithm has enough
                    # confirmed HS peaks to self-calibrate amplitude from the start.
                    parameters['peak_threshold'] = 0.14
                    parameters['prominence']     = 0.10
                    parameters['distance']       = 30
                    parameters['min_distance_between_peaks'] = 30
                    parameters['valley_height']  = 0.4
                    parameters['distance_valleys'] = 40
                    parameters['min_distance_between_valleys'] = 45

                
        elif self.stream_name in ("Right Foot", "Left Foot"): # Method F1 
            if fast_walking:
                parameters['min_distance_between_peaks'] = 15
                parameters['prominence'] = 0.5
                parameters['valley_height'] = 1.5
            else:
                if speed <= 0.3:
                    parameters['peak_threshold'] = 0.3
                    parameters['distance'] = 35
                    parameters['min_distance_between_peaks'] = 35
                    parameters['prominence'] = 0.3
                    parameters['valley_height'] = 0.5
                    parameters['distance_valleys'] = 45
                    parameters['min_distance_between_valleys'] = 50
                    parameters['peak_detection_deadzone'] = 0.25
                    parameters['heel_strike_peak_range'] = 1

                elif 0.3 < speed <= 0.8: 
                    parameters['peak_threshold'] = 0.25
                    parameters['distance'] = 25
                    parameters['min_distance_between_peaks'] = 25
                    parameters['prominence'] = 0.5
                    parameters['valley_height'] = 0.5
                    parameters['distance_valleys'] = 45
                    parameters['min_distance_between_valleys'] = 50
                    parameters['peak_detection_deadzone'] = 0.25
                    parameters['heel_strike_peak_range'] = 1
                    
                else: # this would mean 0.8 km/h - 1.5 km/h, and we leave the parameters as they are
                    pass 
                    
                    
                
            
        # Parameters for peak detection
        self.peak_threshold = parameters["peak_threshold"]
        self.distance = parameters["distance"]
        self.min_distance_between_peaks = parameters["min_distance_between_peaks"]
        self.valley_height = parameters["valley_height"]
        self.distance_valleys = parameters["distance_valleys"]
        self.min_distance_between_valleys = parameters["min_distance_between_valleys"]
        self.prominence = parameters["prominence"]
        self.peak_detection_deadzone = parameters['peak_detection_deadzone']
        self.heel_strike_peak_range = parameters['heel_strike_peak_range']


        self.active_subphase = Phase.UNKNOWN  # Initial state
        self.previous_subphase = Phase.UNKNOWN  # Previous state
        self.subphase_counters = {
            Phase.LOADING_RESPONSE: 0,
            Phase.MID_STANCE: 0,
            Phase.PRE_SWING: 0,
            Phase.MID_SWING: 0,
            Phase.TERMINAL_SWING: 0,
            Phase.UNKNOWN: 0,
        }

        self.subphase_timestamps = {
            Phase.LOADING_RESPONSE: np.array([]),
            Phase.MID_STANCE: np.array([]),
            Phase.PRE_SWING: np.array([]),
            Phase.MID_SWING: np.array([]),
            Phase.TERMINAL_SWING: np.array([]),
            Phase.UNKNOWN: np.array([]),
        }
        
        #Loading phase info
        self.stance_time=0
        self.loading_response_durations = np.array([])
        self.mid_stance_durations = np.array([])
        self.stance_durations = np.array([])

    ###############################
    # Public methods
    ###############################

    def is_phase_unknown(self) -> bool:
        # Check if the current phase is "UNKNOWN"
        return self.active_phase == Phase.UNKNOWN

    def is_subphase_unknown(self) -> bool:
        # Check if the current subphase is "UNKNOWN"
        return self.active_subphase == Phase.UNKNOWN

    def changed_phase(self) -> bool:
        # Check if the current phase has changed from the previous one
        return self.active_phase != self.previous_phase

    def changed_subphase(self) -> bool:
        # Check if the current subphase has changed from the previous one
        return self.active_subphase != self.previous_subphase

    def update_previous_phase(self):
        # Update the previous phase to the current one
        self.previous_phase = self.active_phase

    def update_previous_subphase(self):
        # Update the previous subphase to the current one
        self.previous_subphase = self.active_subphase

    def update_imu(self):
        """Update the IMU data by pulling a chunk of samples from the LSL stream."""
        # Pull data from lsl stream
        samples, timestamps = self.inlet.pull_chunk(timeout=0.001, max_samples=1000)

        if timestamps:
            # Extend deque with new data, data_gy is the only one used online
            if self.do_closed_loop is True: # Assumes Functional Calibration
                self.data_gy.extend(sample[4] for sample in samples)
            else: #open-loop doesnt need calibration for now so just invert y
                self.data_gy.extend(-sample[4] for sample in samples) # ADDING A MINUS INORDER TO AVOID CALIBRATION OF IMU SENSORS, THIS ASSUMES THAT IMU IS PLACED ON THE FRONTAL PLANE, ON THE SHANK JUST BELOW THE KNEES, WITH THE X-SENSE LOGO AT THE BOTTOM (READABLE)
            self.quaternion.extend([timestamp] + sample[6:10] for sample, timestamp in zip(samples, timestamps))
            self.timestamps.extend(timestamps)

            # Update the data for ROM calculation (offline)
            self.data_gx_rom.extend(sample[3] for sample in samples)
            if self.do_closed_loop is True: # Assumes Functional Calibration
                self.data_gy_rom.extend(sample[4] for sample in samples)
            else: #open-loop doesnt need calibration for now so just invert y
                self.data_gy_rom.extend(-sample[4] for sample in samples)
            
            self.data_gz_rom.extend(sample[5] for sample in samples)
            self.data_accx_rom.extend(sample[0] for sample in samples)
            self.data_accy_rom.extend(sample[1] for sample in samples)
            self.data_accz_rom.extend(sample[2] for sample in samples)
            
            self.data_quatw_rom.extend(sample[6] for sample in samples)
            self.data_quatx_rom.extend(sample[7] for sample in samples)
            self.data_quaty_rom.extend(sample[8] for sample in samples)
            self.data_quatz_rom.extend(sample[9] for sample in samples)
            
            # self.data_magx_rom.extend(sample[10] for sample in samples) we dont send magnetometer data :(
            # self.data_magy_rom.extend(sample[11] for sample in samples)
            # self.data_magz_rom.extend(sample[12] for sample in samples)
            
            
            self.timestamps_rom.extend(timestamps)
            
    def get_quaternion(self, last_n: int = None) -> np.ndarray[float]:
        """Get the quaternion data from the IMU."""
        if last_n is not None and last_n > 0:
            return np.array(self.quaternion[-last_n:])
        return np.array(self.quaternion)

    def imu_phase_detection(self):
        """Detect the gait phase based on the IMU data."""
        # Ensure we have enough data points to update the plot
        # (changing this parameter would not affect the phase counters result but only the plots' starting point)
        if len(self.data_gy) <= 100:
            return

        # Detect the peaks and valleys in the data_gy (angle of shank)
        self.peaks, self.height_peaks = identify_gait_phases(
            np.array(self.data_gy),
            self.peak_threshold,
            self.distance,
            self.min_distance_between_peaks,
            self.prominence,
        )

        self.valleys = identify_valleys(
            np.array(self.data_gy),
            self.valley_height,
            self.distance_valleys,
            self.min_distance_between_valleys,
        )

        # Get the timestamp for the latest valley and record it
        valley_timestamp = self.__record_valley_timestamp()

        # Skip the rest of the function if no peaks are detected
        if self.peaks.size <= 0:
            return

        # Get timestamp for the latest peak
        timestamps_data_array = np.array(self.timestamps)
        peak_timestamp = timestamps_data_array[self.peaks[-1]]

        # Separate case to detect the first step
        if self.first_step_detected is not FirstStep.DETECTED:
            self.__detect_first_step(valley_timestamp, peak_timestamp)

        # For the steps after the first step
        else:
            self.__detect_steps(peak_timestamp)

    def imu_subphase_detection(self, other_fsm: "IMUGaitFSM"):
        """Detect the gait subphase based on the IMU data and the current phase.

        :param other_fsm: The gait finite state machine for the other leg.
        :type other_fsm: IMUGaitFSM
        """
        active_phase_other = other_fsm.active_phase
        heel_strike_peaks_other_offline = other_fsm.heel_strike_peaks_timestamps
        heel_strike_peaks_other = other_fsm.heel_strike_peaks

        if self.active_subphase == Phase.UNKNOWN or self.active_subphase == Phase.TERMINAL_SWING:
            if self.active_phase == Phase.STANCE and active_phase_other == Phase.STANCE:
                if (
                    self.heel_strike_peaks.size > 0
                    and heel_strike_peaks_other.size > 0
                    and self.heel_strike_peaks_timestamps[-1] > heel_strike_peaks_other_offline[-1]
                ):
                    self.__transition_to_sub(Phase.LOADING_RESPONSE)

        # MID STANCE subphase is defined to represent MID STANCE + TERMINAL STANCE (real subphases of the gait) together
        # this assumption follows previous considerations about muscles aactivation (the only muscles active are the SOL and GAS),
        # is possible to add also the TERMINAL STANCE subphase detection with increased risk of misdetections (the detection of the TERMINAL STANCE
        # relies on the valley of the other IMU (Behboodi 2015), this causes bad detections in real time)
        elif self.active_subphase == Phase.LOADING_RESPONSE:
            if self.active_phase == Phase.STANCE and active_phase_other == Phase.SWING:
                self.__transition_to_sub(Phase.MID_STANCE)

        elif self.active_subphase == Phase.MID_STANCE:
            if self.active_phase == Phase.STANCE and active_phase_other == Phase.STANCE:
                if (
                    self.heel_strike_peaks.size > 0
                    and heel_strike_peaks_other.size > 0
                    and self.heel_strike_peaks_timestamps[-1] < heel_strike_peaks_other_offline[-1]
                ):
                    self.__transition_to_sub(Phase.PRE_SWING)

        # MID SWING subphase is defined to represent INITIAL SWING + MID SWING (real subphases of the gait) together.
        # this assumption follows previous considerations about muscles aactivation (the only muscle active is the TA),
        # is possible to add also the INITIAL SWING subphase detection (go from 5 to 6 detected subphases), but this isnt going to
        # improve the stimulation algorithm (only the subphases detection)
        elif self.active_subphase == Phase.PRE_SWING:
            if self.active_phase == Phase.SWING and active_phase_other == Phase.STANCE:
                # no need for other conditions (we move in discrete steps in the FSM)
                self.__transition_to_sub(Phase.MID_SWING)

        elif self.active_subphase == Phase.MID_SWING:
            if self.active_phase == Phase.SWING and active_phase_other == Phase.STANCE:  # current_b == STANCE not necessary
                if (
                    self.valleys.size > 0
                    and self.valleys_timestamps[-1] > self.toe_off_peaks_timestamps[-1]
                    and self.timestamps[-1] >= self.timestamps[self.valleys[-1]]
                ):
                    # we pass over the last valley (this is true even though the last valley is not detected --> problem?)  --> we could also compare the value at the peak with later ones, similar approach
                    # data_gx_a[valleys_a[-1]] < data_gx_a[-1] < 0 (Behboodi 2015) would be another possibility to use but accuracy is lower (smaller interval to detect this subphase),
                    # anyway the approach used is coherent with what we have done for LOADING RESPONSE, considering the short_peak as the beginning of the STANCE phase instead
                    # of the zero crossing used in Behboodi (for both STANCE definition and LOADING RESPONSE condition)
                    self.__transition_to_sub(Phase.TERMINAL_SWING)

        else:
            # Default case: if no conditions are met, transition to UNKNOWN subphase
            self.__transition_to_sub(Phase.UNKNOWN)
        
    def get_step_count(self) -> int:
        # Count steps as heel strikes:
        # - split_stance=True => LOADING_RESPONSE increments at HS
        # - split_stance=False => STANCE increments at HS
        try:
            return (
                int(self.phase_counters[Phase.LOADING_RESPONSE])
                if self.split_stance
                else int(self.phase_counters[Phase.STANCE])
            )
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
            # check if both imu are in used and disable the step counter if yes
            if  not self.both_imu_methods:
                # Emit steps when we hit a heel-strike phase
                if (self.split_stance and next_phase == Phase.LOADING_RESPONSE) or (not self.split_stance and next_phase == Phase.STANCE):
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

    def __transition_to_sub(self, next_subphase: Phase):
        """Transition to the next subphase of the gait cycle and record the timestamp.

        :param next_phase: The next subphase to transition to.
        :type next_phase: Phase
        :raises ValueError: If next_phase is not an instance of the Phase Enum.
        """
        if not isinstance(next_subphase, Phase):
            raise ValueError("next_subphase must be an instance of the Phase Enum")
        # Update counter and current state
        if next_subphase != self.active_subphase:
            # print(f"Transitioning from {self.current_phase} to {next_phase}")  # print for debugging
            self.subphase_counters[next_subphase] += 1
            self.active_subphase = next_subphase
            self.subphase_timestamps[next_subphase] = np.append(self.subphase_timestamps[next_subphase], self.timestamps[-1])

    def __detect_steps(self, peak_timestamp: float) -> None:
        """Detect and handle phase transitions of the gait based on the peak timestamp.\n
        This function classifies the detected peak as either a heel strike or a toe off based on the distance to the last valley and the last peak.
        The peak is classified as a heel strike if the distance to the last valley is less than the distance to the last recorded peak, and as a toe off otherwise.

        For the detection of the first step, another function is used.

        :param peak_timestamp: The timestamp of the detected peak.
        :type peak_timestamp: float
        """
        # Get closest (latest) peak to found peak (these are timestamps)
        closest_peak_timestamp = max(self.heel_strike_peaks_timestamps[-1], self.toe_off_peaks_timestamps[-1])
        # Calculate the distance to the last valley and the last peak
        distance_to_valley = peak_timestamp - self.valleys_timestamps[-1]
        distance_to_peak = peak_timestamp - closest_peak_timestamp

        # Use a deadzone [s] to avoid detecting the same peak twice
        if peak_timestamp < closest_peak_timestamp + self.peak_detection_deadzone:
            return

        # If the distance to the valley is greater than the distance to the last peak, it is classified as a toe off
        if distance_to_valley > distance_to_peak:
            self.__record_toe_off_peak(peak_timestamp)
            
            if not self.FES:  # tSCS - single SWING phase
                self.__transition_to(Phase.SWING)
            else:
                # FES: split swing. Go to MID_SWING and wait for the next valley to enter TERMINAL_SWING.
                self.__transition_to(Phase.MID_SWING)
                # mark we are awaiting the valley that will trigger TERMINAL_SWING
                self._awaiting_terminal_swing = True               
                self._last_toe_off_ts = peak_timestamp
                
            if self.heel_strike_peaks_timestamps.size == 0 or self.toe_off_peaks_timestamps.size == 0:
                # not enough data yet to compute stance_time
                pass
            
            else:
                dt = float(self.toe_off_peaks_timestamps[-1] - self.heel_strike_peaks_timestamps[-1])
                self.stance_durations = np.append(self.stance_durations, dt)
                if self.stance_time == 0:
                    self.stance_time = dt
                else:
                   # smoother update (alpha controls responsiveness), if we averaged the mean and new, 50% of the value will depend on the new 
                    alpha = 0.2
                    self.stance_time = alpha * dt + (1.0 - alpha) * self.stance_time

        # If the distance to the valley is less than the distance to the last peak, it is classified as a heel strike
        else:
            self.__record_heel_strike_peak(peak_timestamp)
            # Check if the stance should be seperated into loading response and mid stance
            if self.split_stance:
                self.__transition_to(Phase.LOADING_RESPONSE)
                if self.heel_strike_peaks_timestamps.size < 2:
                    # Transition to mid stance after 100 ms
                    QTimer.singleShot(100, Qt.TimerType.PreciseTimer, self, SLOT("_mid_stance_transition()"))
                    QTimer.singleShot(300, Qt.TimerType.PreciseTimer, self, SLOT("_terminal_stance_transition()"))
                    QTimer.singleShot(500, Qt.TimerType.PreciseTimer, self, SLOT("_pre_swing_transition()"))

                else: 
                    # compute loading response duration as 1/6 of stance, convert seconds -> milliseconds
                    LR_time_ms = max(100, int((self.stance_time / 6.0) * 1000.0)) # always stimulate at least for 100 ms 
                    self.loading_response_durations = np.append(self.loading_response_durations, LR_time_ms)
                    QTimer.singleShot(LR_time_ms, Qt.TimerType.PreciseTimer, self, SLOT("_mid_stance_transition()"))
                    
                    # compute mid stance duration as 1/3 of stance, convert seconds -> milliseconds
                    MST_time_ms = max(200, int((self.stance_time / 3.0) * 1000.0)) # always stimulate at least for 300 ms 
                    self.mid_stance_durations = np.append(self.mid_stance_durations, MST_time_ms)
                    delay_MST= LR_time_ms + MST_time_ms
                    QTimer.singleShot(delay_MST, Qt.TimerType.PreciseTimer, self, SLOT("_terminal_stance_transition()"))
                   
                    # compute terminal stance duration , convert seconds -> milliseconds
                    TST_time_ms = max(200, int((self.stance_time / self.terminal_stance_divider) * 1000.0)) # always stimulate at least for 300 ms 
                    delay_TST= delay_MST + TST_time_ms
                    print(f"DEBUG: Terminal stance duration = {TST_time_ms} ms, divider = {self.terminal_stance_divider}")
                    QTimer.singleShot(delay_TST, Qt.TimerType.PreciseTimer, self, SLOT("_pre_swing_transition()"))
                   
                    
            else:
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
        if self.first_step_detected == FirstStep.DETECTING_TOE_OFF:
            # Make sure that the peak is not the same as the one detected for heel strike
            if peak_timestamp > self.heel_strike_peaks_timestamps[-1] + self.peak_detection_deadzone:
                self.__record_toe_off_peak(peak_timestamp)
                if not self.FES:  # tSCS - single SWING phase
                 self.__transition_to(Phase.SWING)
                else:
                    # FES: split swing. Go to MID_SWING and wait for the next valley to enter TERMINAL_SWING.
                    self.__transition_to(Phase.MID_SWING)
                # Update the fsm -> first step fully detected, this function should not be called anymore
                self.first_step_detected = FirstStep.DETECTED

        # Check if a valley was detected before the latest peak
        elif peak_timestamp > valley_timestamp:
            # Check if the time between the valley and the peak is less than the defined range
            # This is done in case the first heel strike peak is not detected (a toe off peak is detected instead)
            if peak_timestamp - valley_timestamp < self.heel_strike_peak_range:
                self.__record_heel_strike_peak(peak_timestamp)
                if self.split_stance:
                    self.__transition_to(Phase.LOADING_RESPONSE)
                    # Transition to mid stance after 100 ms
                    QTimer.singleShot(100, Qt.TimerType.PreciseTimer, self, SLOT("_mid_stance_transition()"))
                    QTimer.singleShot(300, Qt.TimerType.PreciseTimer, self, SLOT("_terminal_stance_transition()"))
                    QTimer.singleShot(500, Qt.TimerType.PreciseTimer, self, SLOT("_pre_swing_transition()"))
                else:
                    self.__transition_to(Phase.STANCE)
                # Update the finite state machine to detect the first step
                self.first_step_detected = FirstStep.DETECTING_TOE_OFF

    def __record_heel_strike_peak(self, peak_timestamp: float) -> None:
        """Record the time of the detected and classified heel strike peak."""
        self.heel_strike_peaks = np.append(self.heel_strike_peaks, self.peaks[-1])
        self.heel_strike_peaks_timestamps = np.append(self.heel_strike_peaks_timestamps, peak_timestamp)
        self.height_heel_strike = np.append(self.height_heel_strike, self.height_peaks[-1])
        self._adaptive_update_params()

    def __record_toe_off_peak(self, peak_timestamp: float) -> None:
        """Record the time of the detected and classified toe off peak."""
        self.toe_off_peaks = np.append(self.toe_off_peaks, self.peaks[-1])
        self.toe_off_peaks_timestamps = np.append(self.toe_off_peaks_timestamps, peak_timestamp)
        self.height_toe_off = np.append(self.height_toe_off, self.height_peaks[-1])

    def __record_valley_timestamp(self) -> float:
        """Detect and record the timestamp of the latest valley.

        :return: The timestamp of the latest valley detected or np.inf if no valleys are detected.
        :rtype: float
        """
        try:
            # Get timestamp for the latest valley
            timestamps_data_array = np.array(self.timestamps)
            valley_timestamp = timestamps_data_array[self.valleys[-1]]

            try:
                # Append the valley timestamp only if it's greater (not the same) than the last one
                # This ensures valleys_offline doesn't append the same timestamps multiple times
                if valley_timestamp > self.valleys_timestamps[-1]:
                    self.valleys_timestamps = np.append(self.valleys_timestamps, valley_timestamp)

            except IndexError:
                # Append the first valley timestamp if empty
                self.valleys_timestamps = np.append(self.valleys_timestamps, valley_timestamp)

             # If we were awaiting the terminal-swing trigger (FES mode), and the valley is after the last toe-off,
            # then transition to TERMINAL_SWING. 
            try:
                if (
                    self._awaiting_terminal_swing
                    and self.active_phase == Phase.MID_SWING
                    and self._last_toe_off_ts is not None
                    and np.isfinite(valley_timestamp)
                    and valley_timestamp > self._last_toe_off_ts
                ):
                    self._awaiting_terminal_swing = False
                    # safe transition
                    self.__transition_to(Phase.TERMINAL_SWING)
            except Exception:
                # defensive: don't let valley bookkeeping break phase logic
                self._awaiting_terminal_swing = False
            
        except IndexError:
            # No valleys detected
            return np.inf

        return valley_timestamp

    def _adaptive_update_params(self) -> None:
        """Adapt peak-detection parameters from measured inter-HS cadence and peak heights.

        Called after every Heel Strike detection. Updates both temporal parameters
        (distance, min_distance) and amplitude thresholds (peak_threshold, prominence)
        so the FSM stays accurate regardless of the manually-entered walking speed.

        Temporal adaptation
        -------------------
        Uses median of last 5 inter-HS intervals to estimate step period, then
        rescales sample-space distance parameters.  4-step warm-up, 15% hysteresis.

        Amplitude adaptation  (NEW)
        -------------------
        Uses the median height of the last 8 confirmed HS peaks.  The new threshold
        is set to 40% of that median (generous margin to not miss valid peaks) and
        the prominence to 30%.  A 20% hysteresis prevents oscillation.
        Hard lower bounds ensure we never set thresholds so low that noise triggers.
        """
        N_MIN         = 4      # warm-up: need at least this many HS events
        N_WINDOW      = 5      # rolling window: last N inter-HS intervals
        UPDATE_THR    = 0.15   # relative change required to trigger temporal update
        SR_NOMINAL    = 100.0  # Xsens Dot nominal sample rate (Hz)

        if self.heel_strike_peaks_timestamps.size < N_MIN:
            return  # still warming up

        # ── 1. Estimate step period (seconds) via median ─────────────────────
        recent_hs = self.heel_strike_peaks_timestamps[-min(N_WINDOW + 1,
                                                           self.heel_strike_peaks_timestamps.size):]
        intervals = np.diff(recent_hs)
        if intervals.size < 2:
            return  # not enough intervals for a robust median

        step_period_s = float(np.median(intervals))

        # Sanity gate: reject obviously wrong values
        if not (0.4 <= step_period_s <= 2.5):
            return

        # ── 2. Estimate sample rate from actual timestamps ────────────────────
        if len(self.timestamps) >= 50:
            ts_list = list(self.timestamps)
            sr = (len(ts_list) - 1) / (ts_list[-1] - ts_list[0])
            sr = float(np.clip(sr, 50.0, 200.0))
        else:
            sr = SR_NOMINAL

        step_period_samples = step_period_s * sr

        # ── 3. Compute new temporal parameters ───────────────────────────────
        new_dist     = int(np.clip(step_period_samples * 0.20, 10,  200))
        new_min_dist = int(np.clip(step_period_samples * 0.30, 15,  300))
        new_dist_v   = int(np.clip(step_period_samples * 0.25, 20,  200))
        new_min_v    = int(np.clip(step_period_samples * 0.35, 30,  300))

        # ── 4. Hysteresis check for temporal parameters ───────────────────────
        current_dist = self.distance
        if current_dist > 0:
            relative_change = abs(new_dist - current_dist) / current_dist
            if relative_change >= UPDATE_THR:
                # Apply temporal parameters
                self.distance                    = new_dist
                self.min_distance_between_peaks  = new_min_dist
                self.distance_valleys            = new_dist_v
                self.min_distance_between_valleys = new_min_v

        # ── 5. Amplitude adaptation from confirmed HS peak heights ────────────
        N_AMP_WINDOW  = 8    # last N confirmed HS peaks to compute median
        AMP_UPDATE_THR = 0.20  # 20 % hysteresis for amplitude
        # Hard lower bounds prevent noise from becoming valid peaks
        MIN_THRESHOLD  = 0.08
        MIN_PROMINENCE = 0.06

        if self.height_heel_strike.size >= N_AMP_WINDOW:
            recent_heights = self.height_heel_strike[-N_AMP_WINDOW:]
            median_height  = float(np.median(recent_heights))

            if median_height > 0:
                # New threshold = 40% of median HS peak height
                new_threshold  = float(np.clip(median_height * 0.40, MIN_THRESHOLD, 5.0))
                # New prominence = 30% of median HS peak height
                new_prominence = float(np.clip(median_height * 0.30, MIN_PROMINENCE, 4.0))

                # Apply only if change is significant (hysteresis)
                if self.peak_threshold > 0:
                    rel_thr = abs(new_threshold - self.peak_threshold) / self.peak_threshold
                    if rel_thr >= AMP_UPDATE_THR:
                        self.peak_threshold = new_threshold
                        self.prominence     = new_prominence


class IMUGaitFSM_2(QObject):
    # initialize the class and phase counters
    steps_changed = Signal(int)
    phase_changed = Signal(int)

    # initialize the class and phase counters
    def __init__(self, inlet: StreamInlet, speed: float, terminal_stance_divider: int, split_stance: bool = True, FES: bool = False, both_imu_methods: bool = False , do_closed_loop: bool = False): #adding speed paramter fopr slow walking , and remove fast walking
        """Initialize the IMU Gait Finite State Machine

        :param inlet: The LSL inlet for receiving IMU data
        :type inlet: StreamInlet
        :param split_stance: The flag to indicate whether to split the stance phase into loading response and mid stance, defaults to True
        :type split_stance: bool, optional
        :param fast_walking: Flag to indicate if the gait is fast walking, defaults to False
        :type fast_walking: bool, optional
        """
        super().__init__()
        self.inlet = inlet
        self.split_stance = split_stance  # Flag to indicate whether to split the stance phase
        self.active_phase = Phase.UNKNOWN  # Initial state
        self.previous_phase = Phase.UNKNOWN  # Previous state
        self.phase_counters = {Phase.STANCE: 0, Phase.SWING: 0, Phase.UNKNOWN: 0}
        self.phase_timestamps = {Phase.STANCE: np.array([]), Phase.SWING: np.array([]), Phase.UNKNOWN: np.array([])}
        self.speed = speed
        self.terminal_stance_divider=terminal_stance_divider

        
        self.FES = FES
        self.do_closed_loop=do_closed_loop
        
        self._awaiting_terminal_swing = False
        self._last_toe_off_ts = None
        
        if FES: #If FES is true we will split swing
            self.phase_counters[Phase.MID_SWING] = 0
            self.phase_counters[Phase.TERMINAL_SWING] = 0
            self.phase_timestamps[Phase.MID_SWING] = np.array([])
            self.phase_timestamps[Phase.TERMINAL_SWING] = np.array([])
            self._last_valley_ts = None
            self._awaiting_terminal_swing = False
            self._last_toe_off_ts = None
            self.valleys = np.array([])
            self.valleys_timestamps = np.array([])


        
        # Add loading response and mid stance to the phase counters and timestamps if the stance phase is split
        if split_stance:
            self.phase_counters[Phase.LOADING_RESPONSE] = 0
            self.phase_counters[Phase.MID_STANCE] = 0
            self.phase_counters[Phase.TERMINAL_STANCE]= 0
            self.phase_counters[Phase.PRE_SWING] = 0
            self.phase_timestamps[Phase.LOADING_RESPONSE] = np.array([])
            self.phase_timestamps[Phase.MID_STANCE] = np.array([])
            self.phase_timestamps[Phase.TERMINAL_STANCE] = np.array([])
            self.phase_timestamps[Phase.PRE_SWING] = np.array([])

        self.heel_strike_peaks = np.array([])
        self.toe_off_peaks = np.array([])
        self.peaks = np.array([])
        self.height_toe_off = np.array([])
        self.height_heel_strike = np.array([])
        self.height_peaks = np.array([])

        self.heel_strike_peaks_timestamps = np.array([])
        self.toe_off_peaks_timestamps = np.array([])
        self.height_toe_off = np.array([])
        self.height_heel_strike = np.array([])

        self.data_gx = deque(maxlen=1000)
        self.data_gy = deque(maxlen=1000)
        self.data_gz = deque(maxlen=1000)
        self.timestamps = deque(maxlen=1000)
        self.quaternion = deque(maxlen=10)  # Quaternion data for IMU
        self.data_gx_rom = []
        self.data_gy_rom = []
        self.data_gz_rom = []
        self.data_accx_rom = []
        self.data_accy_rom = []
        self.data_accz_rom = []
        self.data_quatw_rom = []
        self.data_quatx_rom = []
        self.data_quaty_rom = []
        self.data_quatz_rom = []
        
        # self.data_magx_rom = [] we dont send magnetometer data :()
        # self.data_magy_rom = []
        # self.data_magz_rom = []
        
        self.timestamps_rom = []

        self.first_step_detected = FirstStep.DETECTING_HEEL_STRIKE  # Initial state for first step detection
        
        # Increase the number of samples between two peaks, if the gait is slow (e.g., walking at 1 km/h)
        
        self.stream_name = self.inlet.info().name() # extract name of stream 
        
        if speed > 1.5:
            fast_walking= True # TEST WHAT PARAMETERS WORK FOR FAST WALKIONG AND 1.5 - 3 m/s
        else:
            fast_walking = False
        
        if self.stream_name in ("Right Shank", "Left Shank" , "Right Thigh", "Left Thigh"): # method S2
            if fast_walking:
                    self.TO_threshold=120
                    self.HS_threshold=30
                    self.min_event_distance=1
                    self.min_TO_HS_distance=0.25
                    self.valley_height= 1.5
                    self.distance_valleys=45
                    self.min_distance_between_valleys= 50
                    
            else:
                if speed <= 0.3:
                    self.TO_threshold=45
                    self.HS_threshold=10
                    self.min_event_distance=2
                    self.min_TO_HS_distance=1
                    self.valley_height= 0.5
                    self.distance_valleys=45
                    self.min_distance_between_valleys= 50


                elif 0.3 < speed <= 0.5: 
                    self.TO_threshold=55 
                    self.HS_threshold=10
                    self.min_event_distance=2
                    self.min_TO_HS_distance=0.5
                    self.valley_height= 0.5
                    self.distance_valleys=45
                    self.min_distance_between_valleys= 50
                    
                elif 0.5 < speed < 0.8: 
                    self.TO_threshold=67
                    self.HS_threshold=10
                    self.min_event_distance=1
                    self.min_TO_HS_distance=0.5
                    self.valley_height= 0.5
                    self.distance_valleys=45
                    self.min_distance_between_valleys= 50

                    
                else: # this would mean 0.8 km/h - 1.5 km/h, and we leave the parameters as they are
                    self.TO_threshold=75
                    self.HS_threshold=20
                    self.min_event_distance=1
                    self.min_TO_HS_distance=0.5
                    self.valley_height= 0.5
                    self.distance_valleys=45
                    self.min_distance_between_valleys= 50              
                
        elif self.stream_name in ("Right Foot", "Left Foot"): # Method F2 
            if fast_walking:
                    self.TO_threshold=200
                    self.HS_threshold=35
                    self.min_event_distance=1
                    self.min_TO_HS_distance=0.25   
                    self.valley_height= 1.5
                    self.distance_valleys=45
                    self.min_distance_between_valleys= 50
            else:
                if speed <= 0.1:
                    self.TO_threshold=25
                    self.HS_threshold=5 
                    self.min_event_distance=5
                    self.min_TO_HS_distance=2.4
                    self.valley_height= 0.5
                    self.distance_valleys=45
                    self.min_distance_between_valleys= 50
                    
                elif 0.1 < speed <= 0.5: 
                    self.TO_threshold=50
                    self.HS_threshold=25
                    self.min_event_distance=2
                    self.min_TO_HS_distance=0.5
                    self.valley_height= 0.5
                    self.distance_valleys=45
                    self.min_distance_between_valleys= 50
                
                elif 0.5 < speed <= 0.8: 
                    self.TO_threshold=100
                    self.HS_threshold=25
                    self.min_event_distance=2
                    self.min_TO_HS_distance=0.5
                    self.valley_height= 0.5
                    self.distance_valleys=45
                    self.min_distance_between_valleys= 50
                    
                else: # this would mean 0.8 km/h - 1.5 km/h, and we leave the parameters as they are
                    self.TO_threshold=125
                    self.HS_threshold=25
                    self.min_event_distance=2
                    self.min_TO_HS_distance=0.5              
                    self.valley_height= 0.5
                    self.distance_valleys=45
                    self.min_distance_between_valleys= 50 
                    


        self.active_subphase = Phase.UNKNOWN  # Initial state
        self.previous_subphase = Phase.UNKNOWN  # Previous state
        self.subphase_counters = {
            Phase.LOADING_RESPONSE: 0,
            Phase.MID_STANCE: 0,
            Phase.PRE_SWING: 0,
            Phase.MID_SWING: 0,
            Phase.TERMINAL_SWING: 0,
            Phase.UNKNOWN: 0,
        }

        self.subphase_timestamps = {
            Phase.LOADING_RESPONSE: np.array([]),
            Phase.MID_STANCE: np.array([]),
            Phase.PRE_SWING: np.array([]),
            Phase.MID_SWING: np.array([]),
            Phase.TERMINAL_SWING: np.array([]),
            Phase.UNKNOWN: np.array([]),
        }
        
        self.last_processed_time = None
        self._to_gate_open = False
        self._swing_active = False
        self._deg = 180.0 / np.pi
        
        #Loading phase info
        self.stance_time=0
        self.loading_response_durations = np.array([])
        self.mid_stance_durations = np.array([])
        self.stance_durations = np.array([])

    ###############################
    # Public methods
    ###############################

    def is_phase_unknown(self) -> bool:
        # Check if the current phase is "UNKNOWN"
        return self.active_phase == Phase.UNKNOWN

    def is_subphase_unknown(self) -> bool:
        # Check if the current subphase is "UNKNOWN"
        return self.active_subphase == Phase.UNKNOWN

    def changed_phase(self) -> bool:
        # Check if the current phase has changed from the previous one
        return self.active_phase != self.previous_phase

    def changed_subphase(self) -> bool:
        # Check if the current subphase has changed from the previous one
        return self.active_subphase != self.previous_subphase

    def update_previous_phase(self):
        # Update the previous phase to the current one
        self.previous_phase = self.active_phase

    def update_previous_subphase(self):
        # Update the previous subphase to the current one
        self.previous_subphase = self.active_subphase

    def update_imu(self):
        """Update the IMU data by pulling a chunk of samples from the LSL stream."""
        # Pull data from lsl stream
        samples, timestamps = self.inlet.pull_chunk(timeout=0.001, max_samples=1000)

        if timestamps:
            # Extend deque with new data, data_gy is the only one used online
                try:
                    self.data_gx.extend(sample[3] for sample in samples)
                except Exception:
                    pass
                if self.do_closed_loop is True:
                    self.data_gy.extend(sample[4] for sample in samples)
                else:
                    self.data_gy.extend(-sample[4] for sample in samples)
                try:
                    self.data_gz.extend(sample[5] for sample in samples)
                except Exception:
                    pass

                self.quaternion.extend([timestamp] + sample[6:10] for sample, timestamp in zip(samples, timestamps))
                self.timestamps.extend(timestamps)

                # offline / ROM bookkeeping (unchanged)
                self.data_gx_rom.extend(sample[3] for sample in samples)
                if self.do_closed_loop is True:
                    self.data_gy_rom.extend(sample[4] for sample in samples)
                else:
                    self.data_gy_rom.extend(-sample[4] for sample in samples)
                self.data_gz_rom.extend(sample[5] for sample in samples)
                self.data_accx_rom.extend(sample[0] for sample in samples)
                self.data_accy_rom.extend(sample[1] for sample in samples)
                self.data_accz_rom.extend(sample[2] for sample in samples)
                self.timestamps_rom.extend(timestamps)
                
                self.data_quatw_rom.extend(sample[6] for sample in samples)
                self.data_quatx_rom.extend(sample[7] for sample in samples)
                self.data_quaty_rom.extend(sample[8] for sample in samples)
                self.data_quatz_rom.extend(sample[9] for sample in samples)
                
                # self.data_magx_rom.extend(sample[10] for sample in samples)
                # self.data_magy_rom.extend(sample[11] for sample in samples)
                # self.data_magz_rom.extend(sample[12] for sample in samples)
            
    def get_quaternion(self, last_n: int = None) -> np.ndarray[float]:
        """Get the quaternion data from the IMU."""
        if last_n is not None and last_n > 0:
            return np.array(self.quaternion[-last_n:])
        return np.array(self.quaternion)
    


    def imu_phase_detection(self):
        """Detect the gait phase based on the IMU data."""
        # Ensure we have enough data points to update the plot
        if min(len(self.data_gx), len(self.data_gy), len(self.data_gz)) <= 100:
            return

        gx = np.asarray(self.data_gx) * self._deg
        gy = np.asarray(self.data_gy) * self._deg
        gz = np.asarray(self.data_gz) * self._deg
        ts = np.asarray(self.timestamps, dtype=float)
        if ts.size == 0:
            return

        # process only new samples
        start_idx = 0
        if self.last_processed_time is not None:
            start_idx = np.searchsorted(ts, self.last_processed_time, side="right")

        if start_idx >= ts.size:
            return

        g_norm = np.sqrt(gx*gx + gy*gy + gz*gz)

        for i in range(start_idx, ts.size):
            t = ts[i]
            norm_gyro = g_norm[i]

            # --- TO detection ---
            if norm_gyro > self.TO_threshold:
                if not self._swing_active and not self._to_gate_open:
                    last_to_ts = self.toe_off_peaks_timestamps[-1] if self.toe_off_peaks_timestamps.size else None
                    if (last_to_ts is None) or ((t - last_to_ts) >= self.min_event_distance):
                        # record toe-off
                        self.peaks = np.append(self.peaks, i)
                        self.height_peaks = np.append(self.height_peaks, gy[i])
                        self.__record_toe_off_peak(t)

                        if not self.FES:  # tSCS - single SWING phase
                            self.__transition_to(Phase.SWING)
                        else:
                            # FES: split swing
                            self.__transition_to(Phase.MID_SWING)
                            self._awaiting_terminal_swing = True
                            self._last_toe_off_ts = t

                        if self.heel_strike_peaks_timestamps.size == 0 or self.toe_off_peaks_timestamps.size == 0:
                        # not enough data yet to compute stance_time
                           pass
                    
                        else:
                            dt = float(self.toe_off_peaks_timestamps[-1] - self.heel_strike_peaks_timestamps[-1])
                            self.stance_durations = np.append(self.stance_durations, dt)

                            if self.stance_time == 0:
                                self.stance_time = dt
                            else:
                            # smoother update (alpha controls responsiveness), if we averaged the mean and new, 50% of the value will depend on the new 
                                alpha = 0.2
                                self.stance_time = alpha * dt + (1.0 - alpha) * self.stance_time
                                
                        self._to_gate_open = True
                        self._swing_active = True
            else:
                # dropping below TO threshold closes the gate next HS cycle
                pass

            # --- HS detection (only after a TO has occurred) ---
            if (norm_gyro < self.HS_threshold) and self._to_gate_open:
                #print(f"HS CHECK: norm={norm_gyro:.2f}, threshold={self.HS_threshold}")
                last_hs_ts = self.heel_strike_peaks_timestamps[-1] if self.heel_strike_peaks_timestamps.size else None
                last_to_ts = self.toe_off_peaks_timestamps[-1]      if self.toe_off_peaks_timestamps.size else None

                hs_spacing_ok    = (last_hs_ts is None) or ((t - last_hs_ts) >= self.min_event_distance)
                to_hs_spacing_ok = (last_to_ts is None)  or ((t - last_to_ts)  >= self.min_TO_HS_distance)

                if hs_spacing_ok and to_hs_spacing_ok:
                    self.peaks = np.append(self.peaks, i)
                    self.height_peaks = np.append(self.height_peaks, gy[i])
                    self.__record_heel_strike_peak(t)

                    if self.split_stance:
                        self.__transition_to(Phase.LOADING_RESPONSE)
                        if self.heel_strike_peaks_timestamps.size < 2:
                            QTimer.singleShot(100, Qt.TimerType.PreciseTimer, self, SLOT("_mid_stance_transition()"))
                            QTimer.singleShot(300, Qt.TimerType.PreciseTimer, self, SLOT("_terminal_stance_transition()"))
                            QTimer.singleShot(500, Qt.TimerType.PreciseTimer, self, SLOT("_pre_swing_transition()"))

                        else:
                            LR_time_ms = max(100, int((self.stance_time / 6.0) * 1000.0))
                            self.loading_response_durations = np.append(self.loading_response_durations, LR_time_ms)
                            QTimer.singleShot(LR_time_ms, Qt.TimerType.PreciseTimer, self, SLOT("_mid_stance_transition()"))

                            MST_time_ms = max(200, int((self.stance_time / 3.0) * 1000.0))
                            self.mid_stance_durations = np.append(self.mid_stance_durations, MST_time_ms)
                            delay_MST = LR_time_ms + MST_time_ms
                            QTimer.singleShot(delay_MST, Qt.TimerType.PreciseTimer, self, SLOT("_terminal_stance_transition()"))
                          
                            # compute terminal stance duration , convert seconds -> milliseconds
                            TST_time_ms = max(200, int((self.stance_time / self.terminal_stance_divider) * 1000.0)) # always stimulate at least for 300 ms 
                            delay_TST= delay_MST + TST_time_ms
                            print(f"DEBUG: Terminal stance duration = {TST_time_ms} ms, divider = {self.terminal_stance_divider}")
                            QTimer.singleShot(delay_TST, Qt.TimerType.PreciseTimer, self, SLOT("_pre_swing_transition()"))
                   
                    else:
                        self.__transition_to(Phase.STANCE)

                    # reset transient flags on HS
                    self._to_gate_open = False
                    self._swing_active = False
                    # also reset valley waiting state – new cycle starts
                    self._awaiting_terminal_swing = False
                    self._last_toe_off_ts = None

            # --- Valley / TERMINAL_SWING detection (FES only) ---
            if self.FES and self._awaiting_terminal_swing:
                try:
                    gy_arr = np.asarray(self.data_gy)
                    #print(f"[{self.stream_name}] Awaiting TS, t={t:.3f}, gy={gy_arr[i]:.2f}")
                    ts_arr = np.asarray(self.timestamps, dtype=float)

                    if self._last_toe_off_ts is not None:
                        start_idx_val = np.searchsorted(ts_arr, self._last_toe_off_ts, side="right")
                    else:
                        start_idx_val = 0

                    if (i - start_idx_val) > 5:
                        sub_gy = gy_arr[start_idx_val : i + 1]

                        valleys_sub = identify_valleys(
                            sub_gy,
                            self.valley_height,
                            self.distance_valleys,
                            self.min_distance_between_valleys,
                        )

                        if valleys_sub.size:
                            last_local_idx = valleys_sub[-1]
                            global_idx = start_idx_val + last_local_idx
                            valley_ts = ts_arr[global_idx]

                            if (self._last_valley_ts is not None) and (valley_ts <= self._last_valley_ts):
                                # already processed this one – do NOT return from the whole function
                                continue

                            self._last_valley_ts = valley_ts
                            self.valleys = np.append(self.valleys, global_idx)
                            self.valleys_timestamps = np.append(self.valleys_timestamps, valley_ts)

                            #print(f"[{self.stream_name}] Valley candidate at t={valley_ts:.3f}, gy={gy_arr[global_idx]:.2f}")

                            if (
                                self._last_toe_off_ts is not None
                                and valley_ts > self._last_toe_off_ts
                                and self.active_phase == Phase.MID_SWING
                            ):
                                self._awaiting_terminal_swing = False
                                self.__transition_to(Phase.TERMINAL_SWING)
                                #print(f"[{self.stream_name}] → TERMINAL_SWING at t={valley_ts:.3f}")
                except Exception:
                    pass

        self.last_processed_time = ts[-1]
    
    def get_step_count(self) -> int:
        # Count steps as heel strikes:
        # - split_stance=True => LOADING_RESPONSE increments at HS
        # - split_stance=False => STANCE increments at HS
        try:
            return (
                int(self.phase_counters[Phase.LOADING_RESPONSE])
                if self.split_stance
                else int(self.phase_counters[Phase.STANCE])
            )
        except Exception:
            return 0
        
    def __transition_to(self, next_phase: Phase) -> None:
        """Transition to the next phase of the gait cycle and record the timestamp. :param next_phase: The next phase to transition to. :type next_phase: Phase :raises ValueError: If next_phase is not an instance of the Phase Enum. """ 
        if not isinstance(next_phase, Phase): 
            raise ValueError("next_phase must be an instance of the Phase Enum") 
        # Update counter and current state 
        if next_phase != self.active_phase: 
            #print(f"Transitioning from {self.current_phase} to {next_phase}") # print for debugging s
            self.phase_counters[next_phase] += 1 
            self.active_phase = next_phase 
            self.phase_timestamps[next_phase] = np.append(self.phase_timestamps[next_phase], self.timestamps[-1])
            try:
                # emit numeric Phase so Qt signals are simple to forward
                self.phase_changed.emit(int(self.active_phase.value))
            except Exception:
                pass
            # Emit steps when we hit a heel-strike phase
            if (self.split_stance and next_phase == Phase.LOADING_RESPONSE) or (not self.split_stance and next_phase == Phase.STANCE):
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

    # def __transition_to_sub(self, next_subphase: Phase):
    #     """Transition to the next subphase of the gait cycle and record the timestamp.

    #     :param next_phase: The next subphase to transition to.
    #     :type next_phase: Phase
    #     :raises ValueError: If next_phase is not an instance of the Phase Enum.
    #     """
    #     if not isinstance(next_subphase, Phase):
    #         raise ValueError("next_subphase must be an instance of the Phase Enum")
    #     # Update counter and current state
    #     if next_subphase != self.active_subphase:
    #         # print(f"Transitioning from {self.current_phase} to {next_phase}")  # print for debugging
    #         self.subphase_counters[next_subphase] += 1
    #         self.active_subphase = next_subphase
    #         self.subphase_timestamps[next_subphase] = np.append(self.subphase_timestamps[next_subphase], self.timestamps[-1])



    # def __detect_first_step(self, valley_timestamp: float, peak_timestamp: float) -> None:
    #     """Detect the first step of the gait cycle based on the peak and valley timestamps.\n
    #     This function is only called for the first step of the gait cycle and is not called again after the first step is detected.

    #     This function waits for the first valley to be detected and then starts detecting the first step.\n
    #     Valley -> Peak (Heel Strike) -> Peak (Toe Off) -> First Step Detected.

    #     :param valley_timestamp: The timestamp of the detected valley.
    #     :type valley_timestamp: float
    #     :param peak_timestamp: The timestamp of the detected peak.
    #     :type peak_timestamp: float
    #     """
    #     # The first peak after the valley is detected (short peak)
    #     if self.first_step_detected == FirstStep.DETECTING_TOE_OFF:
    #         # Make sure that the peak is not the same as the one detected for heel strike
    #         if peak_timestamp > self.heel_strike_peaks_timestamps[-1] + self.peak_detection_deadzone:
    #             self.__record_toe_off_peak(peak_timestamp)
    #             self.__transition_to(Phase.SWING)
    #             # Update the fsm -> first step fully detected, this function should not be called anymore
    #             self.first_step_detected = FirstStep.DETECTED

    #     # Check if a valley was detected before the latest peak
    #     elif peak_timestamp > valley_timestamp:
    #         # Check if the time between the valley and the peak is less than the defined range
    #         # This is done in case the first heel strike peak is not detected (a toe off peak is detected instead)
    #         if peak_timestamp - valley_timestamp < self.heel_strike_peak_range:
    #             self.__record_heel_strike_peak(peak_timestamp)
    #             if self.split_stance:
    #                 self.__transition_to(Phase.LOADING_RESPONSE)
    #                 # Transition to mid stance after 100 ms
    #                 QTimer.singleShot(100, Qt.TimerType.PreciseTimer, self, SLOT("_mid_stance_transition()"))
    #             else:
    #                 self.__transition_to(Phase.STANCE)
    #             # Update the finite state machine to detect the first step
    #             self.first_step_detected = FirstStep.DETECTING_TOE_OFF

    def __record_heel_strike_peak(self, peak_timestamp: float) -> None:
        """Record the time of the detected and classified heel strike peak."""
        self.heel_strike_peaks = np.append(self.heel_strike_peaks, self.peaks[-1])
        self.heel_strike_peaks_timestamps = np.append(self.heel_strike_peaks_timestamps, peak_timestamp)
        self.height_heel_strike = np.append(self.height_heel_strike, self.height_peaks[-1])
        self._adaptive_update_params()

    def _adaptive_update_params(self) -> None:
        """Adapt temporal and amplitude parameters from measured inter-HS cadence (FSM_2).

        Temporal (min_event_distance, min_TO_HS_distance, valley params):
          median of last 5 inter-HS intervals, 4-step warm-up, 15% hysteresis.
        Amplitude (HS_threshold, TO_threshold):
          median of last 8 confirmed HS peak heights, 20% hysteresis.
        """
        N_MIN         = 4
        N_WINDOW      = 5
        UPDATE_THR    = 0.15
        SR_NOMINAL    = 100.0

        if self.heel_strike_peaks_timestamps.size < N_MIN:
            return

        recent_hs = self.heel_strike_peaks_timestamps[-min(N_WINDOW + 1,
                                                           self.heel_strike_peaks_timestamps.size):]
        intervals = np.diff(recent_hs)
        if intervals.size < 2:
            return

        step_period_s = float(np.median(intervals))
        if not (0.4 <= step_period_s <= 2.5):
            return

        if len(self.timestamps) >= 50:
            ts_list = list(self.timestamps)
            sr = float(np.clip(
                (len(ts_list) - 1) / (ts_list[-1] - ts_list[0]), 50.0, 200.0
            ))
        else:
            sr = SR_NOMINAL

        step_period_samples = step_period_s * sr

        # ── Temporal parameters ───────────────────────────────────────────────
        new_min_event = float(np.clip(step_period_s * 0.45, 0.3, 3.0))
        new_min_to_hs = float(np.clip(step_period_s * 0.30, 0.2, 2.5))
        new_dist_v    = int(np.clip(step_period_samples * 0.25, 20, 200))
        new_min_v     = int(np.clip(step_period_samples * 0.35, 30, 300))

        if self.min_event_distance > 0:
            rel_change = abs(new_min_event - self.min_event_distance) / self.min_event_distance
            if rel_change >= UPDATE_THR:
                self.min_event_distance           = new_min_event
                self.min_TO_HS_distance           = new_min_to_hs
                self.distance_valleys             = new_dist_v
                self.min_distance_between_valleys = new_min_v

        # ── Amplitude adaptation from confirmed HS peak heights ───────────────
        N_AMP_WINDOW   = 8
        AMP_UPDATE_THR = 0.20
        MIN_THRESHOLD  = 0.08

        if self.height_heel_strike.size >= N_AMP_WINDOW:
            median_height = float(np.median(self.height_heel_strike[-N_AMP_WINDOW:]))
            if median_height > 0:
                new_hs_thr = float(np.clip(median_height * 0.40, MIN_THRESHOLD, 5.0))
                new_to_thr = float(np.clip(median_height * 0.50, MIN_THRESHOLD, 5.0))
                if self.HS_threshold > 0:
                    rel_thr = abs(new_hs_thr - self.HS_threshold) / self.HS_threshold
                    if rel_thr >= AMP_UPDATE_THR:
                        self.HS_threshold = new_hs_thr
                        self.TO_threshold = new_to_thr

    def __record_toe_off_peak(self, peak_timestamp: float) -> None:
        """Record the time of the detected and classified toe off peak."""
        self.toe_off_peaks = np.append(self.toe_off_peaks, self.peaks[-1])
        self.toe_off_peaks_timestamps = np.append(self.toe_off_peaks_timestamps, peak_timestamp)
        self.height_toe_off = np.append(self.height_toe_off, self.height_peaks[-1])
        
    def __record_valley_timestamp(self) -> None:
        """Detect and record the timestamp of the latest valley.

        :return: The timestamp of the latest valley detected or np.inf if no valleys are detected.
        :rtype: float
        """
        try:
            # Get timestamp for the latest valley
            timestamps_data_array = np.array(self.timestamps)
            valley_timestamp = timestamps_data_array[self.valleys[-1]]

            try:
                # Append the valley timestamp only if it's greater (not the same) than the last one
                # This ensures valleys_offline doesn't append the same timestamps multiple times
                if valley_timestamp > self.valleys_timestamps[-1]:
                    self.valleys_timestamps = np.append(self.valleys_timestamps, valley_timestamp)

            except IndexError:
                # Append the first valley timestamp if empty
                self.valleys_timestamps = np.append(self.valleys_timestamps, valley_timestamp)

             # If we were awaiting the terminal-swing trigger (FES mode), and the valley is after the last toe-off,
            # then transition to TERMINAL_SWING. 
            try:
                if (
                    self._awaiting_terminal_swing
                    and self.active_phase == Phase.MID_SWING
                    and self._last_toe_off_ts is not None
                    and np.isfinite(valley_timestamp)
                    and valley_timestamp > self._last_toe_off_ts
                ):
                    self._awaiting_terminal_swing = False
                    # safe transition
                    self.__transition_to(Phase.TERMINAL_SWING)
            except Exception:
                # defensive: don't let valley bookkeeping break phase logic
                self._awaiting_terminal_swing = False
            
        except IndexError:
            # No valleys detected
            pass
        
        
        



class IMUGaitFSM_DUMMY(QObject):
    # initialize the class and phase counters
    steps_changed = Signal(int)
    # initialize the class and phase counters
    def __init__(self): #adding speed paramter fopr slow walking , and remove fast walking
        """Initialize the IMU Gait Finite State Machine

        :param inlet: The LSL inlet for receiving IMU data
        :type inlet: StreamInlet
        :param split_stance: The flag to indicate whether to split the stance phase into loading response and mid stance, defaults to True
        :type split_stance: bool, optional
        :param fast_walking: Flag to indicate if the gait is fast walking, defaults to False
        :type fast_walking: bool, optional
        """
        super().__init__()
        
        self.active_phase = Phase.UNKNOWN  # Initial state
        self.previous_phase = Phase.UNKNOWN  # Previous state

        self.active_subphase = Phase.UNKNOWN  # Initial state
        self.previous_subphase = Phase.UNKNOWN  # Previous state
        self.subphase_counters = {
            Phase.LOADING_RESPONSE: 0,
            Phase.MID_STANCE: 0,
            Phase.PRE_SWING: 0,
            Phase.MID_SWING: 0,
            Phase.TERMINAL_SWING: 0,
            Phase.UNKNOWN: 0,
        }

        self.subphase_timestamps = {
            Phase.LOADING_RESPONSE: np.array([]),
            Phase.MID_STANCE: np.array([]),
            Phase.PRE_SWING: np.array([]),
            Phase.MID_SWING: np.array([]),
            Phase.TERMINAL_SWING: np.array([]),
            Phase.UNKNOWN: np.array([]),
        }
        
       

    ###############################
    # Public methods
    ###############################

    def is_phase_unknown(self) -> bool:
        # Check if the current phase is "UNKNOWN"
        return self.active_phase == Phase.UNKNOWN

    def is_subphase_unknown(self) -> bool:
        # Check if the current subphase is "UNKNOWN"
        return self.active_subphase == Phase.UNKNOWN

    def changed_phase(self) -> bool:
        # Check if the current phase has changed from the previous one
        return False

    def changed_subphase(self) -> bool:
        # Check if the current subphase has changed from the previous one
        return self.active_subphase != self.previous_subphase

    def update_previous_phase(self):
        # Update the previous phase to the current one
        self.previous_phase = self.active_phase

    def update_previous_subphase(self):
        # Update the previous subphase to the current one
        self.previous_subphase = self.active_subphase

    def update_imu(self):
        pass
            
    def get_quaternion(self, last_n: int = None) -> np.ndarray[float]:
        """Get the quaternion data from the IMU."""
        if last_n is not None and last_n > 0:
            return np.array(self.quaternion[-last_n:])
        return np.array(self.quaternion)
    


    def imu_phase_detection(self):
       pass
    
    def get_step_count(self) -> int:
        # Count steps as heel strikes:
        # - split_stance=True => LOADING_RESPONSE increments at HS
        # - split_stance=False => STANCE increments at HS
        try:
            return (
                int(self.phase_counters[Phase.LOADING_RESPONSE])
                if self.split_stance
                else int(self.phase_counters[Phase.STANCE])
            )
        except Exception:
            return 0
        
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

    def __record_heel_strike_peak(self, peak_timestamp: float) -> None:
        """Record the time of the detected and classified heel strike peak."""
        pass

    def __record_toe_off_peak(self, peak_timestamp: float) -> None:
        """Record the time of the detected and classified toe off peak."""
        pass
        
    def __record_valley_timestamp(self) -> None:
        pass