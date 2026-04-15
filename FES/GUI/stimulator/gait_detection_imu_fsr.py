import numpy as np
from pylsl import StreamInlet
from collections import deque
from enum import Enum
from PySide6.QtCore import QTimer, Qt, QObject, Slot, SLOT, Signal
from .gait_phases import Phase
from typing import Optional
from scipy.signal import find_peaks
from .gait_detection_imu import filter_peaks_by_min_distance , identify_valleys


class FSRIMUGaitFSM(QObject):
    # initialize the class and phase counters
    steps_changed = Signal(int)
    # emit when active phase changes (value is Phase enum value -> int)
    phase_changed = Signal(int)

    # initialize the class and phase counters
    def __init__(self, inlet_fsr: StreamInlet,inlet_imu: StreamInlet, threshold: int = 5 , hysteresis: int = 2, terminal_stance_divider: int = 4 , FES: bool = False, do_closed_loop: bool = False):
        super().__init__()  # required for Qt signals to work
        self.inlet_fsr = inlet_fsr
        self.inlet_imu = inlet_imu
        self.threshold = threshold  # Threshold for phase detection
        self.hysteresis = hysteresis
        self.terminal_stance_divider=terminal_stance_divider
        
        self.FES=FES
        self.do_closed_loop=do_closed_loop
        
        # helper used when splitting SWING into MID_SWING -> TERMINAL_SWING
        self._awaiting_terminal_swing = False
        self._last_toe_off_ts = None

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
        
        if FES: #If FES is true we will split swing
            self.phase_counters[Phase.MID_SWING] = 0
            self.phase_counters[Phase.TERMINAL_SWING] = 0
            self.phase_timestamps[Phase.MID_SWING] = np.array([])
            self.phase_timestamps[Phase.TERMINAL_SWING] = np.array([])


        self.heel_strike = np.array([])
        self.toe_off = np.array([])
        self.mid_stance = np.array([])

        self.heel_strike_timestamps = np.array([])
        self.toe_off_timestamps = np.array([])
        self.mid_stance_timestamps = np.array([])

        self.data_ff = deque(maxlen=1000)  # Data for the front foot sensor
        self.data_mf = deque(maxlen=1000)  # Data for the middle foot sensor
        self.data_bf = deque(maxlen=1000)  # Data for the back foot sensor
        
        
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
        return self.active_phase != self.previous_phase

    def update_previous_phase(self):
        # Update the previous phase to the current one
        self.previous_phase = self.active_phase

    def update_fsr_imu(self):
        """Update the FSR data by pulling a chunk of samples from the LSL stream."""
        # Pull data from lsl stream
        samples_fsr, timestamps_fsr = self.inlet_fsr.pull_chunk(timeout=0.001, max_samples=1000)

        if timestamps_fsr:
            # Extend deque with new data, data_gx is the only one used online
            self.data_ff.extend(sample[0] for sample in samples_fsr)
            self.data_mf.extend(sample[1] for sample in samples_fsr)
            self.data_bf.extend(sample[2] for sample in samples_fsr)
            self.timestamps_fsr.extend(timestamps_fsr)
            
            
            # For offline analysis, store the data in numpy arrays
            self.data_ff_offline = np.append(self.data_ff_offline, np.array([sample[0] for sample in samples_fsr]))
            self.data_mf_offline = np.append(self.data_mf_offline, np.array([sample[1] for sample in samples_fsr]))
            self.data_bf_offline = np.append(self.data_bf_offline, np.array([sample[2] for sample in samples_fsr]))
            self.timestamps_fsr_offline = np.append(self.timestamps_fsr_offline, np.array(timestamps_fsr))
            
        #IMU
        # Pull data from lsl stream
        samples, timestamps = self.inlet_imu.pull_chunk(timeout=0.001, max_samples=1000)

        if timestamps:
            # Extend deque with new data, data_gy is the only one used online
            if self.do_closed_loop is True: # Assumes Functional Calibration
                self.data_gy.extend(sample[4] for sample in samples)
            else: #open-loop doesnt need calibration for now so just invert y
                self.data_gy.extend(-sample[4] for sample in samples) # ADDING A MINUS INORDER TO AVOID CALIBRATION OF IMU SENSORS, THIS ASSUMES THAT IMU IS PLACED ON THE FRONTAL PLANE, ON THE SHANK JUST BELOW THE KNEES, WITH THE X-SENSE LOGO AT THE BOTTOM (READABLE)
            self.timestamps_imu.extend(timestamps)

            # Update the data for ROM calculation (offline)
            if self.do_closed_loop is True: # Assumes Functional Calibration
                self.data_gy_rom.extend(sample[4] for sample in samples)
            else: #open-loop doesnt need calibration for now so just invert y
                self.data_gy_rom.extend(-sample[4] for sample in samples)
            
            self.timestamps_rom_imu.extend(timestamps)

    
    def _find_valley_after_toeoff(self, after_ts: float, window_s: float = 0.6) -> Optional[float]:
        """Find the first IMU valley timestamp within window_s seconds after after_ts.
        Returns None if no valley found or not enough IMU samples.
        """
        ts_arr = np.asarray(self.timestamps_imu, dtype=float)
        if ts_arr.size == 0 or after_ts is None:
            return None
        # indexes that fall within the window [after_ts, after_ts + window_s]
        start_idx = np.searchsorted(ts_arr, after_ts, side="right")
        end_ts = after_ts + window_s
        end_idx = np.searchsorted(ts_arr, end_ts, side="right")
        if (end_idx - start_idx) <= 5:
            return None
        gy_arr = np.asarray(self.data_gy) * self._deg
        sub_gy = gy_arr[start_idx:end_idx]
        valleys_sub = identify_valleys(
            sub_gy,
            self.valley_height,
            self.distance_valleys,
            self.min_distance_between_valleys,
        )
        if valleys_sub.size == 0:
            return None
        first_local_idx = int(valleys_sub[0])
        global_idx = start_idx + first_local_idx
        return float(ts_arr[global_idx])
    
    def _fsr_ts_closest_to(self, t_imu: float) -> Optional[float]:
        ts = np.asarray(self.timestamps_fsr, dtype=float)
        if ts.size == 0:
            return None
        i = int(np.searchsorted(ts, t_imu))
        if i <= 0:
            return float(ts[0])
        if i >= ts.size:
            return float(ts[-1])
        return float(ts[i-1] if (t_imu - ts[i-1]) <= (ts[i] - t_imu) else ts[i])


    def fsr_phase_detection(self):
        """Detect the gait phase based on the IMU data."""
        # Ensure we have enough data points to update the plot
        # (changing this parameter would not affect the phase counters result but only the plots' starting point)
        if len(self.data_ff) <= 100:
            return        

        ff=np.asarray(self.data_ff)
        mf=np.asarray(self.data_mf)
        bf=np.asarray(self.data_bf)
        
        gy = np.asarray(self.data_gy) * self._deg
        
        data_mean = (ff + mf + bf) / 3 

        # Detect swing if phase is unknown
        if self.active_phase == Phase.UNKNOWN and data_mean[-1] < self.threshold:
            self.__transition_to(Phase.MID_SWING if self.FES else Phase.SWING)
            if self.FES:
                self._awaiting_terminal_swing = True
                self._midswing_start_imu_ts = float(self.timestamps_imu[-1]) if len(self.timestamps_imu) else None


        # Detect heel strike
        if data_mean[-1] > abs(self.threshold + self.hysteresis) and self.active_phase in (Phase.SWING, Phase.MID_SWING, Phase.TERMINAL_SWING):
            self.__record_heel_strike(self.timestamps_fsr[-1])
            #print(f"DEBUG: HS detected ts={self.timestamps_fsr[-1]:.6f}, prev_phase={self.active_phase}")
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
                #print(f"DEBUG: Terminal stance duration = {TST_time_ms} ms, divider = {self.terminal_stance_divider}")
                #print(f"DEBUG: scheduling transitions LR={LR_time_ms}ms MST={MST_time_ms}ms TST={TST_time_ms}ms (delay_TST={delay_TST}ms)")
                QTimer.singleShot(delay_TST, Qt.TimerType.PreciseTimer, self, SLOT("_pre_swing_transition()"))
                self._awaiting_terminal_swing = False
                self._last_toe_off_ts = None
    

        # Detect toe off
        if data_mean[-1] < abs(self.threshold - self.hysteresis) and self.active_phase == Phase.PRE_SWING:
            self.__record_toe_off(self.timestamps_fsr[-1])
            #print(f"DEBUG: TO detected ts={self.timestamps_fsr[-1]:.6f}, prev_phase={self.active_phase}; FES -> MID_SWING, midswing_start_imu_ts={self._midswing_start_imu_ts}")

            if not self.FES:
                self.__transition_to(Phase.SWING)
            
            else:
                self.__transition_to(Phase.MID_SWING)
                self._awaiting_terminal_swing = True
                # Use IMU timestamp recorded when MID_SWING starts as the start of the valley search window
                self._midswing_start_imu_ts = float(self.timestamps_imu[-1]) if len(self.timestamps_imu) else None
                # clear the toe-off anchored ts (not used as the search start anymore)
                self._last_toe_off_ts = None
            
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

        # --- Valley / TERMINAL_SWING detection (FES only) ---
        if self.FES and self._awaiting_terminal_swing:
            try:
                fsr_ts = None  # ensure variable exists
                valley_ts = self._find_valley_after_toeoff(self._midswing_start_imu_ts, window_s=self.valley_search_window_s)
                if valley_ts is not None:
                    # dedupe / append
                    if (self._last_valley_ts is None) or (valley_ts > self._last_valley_ts):
                        self._last_valley_ts = valley_ts
                        ts_arr = np.asarray(self.timestamps_imu, dtype=float)
                        idx = int(np.searchsorted(ts_arr, valley_ts, side="left"))
                        self.valleys = np.append(self.valleys, idx)
                        self.valleys_timestamps = np.append(self.valleys_timestamps, valley_ts)
                        #print(f"DEBUG: Found valley at {valley_ts:.6f} (search start IMU MID_SWING={self._midswing_start_imu_ts:.6f})")

                    # only proceed if midswing start exists and we are still in MID_SWING
                    if (
                        self._midswing_start_imu_ts is not None
                        and valley_ts > self._midswing_start_imu_ts
                        and self.active_phase == Phase.MID_SWING
                    ):
                        fsr_ts = self._fsr_ts_closest_to(valley_ts)
                        #print(f"DEBUG: valley->fsr mapping valley_ts={valley_ts:.6f} -> fsr_ts={fsr_ts}")

                    if fsr_ts is not None:
                        # finalize: stop awaiting terminal swing and transition via the canonical function
                        self._awaiting_terminal_swing = False
                        self._midswing_start_imu_ts = None

                        # use canonical transition (updates counters etc.)
                       # print(f"DEBUG: Triggering TERMINAL_SWING via valley @ {valley_ts:.6f}")
                        self.__transition_to(Phase.TERMINAL_SWING)

                        # override the last appended timestamp with the valley-aligned FSR timestamp
                        try:
                            self.phase_timestamps[Phase.TERMINAL_SWING][-1] = fsr_ts
                        except Exception:
                            # Last-resort: append if replace fails
                            self.phase_timestamps[Phase.TERMINAL_SWING] = np.append(
                                self.phase_timestamps[Phase.TERMINAL_SWING], fsr_ts
                            )
                        #print(f"DEBUG: TERMINAL_SWING recorded at fsr_ts={fsr_ts}")
            except Exception:
                pass
                #print(f"DEBUG: Exception in valley detection: {e}")


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
            #print(f"Transitioning from {self.active_phase} to {next_phase}")  # print for debugging
            self.phase_counters[next_phase] += 1
            self.active_phase = next_phase
            self.phase_timestamps[next_phase] = np.append(self.phase_timestamps[next_phase], self.timestamps_fsr[-1])
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
        # only allow if we are still in stance progression
        if self.active_phase == Phase.LOADING_RESPONSE:
         self.__transition_to(Phase.MID_STANCE)
         #print(f"DEBUG: _mid_stance_transition called; active_phase={self.active_phase}")
        
    @Slot()
    def _terminal_stance_transition(self) -> None:
        """Transition to the pre swing phase of the gait cycle and record the timestamp.
        This function is used for QTimer.singleShot as it requires a member function as a string (slot) -> no arguments are passed.
        """
        # only allow if we are still in stance progression
        if self.active_phase in (Phase.LOADING_RESPONSE, Phase.MID_STANCE):
         self.__transition_to(Phase.TERMINAL_STANCE)
        
    @Slot()
    def _pre_swing_transition(self) -> None:
        """Transition to the pre swing phase of the gait cycle and record the timestamp.
        This function is used for QTimer.singleShot as it requires a member function as a string (slot) -> no arguments are passed.
        """
        # only allow if we are still in stance progression
        if self.active_phase in (Phase.LOADING_RESPONSE, Phase.MID_STANCE, Phase.TERMINAL_STANCE):
         self.__transition_to(Phase.PRE_SWING)

    def __record_heel_strike(self, timestamp: float) -> None:
        """Record the time of the detected and classified heel strike."""
        self.heel_strike_timestamps = np.append(self.heel_strike_timestamps, timestamp)
        self.heel_strike = np.append(self.heel_strike, self.data_bf[-1])
        #print(f"DEBUG: __record_heel_strike ts={timestamp:.6f}")


    def __record_toe_off(self, timestamp: float) -> None:
        """Record the time of the detected and classified toe off."""
        self.toe_off_timestamps = np.append(self.toe_off_timestamps, timestamp)
        self.toe_off = np.append(self.toe_off, self.data_ff[-1])
        #print(f"DEBUG: __record_toe_off ts={timestamp:.6f}")


        
        