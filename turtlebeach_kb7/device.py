"""
Hardware driver interface for Turtle Beach Command Series KB7 (VID 0x10F5, PID 0x5038).
Pure-Python implementation using native Windows Win32 HID APIs via ctypes.
"""

import sys
import time
import struct
from dataclasses import dataclass, field
from typing import Optional, Callable, Dict, Any, List, Tuple

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

# Protocol Command IDs (mi_01 Display Endpoint)
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

# Feature Report Constants (mi_02 COL06 Endpoint)
FEATURE_REQ_CMD_LCD_SETTINGS = 0xB8  # 164 bytes (Report ID 0x25)
FEATURE_REQ_CMD_SCREEN_KEYS  = 0xB9  # 584 bytes (Report ID 0x29)

REPORT_ID_LCD_SETTINGS       = 0x25
REPORT_ID_SCREEN_KEYS        = 0x29
REPORT_ID_SLOT_UPDATE        = 0x35

LEN_LCD_SETTINGS             = 164
LEN_SCREEN_KEYS              = 584
LEN_SLOT_UPDATE              = 12


GESTURES = {
    0: "up",
    1: "down",
    2: "move",
    3: "tap",
    4: "long_press",
    5: "swipe_left",
    6: "swipe_right"
}


@dataclass
class ScreenKey:
    """Represents a virtual touch key on the KB7 display (Numpad / Macro key)."""
    index: int
    key_code: int
    modifiers: int
    label: str


@dataclass
class LCDSettings:
    """Represents the active display configuration of the KB7 keyboard."""
    active_page: int
    timeout_seconds: int
    dim_timeout_seconds: int
    brightness: int
    widget_slots: List[Tuple[int, int]] = field(default_factory=list)  # (widget_type, widget_id)
    raw: bytes = b""


