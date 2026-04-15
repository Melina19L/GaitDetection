import numpy as np
import logging
from serial import Serial
from .ComPortFunc import SetSingleChanAllParam, SetSingleChanState, SetSingleChanSingleParam
from collections import defaultdict
from .gait_phases import Phase

NB_CHANNELS = 8  # number of channels
MIN_REAL_INTERPULSE = 42  # [us], minimum interpulse interval, when it is set to 10 in the software (the real interpulse interval is 42us)
MIN_REAL_DEADTIME = 32  # [us], minimum deadtime, when it is set to 19 in the software (the real deadtime is 32us)
OFF = 0
ON = 1
CURRENT_AMPLITUDE_ID = 6  # ID for the current amplitude parameter in the stimulator

# NOTE to deadtime and interpulse_interval:
# Due to hardware limitations, the minimum pulse_deadtime is 19us (real value: 32us) plus an initial step (~32us).
# Similarly, the minimum interpulse_interval that can be set is 10us (software limit, actual value: 42us) plus an initial step (~42us).
# This results in a minimum transition time of approximately 74us, regardless of the chosen carrier frequency.
# These deadtimes remain consistent across different frequencies (e.g., 1kHz, 2kHz, 5kHz, 10kHz).
# The initial step observed in the rising and falling edge transitions on the oscilloscope is likely due to the charging and discharging times of capacitors in the circuit.

MAX_CURRENT = 110 # [mA], maximum current that can be set for a channel, this is a hardware limitation, higher current results in unexpected behavior of the stimulator.

# Function as callable for defaultdict
# So that defaultdict can create a new array everytime a new key is used
def empty_array():
    return np.array([])


