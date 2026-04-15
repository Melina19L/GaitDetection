from .gait_detection_imu import IMUGaitFSM
from .gait_detection_fsr import FSRGaitFSM
from .gait_detection_imu_fsr import FSRIMUGaitFSM
from .stimulator_parameters import StimulatorParameters
from serial import Serial
from .gait_phases import Phase
import time
from typing import Iterable, List
from itertools import chain

LEFT_SIDE = 0
RIGHT_SIDE = 1

######################################################
""" Dictionaries for muscular group selection """
#######################################################
# Please add more dictionaries or modify the existing ones as needed.
# This will allow to adapt the gait model to different stimulation setups or configurations.
# If new ones are added, please remember to either add new open_stimulation_channel functions or modify the existing ones to use the new dictionaries.

# Gait Model with Distal (New Gait Model): 
#           - includes distal muscles for mid-stance for tSCS
#           - added Gluteeous Maximus as an option in all stance subphases, stance phase alone is never detected
#           - Swing phase is divided into Mid-swing and Terminal-Swing, these 2 subphases are used by FES to engage the BF and then VM , 
#             tSCS however, does not divid the swing phase (YET , THIS MIGHT CHANGE IN THE FUTURE), it will only detect Swing where it stimulates the FULL LEG.
#             This will cause a problem, since in hybrid strategies, the detection method will be unique to all stimulation types (tSCS or FES), meaning that the
#             method will govern the phases/sub-phases detected which will then be used to match the target to channel to stimulate, so inorder to increase efficiency
#             we need to ensure the gait model used has the same phases and subphases and the corrisponding targets that we want to stimulate 
              
MUSCULAR_GROUP_SELECTION = {
    # Subphases
    Phase.LOADING_RESPONSE: [["proximal_left" , "TA_left" , "VM_left" , "RF_left", "GM_left"],               ["proximal_right" , "TA_right", "VM_right" , "RF_right" , "GM_right"]],
    Phase.MID_STANCE: [["distal_left" , "GA_left" , "GM_left" ],                                             ["distal_right" , "GA_right" ,"GM_right"]],
    Phase.TERMINAL_STANCE: [["full_leg_left" , "GA_left" , "GM_left" ],                                      ["full_leg_right" ,"GA_right" ,"GM_right"]],
    Phase.PRE_SWING: [["full_leg_left" , "GA_left" , "GM_left", "BF_left" ],                                 ["full_leg_right" ,"GA_right" ,"GM_right", "BF_right"]],

    Phase.MID_SWING: [["full_leg_left" ,"BF_left", "TA_left"],                                               ["full_leg_right" , "BF_right", "TA_right"]],
    Phase.TERMINAL_SWING: [["full_leg_left" , "VM_left", "RF_left", "TA_left"],                              ["full_leg_right" , "VM_right", "RF_right", "TA_right"]],
    Phase.UNKNOWN: [["unknown"],                                                                             ["unknown"]],
    # Swing and stance (phases)
    Phase.STANCE: [["proximal_left"],                                                                        ["proximal_right"]],
    Phase.SWING: [["full_leg_left"],                                                                         ["full_leg_right"]],
}

# original Gait Model without Distal: (now is Gait Model 2 - ie no distal muscles)
MUSCULAR_GROUP_SELECTION_2 = {
    # Subphases
    Phase.LOADING_RESPONSE: [["proximal_left" , "TA_left" , "VM_left" ,"RF_left", "GM_left"],                ["proximal_right" , "TA_right", "VM_right" , "RF_right", "GM_right"]],
    Phase.MID_STANCE: [["full_leg_left"  , "GA_left" , "GM_left"],                                           ["full_leg_right", "GA_right" ,"GM_right"]],
    Phase.TERMINAL_STANCE: [["full_leg_left", "GA_left" , "GM_left"],                                        ["full_leg_right", "GA_right" ,"GM_right"]], # was:[["proximal_left"], ["proximal_right"]],
    Phase.PRE_SWING: [["full_leg_left" , "GA_left" , "GM_left", "BF_left" ],                                 ["full_leg_right" ,"GA_right" ,"GM_right", "BF_right"]],
    
    Phase.MID_SWING: [["full_leg_left" ,"BF_left", "TA_left"],                                               ["full_leg_right" , "BF_right", "TA_right"]],
    Phase.TERMINAL_SWING: [["full_leg_left" , "VM_left", "RF_left", "TA_left"],                              ["full_leg_right" , "VM_right","RF_right" , "TA_right"]],
    Phase.UNKNOWN: [["unknown"],                                                                             ["unknown"]],
    # Swing and stance (phases)
    Phase.STANCE: [["proximal_left"],                                                                        ["proximal_right"]],
    Phase.SWING: [["full_leg_left"],                                                                         ["full_leg_right"]],
}


# ======= OLD GAIT MODEL for tSCS from Dominik ======
# MUSCULAR_GROUP_SELECTION = {
#     # Subphases
#     Phase.LOADING_RESPONSE: [["proximal_left"], ["proximal_right"]],
#     Phase.MID_STANCE: [["full_leg_left"], ["full_leg_right"]],
#     Phase.PRE_SWING: [["proximal_left"], ["proximal_right"]],
#     Phase.MID_SWING: [["proximal_left"], ["proximal_right"]],
#     Phase.TERMINAL_SWING: [["proximal_left"], ["proximal_right"]],
#     Phase.UNKNOWN: [["unknown"], ["unknown"]],
#     # Swing and stance (phases)
#     Phase.STANCE: [["proximal_left"], ["proximal_right"]],
#     Phase.SWING: [["full_leg_left"], ["full_leg_right"]],
# }

RAMP_START_TIME = None
LAST_PAUSE_RECORDED_TIME = None

