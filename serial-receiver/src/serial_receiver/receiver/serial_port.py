"""Opening a serial port for reading the protocol stream."""

import serial


def open_serial_port(port: str, baudrate: int, timeout_s: float = 0.1) -> serial.Serial:
    """Opens the port the way every reader in this package needs it.

    Shared by Receiver (long-running read loop) and DeviceProber (short probe),
    so both see the device the same way. Use it as a context manager to close
    the port on exit:

        with open_serial_port("/dev/ttyUSB0", 921600) as ser:
            data = ser.read(ser.in_waiting or 1)

    - Short read timeout: read() returns after at most timeout_s even on a silent
      line, so read loops can check timers and deadlines.
    - DTR/RTS deasserted, see below.

    Raises serial.SerialException if the port can't be opened (missing, busy...).
    """
    ser = serial.Serial()  # created closed, so the settings below apply before open()
    ser.port = port
    ser.baudrate = baudrate
    ser.timeout = timeout_s
    # Many USB-serial devices wire DTR/RTS to a reset circuit; keep them
    # deasserted to avoid resetting the device (not guaranteed: some OSes, e.g.
    # macOS, still pulse them during open, so the device may reboot anyway).
    ser.dtr = False
    ser.rts = False
    ser.open()
    return ser
