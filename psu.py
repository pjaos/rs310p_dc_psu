#!/usr/bin/env python3

from    optparse import OptionParser
import  logging
from    pymodbus.client.sync import ModbusSerialClient as ModbusClient

class UIO(object):
    """@brief responsible for user output and input via stdout/stdin"""

    def info(self, text):
        print( 'INFO:  '+str(text) )

    def debug(self, text):
        print( 'DEBUG: '+str(text) )

    def warn(self, text):
        print( 'WARN:  '+str(text) )

    def error(self, text):
        print( 'ERROR: '+str(text) )

    def input(self, prompt):
        return input("INPUT: "+prompt)

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

    MIN_VOLTAGE                     = 0
    MAX_VOLTAGE                     = 32.0
    MAX_OVER_VOLTAGE                = 33.0  #This is the max value that can be set on the PSU
    MAX_CURRENT                     = 10.0  #10A max, some models have a 5A max current.
    MAX_OVER_CURRENT                = 10.5  #This is the max value that can be set on the PSU
    MAX_OVER_POWER                  = 310.0 #This is the max value that can be set on the PSU
    #RW REG
    OUTPUT_STATE_REG_ADDR           = 0x0001
    #R REGS
    PROTECTION_STATE_REG_ADDR       = 0x0002
    MODEL_ID_REG_ADDR               = 0x0004
    OUTPUT_VOLTAGE_REG_ADDR         = 0x0010
    OUTPUT_CURRENT_REG_ADDR         = 0x0011
    OUTPUT_PWR_HI_REG_ADDR          = 0x0012 #Top 16 bits of output power reg
    OUTPUT_PWR_LO_REG_ADDR          = 0x0013 #Bottom 16 bits of output power reg
    #R/WR REGS
    VOLTAGE_TARGET_REG_ADDR     = 0x0030
    CURRENT_LIMIT_REG_ADDR      = 0x0031
    OVER_VOLTAGE_PROT_REG_ADDR  = 0x0020
    OVER_CURRENT_PROT_REG_ADDR  = 0x0021
    OVER_PWR_PROT_HI_REG_ADDR   = 0x0022    #Top 16 bits of over power protection
    OVER_PWR_PROT_LOW_REG_ADDR  = 0x0023    #Bottom 16 bits of over power protection
    BUZZER_REG_ADDR             = 0x8804    # 1 = enable (beep on key press), 0 = disable

    def __init__(self, port, unit=1, debug=False):
        """@brief Constructor
           @param uio A UIO instance handling user input and output (E.G stdin/stdout or a GUI)
           @param options An instance of the OptionParser command line options.
           @param unit The unit number on the modbus"""
        self._port = port
        self._unit = unit
        #Modbus client connection
        self._client = None

        if debug:
            logging.basicConfig()
            log = logging.getLogger()
            log.setLevel(logging.DEBUG)

    def connect(self):
        """@brief connect to the PSU over the serial port."""
        self._client = ModbusClient(method='rtu', port=self._port, baudrate=9600, stopbits=1, bytesize=8, timeout=10)
        self._client.connect()

    def disconnect(self):
        """@brief Disconnect from the PSU if connected."""
        if self._client:
            self._client.close()
            self._client = None

    ### READ REGS ###
    def getOutput(self):
        """@brief Get the state of the PSU output.
           @return 1 if the output is on, else 0."""
        rr = self._client.read_holding_registers(ETMXXXXP.OUTPUT_STATE_REG_ADDR, 1, unit=self._unit)
        return rr.getRegister(0)

    def getProtectionState(self):
        """@brief Get the state of the protections switch.
           @return 1 if protection mode is enabled, else 0."""
        rr = self._client.read_holding_registers(ETMXXXXP.PROTECTION_STATE_REG_ADDR, 1, unit=self._unit)
        return rr.getRegister(0)

    def getModel(self):
        """@brief Get the model ID
           @return The model ID value"""
        rr = self._client.read_holding_registers(ETMXXXXP.MODEL_ID_REG_ADDR, 1, unit=self._unit)
        return rr.getRegister(0)

    def getOutputStats(self):
        """@brief Read the output voltage, current and power of the PSU.
           @return A tuple containing
                   0: voltage
                   1: amps
                   2: watts"""
        rr = self._client.read_holding_registers(ETMXXXXP.OUTPUT_VOLTAGE_REG_ADDR, 4, unit=self._unit)
        voltage = float(rr.getRegister(0))
        if voltage > 0:
            voltage=voltage/100.0
        amps = float(rr.getRegister(1))
        if amps > 0:
            amps=amps/1000.0
        wattsH = rr.getRegister(2)
        wattsL = rr.getRegister(3)
        watts = wattsH<<16|wattsL
        if watts > 0:
            watts=watts/1000.0
        return (voltage, amps, watts)

    def getTargetVolts(self):
        """@brief Read the target output voltage
           @return The output voltage set in volts."""
        rr = self._client.read_holding_registers(ETMXXXXP.VOLTAGE_TARGET_REG_ADDR, 1, unit=self._unit)
        voltage = float(rr.getRegister(0))
        if voltage > 0:
            voltage=voltage/100.0
        return voltage

    def getCurrentLimit(self):
        """@brief Read the current limit in amps
           @return The current limit."""
        rr = self._client.read_holding_registers(ETMXXXXP.CURRENT_LIMIT_REG_ADDR, 1, unit=self._unit)
        amps = float(rr.getRegister(0))
        if amps > 0:
            amps=amps/1000.0
        return amps

    def getProtectionValues(self):
        """@brief Read the over voltage, current and power protection values
           @return A tuple containing
                   0: over voltage protection value
                   1: over current protection value
                   2: over power protection value"""
        rr = self._client.read_holding_registers(ETMXXXXP.OVER_VOLTAGE_PROT_REG_ADDR, 4, unit=self._unit)
        voltage = float(rr.getRegister(0))
        if voltage > 0:
            voltage=voltage/100.0
        amps = float(rr.getRegister(1))
        if amps > 0:
            amps=amps/1000.0
        wattsH = rr.getRegister(2)
        wattsL = rr.getRegister(3)
        watts = float(wattsH<<16|wattsL)
        if watts > 0:
            watts=watts/1000.0
        return (voltage, amps, watts)

    def getBuzzer(self):
        """@brief Get the state of the buzzer
           @return 1 if enabled, 0 if disabled."""
        rr = self._client.read_holding_registers(ETMXXXXP.BUZZER_REG_ADDR, 1, unit=self._unit)
        return rr.getRegister(0)

    ### WRITE REGS ###
    def setOutput(self, on):
        """@brief Set The PSU output on/off.
           @param on If True the PSU output is on."""
        self._client.write_register(ETMXXXXP.OUTPUT_STATE_REG_ADDR , on, unit=self._unit)

    def setVoltage(self, voltage):
        """@brief Set the output voltage.
           @param voltage The voltage in volts (a float value)."""
        if voltage < ETMXXXXP.MIN_VOLTAGE or voltage > ETMXXXXP.MAX_VOLTAGE:
            raise ETMXXXXPError("{} is an invalid voltage (valid range {}V - {}V)".format(voltage, ETMXXXXP.MIN_VOLTAGE, ETMXXXXP.MAX_VOLTAGE))
        self._client.write_register(ETMXXXXP.VOLTAGE_TARGET_REG_ADDR , int(voltage*100.0), unit=self._unit)

    def setCurrentLimit(self, amps):
        """@brief Set the current limit value.
           @param amps The current in amps (a float value)."""
        if amps < 0.0 or amps > ETMXXXXP.MAX_CURRENT:
            raise ETMXXXXPError("{} is an invalid current value (valid range 0A - {}A)".format(amps, ETMXXXXP.MAX_CURRENT))
        self._client.write_register(ETMXXXXP.CURRENT_LIMIT_REG_ADDR , int(amps*1000.0), unit=self._unit)

    def setOverVoltageP(self, voltage):
        """@brief Set the over voltage protection value.
           @param voltage The voltage in volts (a float value)."""
        if voltage < ETMXXXXP.MIN_VOLTAGE or voltage > ETMXXXXP.MAX_OVER_VOLTAGE:
            raise ETMXXXXPError("{} is an invalid voltage (valid range {}V - {}V)".format(voltage, ETMXXXXP.MIN_VOLTAGE, ETMXXXXP.MAX_VMAX_OVER_VOLTAGEOLTAGE))
        self._client.write_register(ETMXXXXP.OVER_VOLTAGE_PROT_REG_ADDR , int(voltage*100.0), unit=self._unit)

    def setOverCurrentP(self, amps):
        """@brief Set the over current protection value.
           @param amps The current in amps (a float value)."""
        if amps < 0.0 or amps > ETMXXXXP.MAX_OVER_CURRENT:
            raise ETMXXXXPError("{} is an invalid voltage (valid range 0V - {}V)".format(amps, ETMXXXXP.MAX_OVER_CURRENT))
        self._client.write_register(ETMXXXXP.OVER_CURRENT_PROT_REG_ADDR , int(amps*1000.0), unit=self._unit)

    def setOverPowerP(self, watts):
        """@brief Set the over power protection value.
           @param watts The power in watts (a float value)."""
        if watts < 0.0 or watts > ETMXXXXP.MAX_OVER_POWER:
            raise ETMXXXXPError("{} is an invalid power (valid range 0W - {}W)".format(watts, ETMXXXXP.MAX_OVER_POWER))
        wattValue = int((watts*1000))
        wattsL = wattValue&0x0000ffff
        wattsH = (wattValue&0xffff0000)>>16
        self._client.write_register(ETMXXXXP.OVER_PWR_PROT_HI_REG_ADDR , wattsH, unit=self._unit)
        self._client.write_register(ETMXXXXP.OVER_PWR_PROT_LOW_REG_ADDR , wattsL, unit=self._unit)

    def setBuzzer(self, on):
        """@brief Set the buzzer on/off.
           @param on If True the buzzer is set on, 0 = off."""
        self._client.write_register(ETMXXXXP.BUZZER_REG_ADDR , on, unit=self._unit)