def _compute_ramp_multi() -> float:
    # Do not implicitly start the ramp here. Only apply the ramp if it was
    # explicitly started (RAMP_START_TIME is set by start_ramp()).
    global RAMP_START_TIME
    if RAMP_START_TIME is None:
        return 1.0
    ramp_time = time.monotonic() - RAMP_START_TIME

    if ramp_time < 2:
        return 0.5
    elif ramp_time < 4:
        return 0.6
    elif ramp_time < 6:
        return 0.7
    elif ramp_time < 8:
        return 0.8
    elif ramp_time < 10:
        return 0.9
    else:
        return 1.0

def start_ramp() -> None:
    """Start the global 10s ramp (call on experiment start / resume)."""
    global RAMP_START_TIME, LAST_PAUSE_RECORDED_TIME
    now = time.monotonic()
    # Ignore duplicate/rapid calls (idempotent)
    if RAMP_START_TIME is not None:
        # If ramp already active and started recently, don't restart it
        if now - RAMP_START_TIME < 1.0:
            try:
                import logging
                logging.getLogger(__name__).debug("start_ramp() ignored duplicate call")
            except Exception:
                pass
            return
    RAMP_START_TIME = now
    LAST_PAUSE_RECORDED_TIME = None

def stop_ramp() -> None:
    """Stop / clear the global ramp (call on pause)."""
    global RAMP_START_TIME
    RAMP_START_TIME = None
#################################################
""" Functions for updating offset """
#################################################

#TODO: If the muscular groups are added to the GUI as a configuration option, then this function wouldn't be required anymore as the stimulation classes could access the target easily
# def update_offset(
#     stim_conn: Serial,
#     stim_param: StimulatorParameters,
#     phase: Phase,
#     offset: float,
#     timestamp: float,
#     left_leg: bool = False,
# ):
#     if phase == Phase.UNKNOWN:
#         return  # No stimulation for unknown phase (not yet started or not detected)
#     muscle_group = MUSCULAR_GROUP_SELECTION[phase][LEFT_SIDE if left_leg else RIGHT_SIDE]
#     for group in muscle_group:
#         channel = stim_param.get_channel_of_target(group)
#         stim_param.update_pi_current_offset(target=group, offset=offset)
#         # Update the current amplitude for the channel
#         stim_param.set_current_of_channel_from_target(stim_conn, target=group)
#         if left_leg:
#             stim_param.append_stim_left(channel, group, phase, timestamp)
#         else:
#             stim_param.append_stim_right(channel, group, phase, timestamp)

def _flatten_groups(groups: Iterable) -> List[str]:
    """Flatten nested lists/tuples of group names into a flat list of strings."""
    flat = []
    for g in groups:
        if isinstance(g, (list, tuple)):
            flat.extend(_flatten_groups(g))
        else:
            flat.append(g)
    return flat

def update_offset(
    stim_conn: Serial,
    stim_param: StimulatorParameters,
    phase: Phase,
    offset: float,
    timestamp: float,
    is_left: bool,  # True = left, False = right
    _total_paused_duration: float = 0.0,   # new optional param (backwards compatible)
) -> None:
    """Update PI offset/current for the active muscle groups on one side."""
    global RAMP_START_TIME, LAST_PAUSE_RECORDED_TIME

    if phase == Phase.UNKNOWN:
        return  # no stim on unknown phase

    # Pick which side’s groups to stimulate
    side_index = LEFT_SIDE if is_left else RIGHT_SIDE

    # Get groups for this phase & side; fall back to empty if not configured
    try:
        side_groups = MUSCULAR_GROUP_SELECTION[phase][side_index]
    except (KeyError, IndexError, TypeError):
        return  # nothing mapped for this phase/side

    # Normalize to a flat list of group names (handles nested structures)
    groups = _flatten_groups(side_groups)

    # # allow reading/modifying global ramp timer
    # global RAMP_START_TIME
    
    # if _all_timestamp_containers_empty(getattr(stim_param, "timestamps_stim_left", {})) and \
    #    _all_timestamp_containers_empty(getattr(stim_param, "timestamps_stim_right", {})):
    #      if RAMP_START_TIME is None:
    #         RAMP_START_TIME = time.monotonic()

    for group in groups:
        if not group or group == "unknown":
            continue

        # Resolve channel for this group; skip if not mapped
        channel = None
        try:
            channel = stim_param.get_channel_of_target(group)
        except (KeyError, ValueError, AttributeError):
            pass
        if channel is None:
            continue

        # Apply offset & push the new current; record metadata
        try:
            stim_param.update_pi_current_offset(target=group, offset=offset)
            # Apply ramped current so closed-loop updates are gradual
            ramp_multi = _compute_ramp_multi()
            stim_param.set_ramp_current_of_channel_from_target(stim_conn, group, ramp_multi)
            stim_param.activate_output(stim_conn, channel)
            if is_left:
                stim_param.append_stim_left(channel, group, phase, timestamp)
            else:
                stim_param.append_stim_right(channel, group, phase, timestamp)
        except Exception:
            # If one target fails, continue with the others (avoid crashing the loop)
            continue

###############################################
""" Functions for stimulation """
###############################################

#function to check if stimulation timestamps are empty
def _all_timestamp_containers_empty(d: dict) -> bool:
    """Return True if every value in dict `d` is empty (supports numpy arrays and sequences)."""
    try:
        for v in d.values():
            # numpy arrays
            if hasattr(v, "size"):
                if int(getattr(v, "size", 0)) > 0:
                    return False
            # sequences / lists / defaultdict(list)
            elif hasattr(v, "__len__"):
                if len(v) > 0:
                    return False
            # fallback truthiness
            elif v:
                return False
        return True
    except Exception:
        # on error, be conservative and treat as empty
        return True
    
