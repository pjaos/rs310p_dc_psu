from nicegui import ui
import plotly.graph_objects as go

import datetime
import threading

from time import sleep
from queue import Queue

import serial.tools.list_ports

from rs310p_dc_psu.controller import ETMXXXXP


class Executioner(object):
    """@brief Responsible for executing methods in a separate thread. Responses are received back from
              the methods in a queue. Messages can be read from this queue by calling the method_response()
              method on instances of this class."""

    INFO_MESSAGE = "INFO"
    ERROR_MESSAGE = "ERROR"
    WARNING_MESSAGE = "WARNING"

    def __init__(self):
        self._from_thread_queue = Queue()

    def _call_method(self, method, args=None):
        """@brief Call the method from a separate thread. This method will not block but responses may
                  take some to to be returned (if at all)."""
        if args:
            threading.Thread(target=method, args=args).start()
        else:
            threading.Thread(target=method).start()

    def _get_response(self):
        """@return Return A response from a method or None if no responses are currently available.
                          If a response is found a dict is returned.
                          The dict key = The type of message.
                          The dict value is the message returned."""
        response = None
        if not self._from_thread_queue.empty():
            response = self._from_thread_queue.get()
        return response

    def _send(self, name, msg):
        """@brief Send a message from an executed method via the self._from_thread_queue."""
        ret_dict = {}
        ret_dict[name] = msg
        self._from_thread_queue.put(ret_dict)