class StimulatorParameters:
    """A class to store the parameters of the waveform used for stimulation"""

    def __init__(
        self,
        burst_frequency: float = 10,
        burst_duration: int = 1000,
        interpulse_interval: int = 10,
        pulse_deadtime: int = 19,
        carrier_frequency: int = 5000,
        initial_current: int = 5,
        stim_currents: dict = {},
        tscs_params: dict | None = None,
        fes_params: dict | None = None,
    ):
        """Constructor for the WaveformParameters class, only stim_currents should be modified

        :param burst_frequency: [Hz], frequency of stimulation bursts (float so that it can be lower than 1Hz), defaults to 10
        :type burst_frequency: float, optional
        :param burst_duration: [us], total duration of a burst composed of one or more biphasic pulses, defaults to 1000
        :type burst_duration: int, optional
        :param interpulse_interval: [us], interval between two consecutive biphasic pulses, the real interpulse reported by oscilloscope is 42us (if we set a lower value than 10 we dont have a signal, probably because of a firwmware limitation), defaults to 10
        :type interpulse_interval: int, optional
        :param pulse_deadtime: [us], interval between the end of the positive phase and the beginning of the negative phase of a biphasic pulse, 19us is the minimum interval (by hardware) --> real is 32us, defaults to 19
        :type pulse_deadtime: int, optional
        :param carrier_frequency: [Hz], frequency of the carrier signal, defaults to 5000
        :type carrier_frequency: int, optional
        :param initial_current: [mA], initial current to activate the channel, defaults to 5
        :type initial_current: int, optional
        :param stim_currents: [mA], currents for each channel, defaults to {}
        :type stim_currents: dict, optional
        """

        # Parameters
        self.burst_frequency = np.float32(burst_frequency)
        self.burst_duration = np.uint32(burst_duration)
        self.interpulse_interval = np.uint32(interpulse_interval)
        self.pulse_deadtime = np.uint32(pulse_deadtime)
        self.carrier_frequency = np.uint32(carrier_frequency)
        self.tscs_params = tscs_params
        self.fes_params= fes_params

        # Currents
        # Set default currents of -1 for all channels (no stimulation)
        if len(stim_currents) > NB_CHANNELS:
            stim_currents = {0: -1, 1: -1, 2: -1, 3: -1, 4: -1, 5: -1, 6: -1, 7: -1}
        self.stim_currents = stim_currents
        self.initial_current = np.uint32(initial_current)
        # Max currents for each channel, initialized to the same values as stim_currents
        self.max_stim_currents: dict = {i: stim_currents[i] for i in stim_currents.keys()}
        
        # Targets
        # To get the the amplitude of the current having the channel value as key (0,1,2,...,7 and not distal_left, proximal_right, etc.)
        # Will be set using a function after initialization
        self.channel_to_target: dict = {}
        self.target_to_channel: dict = {} # The inverse of targets
        
        # PI controller offset for each channel, initialized to 0
        self.pi_current_offset: dict = {i: 0.0 for i in stim_currents.keys()}

        # Recording
        # Timestamps of the stimulation for the right leg
        self.timestamps_stim_right: dict = {i: defaultdict(empty_array) for i in range(NB_CHANNELS)}
        # Stimulation value for the right leg
        self.stim_values_right: dict = {i: defaultdict(empty_array) for i in range(NB_CHANNELS)}
        # Timestamps of the deactivation of stimulation for the right leg
        self.timestamps_de_stim_right: dict = {i: defaultdict(empty_array) for i in range(NB_CHANNELS)}
        

        # Timestamps of the stimulation for the left leg
        self.timestamps_stim_left: dict = {i: defaultdict(empty_array) for i in range(NB_CHANNELS)}
        # Stimulation value for the left leg
        self.stim_values_left: dict = {i: defaultdict(empty_array) for i in range(NB_CHANNELS)}
        # Timestamps of the deactivation of stimulation for the left leg
        self.timestamps_de_stim_left: dict = {i: defaultdict(empty_array) for i in range(NB_CHANNELS)}
        
        # Helper: compute derived values for a given param dict
        def _compute_derived(params):
            out = {}
            # safe lookups with fallbacks to constructor args
            bf = float(params.get("burst_frequency", float(self.burst_frequency)))
            bd = int(params.get("burst_duration", int(self.burst_duration)))
            ipi = int(params.get("interpulse_interval", int(self.interpulse_interval)))
            pd = int(params.get("pulse_deadtime", int(self.pulse_deadtime)))
            cf = params.get("carrier_frequency", None)
            # compute params safely
            try:
               out["burst_period"] = np.uint32(1e6 / bf)
            except Exception:
                out["burst_period"] = np.nan
            out["min_total_deadtime"] = np.uint32(MIN_REAL_INTERPULSE + MIN_REAL_DEADTIME)
            try:
                out["carrier_period"] = np.uint32(1e6 / int(cf)) if cf not in (None, 0) else np.nan
            except Exception:
                out["carrier_period"] = np.nan
            if np.isnan(out["carrier_period"]):
                out["ideal_pulse_width"] = np.uint32(bd // 2)
            else:
                out["ideal_pulse_width"] = np.uint32((out["carrier_period"] - out["min_total_deadtime"]) // 2)
            try:
                out["pulses_per_burst"] = np.uint32(bd / out["carrier_period"])
            except Exception:
                out["pulses_per_burst"] = np.uint32(1)
            # keep raw values
            out.update({"burst_frequency": bf, "burst_duration": bd, "interpulse_interval": ipi, "pulse_deadtime": pd, "carrier_frequency": cf})
            
            return out
        

        # Compute derived values per-mode when provided
        if self.tscs_params is not None:
            self.tscs_derived = _compute_derived(self.tscs_params)
        else:
            self.tscs_derived = None

        if self.fes_params is not None:
            self.fes_derived = _compute_derived(self.fes_params)
        else:
            self.fes_derived = None
            
        # Backwards-compatible single-mode attributes: compute only when no per-mode dicts provided
        if self.tscs_params is None and self.fes_params is None:
            # original single-mode behavior (kept as before)
            try:
                self.burst_period = np.uint32(1e6 / burst_frequency)
            except ZeroDivisionError:
                self.burst_period = np.nan
            self.min_total_deadtime = np.uint32(MIN_REAL_INTERPULSE + MIN_REAL_DEADTIME)
            try:
                self.carrier_period = np.uint32(1e6 / carrier_frequency)
            except ZeroDivisionError:
                self.carrier_period = np.nan
            if np.isnan(self.carrier_period):
                self.ideal_pulse_width = np.uint32(self.burst_duration / 2)
            else:
                self.ideal_pulse_width = np.uint32((self.carrier_period - self.min_total_deadtime) // 2)
            try:
                self.pulses_per_burst = np.uint32(burst_duration / self.carrier_period)
            except ZeroDivisionError:
                self.pulses_per_burst = np.nan
            except ValueError:
                self.pulses_per_burst = np.uint32(1)
        else:
            # Keep placeholders when using per-mode configs so callers don't accidentally read stale single-mode attrs
            self.burst_period = np.nan
            self.min_total_deadtime = np.uint32(MIN_REAL_INTERPULSE + MIN_REAL_DEADTIME)
            self.carrier_period = np.nan
            self.ideal_pulse_width = np.uint32(0)
            self.pulses_per_burst = np.uint32(1) # For FES: the "Burst" should gointain 1 biphasic pulse
            
        # Per-channel / per-target mode mapping: values: "tSCS" or "FES"
        self.channel_mode_by_channel: dict[int, str] = {}
        self.channel_mode_by_target: dict[str, str] = {}

    # ------------------------ mode helpers ------------------------
    def set_channel_mode(self, channel_or_target, mode: str) -> None:
        """Set mode for a hardware channel (int) or a target name (str). mode in {'tSCS','FES'}."""
        if mode not in ("tSCS", "FES"):
            raise ValueError("mode must be 'tSCS' or 'FES'")
        if isinstance(channel_or_target, int):
            self.channel_mode_by_channel[channel_or_target] = mode
            return
        if isinstance(channel_or_target, str):
            self.channel_mode_by_target[channel_or_target] = mode
            return
        raise TypeError("channel_or_target must be int (channel) or str (target)")
    
    def infer_channel_modes_from_targets(self, fes_target_names: set | None = None) -> dict:
        """
        Infer per-channel / per-target mode ("FES" | "tSCS") from self.target_to_channel.
        - If fes_target_names provided, any target in that set -> "FES".
        - Otherwise, heuristic: targets containing known muscle tokens -> "FES", else "tSCS".
        Returns mapping channel->mode.
        """
        if not getattr(self, "target_to_channel", None):
            return {}

        # default FES muscle tokens (adjust if your keys differ)
        default_tokens = {"TA", "GA", "VM", "BF", "GM","RF", "TA_left", "TA_right", "GA_left", "GA_right", "VM_left", "VM_right", "BF_left", "BF_right","GM_left", "GM_right","RF_left", "RF_right"}
        fes_set = set(fes_target_names) if fes_target_names else set()

        channel_modes: dict[int, str] = {}
        for tgt, ch in self.target_to_channel.items():
            mode = "tSCS"
            try:
                name = str(tgt)
                # explicit list check
                if name in fes_set:
                    mode = "FES"
                else:
                    # token heuristic: e.g. "TA_left", "VM_right" or labels containing muscle abbreviations
                    for tok in default_tokens:
                        if tok in name:
                            mode = "FES"
                            break
            except Exception:
                mode = "tSCS"
            # set both mappings so other helpers use them
            try:
                self.channel_mode_by_channel[int(ch)] = mode
            except Exception:
                pass
            try:
                self.channel_mode_by_target[name] = mode
            except Exception:
                pass
            channel_modes[int(ch)] = mode
        return channel_modes

    def get_mode_for_channel(self, channel: int) -> str:
        """Return mode for channel (priority: explicit channel -> target mapping -> default 'tSCS')."""
        try:
            if channel in self.channel_mode_by_channel:
                return self.channel_mode_by_channel[channel]
            target = self.channel_to_target.get(channel)
            if target and target in self.channel_mode_by_target:
                return self.channel_mode_by_target[target]
        except Exception:
            pass
        # default: if fes_params provided assume FES only if explicitly mapped; otherwise tSCS
        return "tSCS"

    def _get_derived_for_channel(self, channel: int) -> dict:
        """Return derived parameter dict (same structure as computed) for given channel according to mode.
           Falls back to single-mode attributes if no per-mode dicts are present.
        """
        mode = self.get_mode_for_channel(channel)
        if mode == "FES" and self.fes_derived is not None:
            return self.fes_derived
        if mode == "tSCS" and self.tscs_derived is not None:
            return self.tscs_derived
        # Fallback: create derived dict from single-mode attributes for compatibility
        try:
            return {
                "burst_period": getattr(self, "burst_period", np.nan),
                "min_total_deadtime": getattr(self, "min_total_deadtime", np.uint32(MIN_REAL_INTERPULSE + MIN_REAL_DEADTIME)),
                "carrier_period": getattr(self, "carrier_period", np.nan),
                "ideal_pulse_width": getattr(self, "ideal_pulse_width", np.uint32(0)),
                "pulses_per_burst": getattr(self, "pulses_per_burst", np.uint32(1)),
                "burst_frequency": float(getattr(self, "burst_frequency", np.nan)),
                "burst_duration": int(getattr(self, "burst_duration", 0)),
                "interpulse_interval": int(getattr(self, "interpulse_interval", 0)),
                "pulse_deadtime": int(getattr(self, "pulse_deadtime", 0)),
                "carrier_frequency": getattr(self, "carrier_frequency", None),
            }
        except Exception:
            return {}
    # ---------------------- end mode helpers ----------------------


    def __str__(self):
        # Show per-mode config presence concisely
        modes = []
        if self.tscs_params is not None:
            modes.append("tSCS")
        if self.fes_params is not None:
            modes.append("FES")
        mode_str = ",".join(modes) if modes else "single"
        return (
            f"WaveformParameters(mode={mode_str},\n"
            f"  burst_frequency={getattr(self, 'burst_frequency', None)},\n"
            f"  burst_duration={getattr(self, 'burst_duration', None)},\n"
            f"  interpulse_interval={getattr(self, 'interpulse_interval', None)},\n"
            f"  pulse_deadtime={getattr(self, 'pulse_deadtime', None)},\n"
            f"  carrier_frequency={getattr(self, 'carrier_frequency', None)},\n"
            f"  initial_current={getattr(self, 'initial_current', None)},\n"
            f"  stim_currents={getattr(self, 'stim_currents', None)},\n"
            f"  max_stim_currents={getattr(self, 'max_stim_currents', None)},\n"
            f"  targets={getattr(self, 'channel_to_target', None)}\n"
            f")"
        )

    def is_valid(self) -> bool:
        """Check if the parameters are valid

        :return: True if the parameters are valid, False otherwise
        :rtype: bool
        """
        # Validate either per-mode derived dicts (if present) or the legacy single-mode attributes
        try:
            # If per-mode derived configs exist, validate their numeric contents
            if self.tscs_derived is not None or self.fes_derived is not None:
                for derived in (self.tscs_derived, self.fes_derived):
                    if derived is None:
                        continue
                    for k, v in derived.items():
                        if v is None:
                            logging.warning(f"Invalid derived value for {k}: None")
                            return False
                        if np.issubdtype(type(v), np.floating) and np.isnan(v):
                            # allow carrier_period to be NaN for FES (no carrier)
                            if k == "carrier_period":
                                continue
                            logging.warning(f"Invalid derived value for {k}: NaN")
                            return False
                # also ensure stim_currents exists
                if not isinstance(self.stim_currents, dict):
                    logging.warning("Invalid value for stim_currents: not a dict")
                    return False
                return True

            # Legacy single-mode validation
            attributes_to_validate = [
                "burst_frequency",
                "burst_duration",
                "interpulse_interval",
                "carrier_frequency",
                "stim_currents",
                "burst_period",
                "min_total_deadtime",
                #"carrier_period", allow NaN for FES 
                "ideal_pulse_width",
                "pulses_per_burst",
             ]
            for attr in attributes_to_validate:
                value = getattr(self, attr, None)
                if value is None:
                    logging.warning(f"Invalid value for {attr}: None")
                    return False
                if np.issubdtype(type(value), np.floating) and np.isnan(value):
                    logging.warning(f"Invalid value for {attr}: NaN")
                    return False
                if isinstance(value, dict):
                    if any(np.issubdtype(type(v), np.floating) and np.isnan(v) for v in value.values()):
                        logging.warning(f"Invalid value for {attr}: NaN in dict")
                        return False
            return True
        except Exception as e:
            logging.warning(f"is_valid encountered exception: {e}")
            return False

    def set_stim_currents(self, stim_currents: dict) -> None:
        """Set the stimulation currents for each channel. Resets the pi_current_offset for each channel to 0.

        :param stim_currents: [mA], currents for each channel
        :type stim_currents: dict
        :raises ValueError: If the length of stim_currents is greater than NB_CHANNELS or if stim_currents is None
        """
        if len(stim_currents) > NB_CHANNELS:
            raise ValueError(f"Invalid value or length for stim_currents: {stim_currents}")

        self.stim_currents = stim_currents
        self.pi_current_offset = {i: 0.0 for i in self.stim_currents.keys()}  # Reset the PI controller offset for each channel
        
    def set_max_currents(self, max_currents: dict) -> None:
        """Set the maximum stimulation currents for each channel. Resets the pi_current_offset for each channel to 0.

        :param max_currents: [mA], currents for each channel
        :type max_currents: dict
        :raises ValueError: If the length of max_currents is greater than NB_CHANNELS or if max_currents has a key not present in stim_currents
        """
        if len(max_currents) > NB_CHANNELS:
            raise ValueError(f"Invalid value or length for max_currents: {max_currents}")
        # If a key in max_currents is not present in stim_currents, raise an error
        for key in max_currents.keys():
            if key not in self.stim_currents:
                raise ValueError(f"Key '{key}' in max_currents not found in stim_currents: {self.stim_currents.keys()}")
        
        self.max_stim_currents = max_currents
        self.pi_current_offset = {i: 0.0 for i in self.stim_currents.keys()}  # Reset the PI controller offset for each channel

    def set_targets(self, channels: dict) -> None:
        """Set the targets for the stimulation channels. This function maps the channel numbers to the targets in the stim_currents dictionary.

        :param channels: A dictionary mapping channel numbers to their respective targets (e.g., {0: 'proximal_left', 1: 'distal_right', ...})
        :type channels: dict
        """
        # Add the pairs {channel: target} (e.g., {0: 'proximal_left'}) to the targets dictionary if the target is in the stim_currents dictionary
        self.channel_to_target = {channels[target]: target for target in self.stim_currents.keys()}
        self.target_to_channel = channels  # Inverse mapping for convenience
        
    def get_channel_of_target(self, target: str) -> int:
        """Get the channel number of a target muscle group.

        :param target: Target muscle group (e.g., "proximal_right" or "distal_left")
        :type target: str
        :return: Channel number associated with the target
        :rtype: int
        :raises ValueError: If the target is not found in the channel dictionary
        """
        if target not in self.target_to_channel.keys():
            raise ValueError(f"Target '{target}' not found in targets: {self.target_to_channel.values()}")
        return self.target_to_channel[target]

    def set_all_param_of_channel(self, stimulator_connection: Serial, channel: int, mode: bool = False) -> None:
        """Set the stimulation parameters for a specific channel

        :param stimulator_connection: Serial connection to the stimulator
        :type stimulator_connection: Serial
        :param channel: Channel number
        :type channel: int
        :param mode: continuous (0) or singleshot (1) stimulation mode, defaults to False
        :type mode: bool
        """
        assert channel in self.channel_to_target.keys(), f"Channel {channel} not found in targets: {self.channel_to_target.keys()}"
        # Use derived params according to configured mode for this channel (fallback to legacy attrs)
        derived = self._get_derived_for_channel(channel)
        try:
            ipw = int(derived.get("ideal_pulse_width", getattr(self, "ideal_pulse_width", 0)))
        except Exception:
            ipw = int(getattr(self, "ideal_pulse_width", 0))
        try:
            pd = int(derived.get("pulse_deadtime", getattr(self, "pulse_deadtime", 0)))
        except Exception:
            pd = int(getattr(self, "pulse_deadtime", 0))
        try:
            ipi = int(derived.get("interpulse_interval", getattr(self, "interpulse_interval", 0)))
        except Exception:
            ipi = int(getattr(self, "interpulse_interval", 0))
        try:
            bp = int(derived.get("burst_period", getattr(self, "burst_period", 0)))
        except Exception:
            bp = int(getattr(self, "burst_period", 0))
        try:
            ppb = int(derived.get("pulses_per_burst", getattr(self, "pulses_per_burst", 1)))
        except Exception:
            ppb = int(getattr(self, "pulses_per_burst", 1))
        try:
            cur = int(self.stim_currents[self.channel_to_target[channel]])
        except Exception:
            cur = int(getattr(self, "initial_current", 0))

        SetSingleChanAllParam(
            stimulator_connection,
            channel,
            ipw,
            pd,
            ipi,
            bp,
            ppb,
            cur,
            mode,
        )

    def set_current_of_channel_from_target(self, stimulator_connection: Serial, target: str) -> None:
        """Set the current of a channel. The current is stored in this class and consists of a base current defined at the start and an offset modified by the PI controller.

        :param stimulator_connection: Serial connection to the stimulator
        :type stimulator_connection: Serial
        :param target: Target muscle group of the electrode (e.g., "proximal_right" or "distal_left"). The channel is determined from the target_to_channel mapping.
        :type target: int
        """
        assert target in self.stim_currents, f"Target '{target}' not found in stim_currents: {self.stim_currents.keys()}"
        target_channel = self.get_channel_of_target(target)
        assert self.stim_currents[target] + self.pi_current_offset[target] <= self.max_stim_currents[target], f"Current exceeds maximum limit: {self.stim_currents[target] + self.pi_current_offset[target]} mA > {MAX_CURRENT} mA"
        SetSingleChanSingleParam(stimulator_connection, target_channel, CURRENT_AMPLITUDE_ID, self.stim_currents[target] + self.pi_current_offset[target])
        
    def set_ramp_current_of_channel_from_target(self, stimulator_connection: Serial, target: str, ramp_multi: float) -> None:
        """Set the ramp current of a channel. The current is stored in this class and consists of a base current defined at the start and an offset modified by the PI controller.

        :param stimulator_connection: Serial connection to the stimulator
        :type stimulator_connection: Serial
        :param target: Target muscle group of the electrode (e.g., "proximal_right" or "distal_left"). The channel is determined from the target_to_channel mapping.
        :type target: int
        """
        assert target in self.stim_currents, f"Target '{target}' not found in stim_currents: {self.stim_currents.keys()}"
        target_channel = self.get_channel_of_target(target)
        assert self.stim_currents[target] + self.pi_current_offset[target] <= self.max_stim_currents[target], f"Current exceeds maximum limit: {self.stim_currents[target] + self.pi_current_offset[target]} mA > {MAX_CURRENT} mA"
        SetSingleChanSingleParam(stimulator_connection, target_channel, CURRENT_AMPLITUDE_ID, (self.stim_currents[target] + self.pi_current_offset[target])*ramp_multi)

    def append_stim_right(self, channel: int, target:str, stim_type: Phase, timestamp: float) -> None:
        """Append a stimulation per phase to the right stimulation recording.

        :param channel: Channel number
        :type channel: int
        :param target: Which target the channel is associated with (e.g., "proximal_right" or "distal_left") - This is important for the case where the same channel is used for different targets in different phases.
        :type target: str
        :param stim_type: Which phase change results in a stimulation
        :type stim_type: Phase
        :param timestamp: Timestamp of the stimulation
        :type timestamp: float
        """
        self.timestamps_stim_right[channel][stim_type.name] = np.append(self.timestamps_stim_right[channel][stim_type.name], timestamp)
        self.stim_values_right[channel][stim_type.name] = np.append(self.stim_values_right[channel][stim_type.name], self.stim_currents[target] + self.pi_current_offset[target])

    def append_stim_left(self, channel: int, target:str, stim_type: Phase, timestamp: float) -> None:
        """Append a stimulation per phase to the left stimulation recording.

        :param channel: Channel number
        :type channel: int
        :param target: Which target the channel is associated with (e.g., "proximal_right" or "distal_left") - This is important for the case where the same channel is used for different targets in different phases.
        :type target: str
        :param stim_type: Which phase change results in a stimulation
        :type stim_type: Phase
        :param timestamp: Timestamp of the stimulation
        :type timestamp: float
        """
        self.timestamps_stim_left[channel][stim_type.name] = np.append(self.timestamps_stim_left[channel][stim_type.name], timestamp)
        self.stim_values_left[channel][stim_type.name] = np.append(self.stim_values_left[channel][stim_type.name], self.stim_currents[target] + self.pi_current_offset[target])
        
    
    def append_de_stim_right(self, channel: int, target:str, stim_type: Phase, timestamp: float) -> None:
        """Append a deactivation of stimulation per phase to the right stimulation recording.

        :param channel: Channel number
        :type channel: int
        :param target: Which target the channel is associated with (e.g., "proximal_right" or "distal_left") - This is important for the case where the same channel is used for different targets in different phases.
        :type target: str
        :param stim_type: Which phase change results in a stimulation
        :type stim_type: Phase
        :param timestamp: Timestamp of the stimulation
        :type timestamp: float
        """
        self.timestamps_de_stim_right[channel][stim_type.name] = np.append(self.timestamps_de_stim_right[channel][stim_type.name], timestamp)

    def append_de_stim_left(self, channel: int, target:str, stim_type: Phase, timestamp: float) -> None:
        """Append a deactivation of stimulation per phase to the left stimulation recording.

        :param channel: Channel number
        :type channel: int
        :param target: Which target the channel is associated with (e.g., "proximal_right" or "distal_left") - This is important for the case where the same channel is used for different targets in different phases.
        :type target: str
        :param stim_type: Which phase change results in a stimulation
        :type stim_type: Phase
        :param timestamp: Timestamp of the stimulation
        :type timestamp: float
        """
        self.timestamps_de_stim_left[channel][stim_type.name] = np.append(self.timestamps_de_stim_left[channel][stim_type.name], timestamp)
        
        
    def update_pi_current_offset(self, target: str, offset: float) -> None:
        """Update the PI controller offset for a specific target. This is used to adjust the current applied to the channel based on the PI controller output.

        :param target: Target muscle groups of the electrode (e.g., "proximal_right" or "distal_left")
        :type target: str
        :param offset: Offset to be applied to the current for the specified target. This is a float value that can be positive or negative, allowing for both increase and decrease of the current.
        :type offset: float
        :raises ValueError: If the target is not found in stim_currents.
        """
        if target not in self.stim_currents:
            raise ValueError(f"Target '{target}' not found in stim_currents. Available targets: {list(self.stim_currents.keys())}")
        
        # Ensure the offset does not exceed the maximum current limits
        if self.stim_currents[target] + offset < 0:
            offset = -self.stim_currents[target]  # Prevent negative current
        elif self.stim_currents[target] + offset > self.max_stim_currents[target]:
            offset = self.max_stim_currents[target] - self.stim_currents[target]
            
        self.pi_current_offset[target] = offset
        

    @staticmethod
    def close_all_channels(stimulator_connection: Serial, channels=[0, 1, 2, 3, 4, 5, 6, 7]) -> None:
        for channel in channels:
            SetSingleChanState(stimulator_connection, channel, OFF, OFF, OFF)

    # These functions are here to increase the readability of the code
    @staticmethod
    def activate_output(stimulator_connection: Serial, channel: int) -> None:
        SetSingleChanState(stimulator_connection, channel, ON, ON, ON)

    @staticmethod
    def deactivate_output(stimulator_connection: Serial, channel: int) -> None:
        SetSingleChanState(stimulator_connection, channel, ON, ON, OFF)

    @staticmethod
    def activate_hv(stimulator_connection: Serial, channel: int) -> None:
        # Activate the high voltage (HV) mode for the channel
        SetSingleChanState(stimulator_connection, channel, ON, ON, OFF)

    @staticmethod
    def deactivate_hv(stimulator_connection: Serial, channel: int) -> None:
        # Deactivate the high voltage (HV) mode for the channel
        SetSingleChanState(stimulator_connection, channel, ON, OFF, OFF)

    @staticmethod
    def open_channel(stimulator_connection: Serial, channel: int) -> None:
        SetSingleChanState(stimulator_connection, channel, ON, OFF, OFF)

    @staticmethod
    def close_channel(stimulator_connection: Serial, channel: int) -> None:
        SetSingleChanState(stimulator_connection, channel, OFF, OFF, OFF)
