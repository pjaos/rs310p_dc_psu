#!/usr/bin/env python3

from    time import sleep
import  sys
import  queue
import  threading
from    functools import partial

from    datetime import datetime
import  itertools
from    time import time
import  glob
from    random import randint
from    datetime import date, datetime

from    p3lib.pconfig import ConfigManager

from controller import ETMXXXXPError, ETMXXXXP

from bokeh.server.server import Server
from bokeh.application import Application
from bokeh.application.handlers.function import FunctionHandler
from bokeh.plotting import figure, ColumnDataSource
from bokeh.models import Range1d, AutocompleteInput
from bokeh.palettes import Category20_20 as palette

from bokeh.plotting import save, output_file
from bokeh.layouts import gridplot, column, row
from bokeh.models.widgets import CheckboxGroup
from bokeh.models.widgets.buttons import Button
from bokeh.models.widgets import TextInput
from bokeh.models import TextAreaInput
from bokeh.models import Panel, Tabs
from bokeh.models.widgets import Select
from bokeh.models import Spinner
from bokeh.models import Toggle
from bokeh.colors import named
from bokeh.models import DataTable, DateFormatter, TableColumn
from bokeh.models import CustomJS
from bokeh import events
from bokeh.models.layouts import Row
from bokeh.themes import built_in_themes
from bokeh.io.doc import curdoc, set_curdoc

from p3lib.bokeh_gui import TabbedGUI, StatusBarWrapper, ReadOnlyTableWrapper, ShutdownButtonWrapper, UpdateEvent
from pickle import NONE


#PJA TODO
# - Update README.md

class PSUGUIUpdateEvent(UpdateEvent):
    """@brief Responsible for holding the state of an event sent from a non GUI thread 
              to the GUI thread context in order to update the GUI in some way."""
    
    # UPDATE_STATUS_TEXT = 1 # Implemented in parent class
    CONNECTING_TO_PSU  = 2
    CONNECTED_TO_PSU   = 3
    PSU_CONNECT_FAILED = 4
    TURNING_PSU_OFF    = 5
    PSU_OFF            = 6
    SET_PSU_STATE      = 7
    SHUTDOWN_SERVER    = 8
        
    def __init__(self, id, argList=None):
        """@brief Constructor
           @param id An integer event ID
           @param argList A list of arguments associated with the event"""
        super().__init__(id, argList)
    
