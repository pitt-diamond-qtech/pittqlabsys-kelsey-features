# Ethernet Connection Class
# import sys, pathlib
# PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
# if str(PROJECT_ROOT) not in sys.path:
#     sys.path.insert(0, str(PROJECT_ROOT))
# from src.core import Device, Parameter
# import socket
# import time


# class korad_kwr103(Device):
#     _DEFAULT_SETTINGS = Parameter(Device._get_base_settings() + [
#         Parameter('ip', '192.168.2.110', str, 'IP address of the KWR103'),
#         Parameter('port', 18190, int, 'UDP command port of the KWR103'),
#         Parameter('device_id', 1, int, 'device/RS485 address (1-99), embedded in every command'),
#         Parameter('timeout', 1.0, float, 'socket timeout (s) for UDP communication'),
#         Parameter('voltage', 5.0, float, 'output voltage setpoint in V'),
#         Parameter('current', 0.5, float, 'output current setpoint in A'),
#         Parameter('output_enable', False, bool, 'turns the output on/off'),
#         Parameter('beep', False, bool, 'turns the beep on/off'),
#         Parameter('recall_memory', 1, int, 'recall panel setting from memory 1-5, or 6 for LIST dynamic value'),
#         Parameter('save_memory', 1, int, 'save panel setting to memory 1-5'),
#         Parameter('ocp_enable', False, bool, 'turns over-current protection on/off'),
#         Parameter('ocp_value', 1.0, float, 'OCP threshold current in A'),
#         Parameter('ovp_enable', False, bool, 'turns over-voltage protection on/off'),
#         Parameter('ovp_value', 30.0, float, 'OVP threshold voltage in V'),
#     ])

#     def __init__(self, name=None, settings=None):
#         super(korad_kwr103, self).__init__(name, settings)
#         self.sock = None
#         try:
#             self._connect()
#         except Exception as e:
#             raise e

#     def update(self, settings: dict):
#         super(korad_kwr103, self).update(settings)
#         for key, value in settings.items():
#             if self.settings.valid_values[key] == bool:
#                 value = int(value)
#             key = self._param_to_internal(key)
#             if self._settings_initialized:
#                 if key == "voltage":
#                     self._send_command("VSET:%.2f" % float(value))
#                 elif key == "current":
#                     self._send_command("ISET:%.3f" % float(value))
#                 elif key == "output_enable":
#                     self._send_command("OUT:%d" % int(value))
#                 elif key == "beep":
#                     self._send_command("BEEP:%d" % int(value))
#                 elif key == "ocp_enable":
#                     self._send_command("OCP:%s" % ("ON" if int(value) else "OFF"))
#                 elif key == "ocp_value":
#                     self._send_command("OCP:%.2f" % float(value))
#                 elif key == "ovp_enable":
#                     self._send_command("OVP:%s" % ("ON" if int(value) else "OFF"))
#                 elif key == "ovp_value":
#                     self._send_command("OVP:%.2f" % float(value))
#                 elif key == "recall_memory":
#                     if not (1 <= int(value) <= 6):
#                         raise ValueError("Memory slot must be 1-5, or 6 for LIST dynamic value")
#                     self._send_command("RCL%s:%d" % int(value))
#                 elif key == "save_memory":
#                     if not (1 <= int(value) <= 5):
#                         raise ValueError("Memory slot must be 1-5")
#                     self._send_command("SAV:%d" % int(value))
#                 elif key in ("ip", "port", "device_id", "timeout"):
#                     pass
#                 else:
#                     raise ValueError("Unknown key '%s'" % key)

#     def _param_to_internal(self, param):
#         return param

