import sys, pathlib
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from src.core import Device, Parameter
import serial
import time
import matplotlib as plt


class korad_ka3005p(Device):
    _DEFAULT_SETTINGS = Parameter(Device._get_base_settings() + [
        Parameter('port', 'COM4', str, 'com port to which device is connected'),
        Parameter('baudrate', 9600, int, 'baudrate of serial connection'),
        Parameter('timeout', 1.0, float, 'timeout (s) for serial communication'),
        Parameter('voltage', 5.0, float, 'output voltage setpoint in V'),
        Parameter('current', 0.5, float, 'output current setpoint in A'),
        Parameter('output_enable', False, bool, 'turns the output on/off'),
        Parameter('beep', False, bool, 'turns the beep on/off'),
        Parameter('recall_memory', 1, int, 'recall panel setting from memory 1-5 (write-only trigger)'),
        Parameter('save_memory', 1, int, 'save panel setting to memory 1-5 (write-only trigger)'),
        Parameter('ocp', False, bool, 'turns over-current protection on/off'),
        Parameter('ovp', False, bool, 'turns over-voltage protection on/off'),
        Parameter('current_display_unit', 'A', str, 'display unit for current: A or MA'),
        Parameter('analog_control', False, bool, 'enable external analog control of output'),
        Parameter('ext_switch', False, bool, 'enable external switch (EXON)'),
        Parameter('ext_compensation', False, bool, 'enable external voltage sense compensation (SENES)'),
        Parameter('ocp_value', 1.000, float, 'OCP threshold current in A'),
        Parameter('ovp_value', 30.00, float, 'OVP threshold voltage in V'),
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
                elif key == "ovp":
                    self._send_command("OVP%d" % int(value))
                elif key == "recall_memory":
                    if not (1 <= int(value) <= 5):
                        raise ValueError("Memory slot must be 1-5")
                    self._send_command("RCL%d" % int(value))
                elif key == "save_memory":
                    if not (1 <= int(value) <= 5):
                        raise ValueError("Memory slot must be 1-5")
                    self._send_command("SAV%d" % int(value))
                elif key == "current_display_unit":
                    unit = str(value).upper()
                    if unit not in ("A", "MA"):
                        raise ValueError("current_display_unit must be 'A' or 'MA'")
                    self._send_command("CURRENT %s" % unit)
                elif key == "analog_control":
                    self._send_command("ANALOGE%d" % int(value))
                elif key == "ext_switch":
                    self._send_command("EXON:%d" % int(value))
                elif key == "ext_compensation":
                    self._send_command("SENES:%d" % int(value))
                elif key == "ocp_value":
                    self._send_command("OCP1:%.3f" % float(value))
                elif key == "ovp_value":
                    self._send_command("OVP1:%05.2f" % float(value)) 
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
            value = float(self._query("VSET1?")) #output voltage setting
        elif key_internal == "current_set":
            value = float(self._query("ISET1?")) #ouput current setting
        elif key_internal == "voltage_out":
            value = float(self._query("VOUT1?")) #actual output voltage
        elif key_internal == "current_out":
            value = float(self._query("IOUT1?")) #actual output current
        elif key_internal == "status":
            value = self._query_raw("STATUS?")
        elif key_internal == "idn":
            value = self._query("*IDN?")
        elif key_internal == "power_out":
            value = float(self._query("POWER?"))
        elif key_internal == "analog_control":
            value = self._query("ANALOGE?")
        elif key_internal == "ext_switch":
            value = self._query("EXON?")
        elif key_internal == "ext_compensation":
            value = self._query("SENES?")
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
            'power_out': 'output power reading',
            'analog_control': 'status of external analog control',
            'ext_switch': 'status of external switch',
            'ext_compensation': 'status of external voltage sense compensation',
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
    #dev.update({"voltage": 5.0, "current": 0.5})
    dev.update({"output_enable": True})

    #graphing IV
    dev.update({"current": 0.5})
    voltages = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0,
                5.5, 6.0, 6.5, 7.0, 7.5, 8.0, 8.5, 9.0, 9.5, 10.0]
    measured_voltages = []
    measured_currents = []

    for target_voltage in voltages:
        dev.update({'voltage': target_voltage})
        time.sleep(0.5)
        v_out = dev.read_probes("voltage_out")
        i_out = dev.read_probes("current_out")
        measured_voltages.append(v_out)
        measured_currents.append(i_out)
        print(f"Measured: {v_out:.2f}V, {i_out:.3f}A")
    dev.close()

    plt.figure()
    plt.plot(measured_voltages, measured_currents)
    plt.xlabel("Voltage (V)")
    plt.ylabel("Current (A)")
    plt.title("I-V Graph")
    plt.grid(True)
    plt.show()


    #print("Voltage Set:", dev.read_probes("voltage_set"))
    #print("Current Set:", dev.read_probes("current_set"))
    #print("Voltage Output:", dev.read_probes("voltage_out"))
    #print("Current Output:", dev.read_probes("current_out"))
    #print("Power Output:", dev.read_probes("power_out"))
    #time.sleep(10)
    #dev.close()