class PSUGUI(TabbedGUI):
    """@brief Responsible for plotting data on tab 0 with no other tabs."""
    
    CFG_FILENAME = ".RS310P_GUI.cfg"
    AMPS = "amps"
    VOLTS = "volts"
    PLOT_SECONDS = "plotSeconds"
    CFG_DICT = {
        VOLTS: 5,
        AMPS: 1,
        PLOT_SECONDS: 300
    }
    def __init__(self, docTitle, bokehPort=12000):
        """@Constructor"""
        super().__init__(docTitle, bokehPort=bokehPort)
        self._figTable=[[]]
        self._grid = None
        self._textBuffer = ""
        self._psu = None
        self._on = False

    def info(self, msg):
        """@brief Display an info level message."""
        self.statusBarWrapper.setStatus("INFO:  "+msg)
        
    def error(self, msg):
        """@brief Display an error level message."""
        self.statusBarWrapper.setStatus("ERROR: "+msg)

    def debug(self, msg):
        """@brief Display an error level message."""
        pass
                
    def addRow(self):
        """@brief Add an empty row to the figures."""
        self._figTable.append([])

    def addToRow(self, fig):
        """@brief Add a figure to the end of the current row of figues.
           @param fig The figure to add."""
        self._figTable[-1].append(fig)

    def createPlot(self, doc, ):
        """@brief create a plot figure.
           @param doc The document to add the plot to."""
        self._doc = doc
        self._doc.title = "RS310P PSU Controller"
        
        self.statusBarWrapper = StatusBarWrapper()
        self._pconfig = ConfigManager(self, PSUGUI.CFG_FILENAME, PSUGUI.CFG_DICT)
        self._pconfig.load()
        
        plotPanel = self._getPlotPanel()
       
        self._tabList.append( Panel(child=plotPanel,  title="DC Power Supply Control") )
        self._doc.add_root( Tabs(tabs=self._tabList) )
        self._doc.add_periodic_callback(self._viewUpdate, 500)
                
    def _viewUpdate(self):
        if self._on:
            volts, amps, watts = self._psu.getOutputStats()
            self._opTableWrapper.setRows( [[volts, amps, watts]] )
            self._updatePlot(volts, amps, watts)
            
    def _updatePlot(self, volts, amps, watts):
        """@brief called periodically to update the plot trace."""
        plotPoints = int(self.plotHistorySpinner.value*2)
        now = datetime.now()     
        newVolts = {'x': [now],
                    'y': [volts]}
        self._voltsSource.stream(newVolts, rollover=plotPoints)
        
        newAmps = {'x': [now],
                   'y': [amps]}
        self._ampsSource.stream(newAmps, rollover=plotPoints)
        
        newWatts = {'x': [now],
                    'y': [watts]}
        self._wattsSource.stream(newWatts, rollover=plotPoints)
        
    def _getPlotPanel(self):
        """@brief Add tab that shows plot data updates."""

        self._figTable.append([])
        self._voltsSource = ColumnDataSource({'x': [], 'y': []})
        self._ampsSource  = ColumnDataSource({'x': [], 'y': []})
        self._wattsSource = ColumnDataSource({'x': [], 'y': []})
        fig = figure(toolbar_location='above', x_axis_type="datetime", x_axis_location="below")
        fig.line(source=self._voltsSource, line_color = "blue", legend_label = "Volts")
        fig.line(source=self._ampsSource, line_color = "green", legend_label = "Amps")
        fig.line(source=self._wattsSource, line_color = "red", legend_label = "Watts")
        fig.legend.location = 'top_left'
        self._figTable[-1].append(fig)
        self._grid = gridplot(children = self._figTable, sizing_mode = 'scale_both',  toolbar_location='right')

        self.selectSerialPort = AutocompleteInput(title="Serial Port:")
        self.selectSerialPort.completions = glob.glob('/dev/ttyU*')
        
        self.outputVoltageSpinner = Spinner(title="Output Voltage (Volts)", low=0, high=40, step=0.5, value=float(self._pconfig.getAttr(PSUGUI.VOLTS)))
        self.currentLimitSpinner = Spinner(title="Currnet Limit (Amps)", low=0, high=10, step=0.25, value=float(self._pconfig.getAttr(PSUGUI.AMPS)))
        self.plotHistorySpinner = Spinner(title="Plot History (Seconds)", low=1, high=10000, step=1, value=float(self._pconfig.getAttr(PSUGUI.PLOT_SECONDS)))
        
        self._setButton = Button(label="Set")
        self._setButton.on_click(self._setHandler)
        self._setButton.disabled=True
                
        self._onButton = Button(label="On")
        self._onButton.on_click(self._psuOnHandler)
        
        shutdownButtonWrapper = ShutdownButtonWrapper(self._quit)
        controlPanel = column([self.selectSerialPort, self._onButton, self.outputVoltageSpinner, self.currentLimitSpinner, self._setButton, self.plotHistorySpinner, shutdownButtonWrapper.getWidget()])
        
        self._opTableWrapper = ReadOnlyTableWrapper( ("volts","amps","watts"), heightPolicy="fixed", height=65, showLastRows=0 )
                
        plotPanel = column([self._grid, self._opTableWrapper.getWidget()])
        panel2 = row([controlPanel, plotPanel])
        plotPanel = column([panel2, self.statusBarWrapper.getWidget()])
        return plotPanel

    def _quit(self):
        if self._on:
            self._psuOff()
        self._run(self._delayedShutdown)
        self._doc.clear()
        
    def _delayedShutdown(self):
        """@brief Allow time for browser page to clear before shutdown."""
        volts = self.outputVoltageSpinner.value
        amps = self.currentLimitSpinner.value
        self._pconfig.addAttr(PSUGUI.VOLTS, volts)
        self._pconfig.addAttr(PSUGUI.AMPS, amps)
        self._pconfig.addAttr(PSUGUI.PLOT_SECONDS, self.plotHistorySpinner.value) 
        self._pconfig.store()
        sleep(0.5)
        self._sendUpdateEvent( PSUGUIUpdateEvent(PSUGUIUpdateEvent.SHUTDOWN_SERVER) ) 
        
    def _psuOnHandler(self):
        """@brief event handler."""
        #Stop the user from clicking the button again until this click has been processed.
        self._onButton.disabled = True
        #Turn the PSUon/off method outside GUI thread
        self._run(self._powerOnOff)
        
    def _setHandler(self):
        """@brief event handler."""
        #Turn the PSUon/off method outside GUI thread
        self._run(self._setPSU)
        
    def _rxUpdateEvent(self, updateEvent):
        """@brief Receive an event into the GUI context to update the GUI.
           @param updateEvent An PSUGUIUpdateEvent instance."""
        if updateEvent.id == PSUGUIUpdateEvent.UPDATE_STATUS_TEXT:
            self.statusBarWrapper.setStatus(updateEvent.argList[0])

        elif updateEvent.id == PSUGUIUpdateEvent.CONNECTING_TO_PSU:
            self._onButton.button_type = "success"
            self._onButton.disabled = True
            self.statusBarWrapper.setStatus(updateEvent.argList[0])
            
        elif updateEvent.id == PSUGUIUpdateEvent.PSU_CONNECT_FAILED:
            self._onButton.button_type = "default"
            self._onButton.disabled = False
            self._setButton.disabled = True
            self._setButton.button_type = "default"
            self.statusBarWrapper.setStatus(updateEvent.argList[0])        
            
        elif updateEvent.id == PSUGUIUpdateEvent.CONNECTED_TO_PSU:            
            self._setButton.button_type = "success"
            self._setButton.disabled = False
            self._onButton.button_type = "success"
            self._onButton.disabled = False
            self._onButton.label = "Off"
            self.statusBarWrapper.setStatus("PSU ON")
            self._pconfig.addAttr(PSUGUI.VOLTS, self.outputVoltageSpinner.value)
            self._pconfig.addAttr(PSUGUI.AMPS, self.currentLimitSpinner.value)
            self._pconfig.addAttr(PSUGUI.PLOT_SECONDS, self.plotHistorySpinner.value)         
            self._pconfig.store()
            
        elif updateEvent.id == PSUGUIUpdateEvent.TURNING_PSU_OFF:
            self._onButton.button_type = "default"
            self._setButton.disabled = True
            self._onButton.disabled = True
            self._setButton.button_type = "default"
            self.statusBarWrapper.setStatus("Turning PSU OFF")
            
        elif updateEvent.id == PSUGUIUpdateEvent.PSU_OFF:
            self._onButton.button_type = "default"
            self._onButton.disabled = False
            self._onButton.label = "On"
            self.statusBarWrapper.setStatus("PSU OFF")
            
        elif updateEvent.id == PSUGUIUpdateEvent.SET_PSU_STATE:    
            volts = self.outputVoltageSpinner.value
            amps = self.currentLimitSpinner.value
            self._pconfig.addAttr(PSUGUI.VOLTS, volts)
            self._pconfig.addAttr(PSUGUI.AMPS, amps)
            self._pconfig.addAttr(PSUGUI.PLOT_SECONDS, self.plotHistorySpinner.value) 
            self._pconfig.store()
            self.statusBarWrapper.setStatus("Set {:.2f} volts with a {:.3f} amp current limit".format(volts, amps))
            
        elif updateEvent.id == PSUGUIUpdateEvent.SHUTDOWN_SERVER:  
            self.stopServer()
            print("PJA: SERVER SHUTDOWN.")
                        
                        
                        
                        
                        
                        
    def _powerOnOff(self):
        """@brief Called to turn the PSU on/off""" 
        if self._on:
            self._psuOff()
        else:
            self._psuOn()
            
    def _setPSU(self):
        """@brief Called when the PSU is on to set the state of the PSU."""
        volts = self.outputVoltageSpinner.value
        amps = self.currentLimitSpinner.value
        self._psu.setVoltage(volts)
        self._psu.setCurrentLimit(amps)
        self._sendUpdateEvent( UpdateEvent(PSUGUIUpdateEvent.SET_PSU_STATE) ) 
        
    def getSelectedSerialPort(self):
        """@brief Get the selected serial port.
           @return the selected Serial port or None if not selected."""
        if ':' in self.selectSerialPort.value_input:
            # hostname & port
            return self.selectSerialPort.value_input.split(':')
        else:
            return self.selectSerialPort.value_input

    def _psuOff(self):
        """@brief Turn the PSU off."""
        self._sendUpdateEvent( UpdateEvent(PSUGUIUpdateEvent.TURNING_PSU_OFF) )
        self._on = False
        self._psu.setOutput(False)
        self._psu.disconnect()
        self._psu = None
        self._sendUpdateEvent( UpdateEvent(PSUGUIUpdateEvent.PSU_OFF) )
                            
    def _psuOn(self):
        """@brief Connect to the PDU.
           @return True if successfully connected to a PSU."""
        serialPort = None
        try:
            serialPort = self.getSelectedSerialPort()
            if serialPort:            
                self._sendUpdateEvent( UpdateEvent(PSUGUIUpdateEvent.CONNECTING_TO_PSU, ("Connecting to {}".format(serialPort),)) ) 
                self._psu = ETMXXXXP(serialPort)
                self._psu.connect()    
                self._psu.getOutput()  
                #Ensure the voltage comes up from a low voltage rather than down 
                #from a previously higher voltage
                self._psu.setVoltage(0)
                self._psu.setVoltage(self.outputVoltageSpinner.value)
                self._psu.setCurrentLimit(self.currentLimitSpinner.value)
                self._psu.setOutput(True)
                self._on = True
                self._sendUpdateEvent( UpdateEvent(PSUGUIUpdateEvent.CONNECTED_TO_PSU) )
            else:
                self._sendUpdateEvent( UpdateEvent(PSUGUIUpdateEvent.PSU_CONNECT_FAILED, ("Failed to to connect to PSU as no serial port was selected.",) ) )        
        except Exception as ex:
            print(ex)
            if self._psu:
                self._psu.disconnect()
                self._psu = None
            if serialPort:
                self._sendUpdateEvent( UpdateEvent(PSUGUIUpdateEvent.PSU_CONNECT_FAILED, ("Failed to connect to PSU on {}".format(serialPort),) ) )        
            else:
                self._sendUpdateEvent( UpdateEvent(PSUGUIUpdateEvent.PSU_CONNECT_FAILED, ("Failed to connect to PSU on {}".format(serialPort),) ) ) 
                self.setStatus("Failed to connect to PSU.")
            