def stimulate_muscle_group(
    stim_conn: Serial,
    channels: dict,
    muscle_group: list,
    stim_param: StimulatorParameters,
    timestamp: float,
    phase: Phase,
    left_leg: bool = False,
    record_stim_time: bool= True,
    _total_paused_duration: float =0.0,
):
    timestamp = time.time()

    global RAMP_START_TIME
    global LAST_PAUSE_RECORDED_TIME
    # check whether all per-channel timestamp containers are empty
    if _all_timestamp_containers_empty(getattr(stim_param, "timestamps_stim_left", {})) and \
       _all_timestamp_containers_empty(getattr(stim_param, "timestamps_stim_right", {})):
        start_ramp()

    # check if we add a pause and then restart the ramp 
    if _total_paused_duration > 0 and _total_paused_duration != LAST_PAUSE_RECORDED_TIME:
        start_ramp()
        LAST_PAUSE_RECORDED_TIME = _total_paused_duration
    for group in muscle_group:
        if left_leg:
            if phase == Phase.SWING:
                print("Swing")
            if phase == Phase.MID_SWING:
                print("Mid Swing")
            if phase == Phase.PRE_SWING:
                print("Pre Swing")
            if phase == Phase.TERMINAL_SWING:
                print("Terminal Swing")
            if phase == Phase.MID_STANCE:
                print("Mid Stance")
            if phase == Phase.LOADING_RESPONSE:
                print("Loading Response")

        channel = channels[group]
        # Set the current amplitude for the channel
        if RAMP_START_TIME is not None:
            ramp_time= time.monotonic() - RAMP_START_TIME
        else:
            ramp_time = 100
        
        if ramp_time < 10:
            if ramp_time < 2:
                ramp_multi=0.5
            elif 2 <= ramp_time < 4:
                ramp_multi=0.6
            elif 4 <= ramp_time < 6:
                ramp_multi=0.7
            elif 6 <= ramp_time < 8:
                ramp_multi=0.8
            elif 8 <= ramp_time < 10:
                ramp_multi=0.9
            else:
                ramp_multi= 1
            stim_param.set_ramp_current_of_channel_from_target(stim_conn, group , ramp_multi)
            stim_param.activate_output(stim_conn, channel)
        else:
            RAMP_START_TIME = None
            stim_param.set_current_of_channel_from_target(stim_conn, group)
            stim_param.activate_output(stim_conn, channel)
        
        if record_stim_time:
            # Saving the stimulation time for each muscular group to compare it with the detection time
            if left_leg:
                stim_param.append_stim_left(channel, group, phase, timestamp)
            else:
                stim_param.append_stim_right(channel, group, phase, timestamp)
            
            
def deactivate_muscle_group(
    stim_conn: Serial,
    channels: dict,
    muscle_group: list,
    stim_param: StimulatorParameters,
    timestamp: float,
    phase: Phase,
    left_leg: bool = False,
):
    #timestamp = time.time()
    for group in muscle_group:

        channel = channels[group]
        # deactivate channel 
        #stim_param.deactivate_output(stim_conn, channel)
        # Saving the disactivation stimulation time for each muscular group to compare it with the detection time
        if left_leg:
            stim_param.append_de_stim_left(channel, group, phase, timestamp)
        else:
            stim_param.append_de_stim_right(channel, group, phase, timestamp)


# for 50 steps we have 250 subphases divided in 150 proximal stimulations and 100 distal, since we dont want to add a timestamp to distal when only proximal subphase has changed
# we add an if condition
# ex:
# 1) LR_right + PS_left (both changed) --> we enter --> muscular groups --> turn ON and save timestamp both
# 2) LR_right + PS_left --> we don't enter (both equal to before) --> they continue to stimulate as before
# 3) LR_right + ISW+MSW_left --> we enter --> muscular groups (different left from before) --> turn ON (different left channel) and save timestamp of only left (only left has changed subphase), right continues to stimulate as before
# 4) MST_right + ISW+MSW_left --> we enter --> muscular groups (different right from before) --> turn ON (different right channel) and save timestamp of only right (only right has changed subphase), left continues to stimulate as before


def open_stimulation_channel_subphases(  # function adapted for IMU only 
    stim_conn: Serial,
    channels: dict[str, int],
    right_leg: IMUGaitFSM,
    left_leg: IMUGaitFSM,
    stim_param: StimulatorParameters,
) -> None:
    """Activate the stimulation channels based on the current subphase of the right and left legs.
    The timestamp of the stimulation is recorded for each muscular group to use it in offline analysis.

    :param stim_conn: The serial connection to the stimulator.
    :type stim_conn: Serial
    :param channels: Dictionary mapping the electrode positions to their respective channels.
    :type channels: dict[str, int]
    :param right_leg: The gait finite state machine for the right leg.
    :type right_leg: Gait_FSM
    :param left_leg: The gait finite state machine for the left leg.
    :type left_leg: Gait_FSM
    :param stim_param: The stimulator parameters object that manages the stimulation settings.
    :type stim_param: StimulatorParameters
    """

    # Skip if no phase change
    if not (right_leg.changed_subphase() or left_leg.changed_subphase()):
        return

    muscular_group_right = MUSCULAR_GROUP_SELECTION[right_leg.active_subphase][RIGHT_SIDE]
    muscular_group_left = MUSCULAR_GROUP_SELECTION[left_leg.active_subphase][LEFT_SIDE]
    if "unknown" in muscular_group_right or "unknown" in muscular_group_left:
        return

    # Turn off channels that are not needed
    for channel in channels.values():
        if channel not in [channels[group] for group in muscular_group_right + muscular_group_left]:
            stim_param.deactivate_output(stim_conn, channel)

    # Only turn on channels that have changed subphase (to avoid multiple activations)
    if right_leg.changed_subphase():
        stimulate_muscle_group(
            stim_conn, channels, muscular_group_right, stim_param, right_leg.timestamps[-1], right_leg.active_subphase, left_leg=False , record_stim_time= True
        )
        right_leg.update_previous_subphase()

    if left_leg.changed_subphase():
        stimulate_muscle_group(
            stim_conn, channels, muscular_group_left, stim_param, left_leg.timestamps[-1], left_leg.active_subphase, left_leg=True, record_stim_time= True
        )
        left_leg.update_previous_subphase()