class PSU(object):
    """Repsonsible for providing a command line interface to the ETommens eTM-xxxxP Series PSU.
       Several Mfg's OEM this supply, Hanmatek HM305P, Rockseed RS305P, Hanmatek HM310P,
       RockSeed RS310P and Rockseed RS605P."""

    DEFAULT_SERIAL_PORT = "/dev/ttyUSB0"

    def __init__(self, uio, options):
        """@brief Constructor
           @param uio A UIO instance handling user input and output (E.G stdin/stdout or a GUI)
           @param options An instance of the OptionParser command line options.
           """
        self._uio = uio
        self._options = options
        #the modbus PSU interface
        self._psuIF = None
        self._init()

    def _checkArgs(self):
        """@brief Check the command line arguments."""
        if self._options.on and self._options.off:
            raise ETMXXXXPError("You cannot use --on and --off arguments together.")

    def _init(self):
        """@brief Init the connection to the PSU"""
        self._checkArgs()

        if self._options.debug:
            logging.basicConfig()
            log = logging.getLogger()
            log.setLevel(logging.DEBUG)

        self._psuIF = ETMXXXXP(self._options.p)
        self._psuIF.connect()

    def _info(self, msg):
        """@brief Display an info level message.
           @param msg The message to be displayed."""
        if self._uio:
            self._uio.info(msg)

    def _getOnOff(self, value):
        """@brief Get the vlaue as either on or off.
           @param value The value to check.
           @return ON if the valie is 1, else OFF is returned"""
        valueStr="OFF"
        if value == 1:
            valueStr="ON"
        return valueStr

    def _showStatus(self):
        """@brief Show the PSU voltage, current and power output status"""
        outputOn = self._psuIF.getOutput()
        volts, amps, watts = self._psuIF.getOutputStats()
        targetVolts = self._psuIF.getTargetVolts()
        self._info("Output:                 {}".format(self._getOnOff(outputOn)))
        self._info("Voltage (volts):        {:.2f}".format(targetVolts))
        self._info("Output voltage (volts): {:.2f}".format(volts))
        self._info("Current (amps):         {:.3f}".format(amps))
        self._info("Watts (watts):          {:.3f}".format(watts))

    def _showVerboseStatus(self):
        """@brief Show the verbose PSU stats."""
        outputOn = self._psuIF.getOutput()
        protection = self._psuIF.getProtectionState()
        model = self._psuIF.getModel()
        targetVolts = self._psuIF.getTargetVolts()
        volts, amps, watts = self._psuIF.getOutputStats()
        currentLimit = self._psuIF.getCurrentLimit()
        oVolts, oAmps, oWatts = self._psuIF.getProtectionValues()
        buzzerOn = self._psuIF.getBuzzer()
        self._info("Output:                 {}".format(self._getOnOff(outputOn)))
        self._info("Voltage (volts):        {:.2f}".format(targetVolts))
        self._info("Output voltage (volts): {:.2f}".format(volts))
        self._info("Current (amps):         {:.3f}".format(amps))
        self._info("Watts (watts):          {:.3f}".format(watts))
        self._info("Current limit (amps):   {:.3f}".format(currentLimit))
        self._info("Over voltage (volts):   {:.3f}".format(oVolts))
        self._info("Over current (amps):    {:.3f}".format(oAmps))
        self._info("Over power (watts):     {:.3f}".format(oWatts))
        self._info("Buzzer:                 {}".format(self._getOnOff(buzzerOn)))

    def process(self):
        """@brief Process the command line arguments"""
        try:
            if self._options.v >= 0:
                self._psuIF.setVoltage(self._options.v)
                self._info("Set output to {:.2f} Volts".format(self._options.v))

            if self._options.a >= 0:
                self._psuIF.setCurrentLimit(self._options.a)
                self._info("Set current limit to {:.3f} Amps".format(self._options.a))

            if self._options.ov >= 0:
                self._psuIF.setOverVoltageP(self._options.ov)
                self._info("Set output over voltage value to {:.2f} volts".format(self._options.ov))

            if self._options.oa >= 0:
                self._psuIF.setOverCurrentP(self._options.oa)
                self._info("Set output over current value to {:.2f} amps".format(self._options.oa))

            if self._options.op >= 0:
                self._psuIF.setOverPowerP(self._options.op)
                self._info("Set output over power value to {:.2f} watts".format(self._options.op))

            if self._options.on:
                self._psuIF.setOutput(True)
                self._info("Set output ON")

            if self._options.off:
                self._psuIF.setOutput(False)
                self._info("Set output OFF")

            if self._options.bon:
                self._psuIF.setBuzzer(True)
                self._info("Set buzzer ON")

            if self._options.boff:
                self._psuIF.setBuzzer(False)
                self._info("Set buzzer OFF")

            if self._options.s:
                self._showStatus()

            if self._options.vs:
                self._showVerboseStatus()

        finally:
            if self._psuIF:
                self._psuIF.disconnect()

