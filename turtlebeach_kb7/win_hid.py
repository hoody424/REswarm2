"""
Windows Win32 ctypes wrapper for HID communication (SetupAPI, hid.dll, kernel32).
Zero external C dependencies required.
"""

import ctypes
from ctypes import wintypes
from typing import List, Dict, Any, Optional

# Load Windows DLLs
Kernel32 = ctypes.windll.kernel32
Hid = ctypes.windll.hid
SetupAPI = ctypes.windll.setupapi

# Structures
class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_ulong),
        ("Data2", ctypes.c_ushort),
        ("Data3", ctypes.c_ushort),
        ("Data4", ctypes.c_ubyte * 8)
    ]

class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("InterfaceClassGuid", GUID),
        ("Flags", wintypes.DWORD),
        ("Reserved", ctypes.POINTER(ctypes.c_ulong))
    ]

class HIDP_CAPS(ctypes.Structure):
    _fields_ = [
        ("Usage", wintypes.USHORT),
        ("UsagePage", wintypes.USHORT),
        ("InputReportByteLength", wintypes.USHORT),
        ("OutputReportByteLength", wintypes.USHORT),
        ("FeatureReportByteLength", wintypes.USHORT),
        ("Reserved", wintypes.USHORT * 17),
        ("NumberLinkCollectionNodes", wintypes.USHORT),
        ("NumberInputButtonCaps", wintypes.USHORT),
        ("NumberInputValueCaps", wintypes.USHORT),
        ("NumberInputDataIndices", wintypes.USHORT),
        ("NumberOutputButtonCaps", wintypes.USHORT),
        ("NumberOutputValueCaps", wintypes.USHORT),
        ("NumberOutputDataIndices", wintypes.USHORT),
        ("NumberFeatureButtonCaps", wintypes.USHORT),
        ("NumberFeatureValueCaps", wintypes.USHORT),
        ("NumberFeatureDataIndices", wintypes.USHORT)
    ]

class OVERLAPPED(ctypes.Structure):
    _fields_ = [
        ("Internal", ctypes.c_void_p),
        ("InternalHigh", ctypes.c_void_p),
        ("Offset", wintypes.DWORD),
        ("OffsetHigh", wintypes.DWORD),
        ("hEvent", wintypes.HANDLE)
    ]

# Constants
GENERIC_READ          = 0x80000000
GENERIC_WRITE         = 0x40000000
FILE_SHARE_READ       = 0x00000001
FILE_SHARE_WRITE      = 0x00000002
OPEN_EXISTING         = 3
FILE_FLAG_OVERLAPPED  = 0x40000000
INVALID_HANDLE_VALUE  = -1
DIGCF_PRESENT         = 0x00000002
DIGCF_DEVICEINTERFACE = 0x00000010


def enumerate_kb7_endpoints(vid: int = 0x10F5, pid: int = 0x5038) -> List[Dict[str, Any]]:
    """Enumerates all HID interface endpoints matching VID and PID."""
    hid_guid = GUID()
    Hid.HidD_GetHidGuid(ctypes.byref(hid_guid))

    hdev = SetupAPI.SetupDiGetClassDevsW(
        ctypes.byref(hid_guid), None, None, DIGCF_PRESENT | DIGCF_DEVICEINTERFACE
    )
    if hdev == INVALID_HANDLE_VALUE:
        return []

    dev_iface_data = SP_DEVICE_INTERFACE_DATA()
    dev_iface_data.cbSize = ctypes.sizeof(SP_DEVICE_INTERFACE_DATA)

    endpoints = []
    idx = 0
    vid_str = f"vid_{vid:04x}"
    pid_str = f"pid_{pid:04x}"

    try:
        while SetupAPI.SetupDiEnumDeviceInterfaces(
            hdev, None, ctypes.byref(hid_guid), idx, ctypes.byref(dev_iface_data)
        ):
            required_size = wintypes.DWORD()
            SetupAPI.SetupDiGetDeviceInterfaceDetailW(
                hdev, ctypes.byref(dev_iface_data), None, 0, ctypes.byref(required_size), None
            )

            buf = ctypes.create_string_buffer(required_size.value)
            # In 64-bit Windows, cbSize is 8 bytes
            ctypes.cast(buf, ctypes.POINTER(wintypes.DWORD))[0] = 8

            if SetupAPI.SetupDiGetDeviceInterfaceDetailW(
                hdev, ctypes.byref(dev_iface_data), buf, required_size.value, None, None
            ):
                path = ctypes.wstring_at(ctypes.addressof(buf) + 4)
                if vid_str in path.lower() and pid_str in path.lower():
                    # Query Capabilities
                    handle = Kernel32.CreateFileW(
                        path, 0, FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING, 0, None
                    )
                    caps = HIDP_CAPS()
                    preparsed = ctypes.c_void_p()
                    if handle != INVALID_HANDLE_VALUE:
                        if Hid.HidD_GetPreparsedData(handle, ctypes.byref(preparsed)):
                            Hid.HidP_GetCaps(preparsed, ctypes.byref(caps))
                            Hid.HidD_FreePreparsedData(preparsed)
                        Kernel32.CloseHandle(handle)

                        endpoints.append({
                            "path": path,
                            "usage_page": caps.UsagePage,
                            "usage": caps.Usage,
                            "input_len": caps.InputReportByteLength,
                            "output_len": caps.OutputReportByteLength,
                            "feature_len": caps.FeatureReportByteLength
                        })
            idx += 1
    finally:
        SetupAPI.SetupDiDestroyDeviceInfoList(hdev)

    return endpoints