#     def read_probes(self, key=None):
#         assert (self._settings_initialized)
#         assert key in list(self._PROBES.keys())
#         key_internal = self._param_to_internal(key)
#         if key_internal == "voltage_set":
#             value = float(self._query("VSET?"))
#         elif key_internal == "current_set":
#             value = float(self._query("ISET?"))
#         elif key_internal == "voltage_out":
#             value = float(self._query("VOUT?"))
#         elif key_internal == "current_out":
#             value = float(self._query("IOUT?"))
#         elif key_internal == "output_status":
#             value = self._query("OUT?")
#         elif key_internal == "status":
#             value = self._query("STATUS?")
#         elif key_internal == "ocp_value":
#             value = float(self._query("OCP?"))
#         elif key_internal == "ovp_value":
#             value = float(self._query("OVP?"))
#         else:
#             raise NotImplementedError
#         return value

#     @property
#     def _PROBES(self):
#         return {
#             'voltage_set': 'output voltage setpoint',
#             'current_set': 'output current setpoint',
#             'voltage_out': 'actual output voltage',
#             'current_out': 'actual output current',
#             'output_status': 'output on/off status',
#             'status': 'device status byte (CC/CV, output, V/C priority, beep, lock, OVP, OCP)',
#             'ocp_value': 'OCP current threshold setting',
#             'ovp_value': 'OVP voltage threshold setting',
#         }

#     def _connect(self):
#         self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#         self.sock.bind(('0.0.0.0', 18190))
#         self.sock.connect((self.settings['ip'], self.settings['port']))
#         self.sock.settimeout(self.settings['timeout'])
#         return 0

#     def _send_command(self, cmd):
#         payload = (cmd + "\n").encode('ascii')
#         self.sock.send(payload)
#         time.sleep(0.1)

#     def _query(self, cmd, read_timeout=0.5):
#         payload = (cmd + "\n").encode('ascii')
#         print(f"Sending: {payload!r}")
#         self.sock.send(payload)
#         self.sock.settimeout(read_timeout)
#         try:
#             data, addr = self.sock.recvfrom(4096)
#         except socket.timeout:
#             print(f"[{cmd}] timed out")
#             return ''
#         except OSError as e:
#             print(f"[{cmd}] socket error: {e!r}")
#             return ''
#         return data.decode('ascii', errors='ignore').strip()

#     def close(self):
#         self._send_command("OUT:0")
#         self.sock.close()
#         print('korad_kwr103 closed')


# if __name__ == "__main__":
#     dev = korad_kwr103()
#     print(dev.read_probes("status"))
#     dev.update({"voltage": 5.0, "current": 0.5})
#     dev.update({"output_enable": True})
#     time.sleep(0.5)
#     raw = dev._query("VOUT?", read_timeout=2.0)
#     print("Raw VOUT? response:", repr(raw))
#     # print(dev.read_probes("voltage_set"))
#     # print(dev.read_probes("current_set"))
#     # print(dev.read_probes("voltage_out"))
#     # print(dev.read_probes("current_out"))
#     dev.close()


# Test for USB connection to set the IP Address
# import serial
# import time
# COM_PORT = "COM7"
# BAUD = 9600
# ser =  serial.Serial(port=COM_PORT, baudrate=BAUD, timeout=1.0, bytesize=8, parity='N', stopbits=1)

# def send(cmd):
#     ser.write((cmd + "\n").encode('ascii'))
#     time.sleep(0.2)

# def query(cmd):
#     send(cmd)
#     return ser.read(ser.in_waiting or 1).decode('ascii', errors='ignore').strip()

# send(":SYSTem:IPADdress 192.168.2.110")
# print("IP set to:", query(":SYSTem:IPADdress?"))
# send(":SYSTem:SMASK 255.255.255.0")
# print("Subnet set to:", query(":SYSTem:SMASK?"))
# send(":SYSTem:GATEway 192.168.2.1")
# print("Gateway set to:", query(":SYSTem:GATEway?"))
# send(":SYSTem:PORT 41000")
# print("Port:", query(":SYSTem:PORT?"))
# print("DHCP:", query(":SYSTem:DHCP?"))
# print("Device Info:", query(":SYSTem:DEVINFO?"))
# send("VSET:6.0")
# print("VSET? ", repr(query("VSET?")))
# print("VSET01?", repr(query("VSET01?")))
# print("STATUS?", repr(query("STATUS?")))
# print("STATUS01?", repr(query("STATUS01?")))
# print("OUT?", repr(query("OUT?")))
# print("OUT01?", repr(query("OUT01?")))