def open_stimulation_channel_phases_imu(
    stim_conn: Serial,
    channels: dict[str, int],
    right_leg: IMUGaitFSM,
    left_leg: IMUGaitFSM,
    stim_param: StimulatorParameters,
    gait_model: str = "Gait Model with Distal",
    personalized_gait_model: bool =False,
    _total_paused_duration: float =0.0,
) -> None:
    """Activate the stimulation channels based on the current phase of the right and left legs.
    The timestamp of the stimulation is recorded for each muscular group to use it in offline analysis.

    :param stim_conn: The serial connection to the stimulator.
    :type stim_conn: Serial
    :param channels: Dictionary mapping the electrode positions to their respective channels.
    :type channels: dict[str, int]
    :param right_leg: The gait finite state machine for the right leg.
    :type right_leg: Gait_FSM
    :param left_leg: The gait finite state machine for the left leg.
    :type left_leg: Gait_FSM
    :param stim_param: The stimulator parameters object that manages the stimulation settings.
    :type stim_param: StimulatorParameters
    """
    # Skip if no phase change
    if not (right_leg.changed_phase() or left_leg.changed_phase()):
        return
    previous_phase_right= right_leg.previous_phase
    previous_phase_left= left_leg.previous_phase

    if gait_model == "Gait Model with Distal" or personalized_gait_model:
        previous_muscular_group_right=MUSCULAR_GROUP_SELECTION[previous_phase_right][RIGHT_SIDE]
        previous_muscular_group_left=MUSCULAR_GROUP_SELECTION[previous_phase_left][LEFT_SIDE]
        muscular_group_right = MUSCULAR_GROUP_SELECTION[right_leg.active_phase][RIGHT_SIDE]
        muscular_group_left = MUSCULAR_GROUP_SELECTION[left_leg.active_phase][LEFT_SIDE]
        #print("Debug: using Gait Model with Distal or Personalized Gait Model")
        
    else:
        previous_muscular_group_right=MUSCULAR_GROUP_SELECTION_2[previous_phase_right][RIGHT_SIDE]
        previous_muscular_group_left=MUSCULAR_GROUP_SELECTION_2[previous_phase_left][LEFT_SIDE]
        muscular_group_right = MUSCULAR_GROUP_SELECTION_2[right_leg.active_phase][RIGHT_SIDE]
        muscular_group_left = MUSCULAR_GROUP_SELECTION_2[left_leg.active_phase][LEFT_SIDE] 
        #print("Debug: Using Gait Model without Distal")
        
    if "unknown" in muscular_group_right and "unknown" in muscular_group_left:
        return

    # Turn off channels that are not needed
    # Build set of currently used hardware channels (flatten group lists)
    left_prev_flat = _flatten_groups(previous_muscular_group_left)
    right_prev_flat = _flatten_groups(previous_muscular_group_right)
    left_curr_flat = _flatten_groups(muscular_group_left)
    right_curr_flat = _flatten_groups(muscular_group_right)
    
    # deactivate hardware outputs once for each unused channel
    # Get list of channels that are actively needed
    active_channels = set()
    for group in muscular_group_right + muscular_group_left:
        if group in channels:
            active_channels.add(channels[group])

    # Turn off channels that are not needed
    if "continuous" in channels:
        # Deactivate all channels except the ones used and the continuous channel
        for channel in channels.values():
            if channel not in active_channels and channel != channels["continuous"]:  
                #add for group in channels since the groups of muscles that are being inputed come from channels which comes from the GUI input
                stim_param.deactivate_output(stim_conn, channel)
                #print(right_leg.active_phase, left_leg.active_phase)
                #print("Channels in use:", active_channels)
    
    else:
        # Deactivate all channels except the ones used
        for channel in channels.values():
            if channel not in active_channels:
                stim_param.deactivate_output(stim_conn, channel)

    used_channels = {channels[g] for g in chain(left_curr_flat, right_curr_flat) if g in channels}
    # groups that were used in the previous phase but are NOT used now -> should be deactivated
    groups_to_deactivate_left = [g for g in left_prev_flat if g in channels and channels[g] not in used_channels]
    groups_to_deactivate_right = [g for g in right_prev_flat if g in channels and channels[g] not in used_channels]


    # now record deactivation metadata for groups that became unused (use previous phase + timestamp)
    if groups_to_deactivate_left:
        deactivate_muscle_group(
            stim_conn,
            channels,
            groups_to_deactivate_left,
            stim_param,
            left_leg.timestamps[-1] if getattr(left_leg, "timestamps", []) else time.time(),
            previous_phase_left,
            left_leg=True,
        )
    if groups_to_deactivate_right:
        deactivate_muscle_group(
            stim_conn,
            channels,
            groups_to_deactivate_right,
            stim_param,
            right_leg.timestamps[-1] if getattr(right_leg, "timestamps", []) else time.time(),
            previous_phase_right,
            left_leg=False,
        )
        

    # Only turn on channels that have changed phase (to avoid multiple activations)
    if right_leg.changed_phase():
        filtered_right = [group for group in muscular_group_right if group in channels]
        if filtered_right:
            stimulate_muscle_group(
                stim_conn, channels, filtered_right, stim_param, right_leg.timestamps[-1], right_leg.active_phase, left_leg=False , record_stim_time= True,_total_paused_duration=_total_paused_duration
            )
        right_leg.update_previous_phase()

    if left_leg.changed_phase():
        filtered_left = [group for group in muscular_group_left if group in channels]
        if filtered_left:
            stimulate_muscle_group(
                stim_conn, channels, filtered_left, stim_param, left_leg.timestamps[-1], left_leg.active_phase, left_leg=True , record_stim_time= True ,_total_paused_duration=_total_paused_duration
            )
        left_leg.update_previous_phase()