class KB7Device:
    """
    Controller for Turtle Beach Command Series KB7 Touch Display, Backlight & Events.
    """

    def __init__(self):
        self.display_handle = None
        self.touch_handle = None
        self.feat_handle = None
        self.display_path: Optional[str] = None
        self.touch_path: Optional[str] = None
        self.feat_path: Optional[str] = None

    def connect(self) -> bool:
        """
        Discovers and opens handles to the KB7 Display, Touch, and Feature HID interfaces.
        """
        if sys.platform != "win32":
            raise NotImplementedError("Direct Windows HID implementation currently supported.")

        from .win_hid import enumerate_kb7_endpoints, open_hid_handle

        endpoints = enumerate_kb7_endpoints()
        if not endpoints:
            raise ConnectionError("No Turtle Beach KB7 devices (10F5:5038) found.")

        for ep in endpoints:
            up = ep["usage_page"]
            u = ep["usage"]
            path = ep["path"]
            if up == USAGE_PAGE_DISPLAY and u == USAGE_DISPLAY:
                self.display_path = path
            elif up == USAGE_PAGE_TOUCH and u == USAGE_TOUCH:
                self.touch_path = path
            elif up == USAGE_PAGE_FEATURE and ep["feature_len"] > 0:
                self.feat_path = path

        if not self.display_path:
            raise ConnectionError("Found KB7 device, but Display interface (0xFF00:0x0001) is missing.")

        self.display_handle = open_hid_handle(self.display_path)

        if self.touch_path:
            try:
                self.touch_handle = open_hid_handle(self.touch_path)
            except Exception:
                self.touch_handle = None

        if self.feat_path:
            try:
                self.feat_handle = open_hid_handle(self.feat_path)
            except Exception:
                self.feat_handle = None

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
            if self.feat_handle:
                close_handle(self.feat_handle)
                self.feat_handle = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    # =========================================================================
    # DISPLAY STREAMING (UsagePage 0xFF00)
    # =========================================================================

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

    # =========================================================================
    # TOUCH EVENTS (UsagePage 0xFF02)
    # =========================================================================

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
            "gesture": GESTURES.get(sub_type, f"gesture_0x{sub_type:02x}"),
            "sub_type": sub_type,
            "slot_id": slot_id,
            "x": x,
            "y": y,
        }

    # =========================================================================
    # FEATURE REPORTS: BACKLIGHT, SETTINGS & SCREEN KEYS (UsagePage 0xFF03)
    # =========================================================================

    def get_lcd_settings(self) -> LCDSettings:
        """
        Queries current LCD settings (brightness, timeout, active page, slots)
        via Feature Command 0xB8 on UsagePage 0xFF03.
        """
        if not self.feat_handle:
            raise RuntimeError("Feature interface (0xFF03) not connected.")

        from .win_hid import hid_set_feature, hid_get_feature

        # Request 0xB8 report preparation
        req = bytes([0x05, 0x00, FEATURE_REQ_CMD_LCD_SETTINGS, 0x00, 0x00])
        if not hid_set_feature(self.feat_handle, req):
            raise IOError("Failed to send 0xB8 feature request to device.")

        time.sleep(0.05)  # Safe delay for firmware buffer preparation

        data = hid_get_feature(self.feat_handle, REPORT_ID_LCD_SETTINGS, LEN_LCD_SETTINGS)
        if len(data) < LEN_LCD_SETTINGS:
            raise IOError(f"Incomplete LCDSettings response from device ({len(data)} bytes).")

        active_page = int.from_bytes(data[6:10], "little")
        timeout_sec = int.from_bytes(data[10:14], "little")
        dim_sec     = int.from_bytes(data[14:18], "little")
        brightness  = int.from_bytes(data[18:22], "little")

        slots = []
        for i in range(22, 162, 4):
            w_type = int.from_bytes(data[i:i+2], "little")
            w_id   = int.from_bytes(data[i+2:i+4], "little")
            slots.append((w_type, w_id))

        return LCDSettings(
            active_page=active_page,
            timeout_seconds=timeout_sec,
            dim_timeout_seconds=dim_sec,
            brightness=brightness,
            widget_slots=slots,
            raw=data
        )

    def _write_lcd_settings(self, settings_data: bytearray) -> bool:
        """
        Recalculates 16-bit sum checksum and writes 164-byte LCDSettings report.
        """
        if not self.feat_handle:
            raise RuntimeError("Feature interface (0xFF03) not connected.")

        from .win_hid import hid_set_feature

        if len(settings_data) != LEN_LCD_SETTINGS:
            raise ValueError(f"Settings buffer must be exactly {LEN_LCD_SETTINGS} bytes.")

        # Checksum is sum of all bytes from index 0 to 161
        csum = sum(settings_data[:162]) & 0xFFFF
        settings_data[162:164] = csum.to_bytes(2, "little")

        res = hid_set_feature(self.feat_handle, bytes(settings_data))
        time.sleep(0.1)  # Inter-packet pacing delay matching official Swarm II timing
        return bool(res)

    def set_brightness(self, level: int) -> bool:
        """
        Sets screen backlight brightness (0 to 100%).
        """
        clamped = max(0, min(100, int(level)))
        settings = self.get_lcd_settings()
        buf = bytearray(settings.raw)
        buf[18:22] = clamped.to_bytes(4, "little")
        return self._write_lcd_settings(buf)

    def set_timeout(self, seconds: int) -> bool:
        """
        Sets screen sleep timeout in seconds.
        """
        sec = max(0, int(seconds))
        settings = self.get_lcd_settings()
        buf = bytearray(settings.raw)
        buf[10:14] = sec.to_bytes(4, "little")
        return self._write_lcd_settings(buf)

    def set_active_page(self, page_index: int) -> bool:
        """
        Sets active display page (1 to 5).
        """
        page = max(1, min(5, int(page_index)))
        settings = self.get_lcd_settings()
        buf = bytearray(settings.raw)
        buf[6:10] = page.to_bytes(4, "little")
        return self._write_lcd_settings(buf)

    def get_screen_keys(self) -> List[ScreenKey]:
        """
        Queries virtual touch keys (Numpad / Macro keys) via Feature Command 0xB9.
        """
        if not self.feat_handle:
            raise RuntimeError("Feature interface (0xFF03) not connected.")

        from .win_hid import hid_set_feature, hid_get_feature

        req = bytes([0x05, 0x00, FEATURE_REQ_CMD_SCREEN_KEYS, 0x00, 0x00])
        if not hid_set_feature(self.feat_handle, req):
            raise IOError("Failed to send 0xB9 feature request to device.")

        time.sleep(0.02)

        data = hid_get_feature(self.feat_handle, REPORT_ID_SCREEN_KEYS, LEN_SCREEN_KEYS)
        if len(data) < LEN_SCREEN_KEYS:
            raise IOError(f"Incomplete ScreenKeys response ({len(data)} bytes).")

        keys = []
        # Key entries start at byte offset 56 (0x38), each entry is 16 bytes
        idx = 0
        for off in range(56, 568, 16):
            chunk = data[off : off + 16]
            vk_code = chunk[0]
            mods = chunk[1]
            raw_label = chunk[3:16]
            # null-terminated string
            zero_idx = raw_label.find(b"\x00")
            if zero_idx != -1:
                label = raw_label[:zero_idx].decode("latin1", errors="ignore")
            else:
                label = raw_label.decode("latin1", errors="ignore")
            if vk_code != 0 or label:
                keys.append(ScreenKey(index=idx, key_code=vk_code, modifiers=mods, label=label))
            idx += 1

        return keys

    def update_widget_slot(
        self,
        page_idx: int,
        slot_idx: int,
        widget_type: int,
        widget_id: int,
        is_last: bool = False
    ) -> bool:
        """
        Sends an individual widget slot assignment update using Report ID 0x35 (12 bytes).
        
        Args:
            page_idx: 0-based page index (0 to 4)
            slot_idx: 0-based slot index (0 to 12)
            widget_type: Widget type ID (e.g. 2, 3)
            widget_id: Assigned widget / icon ID
            is_last: Flag indicating last slot in update batch
        """
        if not self.feat_handle:
            raise RuntimeError("Feature interface (0xFF03) not connected.")

        from .win_hid import hid_set_feature

        pkt = bytearray(LEN_SLOT_UPDATE)
        pkt[0] = REPORT_ID_SLOT_UPDATE          # 0x35
        pkt[1] = LEN_SLOT_UPDATE                # 0x0C (12)
        pkt[2] = (page_idx + 1) & 0xFF          # 1-indexed page
        pkt[3] = slot_idx & 0xFF                # 0-indexed slot
        pkt[4] = 1 if is_last else 0
        pkt[5] = 0x00
        pkt[6:8] = (widget_type & 0xFFFF).to_bytes(2, "little")
        pkt[8:10] = (widget_id & 0xFFFF).to_bytes(2, "little")

        csum = sum(pkt[:10]) & 0xFFFF
        pkt[10:12] = csum.to_bytes(2, "little")

        return hid_set_feature(self.feat_handle, bytes(pkt))

    def apply_template(self, page_idx: int, template_name: str) -> bool:
        """
        Applies a predefined layout template (e.g. 'numpad', 'telemetry', 'productivity')
        to the specified display page (0 to 4).
        """
        from .widgets import LAYOUT_TEMPLATES, lookup_widget

        template = LAYOUT_TEMPLATES.get(template_name.lower())
        if not template:
            raise ValueError(f"Unknown template '{template_name}'. Available: {list(LAYOUT_TEMPLATES.keys())}")

        total = len(template)
        for idx, app_id in enumerate(template):
            is_last = (idx == total - 1)
            # Default widget type: Type 3 for buttons/keys, Type 2 for telemetry
            widget_def = lookup_widget(app_id)
            w_type = 2 if widget_def.runtime_update else 3
            self.update_widget_slot(
                page_idx=page_idx,
                slot_idx=idx,
                widget_type=w_type,
                widget_id=app_id,
                is_last=is_last
            )
            # 100 ms delay matching the official firmware communication timing
            time.sleep(0.1)

        return True