#  Test for ethernet connection
# import socket
# sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
# sock.bind(('0.0.0.0', 18190))
# sock.connect(('192.168.2.110', 18190))
# sock.settimeout(2.0)
# sock.send(b"*IDN?\n")
# try:
#     print("Success:", sock.recv(4096))
# except socket.timeout:
#     print("no response")
# sock.close()


# import socket
# def find_devices(timeout=1.0):
#     sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#     sock.bind(('0.0.0.0', 18191))
#     sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
#     sock.settimeout(timeout)
#     sock.sendto(b"find_ka000", ('255.255.255.255', 18191))
#     try:
#         data, addr = sock.recvfrom(4096)
#         print(f"Discovery response from {addr}: {data!r}")
#         return data
#     except socket.timeout:
#         print("No devices found via broadcast discovery")
#         return None
#     finally:
#         sock.close()

# if __name__ == "__main__":
#     find_devices()


#USB Communications Device Class

import sys, pathlib
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from src.core import Device, Parameter
import serial
import time
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import curve_fit


class korad_kwr103(Device):
    _DEFAULT_SETTINGS = Parameter(Device._get_base_settings() + [
        Parameter('port', 'COM7', str, 'com port to which device is connected'),
        Parameter('baudrate', 115200, int, 'baudrate of serial connection'),
        Parameter('timeout', 1.0, float, 'timeout (s) for serial communication'),
        Parameter('voltage', 5.0, float, 'output voltage setpoint in V'),
        Parameter('current', 0.5, float, 'output current setpoint in A'),
        Parameter('output_enable', False, bool, 'turns the output on/off'),
        Parameter('beep', False, bool, 'turns the beep on/off'),
        Parameter('recall_memory', 1, int, 'recall panel setting from memory 1-6 (6 is LIST dynamic value)'),
        Parameter('save_memory', 1, int, 'save panel setting to memory 1-5'),
        Parameter('ocp_enable', False, bool, 'turns over-current protection on/off'),
        Parameter('ovp_enable', False, bool, 'turns over-voltage protection on/off'),
        Parameter('ocp_value', 1.000, float, 'OCP threshold current in A'),
        Parameter('ovp_value', 30.00, float, 'OVP threshold voltage in V'),
        Parameter('v_slope', 31.5, float, 'output voltage slope V per 100uS'),
        Parameter('i_slope', 1.5, float, 'output current slope A per 100uS'),
        Parameter('list_general', '25,6', str, 'times of repetitions and number of dynamic values'),
        Parameter('list_step', '02:25.6,2.5,6.5,5.8', str, 'step number:voltage,current,slope,time'),
        Parameter('ext_trigger', False, bool, 'enable external trigger'),
        Parameter('ext_comp', False, bool, 'enable external compensation'),
        Parameter('lock', False, bool, 'lock the buttons'),
        Parameter('v_astep', '1,30,0.1,1', str, 'start V, end V, step V, interval s'),
        Parameter('v_astop', True, bool, 'voltage stops automatically'),
        Parameter('v_step', 1.0, float, 'set the step voltage'),
        Parameter('v_up', True, bool, 'step voltage set by voltage increase'),
        Parameter('v_down', True, bool, 'step voltage set by voltage decrease'),
        Parameter('i_astep', '1,3,0.1,1', str, 'start A, end A, step A, interval s'),
        Parameter('i_astop', True, bool, 'current stops automatically'),
        Parameter('i_step', 1.0, float, 'set the step current'),
        Parameter('i_up', True, bool, 'step current set by current increase'),
        Parameter('i_down', True, bool, 'step current set by current decrease'),
        Parameter('priority', 0, int, '0 is voltage priority, 1 is current priority'),
        Parameter('current_display_unit', 'A', str, 'display unit for current: A or MA'),
        Parameter('analog_control', False, bool, 'enable external analog control of output')
    ])

    def __init__(self, name=None, settings=None):
        super(korad_kwr103, self).__init__(name, settings)
        self.ser = None
        try:
            self._connect()
        except Exception as e:
            raise e

    def update(self, settings: dict):
        super(korad_kwr103, self).update(settings)
        for key, value in settings.items():
            if self.settings.valid_values[key] == bool:
                value = int(value)
            key = self._param_to_internal(key)
            if self._settings_initialized:
                if key == "voltage":
                    self._send_command("VSET:%.2f" % float(value))
                elif key == "current":
                    self._send_command("ISET:%.3f" % float(value))
                elif key == "output_enable":
                    self._send_command("OUT:%d" % int(value))
                elif key == "beep":
                    self._send_command("BEEP:%d" % int(value))
                elif key == "ocp_enable":
                    status = "ON" if value else "OFF"
                    self._send_command("OCP:%s" % status)
                elif key == "ovp_enable":
                    status = "ON" if value else "OFF"
                    self._send_command("OVP:%s" % status)
                elif key == "recall_memory":
                    self._send_command("RCL:%d" % int(value))
                elif key == "save_memory":
                    self._send_command("SAV:%d" % int(value))
                elif key == "ocp_value":
                    self._send_command("OCP:%.3f" % float(value))
                elif key == "ovp_value":
                    self._send_command("OVP:%.2f" % float(value))
                elif key == "v_slope":
                    self._send_command("VSLOPE:%.2f" % float(value))
                elif key == "i_slope":
                    self._send_command("ISLOPE:%.3f" % float(value))
                elif key == "list_general":
                    self._send_command("LIST00:%s" % str(value))
                elif key == "list_step":
                    self._send_command("LIST%s" % str(value))
                elif key == "ext_trigger":
                    self._send_command("EXIT:%d" % int(value))
                elif key == "ext_comp":
                    self._send_command("COMP:%d" % int(value))
                elif key == "lock":
                    self._send_command("LOCK:%d" % int(value))
                elif key == "v_astep":
                    self._send_command("VASTEP:%s" % str(value))
                elif key == "v_astop":
                    self._send_command("VASTOP")
                elif key == "v_step":
                    self._send_command("VSTEP:%.2f" % float(value))
                elif key == "v_up":
                    self._send_command("VUP")
                elif key == "v_down":
                    self._send_command("VDOWN")
                elif key == "i_astep":
                    self._send_command("IASTEP:%s" % str(value))
                elif key == "i_astop":
                    self._send_command("IASTOP")
                elif key == "i_step":
                    self._send_command("ISTEP:%.3f" % float(value))
                elif key == "i_up":
                    self._send_command("IUP")
                elif key == "i_down":
                    self._send_command("IDOWN")
                elif key == "priority":
                    self._send_command("PRIORITY:%d" % int(value))
                elif key == "current_display_unit":
                    unit = str(value).upper()
                    self._send_command("CURRENT %s" % unit)
                elif key == "analog_control":
                    self._send_command("ANALOGE%d" % int(value))
                elif key in ("port", "baudrate", "timeout"):
                    pass
                else:
                    raise ValueError("Unknown key '%s'" % key)

    def _param_to_internal(self, param):
        return param

    def read_probes(self, key=None):
        assert (self._settings_initialized)
        assert key in list(self._PROBES.keys())
        key_internal = self._param_to_internal(key)
        
        if key_internal == "voltage_set":
            value = float(self._query("VSET?"))
        elif key_internal == "current_set":
            value = float(self._query("ISET?"))
        elif key_internal == "voltage_out":
            value = float(self._query("VOUT?"))
        elif key_internal == "current_out":
            value = float(self._query("IOUT?"))
        elif key_internal == "status":
            value = self._query_raw("STATUS?")
        elif key_internal == "idn":
            value = self._query("*IDN?")
        elif key_internal == "output_status":
            value = self._query("OUT?")
        elif key_internal == "ocp_value":
            value = self._query("OCP?")
        elif key_internal == "ovp_value":
            value = self._query("OVP?")
        elif key_internal == "v_slope":
            value = float(self._query("VSLOPE?"))
        elif key_internal == "i_slope":
            value = float(self._query("ISLOPE?"))
        elif key_internal == "list_general":
            value = self._query("LIST00?")
        elif key_internal == "list_step":
            step = self.settings["list_step"].split(":")[0]
            value = self._query("LIST%s?" % step)
        elif key_internal == "ext_trigger":
            value = self._query("EXIT?")
        elif key_internal == "ext_comp":
            value = self._query("COMP?")
        elif key_internal == "power_out":
            value = float(self._query("POWER?"))
        elif key_internal == "analog_control":
            value = self._query("ANALOGE?")
        else:
            raise NotImplementedError
        return value

    @property
    def _PROBES(self):
        return {
            'voltage_set': 'output voltage setpoint',
            'current_set': 'output current setpoint',
            'voltage_out': 'actual output voltage',
            'current_out': 'actual output current',
            'status': 'power supply status byte',
            'idn': 'device identification string',
            'output_status': 'output on or off status',
            'ocp_value': 'OCP value reading',
            'ovp_value': 'OVP value reading',
            'v_slope': 'output voltage slope',
            'i_slope': 'output current slope',
            'list_general': 'repetitions of LIST and number of values',
            'list_step': 'settings of the current dynamic LIST step',
            'ext_trigger': 'status of the external trigger',
            'ext_comp': 'status of the external compensation',
            'power_out': 'output power reading',
            'analog_control': 'status of external analog control'
        }

    def _connect(self):
        self.ser = serial.Serial(
            port=self.settings['port'],
            baudrate=self.settings['baudrate'],
            timeout=self.settings['timeout']
        )
        return 0

    def _send_command(self, cmd):
        self.ser.reset_input_buffer()
        self.ser.write(cmd.encode('ascii'))
        time.sleep(0.1) 
                 
    def _query(self, cmd, expected_bytes=None, read_timeout=0.5):
        self.ser.reset_input_buffer()
        self.ser.write(cmd.encode('ascii'))
        deadline = time.time() + read_timeout
        buf = b''
        while time.time() < deadline:
            if self.ser.in_waiting:
                buf += self.ser.read(self.ser.in_waiting)
                time.sleep(0.02)
                if self.ser.in_waiting == 0:
                    break
            else:
                time.sleep(0.01)
        return buf.decode('ascii', errors='ignore').strip()

    def _query_raw(self, cmd, read_timeout=0.5):
        self.ser.reset_input_buffer()
        self.ser.write(cmd.encode('ascii'))
        deadline = time.time() + read_timeout
        buf = b''
        while time.time() < deadline:
            if self.ser.in_waiting:
                buf += self.ser.read(self.ser.in_waiting)
                time.sleep(0.02)
                if self.ser.in_waiting == 0:
                    break
            else:
                time.sleep(0.01)
        return buf

    def close(self):
        self._send_command("OUT:0")
        self.ser.close()
        print('korad_kwr103 closed')

if __name__ == "__main__":
    dev = korad_kwr103()
    print(dev.read_probes("idn"))
    print(dev.read_probes("status"))
    dev.update({"output_enable": True})

    dev.update({"current": 0.5})

    voltages = [float(v) for v in np.round(np.arange(0.0, 5.0, 0.1), 2)]
    set_voltages = []
    measured_currents = []

    for target_voltage in voltages:
        dev.update({'voltage': target_voltage})
        time.sleep(0.5)
        vdd_out = dev.read_probes("voltage_out")
        i_out = dev.read_probes("current_out")
        set_voltages.append(vdd_out)
        measured_currents.append(i_out)
        print(f"Measured: {vdd_out:.2f}V, {i_out:.9f}A")
        
    dev.close()