def open_stimulation_channel_phases_fsr(
    stim_conn: Serial,
    channels: dict[str, int],
    right_leg: FSRGaitFSM,
    left_leg: FSRGaitFSM,
    stim_param: StimulatorParameters,
    gait_model: str = "Gait Model with Distal",
    personalized_gait_model: bool =False,
    method_fsr= str,
    _total_paused_duration: float =0.0,
) -> None:
    """Activate the stimulation channels based on the current phase of the right and left legs.
    The timestamp of the stimulation is recorded for each muscular group to use it in offline analysis.

    :param stim_conn: The serial connection to the stimulator.
    :type stim_conn: Serial
    :param channels: Dictionary mapping the electrode positions to their respective channels.
    :type channels: dict[str, int]
    :param right_leg: The gait finite state machine for the right leg.
    :type right_leg: Gait_FSM
    :param left_leg: The gait finite state machine for the left leg.
    :type left_leg: Gait_FSM
    :param stim_param: The stimulator parameters object that manages the stimulation settings.
    :type stim_param: StimulatorParameters
    """
     # Skip if no phase change
    if not (right_leg.changed_phase() or left_leg.changed_phase()):
        return
    previous_phase_right= right_leg.previous_phase
    previous_phase_left= left_leg.previous_phase

    if (gait_model == "Gait Model with Distal" and method_fsr == "Method 2 - FSR") or personalized_gait_model == True :
        previous_muscular_group_right=MUSCULAR_GROUP_SELECTION[previous_phase_right][RIGHT_SIDE]
        previous_muscular_group_left=MUSCULAR_GROUP_SELECTION[previous_phase_left][LEFT_SIDE]
        muscular_group_right = MUSCULAR_GROUP_SELECTION[right_leg.active_phase][RIGHT_SIDE]
        muscular_group_left = MUSCULAR_GROUP_SELECTION[left_leg.active_phase][LEFT_SIDE]
        #print("Debug: using Gait Model with Distal or Personalized Gait Model")
        
        #PROBLEM: if personalized gait model and FSR method 1 are chosen they shouldnt be given the chance to use pre-swing, since FSR method 1 does not 
        # detect pre-swing, we can resctrict this by not giving the option for pre-swing in the personalization if FSR method 1 is chosen 
        # on the gui restrict gait model 2 for fsr 1
        
    elif gait_model == "Gait Model without Distal" or method_fsr == "Method 1 - FSR":
        previous_muscular_group_right=MUSCULAR_GROUP_SELECTION_2[previous_phase_right][RIGHT_SIDE]
        previous_muscular_group_left=MUSCULAR_GROUP_SELECTION_2[previous_phase_left][LEFT_SIDE]
        #print("WARNING: Method 1 FSR is not adapted for pre-swing detection and therefore DISTAL leg stimulation")
        muscular_group_right = MUSCULAR_GROUP_SELECTION_2[right_leg.active_phase][RIGHT_SIDE]
        muscular_group_left = MUSCULAR_GROUP_SELECTION_2[left_leg.active_phase][LEFT_SIDE] 
        #print("Debug: Using Gait Model without Distal")
        
        
    if "unknown" in muscular_group_right and "unknown" in muscular_group_left:
        return

    # Turn off channels that are not needed
    # Build set of currently used hardware channels (flatten group lists)
    left_prev_flat = _flatten_groups(previous_muscular_group_left)
    right_prev_flat = _flatten_groups(previous_muscular_group_right)
    left_curr_flat = _flatten_groups(muscular_group_left)
    right_curr_flat = _flatten_groups(muscular_group_right)
    
    # deactivate hardware outputs once for each unused channel
    # Get list of channels that are actively needed
    active_channels = set()
    for group in muscular_group_right + muscular_group_left:
        if group in channels:
            active_channels.add(channels[group])

    # Turn off channels that are not needed
    if "continuous" in channels:
        # Deactivate all channels except the ones used and the continuous channel
        for channel in channels.values():
            if channel not in active_channels and channel != channels["continuous"]:  
                #add for group in channels since the groups of muscles that are being inputed come from channels which comes from the GUI input
                stim_param.deactivate_output(stim_conn, channel)
                #print(right_leg.active_phase, left_leg.active_phase)
                #print("Channels in use:", active_channels)
    else:
        # Deactivate all channels except the ones used
        for channel in channels.values():
            if channel not in active_channels:
                stim_param.deactivate_output(stim_conn, channel)
                

    used_channels = {channels[g] for g in chain(left_curr_flat, right_curr_flat) if g in channels}
    # groups that were used in the previous phase but are NOT used now -> should be deactivated
    groups_to_deactivate_left = [g for g in left_prev_flat if g in channels and channels[g] not in used_channels]
    groups_to_deactivate_right = [g for g in right_prev_flat if g in channels and channels[g] not in used_channels]


    # now record deactivation metadata for groups that became unused (use previous phase + timestamp)
    if groups_to_deactivate_left:
        deactivate_muscle_group(
            stim_conn,
            channels,
            groups_to_deactivate_left,
            stim_param,
            left_leg.timestamps[-1] if getattr(left_leg, "timestamps", []) else time.time(),
            previous_phase_left,
            left_leg=True,
        )
    if groups_to_deactivate_right:
        deactivate_muscle_group(
            stim_conn,
            channels,
            groups_to_deactivate_right,
            stim_param,
            right_leg.timestamps[-1] if getattr(right_leg, "timestamps", []) else time.time(),
            previous_phase_right,
            left_leg=False,
        )

    # Only turn on channels that have changed phase (to avoid multiple activations)
    if right_leg.changed_phase():
        filtered_right = [group for group in muscular_group_right if group in channels]
        if filtered_right:
            stimulate_muscle_group(
                stim_conn, channels, filtered_right, stim_param, right_leg.timestamps[-1], right_leg.active_phase, left_leg=False , record_stim_time= True , _total_paused_duration=_total_paused_duration
            )
        right_leg.update_previous_phase()

    if left_leg.changed_phase():
        filtered_left = [group for group in muscular_group_left if group in channels]
        if filtered_left:
            stimulate_muscle_group(
                stim_conn, channels, filtered_left, stim_param, left_leg.timestamps[-1], left_leg.active_phase, left_leg=True , record_stim_time= True , _total_paused_duration=_total_paused_duration
            )
        left_leg.update_previous_phase()
        