class PSUGUI(Executioner):
    """@brief Responsible providing PSU control via a GUI."""
    COL0_WIDTH_PX = 200
    SERIAL_PORT = "Serial Port"
    COL0_WIDTH = f'width: {COL0_WIDTH_PX}px; height:'
    HALF_COL0_WIDTH = f'width: {COL0_WIDTH_PX/2.15}px;'  # Allow for space between elements

    CONNECTED_MESSAGE = "Connected"
    DISCONNECTED_MESSAGE = "Disconnected"
    ON_MESSAGE = "PSU Turned On"
    OFF_MESSAGE = "PSU Turned Off"

    PSU_STATS = "PSU_STATS"
    PSU_SETTINGS = "PSU_SETTINGS"

    def __init__(self, width, address='127.0.0.1', debug=False, reload=False, server_port=9091):
        """@brief Constructor"""
        super().__init__()
        self._debug = debug
        self._reload = reload

        self._port = server_port
        self._width = width
        self._plot_width = width - PSUGUI.COL0_WIDTH_PX
        self._address = address

        self._time_data = []
        self._voltage_data = []
        self._current_data = []
        self._power_data = []

        self._psuIF = None
        self._psu_access_lock = threading.Lock()
        self._connected = False

    def _get_serial_port_list(self):
        """@return A list of available serial ports."""
        connect_serial_port_list = []
        serial_port_list = serial.tools.list_ports.comports(include_links=False)
        for p in serial_port_list:
            if not p.hwid == 'n/a':
                connect_serial_port_list.append(p.device)
        return connect_serial_port_list

    def _create_plot(self):
        """@brief Create the plot instance."""
        layout = go.Layout(title=None,
                           showlegend=True,
                           width=self._plot_width,
                           height=self._plot_width/1.5,
                           plot_bgcolor="darkslategrey",       # Background for the plot area
                           paper_bgcolor="darkslategrey",      # Background for the entire figure
                           font=dict(color="yellow"),   # Font color for labels and title
                           xaxis=dict(title='Time',
                                      color="yellow",
                                      gridcolor="gray",
                                      zerolinecolor="gray"),
                           yaxis=dict(title='',
                                      color="yellow",
                                      gridcolor="gray",
                                      zerolinecolor="gray"))
        fig = go.Figure(layout=layout)

        voltage_trace = go.Scatter(x=self._time_data, y=self._voltage_data, mode='lines+markers', name='Volts')
        current_trace = go.Scatter(x=self._time_data, y=self._current_data, mode='lines+markers', name='Amps')
        power_trace = go.Scatter(x=self._time_data, y=self._power_data, mode='lines+markers', name='Watts')

        fig.add_trace(voltage_trace)
        fig.add_trace(current_trace)
        fig.add_trace(power_trace)

        return fig

    def _init_gui(self, available_serial_port_list):
        """@brief Setup the GUI.
           @param available_serial_port_list A list of serial port device names on this HW platform at the moment.."""
        with ui.row().classes('w-full h-full'):
            if available_serial_port_list is not None:
                with ui.column():
                    self._selected_serial_port_select = ui.select(available_serial_port_list,
                                                                  label=PSUGUI.SERIAL_PORT,
                                                                  value=available_serial_port_list[0]).style(PSUGUI.COL0_WIDTH)

                    with ui.row():
                        self._connect_button = ui.button("Connect",
                                                         on_click=lambda: self._call_method(self._connect)).style(PSUGUI.HALF_COL0_WIDTH)
                        self._connect_button.set_enabled(True)

                        self._disconnect_button = ui.button("Disconnect",
                                                            on_click=lambda: self._call_method(self._disconnect)).style(PSUGUI.HALF_COL0_WIDTH)
                        self._disconnect_button.set_enabled(False)

                    with ui.row():
                        self._on_button = ui.button("On",
                                                    on_click=lambda: self._call_method(self._on)).style(PSUGUI.HALF_COL0_WIDTH)
                        self._on_button.set_enabled(False)

                        self._off_button = ui.button("Off",
                                                     on_click=lambda: self._call_method(self._off)).style(PSUGUI.HALF_COL0_WIDTH)
                        self._off_button.set_enabled(False)

                    self._voltage_number = ui.number(label="Voltage (Volts)",
                                                     min=0,
                                                     max=32,
                                                     value=3.3).style(PSUGUI.COL0_WIDTH)
                    self._set_voltage_button = ui.button("Set Voltage",
                                                         on_click=lambda: self._call_method(self._set_voltage)).style(PSUGUI.COL0_WIDTH)
                    self._set_voltage_button.set_enabled(False)

                    self._current_number = ui.number(label="Current (Amps)",
                                                     min=0,
                                                     max=10,
                                                     value=1).style(PSUGUI.COL0_WIDTH)
                    self._set_current_button = ui.button("Set Current Limit",
                                                         on_click=lambda: self._call_method(self._set_current_limit)).style(PSUGUI.COL0_WIDTH)
                    self._set_current_button.set_enabled(False)

                    self._read_interval_number = ui.number(label="PSU Read Interval (MSEC)",
                                                           min=10, value=250).style(PSUGUI.COL0_WIDTH)

                    self._clear_plot_button = ui.button("Clear Plot",
                                                        on_click=lambda: self._call_method(self._clear_plot)).style(PSUGUI.COL0_WIDTH)

                    self._plot_history_number = ui.number(label="Plot History (Points)",
                                                          min=10, max=10000, value=1000).style(PSUGUI.COL0_WIDTH)

            with ui.column():
                self._plot = ui.plotly(self._create_plot())
                self._plot.update()

        ui.timer(interval=0.1, callback=self._read_response)

    def _clear_plot(self):
        """@brief Clear the plot."""
        self._time_data.clear()
        self._voltage_data.clear()
        self._current_data.clear()
        self._power_data.clear()

        # If not connected then the plot is not being updated so we have to update it here
        if not self._connected:
            # Update the plot and refresh it
            self._plot.figure = self._create_plot()
            self._plot.update()  # Ensure the display is refreshed

    def _plot_stats(self, stats):
        """@brief Plot the stats from the PSU
           @param stats A tuple (volts, amps, watts)"""

        self._time_data.append(datetime.datetime.now())
        self._voltage_data.append(stats[0])
        self._current_data.append(stats[1])
        self._power_data.append(stats[2])
        max_plot_points = self._plot_history_number.value
        if self._time_data and max_plot_points:
            # Ensure the number of points is limited
            while len(self._time_data) > max_plot_points:
                del self._time_data[0]
                del self._voltage_data[0]
                del self._current_data[0]
                del self._power_data[0]

        # Update the plot and refresh it
        self._plot.figure = self._create_plot()
        self._plot.update()  # Ensure the display is refreshed

    def _set_connected_state(self, connected):
        """@brief Set button state as either conected or disconnected.
           @param connected If True then serial port is connected."""
        if connected:
            self._connect_button.set_enabled(False)
            self._disconnect_button.set_enabled(True)
            self._on_button.set_enabled(True)
            self._off_button.set_enabled(True)
            self._set_voltage_button.set_enabled(True)
            self._set_current_button.set_enabled(True)

        else:
            self._connect_button.set_enabled(True)
            self._disconnect_button.set_enabled(False)
            self._on_button.set_enabled(False)
            self._off_button.set_enabled(False)
            self._set_voltage_button.set_enabled(False)
            self._set_current_button.set_enabled(False)

        self._connected = connected

    def _read_response(self):
        """@brief Read responses from methods executed in separate threads."""
        while True:
            response = self._get_response()
            if response:
                for key in response.keys():
                    msg_type = key
                    msg = response[key]
                    if msg_type == PSUGUI.INFO_MESSAGE:
                        ui.notify(msg)
                        if msg == PSUGUI.CONNECTED_MESSAGE:
                            self._set_connected_state(True)

                        elif msg == PSUGUI.DISCONNECTED_MESSAGE:
                            self._set_connected_state(False)

                    elif msg_type == PSUGUI.ERROR_MESSAGE:
                        ui.notify(msg, type='negative')

                    elif msg_type == PSUGUI.WARNING_MESSAGE:
                        ui.notify(msg, type='negative')

                    elif msg_type == PSUGUI.PSU_STATS:
                        self._plot_stats(msg)

                    elif msg_type == PSUGUI.PSU_SETTINGS:
                        voltage = msg[0]
                        current_limit = msg[1]
                        self._voltage_number.value = voltage
                        self._current_number.value = current_limit

            # No response, quit looking until next time
            else:
                break

    def exception_handler_decorator(func):
        """@brief A decorator to handle exceptions and send error messages back to GUI thread
                  if an error occurs. Also handles thread locking of PSU serial interface access."""
        def wrapper(self, *args, **kwargs):
            try:
                try:
                    self._psu_access_lock.acquire()
                    return func(self, *args, **kwargs)
                finally:
                    self._psu_access_lock.release()

            except Exception as ex:
                self._send(PSUGUI.ERROR_MESSAGE, str(ex))
        return wrapper

    @exception_handler_decorator
    def _connect(self):
        """@brief Connect to the PSU."""
        self._psuIF = ETMXXXXP(self._selected_serial_port_select.value)
        self._psuIF.connect()
        self._send(PSUGUI.INFO_MESSAGE, f"Opened {self._selected_serial_port_select.value}")
        self._send(PSUGUI.INFO_MESSAGE, "Checking for PSU response...")
        target_volts = self._psuIF.getTargetVolts()
        current_limit = self._psuIF.getCurrentLimit()
        self._send(PSUGUI.PSU_SETTINGS, (target_volts, current_limit))
        self._start_read_stats_thread()
        self._send(PSUGUI.INFO_MESSAGE, PSUGUI.CONNECTED_MESSAGE)

    def _start_read_stats_thread(self):
        """@brief Start a thread responsible for reading stats from PSU"""
        threading.Thread(target=self._read_stats).start()

    def _read_stats(self):
        """@brief Read stats from PSU at intervals"""
        self._send(PSUGUI.INFO_MESSAGE, "Started reading PSU stats")
        try:
            while self._psuIF:
                volts, amps, watts = self._psuIF.getOutputStats()
                self._send(PSUGUI.PSU_STATS, (volts, amps, watts))
                if self._psuIF:
                    ms_sleep = self._read_interval_number.value
                    if ms_sleep is None or ms_sleep < 10:
                        ms_sleep = 10
                    sleep(ms_sleep/1000)

        except Exception:
            self._send(PSUGUI.INFO_MESSAGE, "Stopped reading PSU stats")

    @exception_handler_decorator
    def _disconnect(self):
        """@brief Disconnect from the PSU."""
        try:
            self._psuIF.disconnect()
        finally:
            self._psuIF = None
        self._send(PSUGUI.INFO_MESSAGE, PSUGUI.DISCONNECTED_MESSAGE)

    @exception_handler_decorator
    def _on(self):
        """@brief Turn the PSU on."""
        self._psuIF.setOutput(True)
        self._send(PSUGUI.INFO_MESSAGE, PSUGUI.ON_MESSAGE)

    @exception_handler_decorator
    def _off(self):
        """@brief Turn the PSU off."""
        self._psuIF.setOutput(False)
        self._send(PSUGUI.INFO_MESSAGE, PSUGUI.OFF_MESSAGE)

    def _set_voltage(self):
        """@brief Set voltage."""
        v = self._voltage_number.value
        self._psuIF.setVoltage(v)
        self._send(PSUGUI.INFO_MESSAGE, f"Set PSU voltage to {v:.2f}")

    def _set_current_limit(self):
        """@brief Set current."""
        v = self._current_number.value
        self._psuIF.setCurrentLimit(v)
        self._send(PSUGUI.INFO_MESSAGE, f"Set PSU current limit to {v:.2f}")

    def _update_gui_log_level(self):
        """@Update the log level used for the GUI."""
        self._guiLogLevel = "warning"
        if self._debug:
            self._guiLogLevel = "debug"

    def start(self):
        """@brief Start the GUI."""
        available_serial_port_list = self._get_serial_port_list()
        if len(available_serial_port_list) == 0:
            print("No serial ports found on this machine.")
            input("Press any key to continue")
            return
        self._update_gui_log_level()

        self._init_gui(available_serial_port_list)
        print("Close this to shutdown GUI server.")

        ui.run(host=self._address,
               port=self._port,
               title="PSU GUI",
               dark=True,
               uvicorn_logging_level=self._guiLogLevel,
               reload=self._reload)

    def plot_data(self, reading_list):
        """@brief Create a GUI plot of the data from a log file.."""
        self._update_gui_log_level()

        self._reading_list = reading_list

        self._init_gui(None)

        self._update_plot()

        print("Close this to shutdown GUI server.")

        ui.run(host=self._address,
               port=self._port,
               title="PSU GUI",
               dark=True,
               uvicorn_logging_level=self._guiLogLevel,
               reload=self._reload)

    def _update_plot(self):
        """@brief Update plot from the reading list."""
        self._time_data = []
        self._voltage_data = []
        self._current_data = []
        self._power_data = []

        for reading in self._reading_list:
            self._time_data.append(reading.time)
            self._voltage_data.append(reading.volts)
            self._current_data.append(reading.amps)
            self._power_data.append(reading.watts)

        # Update the plot and refresh it
        self._plot.figure = self._create_plot()
        self._plot.update()  # Ensure the display is refreshed
