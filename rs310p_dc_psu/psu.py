#!/usr/bin/env python3

import os
import tempfile
import argparse

from p3lib.uio import UIO
from p3lib.helper import logTraceBack

from rs310p_dc_psu.view import PSUGUI
from rs310p_dc_psu.controller import ETMXXXXPError, ETMXXXXP

import logging

from time import sleep, time
from datetime import datetime


class Reading(object):
    """@brief Resonsible for holding a reading value."""
    def __init__(self, timeStamp, volts, amps, watts):
        """@brief Constructor
           @param timeStamp A datetime instance.
           @param volts The Volts value to be plotted
           @param amps The Amps value to be plotted
           @param watts The Watts value to be plotted
           @param timeStamp The x Value. If None then a timestamp is created."""
        if timeStamp:
            self.time = timeStamp
        else:
            self.time = datetime.now()
        self.volts = volts
        self.amps = amps
        self.watts = watts


class PSU(object):
    """Repsonsible for providing a command line interface to the ETommens eTM-xxxxP Series PSU.
       Several Mfg's OEM this supply, Hanmatek HM305P, Rockseed RS305P, Hanmatek HM310P,
       RockSeed RS310P and Rockseed RS605P."""

    DEFAULT_SERIAL_PORT = "/dev/ttyUSB0"
    LOG_FILENAME = "psu.log"
    DEFAULT_LOG_FILE = os.path.join(tempfile.gettempdir(), LOG_FILENAME)

    def __init__(self, uio, options):
        """@brief Constructor
           @param uio A UIO instance handling user input and output (E.G stdin/stdout or a GUI)
           @param options An instance of the OptionParser command line options.
           """
        self._uio = uio
        self._options = options
        # The modbus PSU interface
        self._psuIF = None

        if options.g:
            self._init(openSerialPort=False)

        else:
            self._init()

    def _checkArgs(self):
        """@brief Check the command line arguments."""
        if self._options.on and self._options.off:
            raise ETMXXXXPError("You cannot use --on and --off arguments together.")

    def _init(self, openSerialPort=True):
        """@brief Init the connection to the PSU.
           @param openSerialPort If True then open the defined serial port."""
        self._checkArgs()

        if self._options.debug:
            logging.basicConfig()
            log = logging.getLogger()
            log.setLevel(logging.DEBUG)

        if openSerialPort:
            if self._options.p is None:
                raise Exception("Serial port not set. Use the -p command line option to set the serial port.")

            self._psuIF = ETMXXXXP(self._options.p)
            if not self._psuIF.connect():
                raise Exception(f"Failed to connect to {self._options.p}")

    def _info(self, msg):
        """@brief Display an info level message.
           @param msg The message to be displayed."""
        if self._uio:
            self._uio.info(msg)

    def _getOnOff(self, value):
        """@brief Get the value as either on or off.
           @param value The value to check.
           @return ON if the valie is 1, else OFF is returned"""
        valueStr = "OFF"
        if value == 1:
            valueStr = "ON"
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
        self._info("Model:                  {}".format(model))
        self._info("Protection state:       {}".format(protection))

    def _recordLog(self, reading):
        """@brief Record data to the log file.
           @param reading The reading from the PSU to be saved."""
        timeStr = reading.time.strftime("%d/%m/%Y-%H:%M:%S.%f")
        self._uio.info("{}: Volts={} Amps={} Watts={}".format(timeStr, reading.volts, reading.amps, reading.watts))
        fd = open(self._options.log, 'a')
        fd.write("{},{},{},{}\n".format(timeStr, reading.volts, reading.amps, reading.watts))
        fd.close()

    def _addLogFileHeader(self):
        """@brief Add a header to the log file indication what each column is."""
        fd = open(self._options.log, 'a')
        fd.write("TIME,VOLTS,AMPS,WATTS\n")
        fd.close()

    def _loadLog(self):
        """@brief Load from log file
           @return A list of elements
                   0: xValueList
                   1: yValueList
                   2: label"""
        readingList = []
        fd = open(self._options.log, 'r')
        lines = fd.readlines()
        fd.close()
        for line in lines:
            elems = line.split(',')
            if len(elems) == 4:
                try:
                    tStr = elems[0]
                    # Ignore header lines
                    if tStr.lower() == 'time':
                        continue
                    if tStr.endswith(":"):
                        tStr = tStr[:-1]
                    plotTime = datetime.strptime(tStr, "%d/%m/%Y-%H:%M:%S.%f")
                    volts = float(elems[1])
                    amps = float(elems[2])
                    watts = float(elems[3])
                    reading = Reading(plotTime, volts, amps, watts)
                    readingList.append(reading)
                except ValueError:
                    pass
        reading_count = len(readingList)
        self._uio.info(f"Loaded {reading_count} readings from the {self._options.log} file.")
        return readingList

    def _appendCreateFile(self, uio, aFile, quiet=False):
        """@brief USer interaction to append or create a file.
        @param uio A UIO instance.
        @param quiet If True do not show uio messages (apart from overwrite prompt.
        @param aFile The file to append or delete.
        """
        createFile = False
        if os.path.isfile(aFile):
            if uio.getBoolInput("Overwrite {} y/n: ".format(aFile)):
                os.remove(aFile)
                if not quiet:
                    uio.info("Deleted {}".format(aFile))
                createFile = True
            else:
                if not quiet:
                    uio.info("Appending to {}".format(aFile))

        else:
            createFile = True

        if createFile:
            fd = open(aFile, 'w')
            fd.close()
            if not quiet:
                uio.info("Created {}".format(aFile))

    def _record_stats(self):
        """@brief Record stats to a log file unitl CRTL C is pressed."""
        self._appendCreateFile(self._uio, self._options.log)
        self._uio.info("Log file: {}".format(self._options.log))
        self._addLogFileHeader()
        try:
            while True:
                start_read_time = time()
                # Read the data
                volts, amps, watts = self._psuIF.getOutputStats()
                reading = Reading(None, volts, amps, watts)
                self._recordLog(reading)
                now = time()
                read_time_time = now-start_read_time
                sleep_time = self._options.poll - read_time_time
                if sleep_time > 0:
                    sleep(sleep_time)

        finally:
            self._uio.info("Log file: {}".format(self._options.log))

    def _plotLog(self):
        """@brief Plot the data in the log."""
        reading_list = self._loadLog()
        psgGui = PSUGUI(self._options.width,
                        address=self._options.address,
                        reload=self._options.reload,
                        debug=self._options.debug)
        psgGui.plot_data(reading_list)

    def _runGUI(self):
        """@brief Start the PSU control GUI."""
        psgGui = PSUGUI(self._options.width,
                        address=self._options.address,
                        reload=self._options.reload,
                        debug=self._options.debug)
        psgGui.start(self._options.p)

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

            elif self._options.vs:
                self._showVerboseStatus()

            elif self._options.poll > 0:
                self._record_stats()

            elif self._options.plotl:
                self._plotLog()

            elif self._options.g:
                self._runGUI()

        finally:
            if self._psuIF:
                self._psuIF.disconnect()


