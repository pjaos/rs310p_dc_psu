#!/usr/bin/env python3

import  sys
import  os
import  threading
import  asyncio
import  queue
import  tempfile

from bokeh.server.server import Server
from bokeh.application import Application
from bokeh.application.handlers.function import FunctionHandler
from bokeh.plotting import figure, ColumnDataSource
from bokeh.models import Range1d
from bokeh.layouts import gridplot
from bokeh.themes import built_in_themes

from view import PSUGUI
from controller import ETMXXXXPError, ETMXXXXP

from    time import sleep
from    optparse import OptionParser
import  logging
from    datetime import datetime



def appendCreateFile(uio, aFile, quiet=False):
    """@brief USer interaction to append or create a file.
       @param uio A UIO instance.
       @param quiet If True do not show uio messages (apart from overwrite prompt. 
       @param aFile The file to append or delete."""
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

class Reading(object):
    """@brief Resonsible for holding a reading value."""
    def __init__(self, volts, amps, watts, timeStamp=None):
        """@brief Constructor
           @param volts The Volts value to be plotted
           @param amps The Amps value to be plotted
           @param watts The Watts value to be plotted
           @param timeStamp The x Value. If None then a timestamp is created."""
        if timeStamp:
            self.time = timeStamp
        else:
            self.time = datetime.now()
        self.volts = volts
        self.amps  = amps
        self.watts = watts
    
class Plotter(object):
    """@brief Responsible for plotting the DMM values."""

    def __init__(self, yRangeLimits, bokehPort=5001, plotTitle="RS310P"):
        """@brief Constructor.
           @param yRangeLimits Limits of the Y axis. By default auto range.
           @param bokehPort The TCP IP port for the bokeh server.
           @param plotTitle The title text for the plot area."""
        self._yRangeLimits=yRangeLimits
        self._bokehPort=bokehPort
        self._plotTitle=plotTitle
        self._voltsSource = ColumnDataSource({'x': [], 'y': []})
        self._ampsSource  = ColumnDataSource({'x': [], 'y': []})
        self._wattsSource = ColumnDataSource({'x': [], 'y': []})
        self._evtLoop = None
        self._queue = queue.Queue()
        
    def runBokehServer(self):
        """@brief Run the bokeh server. This is a blocking method."""
        apps = {'/': Application(FunctionHandler(self._createPlot))}
        #As this gets run in a thread we need to start an event loop
        evtLoop = asyncio.new_event_loop()
        asyncio.set_event_loop(evtLoop)
        server = Server(apps, port=self._bokehPort)
        server.start()
        #Show the server in a web browser window
        server.io_loop.add_callback(server.show, "/")
        server.io_loop.start()
        
    def _createPlot(self, doc, ):
        """@brief create a plot figure.
           @param doc The document to add the plot to."""
        if self._yRangeLimits and len(self._yRangeLimits) == 2:
            yrange = Range1d(self._yRangeLimits[0],self._yRangeLimits[1])
        else:
            yrange = None
        fig = figure(title=self._plotTitle, 
                     toolbar_location='above', 
                     x_axis_type="datetime",
                     x_axis_location="below",
                     y_range=yrange)
        fig.line(source=self._voltsSource, line_color = "blue", legend_label = "Volts")
        fig.line(source=self._ampsSource, line_color = "green", legend_label = "Amps")
        fig.line(source=self._wattsSource, line_color = "red", legend_label = "Watts")
        grid = gridplot(children = [[fig]], sizing_mode = 'stretch_both')
        doc.title = self._plotTitle
        doc.add_root(grid)
        doc.add_periodic_callback(self._update, 100)
              
    def _update(self):
        """@brief called periodically to update the plot trace."""
        while not self._queue.empty():
            reading = self._queue.get()                       
            newVolts = {'x': [reading.time],
                        'y': [reading.volts]}
            self._voltsSource.stream(newVolts)
            
            newAmps = {'x': [reading.time],
                       'y': [reading.amps]}
            self._ampsSource.stream(newAmps)
            
            newWatts = {'x': [reading.time],
                        'y': [reading.watts]}
            self._wattsSource.stream(newWatts)
            
    def addReading(self, reading):
        """@brief Add a value to be plotted
           @param reading The reading containing the values to be plotted."""
        self._queue.put(reading)
        
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
    
    def getBoolInput(self, prompt, allowQuit=True):
        """@brief Get boolean repsonse from user (y or n response).
           @param allowQuit If True and the user enters q then the program will exit.
           @return True or False"""
        while True:
            response = self.input(prompt=prompt)
            if response.lower() == 'y':
                return True
            elif response.lower() == 'n':
                return False
            elif allowQuit and response.lower() == 'q':
                sys.exit(0)


