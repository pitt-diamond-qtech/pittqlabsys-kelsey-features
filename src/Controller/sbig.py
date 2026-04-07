import ctypes
import threading
import time
from typing import Optional

import numpy as np
import matplotlib.pyplot as plt
import sys, pathlib
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from src.core import Device, Parameter


class SBIGError(RuntimeError):
    """Exception for SBIG driver errors."""
    pass


class SBIGCamera(Device):
    """
    High-level Python wrapper for SBIG cameras using SBIGUDrv.dll.

    Features:
      - Full-quality single exposure: capture(exposure_ms)
      - Live mode: start_live(), get_image_fast(), stop_live()

    
    Minimal SBIG Camera device with probes:
        - gain
        - integration_time_ms
        - capture
    """

    _DEFAULT_SETTINGS = Parameter([
        Parameter("dll_path", "SBIGUDrv.dll", str, "Path to SBIG DLL"),
        Parameter("integration_time_ms", 100.0, float, "Exposure time", units="ms"),
        Parameter("gain", 0, int, "Camera gain"),
    ])

    # ---- Command constants (from sbigudrv.h) ----
    CC_START_EXPOSURE         = 1
    CC_END_EXPOSURE           = 2
    CC_READOUT_LINE           = 3
    CC_DUMP_LINES             = 4
    CC_SET_TEMPERATURE_REG    = 5
    CC_QUERY_TEMPERATURE      = 6
    CC_ACTIVATE_RELAY         = 7
    CC_PULSE_OUT              = 8
    CC_ESTABLISH_LINK         = 9
    CC_GET_DRIVER_INFO        = 10

    CC_GET_CCD_INFO           = 11
    CC_QUERY_COMMAND_STATUS   = 12

    CC_READ_OFFSET            = 16
    CC_OPEN_DRIVER            = 17
    CC_CLOSE_DRIVER           = 18

    CC_OPEN_DEVICE            = 27
    CC_CLOSE_DEVICE           = 28

    CC_USB_AD_CONTROL = 39

    CC_START_READOUT          = 35
    CC_GET_ERROR_STRING       = 36
    CC_END_READOUT            = 25  # from the 21-30 block in the header

    # USB A/D control commands
    USB_AD_IMAGING_GAIN       = 0

    # ---- enums ----
    CCD_IMAGING               = 0
    CCD_INFO_IMAGING          = 0

    # SBIG_DEVICE_TYPE
    DEV_USB                   = 0x7F00

    # QueryCommandStatus values
    CS_IDLE                   = 0
    CS_IN_PROGRESS            = 1
    CS_INTEGRATING            = 2
    CS_INTEGRATION_COMPLETE   = 3

    # Error codes (partial)
    CE_NO_ERROR               = 0
    CE_EXPOSURE_IN_PROGRESS   = 2

    # Exposure flags
    EXP_WAIT_FOR_TRIGGER_IN   = 0x80000000
    EXP_SEND_TRIGGER_OUT      = 0x40000000
    EXP_LIGHT_CLEAR           = 0x20000000
    EXP_MS_EXPOSURE           = 0x10000000
    EXP_FAST_READOUT          = 0x08000000
    EXP_DUAL_CHANNEL_MODE     = 0x04000000
    EXP_RIPPLE_CORRECTION     = 0x02000000
    EXP_TIME_MASK             = 0x00FFFFFF

    def __init__(self, name: Optional[str] = None, settings=None):
        """
        Initialize the camera, load the DLL, open driver/device, and establish link.
        """
        settings = settings or {}
    
        dll_path = settings.get("dll_path", "SBIGUDrv.dll")

        # Load DLL
        self._dll = ctypes.WinDLL(dll_path)

        # Configure function signature: short SBIGUnivDrvCommand(short, void*, void*)
        self._dll.SBIGUnivDrvCommand.argtypes = [
            ctypes.c_short,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        self._dll.SBIGUnivDrvCommand.restype = ctypes.c_short

        super().__init__(name, settings)

        # camera geometry (will be filled by _get_ccd_info)
        self.width: int = 1600
        self.height: int = 1200

        # live mode state
        self._live_thread: Optional[threading.Thread] = None
        self._live_running: bool = False
        self._live_exposure_ms: float = 200.0
        self._live_frame: Optional[np.ndarray] = None
        self._live_lock = threading.Lock()

        self._is_connected: bool = False

        # ---- do the low-level init ----
        self._open_driver()
        self._open_device_usb()
        self._establish_link()
        self._get_ccd_info()

        # software-tracked
        self._gain = self.settings["gain"]
        self._integration_time_ms = self.settings["integration_time_ms"]

        if self._gain != 0:
            self.set_gain(self._gain)

    @property
    def is_connected(self) -> bool:
        """Return Ture if the camera link has been successfully established."""
        return self._is_connected
    
    def update(self, settings: dict) -> None:
        """Apply a directory of settings to the device."""
        for key, value in settings.items():
            if key == "gain":
                self.set_gain(int(value))
            elif key == "integration_time_ms":
                self.set_integration_time(float(value))

    def read_probes(self,key: str):
        """"Return the current value of a named probe."""
        if key == "gain":
            return self.get_gain()
        elif key == "integration_time_ms":
            return self.get_integration_time()
        elif key == "image":
            return self.capture()
        else:
            raise KeyError(f"Unknown probe {key}. Valid probes: {list(self._PROBES)}")
        
    @property 
    def probes(self) -> dict:
        return {
            "gain": self.get_gain,
            "integration_time_ms": self.get_integration_time,
            "image": self.capture,
        }

    # =========================
    # Low-level helpers
    # =========================
    def _cmd(self, cmd: int, params=None, results=None) -> int:
        """
        Call SBIGUnivDrvCommand with optional params/results.
        params/results can be ctypes structures or arrays.
        """
        if params is None:
            p_params = None
        else:
            p_params = ctypes.byref(params)

        if results is None:
            p_results = None
        else:
            p_results = ctypes.byref(results)

        err = self._dll.SBIGUnivDrvCommand(ctypes.c_short(cmd), p_params, p_results)
        return int(err)

    def _check(self, err: int, where: str = "") -> None:
        if err != self.CE_NO_ERROR:
            raise SBIGError(f"SBIG error {err} in {where}")

    # ----- struct definitions (small ones) -----

    class _OpenDeviceParams(ctypes.Structure):
        _pack_ = 8
        _fields_ = [
            ("deviceType", ctypes.c_ushort),
            ("lptBaseAddress", ctypes.c_ushort),
            ("ipAddress", ctypes.c_uint32),
        ]

    class _EstablishLinkParams(ctypes.Structure):
        _pack_ = 8
        _fields_ = [
            ("sbigUseOnly", ctypes.c_ushort),
        ]

    class _EstablishLinkResults(ctypes.Structure):
        _pack_ = 8
        _fields_ = [
            ("cameraType", ctypes.c_ushort),
        ]

    class _GetCCDInfoParams(ctypes.Structure):
        _pack_ = 8
        _fields_ = [
            ("request", ctypes.c_ushort),
        ]

    class _StartExposureParams(ctypes.Structure):
        _pack_ = 8
        _fields_ = [
            ("ccd", ctypes.c_ushort),
            ("exposureTime", ctypes.c_uint32),
            ("abgState", ctypes.c_ushort),
            ("openShutter", ctypes.c_ushort),
        ]

    class _EndExposureParams(ctypes.Structure):
        _pack_ = 8
        _fields_ = [
            ("ccd", ctypes.c_ushort),
        ]

    class _QueryCommandStatusParams(ctypes.Structure):
        _pack_ = 8
        _fields_ = [
            ("command", ctypes.c_ushort),
        ]

    class _StartReadoutParams(ctypes.Structure):
        _pack_ = 8
        _fields_ = [
            ("ccd", ctypes.c_ushort),
            ("readoutMode", ctypes.c_ushort),
            ("top", ctypes.c_ushort),
            ("left", ctypes.c_ushort),
            ("height", ctypes.c_ushort),
            ("width", ctypes.c_ushort),
        ]

    class _EndReadoutParams(ctypes.Structure):
        _pack_ = 8
        _fields_ = [
            ("ccd", ctypes.c_ushort),
        ]

    class _ReadoutLineParams(ctypes.Structure):
        _pack_ = 8
        _fields_ = [
            ("ccd", ctypes.c_ushort),
            ("readoutMode", ctypes.c_ushort),
            ("pixelStart", ctypes.c_ushort),
            ("pixelLength", ctypes.c_ushort),
        ]

    class _USBADControlParams(ctypes.Structure):
        _pack_ = 8
        _fields_ = [
            ("command", ctypes.c_ushort),  # USB_AD_CONTROL_COMMAND
            ("data", ctypes.c_short),  # gain/offset value
        ]

    # =========================
    # Initialization steps
    # =========================
    def _open_driver(self):
        err = self._cmd(self.CC_OPEN_DRIVER, None, None)
        self._check(err, "OPEN_DRIVER")

    def _open_device_usb(self):
        params = self._OpenDeviceParams()
        params.deviceType = self.DEV_USB
        params.lptBaseAddress = 0
        params.ipAddress = 0

        err = self._cmd(self.CC_OPEN_DEVICE, params, None)
        self._check(err, "OPEN_DEVICE(USB)")

    def _establish_link(self):
        params = self._EstablishLinkParams()
        params.sbigUseOnly = 0

        results = self._EstablishLinkResults()
        err = self._cmd(self.CC_ESTABLISH_LINK, params, results)
        self._check(err, "ESTABLISH_LINK")
        self._is_connected = True

        # cameraType is available as results.cameraType
        # (e.g. ST-2K = 14)
        # print("cameraType:", results.cameraType)

    def _get_ccd_info(self):
        """
        Call GET_CCD_INFO for imaging chip and set width/height from mode 0.
        Uses raw byte buffer for the large result struct.
        """
        params = self._GetCCDInfoParams()
        params.request = self.CCD_INFO_IMAGING

        # struct size we derived from the header (392 bytes)
        buf_len = 392
        buf = (ctypes.c_uint8 * buf_len)()

        err = self._cmd(self.CC_GET_CCD_INFO, params, buf)
        self._check(err, "GET_CCD_INFO")

        # Parse minimal pieces from buf
        raw = bytes(buf)
        import struct

        # firmwareVersion (H), cameraType (H), name[64], readoutModes (H), padding (2)
        firmwareVersion, cameraType = struct.unpack_from("<HH", raw, 0)
        name_bytes = struct.unpack_from("64s", raw, 4)[0]
        readoutModes = struct.unpack_from("<H", raw, 4 + 64)[0]

        # First readoutInfo entry at offset 72
        base = 72
        (mode0,
         width0,
         height0,
         gain0,
         pixelWidth0,
         pixelHeight0) = struct.unpack_from("<HHHHII", raw, base)

        self.width = int(width0)
        self.height = int(height0)
        # You can print or log this if you like:
        # print("CCD name:", name_bytes.split(b"\x00",1)[0].decode("ascii","ignore"))
        # print("geometry:", self.width, "x", self.height)

    # =========================
    # Public API
    # =========================
    def close(self) -> None:
        """Close device and driver and unload resources."""
        try:
            self.stop_live()
        except Exception:
            pass

        # CLOSE_DEVICE
        try:
            self._cmd(self.CC_CLOSE_DEVICE, None, None)
        except Exception:
            pass

        # CLOSE_DRIVER
        try:
            self._cmd(self.CC_CLOSE_DRIVER, None, None)
        except Exception:
            pass

        self._is_connected = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val,exc_tb):
        self.close()

    # =========================
    # Gain control
    # =========================
    def set_gain(self, gain: int) -> None:
        """
        Set imaging A/D gain (camera-specific units).
        Typical range is small integers; check camera docs.
        """
        params = self._USBADControlParams()
        params.command = self.USB_AD_IMAGING_GAIN
        params.data = int(gain)

        err = self._cmd(self.CC_USB_AD_CONTROL, params, None)
        self._check(err, "set_gain")
        self._gain = int(gain)
        self.settings["gain"] = int(gain)

    def get_gain(self) -> int:
        """
        Return the last gain value we successfully set.
        This does NOT try to read it back from the camera,
        because the driver usually doesn't return that.
        """
        return self._gain

    # =========================
    # Integration time control
    # =========================
    def set_integration_time(self, exposure_ms: float) -> None:
        """
        Store the desired integration time (milliseconds) in the camera object.

        This does NOT immediately talk to the hardware; it just sets the value
        that capture() will use by default.
        """
        if exposure_ms <= 0:
            raise ValueError("exposure_ms must be > 0")
        self._integration_time_ms = float(exposure_ms)
        self.settings["integration_time_ms"] = float(exposure_ms)

    def get_integration_time(self) -> float:
        """
        Return the last integration time (milliseconds) that we stored.
        """
        return self._integration_time_ms

    # ---------- Single high-quality exposure ----------

    def capture(self, exposure_ms=None) -> np.ndarray:
        """
        Take a single high-quality exposure and return a uint16 image.
        If exposure_ms is None, use the last value set with set_integration_time().
        """
        if exposure_ms is None:
            exposure_ms = self._integration_time_ms
        else:
            # update stored value so get_integration_time() stays in sync
            self._integration_time_ms = float(exposure_ms)

        # 1) Start exposure
        exp = self._StartExposureParams()
        exp.ccd = self.CCD_IMAGING

        # encode exposure in ms using flag EXP_MS_EXPOSURE
        ms = int(max(1, round(exposure_ms)))
        exp.exposureTime = (ms & self.EXP_TIME_MASK) | self.EXP_MS_EXPOSURE

        exp.abgState = 0      # ABG_LOW7
        exp.openShutter = 1   # SC_OPEN_SHUTTER

        err = self._cmd(self.CC_START_EXPOSURE, exp, None)
        self._check(err, "START_EXPOSURE")

        # 2) Poll for integration complete
        status = self.CS_INTEGRATING
        start_t = time.time()
        timeout = 600.0  # 10 min safety

        qparams = self._QueryCommandStatusParams()
        qparams.command = self.CC_START_EXPOSURE
        status_val = ctypes.c_ushort(0)

        while status != self.CS_INTEGRATION_COMPLETE:
            if time.time() - start_t > timeout:
                raise SBIGError("Exposure timed out")

            time.sleep(0.05)

            err = self._cmd(self.CC_QUERY_COMMAND_STATUS,
                            qparams,
                            status_val)
            self._check(err, "QUERY_COMMAND_STATUS")
            status = status_val.value

        # 3) End exposure
        endp = self._EndExposureParams()
        endp.ccd = self.CCD_IMAGING
        err = self._cmd(self.CC_END_EXPOSURE, endp, None)
        self._check(err, "END_EXPOSURE")

        # 4) Start readout
        sr = self._StartReadoutParams()
        sr.ccd = self.CCD_IMAGING
        sr.readoutMode = 0  # mode 0 = 1x1 full frame
        sr.top = 0
        sr.left = 0
        sr.height = self.height
        sr.width = self.width

        err = self._cmd(self.CC_START_READOUT, sr, None)
        self._check(err, "START_READOUT")

        # 5) Read each line
        img = np.zeros((self.width, self.height), dtype=np.uint16)

        rlp = self._ReadoutLineParams()
        rlp.ccd = self.CCD_IMAGING
        rlp.readoutMode = 0
        rlp.pixelStart = 0
        rlp.pixelLength = self.width

        line_buf = (ctypes.c_ushort * self.width)()

        for y in range(self.height):
            err = self._cmd(self.CC_READOUT_LINE, rlp, line_buf)
            if err != self.CE_NO_ERROR:
                # make sure to end readout before failing
                self._end_readout_silent()
                raise SBIGError(f"READOUT_LINE error {err} on row {y}")
            # copy into numpy
            img[:, y] = np.frombuffer(line_buf, dtype=np.uint16, count=self.width)

        # 6) End readout
        self._end_readout_silent()

        return img

    def _end_readout_silent(self):
        try:
            er = self._EndReadoutParams()
            er.ccd = self.CCD_IMAGING
            self._cmd(self.CC_END_READOUT, er, None)
        except Exception:
            pass

    # ---------- Live / fast mode ----------

    def start_live(self, exposure_ms: float = 200.0):
        """
        Start live mode: a background thread repeatedly captures short exposures.
        The latest frame is available via get_image_fast().
        """
        if self._live_running:
            # already running; just update exposure time
            self._live_exposure_ms = exposure_ms
            return

        self._live_exposure_ms = exposure_ms
        self._live_running = True
        self._live_frame = None

        t = threading.Thread(target=self._live_loop, daemon=True)
        self._live_thread = t
        t.start()

    def _live_loop(self):
        while self._live_running:
            try:
                frame = self.capture(self._live_exposure_ms)
                with self._live_lock:
                    self._live_frame = frame
            except Exception as e:
                # you might want to log the error; for now we just stop live mode
                print("Live capture error:", e)
                self._live_running = False
                break

            # small pause to avoid hammering
            time.sleep(0.01)

    def get_image_fast(self) -> Optional[np.ndarray]:
        """
        Return the latest live frame (copy) or None if not yet available.
        """
        with self._live_lock:
            if self._live_frame is None:
                return None
            return self._live_frame.copy()

    def stop_live(self):
        """
        Stop live mode and join the background thread.
        """
        self._live_running = False
        t = self._live_thread
        if t is not None and t.is_alive():
            t.join(timeout=2.0)
        self._live_thread = None