def _get_phase_timestamp(fsm) -> float:
    # Prefer recorded phase timestamp for the active phase (valley-aligned), else fall back to last FSR ts, then time.time()
    try:
        arr = fsm.phase_timestamps.get(fsm.active_phase, None)
        if arr is not None and getattr(arr, "size", 0) > 0:
            return float(arr[-1])
    except Exception:
        pass
    try:
        if getattr(fsm, "timestamps_fsr", []):
            return float(fsm.timestamps_fsr[-1])
    except Exception:
        pass
    return time.time()
        
def open_stimulation_channel_phases_imu_fsr(
    stim_conn: Serial,
    channels: dict[str, int],
    right_leg: FSRIMUGaitFSM,
    left_leg: FSRIMUGaitFSM,
    stim_param: StimulatorParameters,
    gait_model: str = "Gait Model with Distal",
    personalized_gait_model: bool =False,
    method_fsr= str,
    _total_paused_duration: float =0.0,
) -> None:
    """Activate the stimulation channels based on the current phase of the right and left legs.
    The timestamp of the stimulation is recorded for each muscular group to use it in offline analysis.

    :param stim_conn: The serial connection to the stimulator.
    :type stim_conn: Serial
    :param channels: Dictionary mapping the electrode positions to their respective channels.
    :type channels: dict[str, int]
    :param right_leg: The gait finite state machine for the right leg.
    :type right_leg: Gait_FSM
    :param left_leg: The gait finite state machine for the left leg.
    :type left_leg: Gait_FSM
    :param stim_param: The stimulator parameters object that manages the stimulation settings.
    :type stim_param: StimulatorParameters
    """
      # Normalize method_fsr: fall back to a sensible default if caller omitted it
    if method_fsr is None:
        method_fsr = "Method 2 - FSR"

    # Skip if no phase change
    if not (right_leg.changed_phase() or left_leg.changed_phase()):
        return
    previous_phase_right = right_leg.previous_phase
    previous_phase_left = left_leg.previous_phase

    if (gait_model == "Gait Model with Distal" and method_fsr == "Method 2 - FSR") or personalized_gait_model == True:
        previous_muscular_group_right = MUSCULAR_GROUP_SELECTION[previous_phase_right][RIGHT_SIDE]
        previous_muscular_group_left = MUSCULAR_GROUP_SELECTION[previous_phase_left][LEFT_SIDE]
        muscular_group_right = MUSCULAR_GROUP_SELECTION[right_leg.active_phase][RIGHT_SIDE]
        muscular_group_left = MUSCULAR_GROUP_SELECTION[left_leg.active_phase][LEFT_SIDE]
    elif gait_model == "Gait Model without Distal" or method_fsr == "Method 1 - FSR":
        previous_muscular_group_right = MUSCULAR_GROUP_SELECTION_2[previous_phase_right][RIGHT_SIDE]
        previous_muscular_group_left = MUSCULAR_GROUP_SELECTION_2[previous_phase_left][LEFT_SIDE]
        muscular_group_right = MUSCULAR_GROUP_SELECTION_2[right_leg.active_phase][RIGHT_SIDE]
        muscular_group_left = MUSCULAR_GROUP_SELECTION_2[left_leg.active_phase][LEFT_SIDE]
    else:
        # Fallback so variables are always defined (log for debugging)
        #print(f"WARNING: unexpected gait_model='{gait_model}' method_fsr='{method_fsr}' - using fallback MUSCULAR_GROUP_SELECTION_2")
        previous_muscular_group_right = MUSCULAR_GROUP_SELECTION[previous_phase_right][RIGHT_SIDE]
        previous_muscular_group_left = MUSCULAR_GROUP_SELECTION[previous_phase_left][LEFT_SIDE]
        muscular_group_right = MUSCULAR_GROUP_SELECTION[right_leg.active_phase][RIGHT_SIDE]
        muscular_group_left = MUSCULAR_GROUP_SELECTION[left_leg.active_phase][LEFT_SIDE]

        
        
    if "unknown" in muscular_group_right and "unknown" in muscular_group_left:
        return

    # Turn off channels that are not needed
    # Build set of currently used hardware channels (flatten group lists)
    left_prev_flat = _flatten_groups(previous_muscular_group_left)
    right_prev_flat = _flatten_groups(previous_muscular_group_right)
    left_curr_flat = _flatten_groups(muscular_group_left)
    right_curr_flat = _flatten_groups(muscular_group_right)
    
    # deactivate hardware outputs once for each unused channel
    # Get list of channels that are actively needed
    active_channels = set()
    for group in muscular_group_right + muscular_group_left:
        if group in channels:
            active_channels.add(channels[group])

    # Turn off channels that are not needed
    if "continuous" in channels:
        # Deactivate all channels except the ones used and the continuous channel
        for channel in channels.values():
            if channel not in active_channels and channel != channels["continuous"]:  
                #add for group in channels since the groups of muscles that are being inputed come from channels which comes from the GUI input
                stim_param.deactivate_output(stim_conn, channel)
                #print(right_leg.active_phase, left_leg.active_phase)
                #print("Channels in use:", active_channels)
    
    else:
        # Deactivate all channels except the ones used
        for channel in channels.values():
            if channel not in active_channels:
                stim_param.deactivate_output(stim_conn, channel)

    used_channels = {channels[g] for g in chain(left_curr_flat, right_curr_flat) if g in channels}
    # groups that were used in the previous phase but are NOT used now -> should be deactivated
    groups_to_deactivate_left = [g for g in left_prev_flat if g in channels and channels[g] not in used_channels]
    groups_to_deactivate_right = [g for g in right_prev_flat if g in channels and channels[g] not in used_channels]


    # now record deactivation metadata for groups that became unused (use previous phase + timestamp)
    if groups_to_deactivate_left:
        deactivate_muscle_group(
            stim_conn,
            channels,
            groups_to_deactivate_left,
            stim_param,
            _get_phase_timestamp(left_leg),
            previous_phase_left,
            left_leg=True,
        )
    if groups_to_deactivate_right:
        deactivate_muscle_group(
            stim_conn,
            channels,
            groups_to_deactivate_right,
            stim_param,
            _get_phase_timestamp(right_leg),
            previous_phase_right,
            left_leg=False,
        )

    # Only turn on channels that have changed phase (to avoid multiple activations)
    if right_leg.changed_phase():
        filtered_right = [group for group in muscular_group_right if group in channels]
        if filtered_right:
            stimulate_muscle_group(
                stim_conn, channels, filtered_right, stim_param, right_leg.timestamps_fsr[-1], right_leg.active_phase, left_leg=False , record_stim_time= True , _total_paused_duration=_total_paused_duration
            )
        right_leg.update_previous_phase()

    if left_leg.changed_phase():
        filtered_left = [group for group in muscular_group_left if group in channels]
        #print("PHASE L", left_leg.active_phase, "groups", muscular_group_left, "filtered", filtered_left,"prev", left_leg.previous_phase)
        if filtered_left:
            stimulate_muscle_group(
                stim_conn, channels, filtered_left, stim_param, left_leg.timestamps_fsr[-1], left_leg.active_phase, left_leg=True , record_stim_time= True , _total_paused_duration=_total_paused_duration
            )
        left_leg.update_previous_phase()

