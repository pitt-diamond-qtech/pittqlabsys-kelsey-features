import sys, pathlib
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from src.core import Device, Parameter
import socket
import time


class korad_kwr103(Device):
    _DEFAULT_SETTINGS = Parameter(Device._get_base_settings() + [
        Parameter('ip', '192.168.2.110', str, 'IP address of the KWR103'),
        Parameter('port', 41000, int, 'UDP command port of the KWR103'),
        Parameter('device_id', 1, int, 'device/RS485 address (1-99), embedded in every command'),
        Parameter('timeout', 1.0, float, 'socket timeout (s) for UDP communication'),
        Parameter('voltage', 5.0, float, 'output voltage setpoint in V'),
        Parameter('current', 0.5, float, 'output current setpoint in A'),
        Parameter('output_enable', False, bool, 'turns the output on/off'),
        Parameter('beep', False, bool, 'turns the beep on/off'),
        Parameter('recall_memory', 1, int, 'recall panel setting from memory 1-5, or 6 for LIST dynamic value'),
        Parameter('save_memory', 1, int, 'save panel setting to memory 1-5'),
        Parameter('ocp_enable', False, bool, 'turns over-current protection on/off'),
        Parameter('ocp_value', 1.0, float, 'OCP threshold current in A'),
        Parameter('ovp_enable', False, bool, 'turns over-voltage protection on/off'),
        Parameter('ovp_value', 30.0, float, 'OVP threshold voltage in V'),
    ])

    def __init__(self, name=None, settings=None):
        super(korad_kwr103, self).__init__(name, settings)
        self.sock = None
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
                    self._send_command("OCP:%s" % ("ON" if int(value) else "OFF"))
                elif key == "ocp_value":
                    self._send_command("OCP:%.2f" % float(value))
                elif key == "ovp_enable":
                    self._send_command("OVP:%s" % ("ON" if int(value) else "OFF"))
                elif key == "ovp_value":
                    self._send_command("OVP:%.2f" % float(value))
                elif key == "recall_memory":
                    if not (1 <= int(value) <= 6):
                        raise ValueError("Memory slot must be 1-5, or 6 for LIST dynamic value")
                    self._send_command("RCL%s:%d" % (idn, int(value)))
                elif key == "save_memory":
                    if not (1 <= int(value) <= 5):
                        raise ValueError("Memory slot must be 1-5")
                    self._send_command("SAV:%d" % int(value))
                elif key in ("ip", "port", "device_id", "timeout"):
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
        elif key_internal == "output_status":
            value = self._query("OUT?")
        elif key_internal == "status":
            value = self._query("STATUS?")
        elif key_internal == "idn":
            value = self._query("*IDN?")
        elif key_internal == "ocp_value":
            value = float(self._query("OCP?"))
        elif key_internal == "ovp_value":
            value = float(self._query("OVP?"))
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
            'output_status': 'output on/off status',
            'status': 'device status byte (CC/CV, output, V/C priority, beep, lock, OVP, OCP)',
            'idn': 'device serial number',
            'ocp_value': 'OCP current threshold setting',
            'ovp_value': 'OVP voltage threshold setting',
        }

    def _connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(self.settings['timeout'])
        return 0

    def _send_command(self, cmd):
        payload = (cmd + "\n").encode('ascii')
        self.sock.sendto(payload, (self.settings['ip'], self.settings['port']))
        time.sleep(0.1)

    def _query(self, cmd, read_timeout=0.5):
        payload = (cmd + "\n").encode('ascii')
        self.sock.sendto(payload, (self.settings['ip'], self.settings['port']))
        self.sock.settimeout(read_timeout)
        try:
            data, addr = self.sock.recvfrom(4096)
        except socket.timeout:
            return ''
        return data.decode('ascii', errors='ignore').strip()

    def close(self):
        self._send_command("OUT:0")
        self.sock.close()
        print('korad_kwr103 closed')


if __name__ == "__main__":
    dev = korad_kwr103()
    print(dev.read_probes("status"))
    # dev.update({"voltage": 5.0, "current": 0.5})
    dev.update({"output_enable": True})
    # print(dev.read_probes("voltage_set"))
    # print(dev.read_probes("current_set"))
    print(dev.read_probes("voltage_out"))
    # print(dev.read_probes("current_out"))
    dev.close()



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

# print("IDN:", query("*IDN?"))
# send(":SYSTem:IPADdress 192.168.2.110")
# print("IP set to:", query(":SYSTem:IPADdress?"))
# send(":SYSTem:SMASK 255.255.255.0")
# print("Subnet set to:", query(":SYSTem:SMASK?"))
# send(":SYSTem:GATEway 192.168.2.1")
# print("Gateway set to:", query(":SYSTem:GATEway?"))
# send(":SYSTem:PORT 41000")
# print("Port:", query(":SYSTem:PORT?"))
# print("VSET? ", repr(query("VSET?")))
# print("VSET01?", repr(query("VSET01?")))
# print("STATUS?", repr(query("STATUS?")))
# print("STATUS01?", repr(query("STATUS01?")))
# print("OUT?", repr(query("OUT?")))
# print("OUT01?", repr(query("OUT01?")))