if __name__ == "__main__":
    DLL_PATH = (
            r"C:\Users\duttlab\Desktop\pittqlabsys-kelsey-features\src\Controller\binary_files\sbigu64p\SBIGUDrv.dll")


    with SBIGCamera(settings={"dll_path": DLL_PATH,
                              "integration_time_ms": 100.0,
                              "gain": 2}) as cam:
        print("Connected:", cam.is_connected)
        print("Gain:", cam.read_probes("gain"))
        print("Integration time:", cam.read_probes("integration_time_ms"), "ms")
        print("CCD Geometry:", cam.width, "x", cam.height)

        cam.start_live(exposure_ms=100)
        print("Live mode started. Close the plot window to stop.")

        plt.ion()
        fig, ax = plt.subplots()
        im = None

        while plt.fignum_exists(fig.number):
            frame = cam.get_image_fast()
            if frame is None:
                continue
            if im is None:
                im = ax.imshow(frame, cmap="gray")
                cbar = plt.colorbar(im)
                cbar.set_label("Pixel Intensity")
            else:
                im.set_data(frame)
            if im is None:
                im = ax.imshow(frame, cmap="gray")
                cbar = plt.colorbar(im)
                cbar.set_label("Pixel Intensity")
            else:
                im.set_data(frame)

            ax.set_title("Live View")
            ax.set_xlabel("X Pixels")             
            ax.set_ylabel("Y Pixels")           
            plt.pause(0.01)

        cam.stop_live()
        print("Live mode stopped.")

        plt.ioff()
        plt.show()
        print("Done.")