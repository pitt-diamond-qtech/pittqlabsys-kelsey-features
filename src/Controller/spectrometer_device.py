# Spectrometer device class (COM/PySerial)
# Units: wavelength in nm; grating is integer index (1..N)
#
# Requires:
#   pip install pyserial
#
# Notes:
# - Protocol:
#     QM                  -> text status block (contains current wavelength/grating, grating info, limits)
#     RE                  -> reset
#     GW <value>          -> set wavelength (nm); expect ACK from '+', '-', or '='
#     GS <num>            -> set grating (int); expect ACK from '+', '-', or '='
#     After ACK, send '!' -> commit
#     Wait for '*'        -> DONE
#
#     * Parameter-based settings (init, connect, update)
#     * _PROBES / read_probes for standardized “getters”
#     * _param_to_internal mapping (keys -> device command)
#     * Public helpers: get_/set_ wavelength/grating, get_gratings(), get_grating_limits()
#

from __future__ import annotations

# Force import of this project's src/core.py regardless of CWD
import sys, pathlib
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
import re
import time
from typing import Optional, Dict, Tuple, List

import serial
from src.core import Device, Parameter

#DEBUG for core.py
#import inspect, src.core as _core_dbg
#print("[DEBUG] Using core.py from", getattr(_core_dbg, "__file__", "<unknown>"))
#print("[DEBUG] Parameter.__init__ SIG:", inspect.signature(Parameter.__init__))

ACK_CHARS = b'+-='
DONE_CHAR = b'*'

# Timeouts (seconds)
_DEFAULT_READ_TIMEOUT = 5.0
_DEFAULT_ACK_TIMEOUT = 5.0
_DEFAULT_DONE_TIMEOUT = 120.0
_IDLE_GAP = 2.0 

