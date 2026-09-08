import sys, pathlib
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from src.core import Device, Parameter
import serial
import time


class korad_ka3005p(Device):
    _DEFAULT_SETTINGS = Parameter(Device._get_base_settings() + [
        Parameter('port', 'COM4', str, 'com port to which device is connected'),
        Parameter('baudrate', 9600, int, 'baudrate of serial connection'),
        Parameter('timeout', 1.0, float, 'timeout (s) for serial communication'),
        Parameter('voltage', 5.0, float, 'output voltage setpoint in V'),
        Parameter('current', 0.5, float, 'output current setpoint in A'),
        Parameter('output_enable', False, bool, 'turns the output on/off'),
        Parameter('beep', False, bool, 'turns the beep on/off'),
        Parameter('ocp', False, bool, 'turns over-current protection on/off'),
    ])

    def __init__(self, name=None, settings=None):
        super(korad_ka3005p, self).__init__(name, settings)
        self.ser = None
        try:
            self._connect()
        except Exception as e:
            raise e

    def update(self, settings: dict):
        super(korad_ka3005p, self).update(settings)
        for key, value in settings.items():
            if self.settings.valid_values[key] == bool:  # converts booleans
                value = int(value)  # the integers used internally by the power supply
            key = self._param_to_internal(key)
            # only send update to Device if connection to Device has been established
            if self._settings_initialized:
                if key == "voltage":
                    self._send_command("VSET1:%.2f" % float(value))
                elif key == "current":
                    self._send_command("ISET1:%.3f" % float(value))
                elif key == "output_enable":
                    self._send_command("OUT%d" % int(value))
                elif key == "beep":
                    self._send_command("BEEP%d" % int(value))
                elif key == "ocp":
                    self._send_command("OCP%d" % int(value))
                elif key in ("port", "baudrate", "timeout"):
                    pass  # handled only at connection time
                else:
                    raise ValueError("Unknown key '%s'" % key)

    def _param_to_internal(self, param):
        return param

    def read_probes(self, key=None):
        assert (
            self._settings_initialized)  # will cause read_probes to fail if settings (and connection) not yet initialized
        assert key in list(self._PROBES.keys())
        key_internal = self._param_to_internal(key)
        if key_internal == "voltage_set":
            value = float(self._query("VSET1?"))
        elif key_internal == "current_set":
            value = float(self._query("ISET1?"))
        elif key_internal == "voltage_out":
            value = float(self._query("VOUT1?"))
        elif key_internal == "current_out":
            value = float(self._query("IOUT1?"))
        elif key_internal == "status":
            value = self._query_raw("STATUS?")
        elif key_internal == "idn":
            value = self._query("*IDN?")
        else:
            raise NotImplementedError
        return value

    @property
    def _PROBES(self):
        return {
            'voltage_set': 'CH1 output voltage setpoint',
            'current_set': 'CH1 output current setpoint',
            'voltage_out': 'CH1 actual output voltage',
            'current_out': 'CH1 actual output current',
            'status': 'power supply status byte',
            'idn': 'device identification string',
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
        self._send_command("OUT0")  # turn off output before closing
        self.ser.close()
        print('korad_ka3005p closed')


if __name__ == "__main__":
    dev = korad_ka3005p()
    print(dev.read_probes("idn"))
    print(dev.read_probes("status"))
    dev.update({"voltage": 5.0, "current": 0.5})
    dev.update({"output_enable": True})
    print(dev.read_probes("voltage_set"))
    print(dev.read_probes("current_set"))
    print(dev.read_probes("voltage_out"))
    print(dev.read_probes("current_out"))
    dev.close()