class PSU(object):
    """Repsonsible for providing a command line interface to the ETommens eTM-xxxxP Series PSU.
       Several Mfg's OEM this supply, Hanmatek HM305P, Rockseed RS305P, Hanmatek HM310P,
       RockSeed RS310P and Rockseed RS605P."""

    DEFAULT_SERIAL_PORT = "/dev/ttyUSB0"
    LOG_FILENAME        = "psu.log"
    DEFAULT_LOG_FILE    = os.path.join( tempfile.gettempdir(), LOG_FILENAME)
    
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

    def _recordLog(self, reading):
        """@brief Record data to the log file.
           @param reading The reading from the PSU to be saved."""
        timeStr = reading.time.strftime("%d/%m/%Y-%H:%M:%S.%f")
        self._uio.info("{}: Volts={} Amps={} Watts={}".format(timeStr, reading.volts, reading.amps, reading.watts))
        fd = open(self._options.log, 'a')
        fd.write("{}: {} {} {}\n".format(timeStr, reading.volts, reading.amps, reading.watts))
        fd.close()
    
    def _getYRange(self):
        """@brief Get the Y range.
           @return a tuple with min,max or None if not defined (autorange)"""
        yRange=None
        if self._options.range:
            elems = self._options.range.split(",")
            if len(elems) == 2:
                try:
                    min=int(elems[0])
                    max=int(elems[1])
                except ValueError:
                    pass
                yRange = (min, max)
        return yRange
    
    def _plotStats(self):
        """@brief Plot the stats until CRTL C is pressed."""
        appendCreateFile(self._uio, self._options.log)
        self._plotter = Plotter( self._getYRange() )
        bt = threading.Thread(target=self._plotter.runBokehServer)
        bt.setDaemon(True)
        bt.start()
        self._uio.info("Log file: {}".format(self._options.log))
        try:
            while True:
                #Read the data
                volts, amps, watts = self._psuIF.getOutputStats()
                self
                reading = Reading(volts, amps, watts)       
                self._recordLog(reading)
                self._plotter.addReading(reading)
                sleep(self._options.poll)
        finally:
            self._uio.info("Log file: {}".format(self._options.log))

    def _loadLog(self):
        """@brief Load from log file
           @return A list of elements
                   0: xValueList
                   1: yValueList
                   2: label"""
        readingList=[]
        fd = open(self._options.log,'r')
        lines = fd.readlines()
        fd.close()
        for line in lines:
            elems = line.split()
            if len(elems) == 4:
                tStr = elems[0]
                if tStr.endswith(":"):
                    tStr=tStr[:-1]
                try:
                    plotTime = datetime.strptime(tStr, "%d/%m/%Y-%H:%M:%S.%f")
                    volts = float(elems[1])
                    amps  = float(elems[2])
                    watts = float(elems[3])
                    reading = Reading(volts, amps, watts)
                    readingList.append(reading)
                except ValueError:
                    pass

        return readingList
    
    def _plotLog(self):
        """@brief Plot data from the log file."""
        if not os.path.isfile(self._options.log):
            raise Exception("{} file not found".format(self._options.log))
        readingList = self._loadLog()
        self._plotter = Plotter(self._getYRange())
        bt = threading.Thread(target=self._plotter.runBokehServer)
        bt.setDaemon(True)
        bt.start()
        for reading in readingList:
            self._plotter.addReading(reading)
        bt.join()
        
    def _runGUI(self):
        """@brief Start the GUI."""
        plotPaneWidth = 800
        self._gui = PSUGUI("DOC TITLE")
        self._gui.runBokehServer()
        
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

            if self._options.plot:
                self._plotStats()
                
            if self._options.plotl:
                self._plotLog()
                
            if self._options.g:
                self._runGUI()

        finally:
            if self._psuIF:
                self._psuIF.disconnect()

def main():
    """@brief Program entry point"""
    uio = UIO()

    opts=OptionParser(usage='Provide a control interface to the ROCKSEED RS310P/RS305P Bench PSU.')
    opts.add_option("--debug",      help="Enable debugging.", action="store_true", default=False)
    opts.add_option("-g",           help="Run the GUI.", action="store_true", default=False)
    opts.add_option("-p",           help="Serial port (default={}). Enter in 'host:port' format for an Esp-Link bridge.".format(PSU.DEFAULT_SERIAL_PORT), default=PSU.DEFAULT_SERIAL_PORT)
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

    opts.add_option("--plot",       help="Plot the PSU status.", action="store_true", default=False)
    opts.add_option("--poll",       help="The poll period in seconds (default=1).", type="float", default=1.0)
    opts.add_option("--log",        help="Log file. This is used when plotting (default={}).".format(PSU.DEFAULT_LOG_FILE), default=PSU.DEFAULT_LOG_FILE)
    opts.add_option("--plotl",      help="Plot the data in the log file.", action="store_true", default=False)
    opts.add_option("--range",      help="The Y axis plot range. By default the Y axis will auto range. If defined then a comma separated list of min,max values is required. (E.G 0,10)", default=None)

    try:
        (options, args) = opts.parse_args()

        if ':' in options.p:
            host, port = options.p.split(':')
            options.p = (host, int(port))

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