def main():
    """@brief Program entry point"""
    uio = UIO()

    opts=OptionParser(usage='Provide a control interface to the ROCKSEED RS310P/RS305P Bench PSU.')
    opts.add_option("--debug",      help="Enable debugging.", action="store_true", default=False)
    opts.add_option("-p",           help="Serial port (default={}).".format(PSU.DEFAULT_SERIAL_PORT), default=PSU.DEFAULT_SERIAL_PORT)
    opts.add_option("-v",           help="The required output voltage.", type="float", default=-1)
    opts.add_option("-a",           help="The current limit value in amps.", type="float", default=-1)
    opts.add_option("-s",           help="The PSU status showing output state, voltage, current and power out.", action="store_true", default=False)
    opts.add_option("--vs",         help="The verbose PSU status.", action="store_true", default=False)
    opts.add_option("--ov",         help="The required over voltage protection value in volts", type="float", default=-1)
    opts.add_option("--oa",         help="The required over current protection value in amps.", type="float", default=-1)
    opts.add_option("--op",         help="The required over power protection value in watts.", type="float", default=-1)
    opts.add_option("--on",         help="Turn the PSU output on.", action="store_true", default=False)
    opts.add_option("--off",        help="Turn the PSU output off.", action="store_true", default=False)
    opts.add_option("--bon",        help="Set the buzzer on.", action="store_true", default=False)
    opts.add_option("--boff",       help="Set the buzzer off.", action="store_true", default=False)

    try:
        (options, args) = opts.parse_args()

        psu = PSU(uio, options)
        psu.process()

    #If the program throws a system exit exception
    except SystemExit:
      pass
    #Don't print error information if CTRL C pressed
    except KeyboardInterrupt:
      pass
    except Exception as ex:
     if options.debug:
       raise

     else:
       uio.error( str(ex) )

if __name__== '__main__':
    main()
