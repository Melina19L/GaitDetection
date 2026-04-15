"""
This file has the purpose to read the data coming from the IMUs in order to detect the
gait phases of a walking subject.

The commented snippets in the code are related to subphases detection, should be implemented in later versions (do not remove them)

This should be called by the GUI.

Please run this code with the computer connected to the power supply to avoid rendering delays

"""

from .ComPortFunc import SetSingleChanSingleParam
from .stimulation_classes import StimulationIMUs, StimulationFSR, StimulationBasic, NoStimulation, StimulationFSRandIMU, StimulationFESStep
from .stimulator_parameters import StimulatorParameters
from serial import Serial
import numpy as np
import traceback
import ctypes
from PySide6.QtCore import Signal, QObject, Slot
import platform
import subprocess


#################################################
""" Block sleep mode during the experiment """
#################################################

#NOTE Except for Windows, the other OSes are AI generated and not tested, please test them before using them in a real experiment

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002

def prevent_sleep():
    """ Prevent the system from entering sleep mode. """
    system = platform.system()
    if system == "Windows":
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED)
    elif system == "Darwin":
        # On macOS, use caffeinate to prevent sleep
        # This will spawn a process that keeps the system awake
        # Store the process handle if you want to terminate it later
        global _caffeinate_proc
        _caffeinate_proc = subprocess.Popen(["caffeinate"])
    elif system == "Linux":
        # On Linux, try to use systemd-inhibit if available
        # This will block sleep while the process is running
        global _inhibit_proc
        try:
            _inhibit_proc = subprocess.Popen(
                ["systemd-inhibit", "--what=handle-lid-switch:sleep", "--why=Experiment running", "sleep", "infinity"]
            )
        except FileNotFoundError:
            print("systemd-inhibit not found. Sleep prevention may not work.")
    else:
        print("Sleep prevention not implemented for this OS.")

def allow_sleep():
    """ Reset the execution state to allow sleep """
    system = platform.system()
    if system == "Windows":
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
    elif system == "Darwin":
        # Terminate the caffeinate process if it was started
        global _caffeinate_proc
        if '_caffeinate_proc' in globals() and _caffeinate_proc.poll() is None:
            _caffeinate_proc.terminate()
    elif system == "Linux":
        # Terminate the systemd-inhibit process if it was started
        global _inhibit_proc
        if '_inhibit_proc' in globals() and _inhibit_proc.poll() is None:
            _inhibit_proc.terminate()
    # No action needed for other OSes
    

#########################################
"""Prepare channels for stimulation"""
#########################################


# NOTE this snippet here is to be activated in the TASK 2 (different frequencies for different channels)
# this commented snippet is for the last task of the protocol: we wan to set a different a diffrent stimulation frequency from the 30Hz (reference),
# for a specific channel (so we're going to modify only the interframe_duration parameter for that channel)
def change_stimulation_frequency(
    stimulator_connection: Serial,
    channels: dict,
    positions: list[str],
    new_burst_freq: int,
):
    try:
        burst_duration = np.uint32(1e6 / new_burst_freq)
        for channel in positions:
            SetSingleChanSingleParam(stimulator_connection, channels[channel], 4, burst_duration)  # change t4* for that channel

    except Exception:
        print("Error detected or user interruption. Shutting down all channels...")
        StimulatorParameters.close_all_channels(stimulator_connection)


##########################################################################
""" MAIN Thread - real-time gait detection and tSCS stimulation """
##########################################################################