class Spectrometer(Device):
    """
    Serial (COM) spectrometer using your working command set.
    """

    _DEFAULT_SETTINGS = Parameter([
        # Connection
        Parameter('connection_type', 'COM', ['COM'], 'connection type (COM only)'),
        Parameter('com_port', 5, list(range(1, 100)), 'COM port number (e.g., 5 for COM5)'),
        Parameter('read_timeout_s', _DEFAULT_READ_TIMEOUT, float, 'serial read timeout (s)'),

        Parameter('grating', 1, list(range(1, 10)), 'active grating index (1..N)'),
        Parameter('wavelength_nm', 600.0, float, 'current wavelength (nm)'),
    ])


    def __init__(self, name=None, settings=None):
        self._ser = None
        super(Spectrometer, self).__init__(name, settings)
        self._last_qm_cache: str = ""  

    def _connect(self) -> int:
        if self.settings['connection_type'] != 'COM':
            raise ValueError("Only 'COM' connection_type is supported for this spectrometer.")

        port = f"COM{self.settings['com_port']}"
        self._ser = serial.Serial(
            port=port,
            baudrate=9600,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=float(self.settings['read_timeout_s']),
            write_timeout=5.0,
            xonxoff=False,
            rtscts=False,
            dsrdtr=False,
        )
        print(f"Spectrometer connected on {port} @ 9600 8N1 (nm, integer grating).")
        time.sleep(1.0)  # allow controller to settle
        return 0

    def update(self, settings: dict):
        """
        Apply runtime changes. Reconnect on COM changes.
        Push instrument-state updates (grating/wavelength) when relevant.
        """
        super(Spectrometer, self).update(settings)
        
        # If connection parameters changed, reconnect
        if 'connection_type' in settings or 'com_port' in settings or 'read_timeout_s' in settings:
            # Re-open port with new params
            if self._ser and self._ser.is_open:
                self._ser.close()
            self._connect()

        # If state parameters changed, push them to the instrument (in a safe order)
        # Prefer changing grating first (limits depend on grating), then wavelength.
        if 'grating' in settings:
            self.set_grating(int(self.settings['grating']))
        if 'wavelength_nm' in settings:
            self.set_wavelength(float(self.settings['wavelength_nm']))

    @property
    def is_connected(self) -> bool:
        return bool(self._ser and self._ser.is_open)


    def _monotonic(self) -> float:
        return time.monotonic()

    def _ensure_connected(self):
        if not self.is_connected:
            raise RuntimeError("Spectrometer not connected.")

    def _write_line(self, cmd: str) -> None:
        self._ensure_connected()
        self._ser.write(cmd.encode('ascii', errors='ignore') + b'\r')
        self._ser.flush()

    def _read_until_any(self, chars: bytes, timeout: float) -> bytes:
        self._ensure_connected()
        start = self._monotonic()
        buf = bytearray()
        while self._monotonic() - start < timeout:
            b = self._ser.read(1)
            if b:
                buf += b
                if b in chars:
                    return bytes(buf)
            else:
                time.sleep(0.01)
        raise TimeoutError(f"Timed out waiting for any of {chars!r}; partial={bytes(buf)!r}")

    def _send_command_collect(self, command: str,
                              wait: float = 0.2,
                              timeout: float = _DEFAULT_READ_TIMEOUT,
                              idle_gap: float = _IDLE_GAP) -> str:
        """
        For text-reply commands like QM/RE.
        """
        self._ensure_connected()
        self._ser.reset_input_buffer()
        msg = command.strip().encode('ascii', errors='ignore') + b'\r'
        print(f"[TX] {msg!r}")
        self._ser.write(msg)
        self._ser.flush()
        time.sleep(wait)
        
        start = self._monotonic()
        last = start
        raw = bytearray()

        while self._monotonic() - start < timeout:
            n = self._ser.in_waiting
            if n:
                chunk = self._ser.read(n)
                raw += chunk
                last = self._monotonic()
            elif self._monotonic() - last > idle_gap:
                break
            time.sleep(0.05)

        decoded = raw.decode('ascii', errors='ignore').replace('\r', '\n').strip()
        return decoded

    def _commit_with_ack_done(self,
                              ack_timeout: float = _DEFAULT_ACK_TIMEOUT,
                              done_timeout: float = _DEFAULT_DONE_TIMEOUT) -> None:
        """
        After GW/GS, expect ACK (+/-/=), then send '!' and wait for '*'.
        """
        self._read_until_any(ACK_CHARS, timeout=ack_timeout)
        self._write_line('!')
        self._read_until_any(DONE_CHAR, timeout=done_timeout)

    # high-level operations

    def reset(self) -> str:
        resp = self._send_command_collect("RE", wait=0.2, timeout=max(5.0, self.settings['read_timeout_s']))
        if resp:
            print(f"[INFO] Reset response:\n{resp}")
        else:
            print("[WARN] No response to RE.")
        return resp

    def query_state(self) -> str:
        """
        Raw QM text (cached for probes parsing).
        """
        resp = self._send_command_collect("QM", wait=0.2, timeout=self.settings['read_timeout_s'])
        self._last_qm_cache = resp
        return resp

    # helpers

    def get_wavelength(self) -> float:
        text = self.query_state()
        m = re.search(r"Current\s*Wavelength\s*:?\s*([0-9]+(?:\.[0-9]+)?)", text, flags=re.I)
        if not m:
            raise ValueError("Could not parse current wavelength from QM.")
        wl = float(m.group(1))
        return wl

    def get_entrance_slit(self) -> float:
        text = self.query_state()
        m = re.search(r"Entrance\s*Slit\s*Width\s*:?\s*([0-9.]+)?\s*(um)?", text, flags=re.I)
        if not m:
            raise ValueError("Could not parse entrance slit width from QM.")

        value = float(m.group(1))
        unit = m.group(2)
        unit = unit.lower()
        if unit in ("mm",):
            value *= 1000.0

        print(f"[INFO] Entrance slit width: {value:.2f} um")
        return value

    def get_grating(self) -> int:
        text = self.query_state()
        m = re.search(r"Current\s*Grating\s*:?\s*(\d+)", text, flags=re.I)
        if not m:
            raise ValueError("Could not parse current grating from QM.")
        gr = int(m.group(1))
        return gr

    def get_gratings(self) -> List[str]:
        """
        Returns list of grating descriptions, index aligned to 1..N (element 0 unused for human parity).
        """
        text = self._last_qm_cache or self.query_state()
        m_n = re.search(r"Number\s*of\s*Gratings\s*:\s*(\d+)", text, flags=re.I)
        n = int(m_n.group(1)) if m_n else 3

        out = [None] * (n + 1)
        for i in range(1, n + 1):
            m_id = re.search(rf"Grating{i}\s*ID\s*([0-9]+)", text, flags=re.I)
            m_bl = re.search(rf"Grating{i}\s*Blaze\s*Wavelength\s*([0-9.]+)\s*(nm|um)", text, flags=re.I)
            if not (m_id and m_bl):
                out[i] = f"Grating {i}: (unparsed)"
                continue
            gr_id = int(m_id.group(1))
            blaze_val = float(m_bl.group(1))
            if m_bl.group(2).lower() == 'um':
                blaze_val *= 1000.0
            out[i] = f"{gr_id} g/mm, blaze = {blaze_val:.0f} nm"
            print(f"[INFO] Grating {i}: {out[i]}")
        return out

    def get_grating_limits(self) -> Dict[int, Tuple[float, float]]:
        """
        Parse max wavelength per grating from QM.
        Returns {gr_index: (min_nm, max_nm)}
        """
        text = self._last_qm_cache or self.query_state()
        m_n = re.search(r"Number\s*of\s*Gratings\s*:\s*(\d+)", text, flags=re.I)
        n = int(m_n.group(1)) if m_n else 3
        limits: Dict[int, Tuple[float, float]] = {}
        for i in range(1, n + 1):
            mx = re.search(rf"Grating{i}\s*Maximum\s*Wavelength\s*([0-9.]+)\s*(nm|um)", text, flags=re.I)
            mn = re.search(rf"Grating{i}\s*Minimum\s*Wavelength\s*([0-9.]+)\s*(nm|um)", text, flags=re.I)
            if not mx and not mn:
                continue
            def _to_nm(val: str, unit: str) -> float:
                v = float(val)
                return v * 1000.0 if unit.lower() == 'um' else v
            min_nm = _to_nm(mn.group(1), mn.group(2)) if mn else 0.0
            max_nm = _to_nm(mx.group(1), mx.group(2)) if mx else float('inf')
            limits[i] = (min_nm, max_nm)
        return limits

    def set_wavelength(self, value_nm: float) -> float:
        """
        Sets wavelength in nm, enforcing current grating limits.
        Returns the instrument-reported wavelength after the change.
        """
        gr = self.get_grating()
        limits = self.get_grating_limits()
        if gr in limits:
            lo, hi = limits[gr]
            if not (lo <= value_nm <= hi):
                raise ValueError(f"Wavelength {value_nm:.2f} nm out of range for grating {gr} "
                                 f"(allowed {lo:.2f}–{hi:.2f} nm)")
        self._ser.reset_input_buffer()
        self._write_line(f"GW {value_nm:.2f}")
        self._commit_with_ack_done()
        print("[INFO] Wavelength changed.")
        self.settings['wavelength_nm'] = float(value_nm)
        self._last_qm_cache = ""
        time.sleep(0.2)
        return self.get_wavelength()

    def set_entrance_slit(self, width_um: float) -> float:
        if 1 <= width_um <= 9:
            cmd_value = 0
        else:
            cmd_value = int(width_um)

        self._ser.reset_input_buffer()
        self._write_line(f"AE {cmd_value}")
        self._commit_with_ack_done()

        print(f"[INFO] Entrance slit width changed to {cmd_value} um (requested {width_um} um).")
        self._last_qm_cache = ""
        time.sleep(0.2)
        return self.get_entrance_slit()

    def set_grating(self, gr_num: int) -> int:
        """
        Sets active grating (1..N). Returns instrument-reported grating after change.
        """
        if gr_num < 1:
            raise ValueError("Grating index must be >= 1.")
        self._ser.reset_input_buffer()
        self._write_line(f"GS {int(gr_num)}")
        self._commit_with_ack_done()
        print("[INFO] Grating changed.")
        # Sync cached setting + read back
        self.settings['grating'] = int(gr_num)
        self._last_qm_cache = ""
        time.sleep(0.2)
        return self.get_grating()


    @property
    def _PROBES(self) -> Dict[str, str]:
        return {
            "state block": "Raw QM text block",
            "current wavelength": "Wavelength in nm (float)",
            "current grating": "Active grating index (int)",
            "gratings": "List of grating descriptions",
            "grating limits": "Dict {gr_index: (min_nm, max_nm)}",
        }

    def _param_to_internal(self, param: str) -> str:
        """
        Map probe names to the underlying instrument query command.
        """
        if param == "state block":
            return "QM"
        elif param in ("current wavelength", "current grating", "gratings", "grating limits"):
            return "QM" 
        else:
            raise KeyError(f"Unknown probe '{param}'")

    def read_probes(self, key: str):
        """
        Unified probe access.
        """
        assert self._settings_initialized
        assert key in self._PROBES.keys()
        cmd = self._param_to_internal(key)
        if cmd == "QM":
            text = self.query_state() 
            if key == "state block":
                return text
            if key == "current wavelength":
                return self.get_wavelength()
            if key == "current grating":
                return self.get_grating()
            if key == "gratings":
                return self.get_gratings()
            if key == "grating limits":
                return self.get_grating_limits()
        raise KeyError(f"Unhandled probe '{key}'")

    def close(self):
        if self._ser and self._ser.is_open:
            self._ser.close()
            print("Spectrometer connection closed.")
        self._ser = None


if __name__ == "__main__":
    dev = Spectrometer(settings={
        'connection_type': 'COM',
        'com_port': 5,
        'read_timeout_s': 5.0,
    })

    #print(dev.read_probes("state block"))
    print("Current Wavelength (nm):", dev.read_probes("current wavelength"))
    print("Current Grating:", dev.read_probes("current grating"))
    print("Gratings:", dev.read_probes("gratings"))
    #dev.set_grating(2)
    #dev.set_wavelength(650.0)
    #dev.set_entrance_slit(30)
    dev.close()