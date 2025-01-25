#!/usr/bin/env python3

import logging
from typing import Tuple, Union

from pymodbus.client.serial import ModbusSerialClient
from pymodbus.client.tcp import ModbusTcpClient
from pymodbus.framer import FramerType


class ETMXXXXPError(Exception):
    """@brief An exception produced by ETMXXXXP class instances."""
    pass


class ETMXXXXP(object):
    """Repsonsible for providing an interface to the ETommens eTM-xxxxP Series PSU.
       Several Mfg's use this supply, Hanmatek HM305P, Rockseed RS305P,
       Hanmatek HM310P, RockSeed RS310P, Rockseed RS605P.

       Ref https://sigrok.org/wiki/ETommens_eTM-xxxxP_Series#Protocol

       This class supports

       Setting

       - Output on/off state
       - Output Voltage
       - Current limit
       - Over voltage protection
       - Over current protection
       - Over power protection
       - Setting the buzzer on/off state

       Getting

       - The output on/off state
       - The target output voltage
       - The actual output voltage (drops to 0 if output is off)
       - The output current
       - The output power
       - The current limit value
       - The over voltage protection value
       - The over current protection value
       - The over power protection value

       """

    MIN_VOLTAGE = 0
    MAX_VOLTAGE = 32.0
    MAX_OVER_VOLTAGE = 33.0                 # This is the max value that can be set on the PSU
    MAX_CURRENT = 10.0                      # 10A max, some models have a 5A max current.
    MAX_OVER_CURRENT = 10.5                 # This is the max value that can be set on the PSU
    MAX_OVER_POWER = 310.0                  # This is the max value that can be set on the PSU
    # RW REG
    OUTPUT_STATE_REG_ADDR = 0x0001
    # R REGS
    PROTECTION_STATE_REG_ADDR = 0x0002
    MODEL_ID_REG_ADDR = 0x0004
    OUTPUT_VOLTAGE_REG_ADDR = 0x0010
    OUTPUT_CURRENT_REG_ADDR = 0x0011
    OUTPUT_PWR_HI_REG_ADDR = 0x0012         # Top 16 bits of output power reg
    OUTPUT_PWR_LO_REG_ADDR = 0x0013         # Bottom 16 bits of output power reg
    # R/WR REGS
    VOLTAGE_TARGET_REG_ADDR = 0x0030
    CURRENT_LIMIT_REG_ADDR = 0x0031
    OVER_VOLTAGE_PROT_REG_ADDR = 0x0020
    OVER_CURRENT_PROT_REG_ADDR = 0x0021
    OVER_PWR_PROT_HI_REG_ADDR = 0x0022      # Top 16 bits of over power protection
    OVER_PWR_PROT_LOW_REG_ADDR = 0x0023     # Bottom 16 bits of over power protection
    BUZZER_REG_ADDR = 0x8804                # 1 = enable (beep on key press), 0 = disable

    def __init__(self, port: Union[str, Tuple[str, int]], slave=1, debug=False):
        """@brief Constructor
           @param port The port on which to communicate with the PSU. This may be
                       The local port. E.G /dev/ttyUSB0
                       The address/port if the PSU is remote.
           @param unit The unit number on the modbus interface."""
        self._port = port
        self._slave = slave
        self._client = None  # Modbus client connection

        if debug:
            logging.basicConfig()
            log = logging.getLogger()
            log.setLevel(logging.DEBUG)

    def connect(self, timeout=2):
        """@brief connect to the PSU over the serial port.
           @param timeout The command response timeout in seconds (default=2).
           @return True if connected."""
        if len(self._port) == 2:
            self._client = ModbusTcpClient(host=self._port[0], port=self._port[1], framer=FramerType.RTU)
        else:
            self._client = ModbusSerialClient(framer=FramerType.RTU, port=self._port, baudrate=9600, stopbits=1, bytesize=8, parity='N', timeout=timeout)
        return self._client.connect()

    def disconnect(self):
        """@brief Disconnect from the PSU if connected."""
        if self._client:
            self._client.close()
            self._client = None

    # READ REGS
    def getOutput(self):
        """@brief Get the state of the PSU output.
           @return 1 if the output is on, else 0."""
        rr = self._client.read_holding_registers(ETMXXXXP.OUTPUT_STATE_REG_ADDR, count=1, slave=self._slave)
        return rr.registers[0]

    def getProtectionState(self):
        """@brief Get the state of the protections switch.
           @return 1 if protection mode is enabled, else 0."""
        rr = self._client.read_holding_registers(ETMXXXXP.PROTECTION_STATE_REG_ADDR, count=1, slave=self._slave)
        return rr.registers[0]

    def getModel(self):
        """@brief Get the model ID
           @return The model ID value"""
        rr = self._client.read_holding_registers(ETMXXXXP.MODEL_ID_REG_ADDR, count=1, slave=self._slave)
        return rr.registers[0]

    def getOutputStats(self):
        """@brief Read the output voltage, current and power of the PSU.
           @return A tuple containing
                   0: voltage
                   1: amps
                   2: watts"""
        rr = self._client.read_holding_registers(ETMXXXXP.OUTPUT_VOLTAGE_REG_ADDR, count=4, slave=self._slave)
        voltage = float(rr.registers[0])
        if voltage > 0:
            voltage = voltage / 100.0
        amps = float(rr.registers[1])
        if amps > 0:
            amps = amps / 1000.0
        wattsH = rr.registers[2]
        wattsL = rr.registers[3]
        watts = wattsH << 16 | wattsL
        if watts > 0:
            watts = watts / 1000.0
        return (voltage, amps, watts)

    def getTargetVolts(self):
        """@brief Read the target output voltage
           @return The output voltage set in volts."""
        rr = self._client.read_holding_registers(ETMXXXXP.VOLTAGE_TARGET_REG_ADDR, count=1, slave=self._slave)
        voltage = float(rr.registers[0])
        if voltage > 0:
            voltage = voltage / 100.0
        return voltage

    def getCurrentLimit(self):
        """@brief Read the current limit in amps
           @return The current limit."""
        rr = self._client.read_holding_registers(ETMXXXXP.CURRENT_LIMIT_REG_ADDR, count=1, slave=self._slave)
        amps = float(rr.registers[0])
        if amps > 0:
            amps = amps / 1000.0
        return amps

    def getProtectionValues(self):
        """@brief Read the over voltage, current and power protection values
           @return A tuple containing
                   0: over voltage protection value
                   1: over current protection value
                   2: over power protection value"""
        rr = self._client.read_holding_registers(ETMXXXXP.OVER_VOLTAGE_PROT_REG_ADDR, count=4, slave=self._slave)
        voltage = float(rr.registers[0])
        if voltage > 0:
            voltage = voltage / 100.0
        amps = float(rr.registers[1])
        if amps > 0:
            amps = amps / 1000.0
        wattsH = rr.registers[2]
        wattsL = rr.registers[3]
        watts = float(wattsH << 16 | wattsL)
        if watts > 0:
            watts = watts / 1000.0
        return (voltage, amps, watts)

    def getBuzzer(self):
        """@brief Get the state of the buzzer
           @return 1 if enabled, 0 if disabled."""
        rr = self._client.read_holding_registers(ETMXXXXP.BUZZER_REG_ADDR, count=1, slave=self._slave)
        return rr.registers[0]

    # WRITE REGS
    def setOutput(self, on):
        """@brief Set The PSU output on/off.
           @param on If True the PSU output is on."""
        self._client.write_register(ETMXXXXP.OUTPUT_STATE_REG_ADDR, on, slave=self._slave)

    def setVoltage(self, voltage):
        """@brief Set the output voltage.
           @param voltage The voltage in volts (a float value)."""
        if voltage < ETMXXXXP.MIN_VOLTAGE or voltage > ETMXXXXP.MAX_VOLTAGE:
            raise ETMXXXXPError("{} is an invalid voltage (valid range {}V - {}V)".format(voltage, ETMXXXXP.MIN_VOLTAGE, ETMXXXXP.MAX_VOLTAGE))
        self._client.write_register(ETMXXXXP.VOLTAGE_TARGET_REG_ADDR, int(voltage*100.0), slave=self._slave)

    def setCurrentLimit(self, amps):
        """@brief Set the current limit value.
           @param amps The current in amps (a float value)."""
        if amps < 0.0 or amps > ETMXXXXP.MAX_CURRENT:
            raise ETMXXXXPError("{} is an invalid current value (valid range 0A - {}A)".format(amps, ETMXXXXP.MAX_CURRENT))
        self._client.write_register(ETMXXXXP.CURRENT_LIMIT_REG_ADDR, int(amps*1000.0), slave=self._slave)

    def setOverVoltageP(self, voltage):
        """@brief Set the over voltage protection value.
           @param voltage The voltage in volts (a float value)."""
        if voltage < ETMXXXXP.MIN_VOLTAGE or voltage > ETMXXXXP.MAX_OVER_VOLTAGE:
            raise ETMXXXXPError("{} is an invalid voltage (valid range {}V - {}V)".format(voltage, ETMXXXXP.MIN_VOLTAGE, ETMXXXXP.MAX_VMAX_OVER_VOLTAGEOLTAGE))
        self._client.write_register(ETMXXXXP.OVER_VOLTAGE_PROT_REG_ADDR, int(voltage*100.0), slave=self._slave)

    def setOverCurrentP(self, amps):
        """@brief Set the over current protection value.
           @param amps The current in amps (a float value)."""
        if amps < 0.0 or amps > ETMXXXXP.MAX_OVER_CURRENT:
            raise ETMXXXXPError("{} is an invalid voltage (valid range 0V - {}V)".format(amps, ETMXXXXP.MAX_OVER_CURRENT))
        self._client.write_register(ETMXXXXP.OVER_CURRENT_PROT_REG_ADDR, int(amps*1000.0), slave=self._slave)

    def setOverPowerP(self, watts):
        """@brief Set the over power protection value.
           @param watts The power in watts (a float value)."""
        if watts < 0.0 or watts > ETMXXXXP.MAX_OVER_POWER:
            raise ETMXXXXPError("{} is an invalid power (valid range 0W - {}W)".format(watts, ETMXXXXP.MAX_OVER_POWER))
        wattValue = int((watts*1000))
        wattsL = wattValue & 0x0000ffff
        wattsH = (wattValue & 0xffff0000) >> 16
        self._client.write_register(ETMXXXXP.OVER_PWR_PROT_HI_REG_ADDR, wattsH, slave=self._slave)
        self._client.write_register(ETMXXXXP.OVER_PWR_PROT_LOW_REG_ADDR, wattsL, slave=self._slave)

    def setBuzzer(self, on):
        """@brief Set the buzzer on/off.
           @param on If True the buzzer is set on, 0 = off."""
        self._client.write_register(ETMXXXXP.BUZZER_REG_ADDR, on, slave=self._slave)