# def open_stimulation_channel_phases_imu_fsr( 
#     stim_conn: Serial,
#     channels: dict[str, int],
#     right_leg_imu: IMUGaitFSM,
#     left_leg_imu: IMUGaitFSM,
#     right_leg_fsr: FSRGaitFSM,
#     left_leg_fsr: FSRGaitFSM,
#     stim_param: StimulatorParameters,
#     _total_paused_duration: float =0.0,
# ) -> None:
#     """Activate the stimulation channels based on the current phase of the right and left legs.
#     The timestamp of the stimulation is recorded for each muscular group to use it in offline analysis.
#     :param stim_conn: The serial connection to the stimulator.
#     :type stim_conn: Serial
#     :param channels: Dictionary mapping the electrode positions to their respective channels.
#     :type channels: dict[str, int]
#     :param right_leg_imu: The IMU gait finite state machine for the right leg.
#     :type right_leg_imu: IMUGaitFSM
#     :param left_leg_imu: The IMU gait finite state machine for the left leg.
#     :type left_leg_imu: IMUGaitFSM
#     :param right_leg_fsr: The FSR gait finite state machine for the right leg.
#     :type right_leg_fsr: FSRGaitFSM
#     :param left_leg_fsr: The FSR gait finite state machine for the left leg.
#     :type left_leg_fsr: FSRGaitFSM
#     :param stim_param: The stimulator parameters object that manages the stimulation settings.
#     :type stim_param: StimulatorParameters
#     """
#     # Skip if no phase change
#     if not (right_leg_imu.changed_phase() or left_leg_imu.changed_phase()):
#         # if (right_leg_fsr.changed_phase() or left_leg_fsr.changed_phase()):
#         #     right_leg=right_leg_fsr
#         #     left_leg=left_leg_fsr
#         # else:
#         return
    
#     #Luka: changed the logic to test if it works better, should help with miss detection of the IMU gait FSM, otherwise create a global PHASE parameter 
#     else:
#         right_leg = right_leg_imu
#         left_leg = left_leg_imu

#         if (right_leg_imu.active_phase == Phase.LOADING_RESPONSE and right_leg_imu.previous_phase == Phase.MID_STANCE) or right_leg_imu.active_phase == Phase.UNKNOWN:
#             right_leg = right_leg_fsr
#             #print("IMU detected poorly, Right Leg using FSR") #print for debugging

#         if (left_leg_imu.active_phase == Phase.LOADING_RESPONSE and left_leg_imu.previous_phase == Phase.MID_STANCE) or left_leg_imu.active_phase == Phase.UNKNOWN:
#             left_leg = left_leg_fsr
#             #print("IMU detected poorly, Left Leg using FSR") #print for debugging 

     
#     muscular_group_right = MUSCULAR_GROUP_SELECTION[right_leg.active_phase][RIGHT_SIDE]
#     muscular_group_left = MUSCULAR_GROUP_SELECTION[left_leg.active_phase][LEFT_SIDE]
#     if "unknown" in muscular_group_right or "unknown" in muscular_group_left:
#         return

