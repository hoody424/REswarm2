"""
Hardware driver interface for Turtle Beach Command Series KB7 (VID 0x10F5, PID 0x5038).
Pure-Python implementation using native Windows Win32 HID APIs via ctypes.
"""

import sys
import time
import struct
from typing import Optional, Callable, Dict, Any, Tuple

# Constants
VID_TURTLE_BEACH = 0x10F5
PID_COMMAND_KB7  = 0x5038

# USB Interface Usage Pages
USAGE_PAGE_DISPLAY = 0xFF00
USAGE_DISPLAY      = 0x0001

USAGE_PAGE_TOUCH   = 0xFF02
USAGE_TOUCH        = 0x0001

USAGE_PAGE_FEATURE = 0xFF03
USAGE_FEATURE      = 0x0001

# Protocol Command IDs
CMD_START_UPDATE   = 0xA5
CMD_BLOCK_READY    = 0xF1
CMD_BLOCK_END      = 0xF2
CMD_UPDATE_END     = 0xFF

SLOT_BACKGROUND    = 0x00
SLOT_SCALED_BG     = 0x40
SLOT_ICON_BASE     = 0x41

BLOCK_SIZE         = 4096
CHUNK_PAYLOAD_MAX  = 62
HID_REPORT_SIZE    = 65


