from serial import Serial
import serial.tools.list_ports
import numpy as np
import struct
import time

NOT_MSB_MASK = 0b01111111  # Mask to keep only the 7 least significant bits


def SetSingleChanSingleParam(s: Serial, channel_id: int, var_id: int, data: int | float):
    """SetSingleChanSingleParam: Sets a single parameter of a single channel.\n
    The parameter to be set is determined by the VarID. These are the possible VarIDs: \n
    1: pulse width [us] (t1) - duration of one phase of the biphasic pulse\n
    2: pulse deadtime [us] (t2) - time between positive and negative polarity of the biphasic pulse\n
    3: interpulse interval [us] (t3) - time between two pulses\n
    4: burst period [us] (t4*) - time between the start of the first pulse and the start of the next pulse\n
    5: nb pulses - number of pulses in a burst\n
    6: current [mA] - current in mA (float)\n
    7: mode - 0: continuous, 1: single \n
    8: trigger - manual trigger of a new pulse (timer is respected, value is not used)\n
    9: instant trigger - manual trigger of a new pulse (timer is ignored, value is not used)\n

    :param s: Serial port connected to the stimulator.
    :type s: Serial
    :param channel_id: ID of the channel to set the parameters for.
    :type channel_id: int
    :param var_id: ID of the variable to set.
    :type var_id: int
    :param data: Value for the variable to set. Only the current amplitude is a float.
    :type data: int | float

    :raises ValueError: If the var_id is not in the range of 1 to 9.

    :example:
    >>> SetSingleChanSingleParam(s, 0, 1, 100) # Set pulse width to 100 microseconds for channel 0
    """
    # Define message IDs and end marker
    MSG_ID = np.uint8(221)
    MSG_END = np.uint8(128)

    # Convert data to binary based on var_id
    if var_id in [1, 2, 3, 4, 5, 7, 8, 9]:
        data_bin = uint32_to_binary(data)
    elif var_id == 6:
        data_bin = float_to_binary(data)
    else:
        # Invalid var_id
        raise ValueError("Invalid var_id. Must be between 1 and 9.")

    # Create message
    msg = bytes([MSG_ID, channel_id, var_id]) + data_bin

    # Calculate CCR (Checksum)
    ccr = 0
    for byte in msg:
        ccr ^= byte # XOR operation with each byte in the message

    # Ensure the checksum is within the 7 least significant bits
    ccr = ccr & NOT_MSB_MASK

    # Write message to serial port
    s.write(msg + bytes([ccr, MSG_END]))


def SetSingleChanState(s: Serial, channel_id: int, power_state: bool, hv_state: bool, output_state: bool):
    """SetSingleChanState: Sets the state of a single channel.\n
    Each state can only be set if the state before is set as well:\n
    Power -> HV -> Output

    :param s: Serial port connected to the stimulator.
    :type s: Serial
    :param channel_id: ID of the channel to set the parameters for.
    :type channel_id: int
    :param power_state: Turn the channel on (True) or off (False).
    :type power_state: bool
    :param hv_state: Turn the high voltage on (True) or off (False).
    :type hv_state: bool
    :param output_state: Generate an output current (True) or not (False).
    :type output_state: bool

    :raises ValueError: If power_state is False and hv_state is True, or if hv_state is False and output_state is True.
    """
    MSG_ID = np.uint8(223)  # 0xDF
    MSG_END = np.uint8(128)  # 0x80

    data = 0
    if power_state:
        # Set first bit to 1 for power ON
        data += 1

    if hv_state:
        # Set second bit to 1 for high voltage ON
        data += 2
        if not power_state:
            # If power is not ON, raise an error (for debugging purposes)
            raise ValueError("Power must be ON to be able to set the HV state.")

    if output_state:
        # Set third bit to 1 for output ON
        data += 4
        if not hv_state or not power_state:
            # If power or HV is not ON, raise an error (for debugging purposes)
            raise ValueError("Power and HV must be ON to be able to set the output state.")

    # Create message
    msg = bytes([MSG_ID, channel_id, data])

    # Calculate CCR (Checksum)
    ccr = 0
    for byte in msg:
        ccr ^= byte # XOR operation with each byte in the message
        
    # Ensure the checksum is within the 7 least significant bits
    ccr = ccr & NOT_MSB_MASK

    s.write(msg + bytes([ccr, MSG_END]))