def main():
    """@brief Program entry point"""
    uio = UIO()

    options = None
    try:
        parser = argparse.ArgumentParser(description='Provide a control interface to the ROCKSEED RS310P/RS305P Bench PSU.',
                                         formatter_class=argparse.RawDescriptionHelpFormatter)

        parser.add_argument("-d", "--debug",
                            action='store_true',
                            help="Enable debugging.")
        parser.add_argument("-p",
                            help="The local machine USB serial port connected to the PSU or the 'host:port' format for an Esp-Link bridge.",
                            default=None)
        parser.add_argument("-v",
                            help="The required output voltage.",
                            type=float,
                            default=-1)
        parser.add_argument("-a",
                            help="The current limit value in amps.",
                            type=float,
                            default=-1)
        parser.add_argument("-s",
                            help="The PSU status showing output state, voltage, current and power out.",
                            action="store_true",
                            default=False)
        parser.add_argument("--vs",
                            help="The verbose PSU status.",
                            action="store_true",
                            default=False)
        parser.add_argument("--ov",
                            help="The required over voltage protection value in volts",
                            type=float,
                            default=-1)
        parser.add_argument("--oa",
                            help="The required over current protection value in amps.",
                            type=float,
                            default=-1)
        parser.add_argument("--op",
                            help="The required over power protection value in watts.",
                            type=float,
                            default=-1)
        parser.add_argument("--on",
                            help="Turn the PSU output on.",
                            action="store_true",
                            default=False)
        parser.add_argument("--off",
                            help="Turn the PSU output off.",
                            action="store_true",
                            default=False)
        parser.add_argument("--bon",
                            help="Set the buzzer on.",
                            action="store_true",
                            default=False)
        parser.add_argument("--boff",
                            help="Set the buzzer off.",
                            action="store_true",
                            default=False)
        parser.add_argument("--poll",
                            help="The poll period in seconds (default=1).",
                            type=float,
                            default=0.0)
        parser.add_argument("--log",
                            help="Log file. This is used when plotting (default={}).".format(PSU.DEFAULT_LOG_FILE),
                            default=PSU.DEFAULT_LOG_FILE)

        parser.add_argument("-g",
                            action="store_true",
                            help="Run the GUI.",
                            default=False)
        parser.add_argument("-w",
                            '--width',
                            help="The browser window width. The plot is scaled to fit the preferred window size (default=1100).",
                            type=int,
                            default=1100)

        parser.add_argument("--plot",
                            help="Plot the PSU status.",
                            action="store_true",
                            default=False)
        parser.add_argument("--plotl",
                            help="Plot the data in the log file.",
                            action="store_true",
                            default=False)

        parser.add_argument(
            "--address",
            type=str,
            default='127.0.0.1',
            help="""
            The address to which the GUI server is bound. By default
            127.0.0.1 (localhost) is used which means the GUI
            is only reachable from this machine. You may set this to an
            IP address of an interface on this machine if you wish to make the
            GUI available to other machines that have network connectivity to
            this machine.
            """
        )

        parser.add_argument("-r", "--reload",
                            action='store_true',
                            help="Enable the nicegui reload functionality. Useful during development.")

        options = parser.parse_args()
        uio.enableDebug(options.debug)
        uio.logAll(True)

        if options.p and ':' in options.p:
            host, port = options.p.split(':')
            options.p = (host, int(port))

        psu = PSU(uio, options)
        psu.process()

    # If the program throws a system exit exception
    except SystemExit:
        pass
    # Don't print error information if CTRL C pressed
    except KeyboardInterrupt:
        pass
    except Exception as ex:
        logTraceBack(uio)

        if not options or options.debug:
            raise
        else:
            uio.error(str(ex))


# Note __mp_main__ is used by the nicegui module
if __name__ in {"__main__", "__mp_main__"}:
    main()