class ExperimentHandler(QObject):
    finished = Signal(tuple)
    error_message = Signal(str)
    starting_experiment = Signal()
    step_count_changed = Signal(int)
    
    stimulator = None

    # New signals forwarded to MainWindow
    imu_left_step_count_changed = Signal(int)
    imu_right_step_count_changed = Signal(int)
    imu_left_phase_changed = Signal(int)
    imu_right_phase_changed = Signal(int)
    fsr_left_step_count_changed = Signal(int)
    fsr_right_step_count_changed = Signal(int)
    # per-leg phase signals from backend (FSR)
    fsr_left_phase_changed = Signal(int)
    fsr_right_phase_changed = Signal(int)
    #fsr and imu 
    fsr_imu_left_step_count_changed = Signal(int)
    fsr_imu_right_step_count_changed = Signal(int)
    fsr_imu_left_phase_changed = Signal(int)
    fsr_imu_right_phase_changed = Signal(int)
    # NEW: live active time from backend
    active_run_seconds_changed = Signal(float)

    @Slot(dict)
    def start_experiment_safe(self, kwargs: dict):
        try:
            self.start_experiment(kwargs)
        except Exception as e:
            self.handle_error(e)

    def start_experiment(self, kwargs: dict):
        # Prevent the system from sleeping during the experiment
        prevent_sleep()  
        # DEBUG, Remove after testing
        for key, value in kwargs.items():
            print(f"{key}: {value}")

        # Get bool values for use_imus and use_fsr
        use_imus = kwargs.get("use_imus", False)
        use_fsr = kwargs.get("use_fsr", False)
        
        do_fes_step = kwargs.get("stimulate_fes_step")
        
        if do_fes_step:
            self.stimulator=StimulationFESStep(**kwargs)
            self.stimulator.finished.connect(self.return_results)
            self.stimulator.error.connect(self.handle_error)


            # Start the main loop
            self.starting_experiment.emit()
            self.stimulator.start_main_loop()

        elif use_imus and not use_fsr:
            # Create the StimulationIMUs object
            self.stimulator = StimulationIMUs(**kwargs)
            self.stimulator.finished.connect(self.return_results)
            self.stimulator.error.connect(self.handle_error)
            # Wire step updates to UI
            try:
                self.stimulator.step_count_changed.connect(self.step_count_changed)
            except Exception:
                pass
            try:
                self.stimulator.active_run_seconds_changed.connect(self.active_run_seconds_changed.emit)
            except Exception:
                pass   
            # NEW: per-leg IMU steps
            try:
                self.stimulator.imu_left_step_count_changed.connect(self.imu_left_step_count_changed)
                self.stimulator.imu_right_step_count_changed.connect(self.imu_right_step_count_changed)
                # NEW: per-leg IMU subphase -> forward to handler signals/slots
            except Exception:
                pass
            try:
                self.stimulator.imu_left_phase_changed.connect(self.imu_left_phase_changed)
                self.stimulator.imu_right_phase_changed.connect(self.imu_right_phase_changed)
            except Exception:
                pass
            # Start the main loop
            self.starting_experiment.emit()
            self.stimulator.start_main_loop()

        elif use_imus and use_fsr:
            self.stimulator = StimulationFSRandIMU(**kwargs)
            self.stimulator.finished.connect(self.return_results)
            self.stimulator.error.connect(self.handle_error)
            try:
                self.stimulator.active_run_seconds_changed.connect(self.active_run_seconds_changed.emit)
            except Exception:
                pass
            # NEW: per-leg FSR steps (added in this class)
            try:
                self.stimulator.fsr_imu_left_step_count_changed.connect(self.fsr_imu_left_step_count_changed)
                self.stimulator.fsr_imu_right_step_count_changed.connect(self.fsr_imu_right_step_count_changed)
            except Exception:
                pass
            
            # NEW: per-leg FSR phases
            try:
                self.stimulator.fsr_imu_left_phase_changed.connect(self.fsr_imu_left_phase_changed)
                self.stimulator.fsr_imu_right_phase_changed.connect(self.fsr_imu_right_phase_changed)
            except Exception:
                pass
            
            # Start the main loop
            self.starting_experiment.emit()
            self.stimulator.start_main_loop()

        elif use_fsr and not use_imus:
            self.stimulator = StimulationFSR(**kwargs)
            self.stimulator.finished.connect(self.return_results)
            self.stimulator.error.connect(self.handle_error)
            try:
                self.stimulator.active_run_seconds_changed.connect(self.active_run_seconds_changed.emit)
            except Exception:
                pass
            # Wire step updates to UI
            try:
                self.stimulator.step_count_changed.connect(self.step_count_changed)
            except Exception:
                pass
            # NEW: per-leg FSR steps
            try:
                self.stimulator.fsr_left_step_count_changed.connect(self.fsr_left_step_count_changed)
                self.stimulator.fsr_right_step_count_changed.connect(self.fsr_right_step_count_changed)
            except Exception:
                pass
            
            # NEW: per-leg FSR phases
            try:
                self.stimulator.fsr_left_phase_changed.connect(self.fsr_left_phase_changed)
                self.stimulator.fsr_right_phase_changed.connect(self.fsr_right_phase_changed)
            except Exception:
                pass
            
            # Start the main loop
            self.starting_experiment.emit()
            self.stimulator.start_main_loop()
            
            
        else:
            # Stimulation without gait detection
            self.stimulator = NoStimulation(**kwargs)
            self.stimulator.finished.connect(self.return_results)
            self.stimulator.error.connect(self.handle_error)
            try:
                self.stimulator.active_run_seconds_changed.connect(self.active_run_seconds_changed.emit)
            except Exception:
                pass

            for channel in self.stimulator.channels.values():
                # Activating the output like this will create a stimulation
                self.stimulator.activate_output(channel)

            # Start the main loop
            self.starting_experiment.emit()
            self.stimulator.start_main_loop()

    # Stop the experiment
    @Slot()
    def stop_experiment(self):
        # Allow the system to sleep again
        allow_sleep()
        print("Stopping the experiment...")
         # If paused (timer stopped), main loop will not process stop event → force finalize
        try:
            if self.stimulator and getattr(self.stimulator, "_paused", False):
                print("Force stop during pause.")
                self.stimulator.force_stop_and_save()
                return
        except Exception:
            pass
        # Set the stop event to signal the loop to stop
        StimulationBasic.stop_main_loop()

    # --- NEW: Pause / Resume support ---
    @Slot()
    def pause_experiment(self):
        try:
            if self.stimulator and hasattr(self.stimulator, "pause"):
                self.stimulator.pause()
        except Exception as e:
            print(f"Stimulator.pause() failed: {e}")
        # Try base class static pause if available
        try:
            from .stimulation_basic import StimulationBasic as SB  # type: ignore
            if hasattr(SB, "pause"):
                SB.pause()
        except Exception:
            # Fallback: if base pause is not available, do nothing
            pass

    @Slot()
    def resume_experiment(self):
        try:
            if self.stimulator and hasattr(self.stimulator, "resume"):
                self.stimulator.resume()
        except Exception as e:
            print(f"Stimulator.resume() failed: {e}")
        # Try base class static resume if available
        try:
            from .stimulation_basic import StimulationBasic as SB  # type: ignore
            if hasattr(SB, "resume"):
                SB.resume()
        except Exception:
            # Fallback: if base resume is not available, do nothing
            pass
        
    @Slot(Exception)
    def handle_error(self, e: Exception):
        if self.stimulator:
            self.stimulator.stop_stimulation()
        # Handle the error message (e.g., log it, show a message box, etc.)
        error_message = f"An error of type {type(e).__name__} occurred: {e}"
        # Print the stack trace for debugging
        print(error_message)
        traceback.print_exc()
        self.error_message.emit(error_message)
        
    @Slot(tuple)
    def return_results(self, results: tuple):
        # Emit the results signal with the results dictionary
        self.finished.emit(results)

if __name__ == "__main__":
    print("This module is not meant to be run directly.")