def open_hid_handle(path: str) -> int:
    """Opens an asynchronous (overlapped) handle to an HID device path."""
    handle = Kernel32.CreateFileW(
        path,
        GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None,
        OPEN_EXISTING,
        FILE_FLAG_OVERLAPPED,
        None
    )
    if handle == INVALID_HANDLE_VALUE:
        err = Kernel32.GetLastError()
        raise IOError(f"Failed to open HID device '{path}': Win32 Error {err}")
    return handle


def close_handle(handle: int):
    """Closes an open Win32 handle."""
    if handle and handle != INVALID_HANDLE_VALUE:
        Kernel32.CloseHandle(handle)


def hid_write(handle: int, data: bytes):
    """Writes an HID report to the device synchronously using Overlapped I/O."""
    overlapped = OVERLAPPED()
    overlapped.hEvent = Kernel32.CreateEventW(None, True, False, None)

    written = wintypes.DWORD(0)
    buf = (ctypes.c_ubyte * len(data))(*data)
    try:
        res = Kernel32.WriteFile(
            handle, buf, len(data), ctypes.byref(written), ctypes.byref(overlapped)
        )
        if not res:
            err = Kernel32.GetLastError()
            if err == 997:  # ERROR_IO_PENDING
                Kernel32.WaitForSingleObject(overlapped.hEvent, 2000)
                Kernel32.GetOverlappedResult(handle, ctypes.byref(overlapped), ctypes.byref(written), False)
            else:
                raise IOError(f"WriteFile failed with error {err}")
    finally:
        Kernel32.CloseHandle(overlapped.hEvent)


def hid_read(handle: int, length: int) -> bytes:
    """Reads an HID report from the device."""
    return hid_read_timeout(handle, length, timeout_ms=3000)


def hid_read_timeout(handle: int, length: int, timeout_ms: int = 1000) -> bytes:
    """Reads an HID report with a specific timeout in milliseconds."""
    overlapped = OVERLAPPED()
    overlapped.hEvent = Kernel32.CreateEventW(None, True, False, None)

    # Windows ReadFile includes 1-byte report ID if length is matched
    read_buf_size = length + 1
    buf = (ctypes.c_ubyte * read_buf_size)()
    read_bytes = wintypes.DWORD(0)

    try:
        res = Kernel32.ReadFile(
            handle, buf, read_buf_size, ctypes.byref(read_bytes), ctypes.byref(overlapped)
        )
        if not res:
            err = Kernel32.GetLastError()
            if err == 997:  # ERROR_IO_PENDING
                wait_res = Kernel32.WaitForSingleObject(overlapped.hEvent, timeout_ms)
                if wait_res == 0:  # WAIT_OBJECT_0
                    Kernel32.GetOverlappedResult(
                        handle, ctypes.byref(overlapped), ctypes.byref(read_bytes), False
                    )
                else:
                    Kernel32.CancelIo(handle)
                    return b""
            else:
                raise IOError(f"ReadFile failed with error {err}")

        out_data = bytes(buf[:read_bytes.value])
        # Strip leading report ID if present and returned length is read_buf_size
        if len(out_data) == read_buf_size:
            return out_data[1:]
        return out_data[:length]
    finally:
        Kernel32.CloseHandle(overlapped.hEvent)