#     # Turn off channels that are not needed
#     if "continuous" in channels:
#          # Deactivate all channels except the ones used and the continuous channel
#         used_channels = {channels[group] for group in muscular_group_right + muscular_group_left if group in channels}
#         for channel in channels.values():
#             if channel in used_channels or channel == channels["continuous"]:
#                 continue
#             # deactivate hardware output
#             stim_param.deactivate_output(stim_conn, channel)
#             # record deactivation for every group mapped to this channel
#             groups_for_channel = [g for g, ch in channels.items() if ch == channel]
#             for g in groups_for_channel:
#                 is_left_group = g.endswith("_left") or "_left" in g
#                 try:
#                     if is_left_group:
#                         stim_param.append_de_stim_left(channel, g, left_leg.previous_phase, left_leg.timestamps[-1])
#                     else:
#                         stim_param.append_de_stim_right(channel, g, right_leg.previous_phase, right_leg.timestamps[-1])
#                 except Exception:
#                     pass  
#     else:
#         # Deactivate all channels except the ones used, and record deactivations per group/side
#         used_channels = {channels[group] for group in muscular_group_right + muscular_group_left if group in channels}
#         left_flat = _flatten_groups(muscular_group_left)
#         right_flat = _flatten_groups(muscular_group_right)
#         for channel in channels.values():
#             if channel in used_channels:
#                 continue
#             try:
#                 stim_param.deactivate_output(stim_conn, channel)
#             except Exception:
#                 pass
#             # record deactivation for every group mapped to this channel
#             groups_for_channel = [g for g, ch in channels.items() if ch == channel]
#             for g in groups_for_channel:
#                 try:
#                     if g in left_flat:
#                         stim_param.append_de_stim_left(channel, g, left_leg.active_phase, left_leg.timestamps[-1])
#                     elif g in right_flat:
#                         stim_param.append_de_stim_right(channel, g, right_leg.active_phase, right_leg.timestamps[-1])
#                     else:
#                         # unknown side: default to right
#                         stim_param.append_de_stim_right(channel, g, right_leg.active_phase, right_leg.timestamps[-1])
#                 except Exception:
#                     pass

#     # Only turn on channels that have changed phase (to avoid multiple activations)
#     if right_leg.changed_phase():
#         filtered_right = [group for group in muscular_group_right if group in channels]
#         if filtered_right:
#             stimulate_muscle_group(
#                 stim_conn, channels, filtered_right, stim_param, right_leg.timestamps[-1], right_leg.active_phase, left_leg=False , record_stim_time= True , _total_paused_duration=_total_paused_duration
#             )
#         right_leg.update_previous_phase()

#     if left_leg.changed_phase():
#         filtered_left = [group for group in muscular_group_left if group in channels]
#         if filtered_left:
#             stimulate_muscle_group(
#                 stim_conn, channels, filtered_left, stim_param, left_leg.timestamps[-1], left_leg.active_phase, left_leg=True , record_stim_time= True , _total_paused_duration=_total_paused_duration
#             )
#         left_leg.update_previous_phase()
        
        
def open_stimulation_FES_step(stim_conn: Serial,
    channels: dict[str, int],
    stim_param: StimulatorParameters,
    fes_side: str,
    fes_speed: float,
    fes_steps: int
    ): 
    """This function is used to stimulate a functional step using FES predefined sequence, the speed, the number of steps and which leg
    
    :param stim_conn: The serial connection to the stimulator.
    :type stim_conn: Serial
    :param channels: Dictionary mapping the electrode positions to their respective channels.
    :type channels: dict[str, int]
    :param stim_param: The stimulator parameters object that manages the stimulation settings.
    :type stim_param: StimulatorParameters
    :param fes_side: left, right or both legs
    :type fes_side: str
    :param fes_speed: the walking speed in km/h 
    :type fes_speed: float
    :param fes_steps: the number of steps from TO to TO desired to replicate 
    :type fes_steps: int
    """
    # Define durations (seconds) for chosen speed
    if fes_speed == 0.8:
        MSW, TSW, LR, MST_PS = 0.270, 0.570, 0.360, 1.850
        
    elif fes_speed == 0.4:
        MSW, TSW, LR, MST_PS = 0.238, 0.274, 0.581, 3.088

    else:
        raise ValueError("Unsupported FES speed (only 0.8 km/h defined)")

    sides = []
    if fes_side.lower() in ("left", "both"):
        sides.append(LEFT_SIDE)
    if fes_side.lower() in ("right", "both"):
        sides.append(RIGHT_SIDE)

    phases = [
        (Phase.MID_SWING, MSW),
        (Phase.TERMINAL_SWING, TSW),
        (Phase.LOADING_RESPONSE, LR),
        (Phase.MID_STANCE, MST_PS),
    ]

    # Run sequence: activate once at phase start, wait for phase duration, then deactivate
    for step in range(fes_steps):
        for phase, duration in phases:
            # collect all groups to stimulate this phase (per side)
            all_filtered_groups = []
            for side in sides:
                muscular_group = MUSCULAR_GROUP_SELECTION[phase][side]
                filtered_groups = [group for group in _flatten_groups(muscular_group) if group in channels]
                all_filtered_groups.append((side, filtered_groups))

            # Activate each mapped group once
            for side, filtered_groups in all_filtered_groups:
                if not filtered_groups:
                    continue
                stimulate_muscle_group(
                    stim_conn, channels, filtered_groups,
                    stim_param, time.time(), phase,
                    left_leg=(side == LEFT_SIDE),
                    record_stim_time=False
                )

            # wait whole phase duration (no tight repeated activations)
            time.sleep(duration)

            # Deactivate channels that were activated for this phase
            for side, filtered_groups in all_filtered_groups:
                for group in filtered_groups:
                    try:
                        ch = channels.get(group)
                        if ch is None:
                            continue
                        # deactivate hardware output once
                        stim_param.deactivate_output(stim_conn, ch)
                        # record de-activation timestamp if desired
                    except Exception:
                        pass