def SetSingleChanAllParam(
    s: Serial,
    channel_id: int,
    pulse_width: int,
    pulse_deadtime: int,
    interpulse_interval: int,
    burst_period: int,
    nb_pulses: int,
    current: float,
    mode: int = 2,
):
    """SetSingleChanAllParam: Sets all parameters of a single channel.

    :param s: Serial port connected to the stimulator.
    :type s: Serial
    :param channel_id: ID of the channel to set the parameters for.
    :type channel_id: int
    :param pulse_width: Duration of one phase of the biphasic pulse (t1) [us].
    :type pulse_width: int
    :param pulse_deadtime: Time between positive and negative polarity of the biphasic pulse (t2) [us].
    :type pulse_deadtime: int
    :param interpulse_interval: Time between two pulses (t3) [us].
    :type interpulse_interval: int
    :param burst_period: Time between the start of the first pulse and the start of the next pulse (t4*) [us].
    :type burst_period: int
    :param nb_pulses: Number of pulses in a burst.
    :type nb_pulses: int
    :param current: Current to be produced [mA].
    :type current: float
    :param mode: Repetition mode, (0 = continuous, 1 = single, 2 = don't update), defaults to 2.
    :type mode: int, optional
    """
    # Define message IDs and end marker
    MSG_ID = np.uint8(220)  # Identifier for the message
    MSG_END = np.uint8(128)  # End marker for the message

    # Convert parameters to binary
    pulse_width_BIN = uint32_to_binary(pulse_width)
    pulse_deadtime_BIN = uint32_to_binary(pulse_deadtime)
    interpulse_duration_BIN = uint32_to_binary(interpulse_interval)
    interframe_duration_BIN = uint32_to_binary(burst_period)
    N_pulse_repetition_BIN = np.uint8(nb_pulses)
    current_initial_BIN = float_to_binary(current)
    mode_BIN = np.uint8(mode)

    # Create message by concatenating all parameter binaries
    msg = bytearray()
    msg.extend(MSG_ID)
    msg.extend(np.uint8(channel_id))
    msg.extend(pulse_width_BIN)
    msg.extend(pulse_deadtime_BIN)
    msg.extend(interpulse_duration_BIN)
    msg.extend(interframe_duration_BIN)
    msg.extend(N_pulse_repetition_BIN)
    msg.extend(current_initial_BIN)
    msg.extend(mode_BIN)

    # Calculate CCR (Checksum)
    ccr = 0
    for byte in msg:
        ccr ^= byte  # XOR operation with each byte in the message
    
    # Ensure the checksum is within the 7 least significant bits
    ccr = ccr & NOT_MSB_MASK

    # Write message to serial port
    s.write(msg + bytearray([ccr, MSG_END]))


def uint32_to_binary(uint32: int) -> bytearray:
    """Convert conventional 32-bit integer (int) to 5 bytes
    (7 bits each, with a leading zero for the first 4 bytes and 3 bits for the last byte).\n
    The MSB is used to control the communication (start and end of the message).

    :param uint32: Integer to be converted to binary. It is assumed to be an unsigned 32-bit integer.
    :type uint32: int
    :return: The binary representation of the integer as a bytearray.
    :rtype: bytearray
    """
    # Convert the input integer to a 32-bit binary string
    val_4_bins = format(uint32, "032b")

    # Split the binary string into groups of 7 bits, each with a leading zero
    val_5_bins = [
        "0" + val_4_bins[0:7],
        "0" + val_4_bins[7:14],
        "0" + val_4_bins[14:21],
        "0" + val_4_bins[21:28],
        "0" + val_4_bins[28:] + "000",
    ]

    # Convert each group to an integer and then to a byte
    return bytearray([int(val, 2) for val in val_5_bins])