class KB7Device:
    """
    Controller for Turtle Beach Command Series KB7 Touch Display & Events.
    """

    def __init__(self):
        self.display_handle = None
        self.touch_handle = None
        self.display_path: Optional[str] = None
        self.touch_path: Optional[str] = None

    def connect(self) -> bool:
        """
        Discovers and opens handles to the KB7 Display and Touch HID interfaces.
        """
        if sys.platform != "win32":
            raise NotImplementedError("Direct Windows HID implementation currently supported.")

        from .win_hid import enumerate_kb7_endpoints, open_hid_handle

        endpoints = enumerate_kb7_endpoints()
        if not endpoints:
            raise ConnectionError("No Turtle Beach KB7 devices (10F5:5038) found.")

        # Find Display Endpoint (UsagePage 0xFF00, Usage 0x0001)
        for ep in endpoints:
            if ep["usage_page"] == USAGE_PAGE_DISPLAY and ep["usage"] == USAGE_DISPLAY:
                self.display_path = ep["path"]
            elif ep["usage_page"] == USAGE_PAGE_TOUCH and ep["usage"] == USAGE_TOUCH:
                self.touch_path = ep["path"]

        if not self.display_path:
            raise ConnectionError("Found KB7 device, but Display interface (0xFF00:0x0001) is missing.")

        self.display_handle = open_hid_handle(self.display_path)
        if self.touch_path:
            try:
                self.touch_handle = open_hid_handle(self.touch_path)
            except Exception:
                self.touch_handle = None

        return True

    def disconnect(self):
        """Closes all active device handles."""
        if sys.platform == "win32":
            from .win_hid import close_handle
            if self.display_handle:
                close_handle(self.display_handle)
                self.display_handle = None
            if self.touch_handle:
                close_handle(self.touch_handle)
                self.touch_handle = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def _write_and_read(self, payload: bytes) -> bytes:
        """
        Sends a 65-byte report (0x00 report ID + 64 bytes) and reads the 64-byte ACK.
        """
        from .win_hid import hid_write, hid_read

        if len(payload) != 64:
            raise ValueError(f"Payload must be exactly 64 bytes (got {len(payload)})")

        report = b"\x00" + payload
        hid_write(self.display_handle, report)
        ack = hid_read(self.display_handle, 64)
        return ack

    def upload_image(
        self,
        rgb565_data: bytes,
        slot_id: int = SLOT_BACKGROUND,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> bool:
        """
        Uploads an image in RGB565 Little-Endian format to the KB7 display.
        
        Args:
            rgb565_data: Raw 16-bit RGB565 data (800x480 = 768,000 bytes for background)
            slot_id: Target slot (0x00 for full background, 0x41+n for widgets)
            progress_callback: Optional callback func(sent_bytes, total_bytes)
        """
        if not self.display_handle:
            raise RuntimeError("Device not connected. Call connect() first.")

        from .win_hid import hid_write, hid_read

        total_bytes = len(rgb565_data)

        # -------------------------------------------------------------
        # STEP 1: Start LCD Image Update Process
        # -------------------------------------------------------------
        init_pkt = bytearray(64)
        init_pkt[0] = CMD_START_UPDATE
        init_pkt[1] = slot_id & 0xFF
        ack = self._write_and_read(bytes(init_pkt))
        if len(ack) < 2 or ack[0] != CMD_START_UPDATE or ack[1] != (slot_id & 0xFF):
            raise IOError(f"Device rejected update initialization: ACK {ack[:4].hex()}")

        # -------------------------------------------------------------
        # STEP 2: Transmit in 4096-Byte Blocks
        # -------------------------------------------------------------
        offset = 0
        while offset < total_bytes:
            block_len = min(BLOCK_SIZE, total_bytes - offset)

            # 2a: Send Ready to Start Block (0xF1)
            ready_pkt = bytearray(64)
            ready_pkt[0] = CMD_START_UPDATE
            ready_pkt[1] = CMD_BLOCK_READY
            ack = self._write_and_read(bytes(ready_pkt))
            if len(ack) < 2 or ack[0] != CMD_START_UPDATE or ack[1] != CMD_BLOCK_READY:
                raise IOError(f"Device rejected block start: ACK {ack[:4].hex()}")

            # 2b: Stream data in up to 62-byte chunks
            block_sent = 0
            while block_sent < block_len:
                chunk_len = min(CHUNK_PAYLOAD_MAX, block_len - block_sent)
                chunk_data = rgb565_data[offset + block_sent : offset + block_sent + chunk_len]

                chunk_pkt = bytearray(65)
                chunk_pkt[0] = 0x00               # Report ID
                chunk_pkt[1] = CMD_START_UPDATE   # 0xA5
                chunk_pkt[2] = chunk_len          # Length of chunk payload
                chunk_pkt[3 : 3 + chunk_len] = chunk_data

                # Send chunk output report
                hid_write(self.display_handle, bytes(chunk_pkt))
                # Wait for device acknowledgment
                hid_read(self.display_handle, 64)

                block_sent += chunk_len
                if progress_callback:
                    progress_callback(offset + block_sent, total_bytes)

            offset += block_len

            # 2c: Send End of Block (0xF2)
            end_block_pkt = bytearray(64)
            end_block_pkt[0] = CMD_START_UPDATE
            end_block_pkt[1] = CMD_BLOCK_END
            ack = self._write_and_read(bytes(end_block_pkt))
            if len(ack) < 2 or ack[0] != CMD_START_UPDATE or ack[1] != CMD_BLOCK_END:
                raise IOError(f"Device rejected block end: ACK {ack[:4].hex()}")

        # -------------------------------------------------------------
        # STEP 3: End LCD Image Update Process (0xFF)
        # -------------------------------------------------------------
        finish_pkt = bytearray(64)
        finish_pkt[0] = CMD_START_UPDATE
        finish_pkt[1] = CMD_UPDATE_END
        ack = self._write_and_read(bytes(finish_pkt))
        if len(ack) < 2 or ack[0] != CMD_START_UPDATE or ack[1] != CMD_UPDATE_END:
            raise IOError(f"Device rejected update completion: ACK {ack[:4].hex()}")

        return True

    def read_touch_event(self, timeout_ms: int = 1000) -> Optional[Dict[str, Any]]:
        """
        Polls for a touch screen event on interface mi_02 (UsagePage 0xFF02, Usage 0x0001).
        Returns a dictionary with parsed event details or None on timeout.
        """
        if not self.touch_handle:
            raise RuntimeError("Touch interface not available or not connected.")

        from .win_hid import hid_read_timeout

        report = hid_read_timeout(self.touch_handle, 12, timeout_ms)
        if not report or len(report) < 12:
            return None

        event_type = report[0]
        sub_type = report[1]
        slot_id = report[2]
        x = struct.unpack("<H", report[3:5])[0]
        y = struct.unpack("<H", report[5:7])[0]

        return {
            "raw": report.hex(),
            "event_type": event_type,
            "gesture": "down" if sub_type == 1 else ("move" if sub_type == 2 else "up"),
            "slot_id": slot_id,
            "x": x,
            "y": y,
        }