def float_to_binary(float32: float) -> bytearray:
    """Convert conventional 32-bit float (float) to 5 bytes
    (7 bits each, with a leading zero for the first 4 bytes and 3 bits for the last byte).\n
    The MSB is used to control the communication (start and end of the message).\n

    :param float32: Float to be converted to binary. It is assumed to be a 32-bit float.
    :type float32: float
    :return: The binary representation of the float as a bytearray.
    :rtype: bytearray
    """
    # Convert the float to its 32-bit binary representation
    val_4_bins = "".join(format(byte, "08b") for byte in struct.pack("!f", float32))

    # Split the binary string into groups of 7 bits, each with a leading zero
    val_5_bins = [
        "0" + val_4_bins[0:7],
        "0" + val_4_bins[7:14],
        "0" + val_4_bins[14:21],
        "0" + val_4_bins[21:28],
        "0" + val_4_bins[28:] + "000",
    ]

    # Convert each group to an integer and then to a byte
    return bytearray([int(val, 2) for val in val_5_bins])


def readComBuffer(s: Serial, OPTin: dict = None):
    """Read data from the serial buffer.

    :param s: Serial port object.
    :param OPTin: Optional dictionary containing options.
    :returns:
        data: Byte(s) retrieved from the buffer.
        BAout: Number of bytes retrieved from the buffer.
        ERR: Error code (0 if no error).
    """
    # Define default options
    OPT = {
        "TimeOut": 0.5,  # Time out in seconds
        "Ts": 0.05,  # Timer increment
        "MinRXByteCnt": 1,  # Minimum number of bytes to read from the buffer
        "MaxRXByteCnt": 1e6,  # Maximum number of bytes to read (if the buffer contains more, they won't be read)
        "TimeOutErrId": -1,  # Error ID for time out without receiving at least "OPT.MinRXByteCnt" bytes
        "MaxRXTrig": -2,  # Buffer content exceeds "OPT.MaxRXByteCnt"
    }

    # Update options if provided
    if OPTin:
        for key, value in OPTin.items():
            if key in OPT:
                OPT[key] = value

    # Preliminary tasks
    ERR = 0
    BAout = None

    # Function
    Timer = 0
    BA = s.in_waiting

    while BA < OPT["MinRXByteCnt"]:
        time.sleep(OPT["Ts"])
        Timer += OPT["Ts"]
        BA = s.in_waiting
        if Timer >= OPT["TimeOut"]:
            data = b""
            ERR = OPT["TimeOutErrId"]
            return data, BAout, ERR

    if BA > OPT["MaxRXByteCnt"]:
        data = s.read(OPT["MaxRXByteCnt"])
        BAout = OPT["MaxRXByteCnt"]
        ERR = OPT["MaxRXTrig"]
    else:
        data = s.read(BA)
        BAout = BA

    return data, BAout, ERR

def list_serial_devices() -> list[str]:
    """Create a list of all connected serial devices.

    :return: A list of strings containing the port name and description of each device.
    :rtype: list[str]
    """
    ports = serial.tools.list_ports.comports()
    devices = []
    for port in ports:
        devices.append(port.device + " - " + port.description)
        
    return devices

def open_serial_port(ComPort: str, Baudrate: int) -> Serial:
    """Open a serial port with the specified parameters.

    :param ComPort: String representing the COM port (e.g., 'COM8').
    :param Baudrate: Integer representing the baud rate.
    :return: Serial port object.
    """
    # Close and delete serial port if it exists
    s: Serial = None
    if "s" in globals():
        s.close()
        del s

    # Close all open serial ports
    serial_ports = serial.tools.list_ports.comports()
    for port in serial_ports:
        try:
            ser = Serial(port.device)
            ser.close()
        except Exception:
            pass

    # Reopen serial port
    s = Serial(ComPort, baudrate=Baudrate, timeout=1, write_timeout=1, inter_byte_timeout=None)
    s.reset_input_buffer()
    return s


def close_serial_port(s: Serial):
    """Closes the specified serial port.

    :param s: Serial port object.
    :type s: Serial
    """
    # Close serial port
    s.close()
