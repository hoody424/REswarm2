"""
Core HID driver for the Turtle Beach Command Series KB7 LCD Display & Telemetry protocol.

Grounded in disassembly of COMMAND_KB7.dll and Command_KB7_Profile_Mgr.dat:
- SetBg (0x0029D5C0), UpdateLcdImage (0x0029FF80), LvglImageConverter (0x0023CE40)
- LCDSettings (Report 0x25, 164 bytes: 3 pages x 13 4-byte slots starting at offset 10)
- ScreenKeys (Report 0x29, 584 bytes: 3 pages x 12 16-byte key bindings starting at offset 6)
- SlotUpdate (Report 0x35, 12 bytes: single-slot live update)
- DisplayConfig (Report 0x0D, 20 bytes: byte 2 = timeout, byte 3 = brightness/10, byte 8 = custom_bg_flag)
"""

from dataclasses import dataclass
import struct
import time
from typing import Callable, List, Optional, Tuple, Union
from pathlib import Path

try:
    import hid
except ImportError:
    hid = None

from .image import (
    LCD_HEIGHT,
    LCD_WIDTH,
    THUMB_HEIGHT,
    THUMB_WIDTH,
    convert_to_rgb565,
)
from .widgets import (
    APP_ID_TO_FIRMWARE,
    FIRMWARE_TO_APP_ID,
    LAYOUT_TEMPLATES,
    SCREEN_KEY_BINDINGS,
)

# USB Hardware Identifiers
TURTLE_BEACH_VID = 0x10F5
COMMAND_KB7_PIDS = (0x5038, 0x503A)  # 0x5038 = ANSI/ISO, 0x503A = JIS

# HID Usage Pages (Windows SetupAPI / HidP_GetCaps)
USAGE_PAGE_DISPLAY = 0xFF00          # Interface mi_01: 65B Input/Output Display Stream (0xA5)
USAGE_DISPLAY = 0x0001
USAGE_PAGE_TOUCH = 0xFF02            # Interface mi_02&col04: 12B Input Touch Digitizer
USAGE_TOUCH = 0x0001
USAGE_PAGE_FEATURE = 0xFF03          # Interface mi_02&col06: 1044B Feature Reports

# Feature Request Prep Commands (Report ID 0x05)
FEATURE_REQ_CMD_LCD_SETTINGS = 0xB8  # Prepares Report 0x25 (164 bytes)
FEATURE_REQ_CMD_SCREEN_KEYS = 0xB9   # Prepares Report 0x29 (584 bytes)

# Feature Report IDs
REPORT_ID_SYNC_STATUS = 0x04
REPORT_ID_DISPLAY_CONFIG = 0x0D      # 20B Display Config (byte 2=timeout, byte 3=brightness/10, byte 8=bg_flag)
REPORT_ID_LIGHTING = 0x11            # 348B Backlight / RGB Configuration
REPORT_ID_SYS_METRICS = 0x16         # 104B Live System Telemetry & Audio Mixer
REPORT_ID_LCD_SETTINGS = 0x25        # 164B LCD Page/Slot Layout (3 pages x 13 slots at offset 10)
REPORT_ID_SCREEN_KEYS = 0x29         # 584B Screen Key Bindings (3 pages x 12 slots x 16B at offset 6)
REPORT_ID_SLOT_UPDATE = 0x35         # 12B Single Slot Assignment

# Stream Opcodes (Report ID 0xA5 on Usage Page 0xFF00)
CMD_START_UPDATE = 0xA5
CMD_BLOCK_READY = 0xF1
CMD_BLOCK_END = 0xF2
CMD_UPDATE_END = 0xFF

# Image Slots
SLOT_BACKGROUND = 0x00
SLOT_BACKGROUND_THUMB = 0x40
SLOT_SCALED_BG = 0x40

# Display Stream Constants
BLOCK_SIZE = 4096
CHUNK_PAYLOAD_MAX = 62
PACKET_SIZE = 64

GESTURES = {
    0: "up",
    1: "down",
    2: "move",
    3: "tap",
    4: "long_press",
    5: "swipe_left",
    6: "swipe_right",
}

# Exact factory Report 0x25 (164 bytes) from Command_KB7_Profile_Mgr.dat:
# Page 0 (offset 10..62): Default 1 / 6-Island (Speaker Mute, Screenshot, Emoji, Print, ScrLk, Break, Ins, Home, End, Del, PgUp, PgDown) + (2,0)
# Page 1 (offset 62..114): Numpad (7, 8, 9, 4, 5, 6, 1, 2, 3, 0 [2x1], empty, .) + (3,0)
# Page 2 (offset 114..162): Default 2 (CPU Temp, CPU Load, GPU Load, GPU Temp, RAM, Clock, Weather, Wheel, Actuation, Net, TaskMgr, Lock)
FACTORY_LCD_SETTINGS = (
    b"%\xa4\x00\x00\x00\x00\x01\x00\x00\x00"
    b";\x00\x00\x00>\x00\x00\x00H\x00\x00\x00\x03\x00\x0b\x00"
    b"\x03\x00\x0c\x00\x03\x00\r\x00\x03\x00\x0e\x00\x03\x00\x0f\x00"
    b"\x03\x00\x12\x00\x03\x00\x11\x00\x03\x00\x10\x00\x03\x00\x13\x00"
    b"\x02\x00\x00\x00"
    b"\x03\x00\x07\x00\x03\x00\x08\x00\x03\x00\t\x00\x03\x00\x04\x00"
    b"\x03\x00\x05\x00\x03\x00\x06\x00\x03\x00\x01\x00\x03\x00\x02\x00"
    b"\x03\x00\x03\x00\x03\x00\x00\x00\x00\x00\x00\x00\x03\x00\n\x00"
    b"\x03\x00\x00\x00"
    b"\x15\x00\x00\x00\x16\x00\x00\x00\x17\x00\x00\x00\x18\x00\x00\x00"
    b"\x19\x00\x00\x00\x1a\x00\x00\x00\x1b\x00\x00\x00\x1c\x00\x00\x00"
    b"\x1d\x00\x00\x00\x1e\x00\x00\x00\x1f\x00\x00\x00 \x00\x00\x00"
    b"\xc8\x03"
)


def _build_factory_screen_keys() -> bytes:
    """Build the exact 584-byte factory Report 0x29 (ScreenKeys) from Command_KB7_Profile_Mgr.dat."""
    buf = bytearray(584)
    buf[0] = REPORT_ID_SCREEN_KEYS
    buf[1] = 0x48
    buf[2] = 0x02
    p0_entries = [
        (3, 0x46, "PRINT"),
        (4, 0x47, "SCR LK"),
        (5, 0x48, "BREAK"),
        (6, 0x49, "INS"),
        (7, 0x4A, "HOME"),
        (8, 0x4B, "PGUP"),
        (9, 0x4C, "DEL"),
        (10, 0x4D, "END"),
        (11, 0x4E, "PGDOWN"),
    ]
    for slot_idx, hid_code, label in p0_entries:
        off = 6 + slot_idx * 16
        buf[off + 2] = hid_code
        buf[off + 3] = 0x0C
        enc = label.encode("ascii")[:11]
        buf[off + 5 : off + 5 + len(enc)] = enc

    p1_entries = [
        (0, 0x5F, "7"),
        (1, 0x60, "8"),
        (2, 0x61, "9"),
        (3, 0x5C, "4"),
        (4, 0x5D, "5"),
        (5, 0x5E, "6"),
        (6, 0x59, "1"),
        (7, 0x5A, "2"),
        (8, 0x5B, "3"),
        (11, 0x63, "."),
    ]
    for slot_idx, hid_code, label in p1_entries:
        off = 6 + (12 + slot_idx) * 16
        buf[off + 2] = hid_code
        buf[off + 3] = 0x0C
        enc = label.encode("ascii")[:11]
        buf[off + 5 : off + 5 + len(enc)] = enc

    chk = sum(buf[:-2]) & 0xFFFF
    struct.pack_into("<H", buf, 582, chk)
    return bytes(buf)


FACTORY_SCREEN_KEYS = _build_factory_screen_keys()


@dataclass
class ScreenKeyEntry:
    index: int
    key_code: int
    modifiers: int
    label: str


class LCDSettingsBuffer(bytearray):
    """
    164-byte Report 0x25 buffer that also exposes structured properties
    (`.active_page`, `.brightness`, `.timeout_seconds`, `.dim_timeout_seconds`, `.widget_slots`)
    for compatibility with `KB7Daemon` and `KB7CommandCenterApp`.
    """

    def __init__(self, data: Union[bytes, bytearray] = FACTORY_LCD_SETTINGS, brightness: int = 80, timeout_sec: int = 60):
        super().__init__(data)
        self._brightness = brightness
        self._timeout_sec = timeout_sec

    @property
    def active_page(self) -> int:
        return max(1, min(3, int(self[6]) if len(self) > 6 and self[6] else 1))

    @property
    def brightness(self) -> int:
        return self._brightness

    @property
    def timeout_seconds(self) -> int:
        return self._timeout_sec

    @property
    def dim_timeout_seconds(self) -> int:
        return max(15, self._timeout_sec // 2)

    @property
    def widget_slots(self) -> List[Tuple[int, int]]:
        """
        Return 36 `(w_type, app_id)` pairs (3 pages x 12 slots per page)
        decoded from byte offsets `10 + page_idx * 52 + slot_idx * 4`.
        """
        slots: List[Tuple[int, int]] = []
        for page_idx in range(3):
            for slot_idx in range(12):
                off = 10 + page_idx * 52 + slot_idx * 4
                wt, wid = struct.unpack_from("<HH", self, off)
                app_id = FIRMWARE_TO_APP_ID.get((wt, wid), 0)
                slots.append((wt, app_id))
        return slots


def compute_checksum16(data: Union[bytes, bytearray]) -> int:
    """Compute the 16-bit Little-Endian byte sum checksum over `data`."""
    return sum(data) & 0xFFFF


def append_checksum16(buf: bytearray) -> bytearray:
    """Write the 16-bit byte sum of `buf[:-2]` into the final 2 bytes (`buf[-2:]`)."""
    chk = compute_checksum16(buf[:-2])
    struct.pack_into("<H", buf, len(buf) - 2, chk)
    return buf


class KB7Device:
    """
    Driver interface for the Turtle Beach Command Series KB7 keyboard display.

    Manages all three Windows HID interfaces via native `win_hid` (zero C dependencies):
    - `display_handle` (Usage Page `0xFF00`): High-speed 64-byte Interrupt Out (`0xA5`) and Ack In (`0xA5`)
    - `touch_handle`   (Usage Page `0xFF02`): 12-byte Touch Digitizer Input Reports
    - `feat_handle`    (Usage Page `0xFF03`): Feature Reports (`0x04`, `0x05`, `0x0D`, `0x11`, `0x16`, `0x25`, `0x29`, `0x35`)
    """

    def __init__(self) -> None:
        self.display_handle: Optional[int] = None
        self.touch_handle: Optional[int] = None
        self.feat_handle: Optional[int] = None
        self.display_path: Optional[str] = None
        self.touch_path: Optional[str] = None
        self.feat_path: Optional[str] = None
        self.product_id: Optional[int] = 0x5038
        self._screen_keys_cache: bytearray = bytearray(FACTORY_SCREEN_KEYS)

    # ------------------------------------------------------------------
    # Discovery & Connection Management
    # ------------------------------------------------------------------

    def open(self) -> bool:
        """Open Display (`0xFF00`), Touch (`0xFF02`), and Feature (`0xFF03`) HID handles."""
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

    def connect(self) -> bool:
        """Alias for `open()` used by `KB7Daemon`."""
        return self.open()

    def close(self) -> None:
        """Close all open Win32 HID handles."""
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

    def disconnect(self) -> None:
        """Alias for `close()` used by `KB7Daemon`."""
        self.close()

    def __enter__(self) -> "KB7Device":
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Low-Level Control & Feature Report Primitives
    # ------------------------------------------------------------------

    def wait_ready(self, max_retries: int = 20, poll_interval_sec: float = 0.015) -> bool:
        """
        Poll Feature Report `0x04` (4 bytes) until `buf[1] == 0x01` (Device Ready).
        Replicates `WaitReady_0x226660` in `COMMAND_KB7.dll`.
        """
        if not self.feat_handle:
            return False
        from .win_hid import hid_get_feature

        for _ in range(max_retries):
            try:
                resp = hid_get_feature(self.feat_handle, REPORT_ID_SYNC_STATUS, 4)
                if resp and len(resp) >= 2:
                    if resp[1] == 1:
                        return True
                    if resp[1] in (2, 4):
                        return False
            except Exception:
                pass
            time.sleep(poll_interval_sec)
        return False

    def send_feature_report(
        self,
        buf: Union[bytes, bytearray],
        add_checksum: bool = True,
        post_delay_sec: float = 0.050,
        wait_sync: bool = False,
    ) -> bool:
        """
        Send a Feature Report on the Feature interface (`0xFF03`), optionally computing
        the 16-bit sum checksum in the last 2 bytes.
        """
        if not self.feat_handle:
            raise RuntimeError("Feature interface (0xFF03) not connected.")
        from .win_hid import hid_set_feature

        payload = bytearray(buf)
        if add_checksum:
            append_checksum16(payload)

        ok = hid_set_feature(self.feat_handle, bytes(payload))
        if post_delay_sec > 0:
            time.sleep(post_delay_sec)
        if wait_sync:
            self.wait_ready()
        return bool(ok)

    def get_feature_report(self, report_id: int, length: int) -> bytearray:
        """Read a Feature Report from the Feature interface (`0xFF03`)."""
        if not self.feat_handle:
            raise RuntimeError("Feature interface (0xFF03) not connected.")
        from .win_hid import hid_get_feature, hid_set_feature

        if report_id == REPORT_ID_LCD_SETTINGS:
            req = bytes([0x05, 0x00, FEATURE_REQ_CMD_LCD_SETTINGS, 0x00, 0x00])
            hid_set_feature(self.feat_handle, req)
            time.sleep(0.05)
        elif report_id == REPORT_ID_SCREEN_KEYS:
            req = bytes([0x05, 0x00, FEATURE_REQ_CMD_SCREEN_KEYS, 0x00, 0x00])
            hid_set_feature(self.feat_handle, req)
            time.sleep(0.02)

        data = hid_get_feature(self.feat_handle, report_id, length)
        return bytearray(data)

    # ------------------------------------------------------------------
    # Stream Interface (0xFF00) & Image Upload (0xA5)
    # ------------------------------------------------------------------

    def _write_and_read(self, payload: bytes) -> bytes:
        """
        Send a 65-byte report (`0x00` report ID + 64 bytes) on `0xFF00` and read the 64-byte ACK.
        """
        from .win_hid import hid_read, hid_write

        if len(payload) != 64:
            raise ValueError(f"Payload must be exactly 64 bytes (got {len(payload)})")

        report = b"\x00" + payload
        hid_write(self.display_handle, report)
        return hid_read(self.display_handle, 64)

    @staticmethod
    def _invoke_progress(cb: Optional[Callable], msg: str, pct: int, done: int, total: int) -> None:
        if not cb:
            return
        try:
            cb(msg, pct)
        except TypeError:
            try:
                cb(done, total)
            except Exception:
                pass

    def upload_raw_buffer(
        self,
        raw_bytes: bytes,
        slot_id: int = 0x00,
        progress_callback: Optional[Callable] = None,
    ) -> bool:
        """
        Stream a raw buffer (`480x800` RGB565 for Slot `0x00`, or `142x148` RGB565+Alpha
        for Slot `0x40`) to the KB7 flash memory over Usage Page `0xFF00`.
        """
        if not self.display_handle:
            raise RuntimeError("Device not connected. Call open() or connect() first.")

        from .win_hid import hid_read, hid_write

        total_bytes = len(raw_bytes)

        # STEP 1: Start LCD Image Update Process (0xA5 <slot_id>)
        init_pkt = bytearray(64)
        init_pkt[0] = CMD_START_UPDATE
        init_pkt[1] = slot_id & 0xFF
        ack = self._write_and_read(bytes(init_pkt))
        if len(ack) < 2 or ack[0] != CMD_START_UPDATE or ack[1] != (slot_id & 0xFF):
            raise IOError(f"Device rejected update initialization: ACK {ack[:4].hex()}")

        # STEP 2: Transmit in 4096-Byte Blocks
        offset = 0
        while offset < total_bytes:
            block_len = min(BLOCK_SIZE, total_bytes - offset)

            # 2a: Send Ready to Start Block (0xA5 0xF1)
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
                chunk_data = raw_bytes[offset + block_sent : offset + block_sent + chunk_len]

                chunk_pkt = bytearray(65)
                chunk_pkt[0] = 0x00               # Report ID
                chunk_pkt[1] = CMD_START_UPDATE   # 0xA5
                chunk_pkt[2] = chunk_len          # Length of chunk payload
                chunk_pkt[3 : 3 + chunk_len] = chunk_data

                hid_write(self.display_handle, bytes(chunk_pkt))
                hid_read(self.display_handle, 64)

                block_sent += chunk_len

            offset += block_len

            # 2c: Send End of Block (0xA5 0xF2)
            end_block_pkt = bytearray(64)
            end_block_pkt[0] = CMD_START_UPDATE
            end_block_pkt[1] = CMD_BLOCK_END
            ack = self._write_and_read(bytes(end_block_pkt))
            if len(ack) < 2 or ack[0] != CMD_START_UPDATE or ack[1] != CMD_BLOCK_END:
                raise IOError(f"Device rejected block end: ACK {ack[:4].hex()}")

            pct = int(offset * 100 / max(1, total_bytes))
            self._invoke_progress(
                progress_callback,
                f"Uploading slot 0x{slot_id:02X}: {pct}% ({offset // 1024} / {total_bytes // 1024} KB)",
                pct,
                offset,
                total_bytes,
            )

        # STEP 3: End LCD Image Update Process (0xA5 0xFF)
        finish_pkt = bytearray(64)
        finish_pkt[0] = CMD_START_UPDATE
        finish_pkt[1] = CMD_UPDATE_END
        ack = self._write_and_read(bytes(finish_pkt))
        if len(ack) < 2 or ack[0] != CMD_START_UPDATE or ack[1] != CMD_UPDATE_END:
            raise IOError(f"Device rejected update completion: ACK {ack[:4].hex()}")

        return True

    def upload_image(
        self,
        image_source,
        slot_id: int = 0x00,
        width: int = LCD_WIDTH,
        height: int = LCD_HEIGHT,
        include_alpha: Optional[bool] = None,
        progress_callback: Optional[Callable] = None,
    ) -> bool:
        """
        Convert an image or PIL Image to RGB565 (or RGB565 + Alpha for `slot_id != 0`)
        and upload it to the specified `slot_id`.
        """
        if include_alpha is None:
            include_alpha = (slot_id != 0x00)
        raw_buf = convert_to_rgb565(
            image_source,
            width=width,
            height=height,
            include_alpha=include_alpha,
        )
        return self.upload_raw_buffer(raw_buf, slot_id=slot_id, progress_callback=progress_callback)

    def set_background_mode(self, mode: int = 1) -> bool:
        """
        Set `byte[8]` (`0x2360`) of Feature Report `0x0D` (20 bytes):
        - `mode = 1`: Custom Wallpaper active (`SetBg` at `0x0029D8B3` in `COMMAND_KB7.dll`)
        - `mode = 0`: Built-in Factory Wallpaper active
        """
        buf = self.get_display_config()
        buf[8] = 1 if mode else 0
        return self.send_feature_report(buf, add_checksum=True, post_delay_sec=0.150, wait_sync=True)

    def get_background_mode(self) -> int:
        buf = self.get_display_config()
        return int(buf[8])

    def refresh_screen(self) -> bool:
        lcd_buf = self.get_lcd_settings()
        return self.send_feature_report(lcd_buf, add_checksum=True, post_delay_sec=0.050, wait_sync=True)

    def upload_theme(
        self,
        image_source,
        progress_callback: Optional[Callable] = None,
    ) -> bool:
        """
        Upload a complete theme/wallpaper to the KB7 display, replicating `SetBg`
        (`0x0029D5C0` in `COMMAND_KB7.dll`) with 100% binary accuracy:
        1. Scales & center-crops to `480x800` (Mode 0: 768,000B RGB565 LE) and streams to Slot `0x00`.
        2. Waits 5.0 seconds (`Sleep(5000)` at `0x0029D735`) while the MCU commits flash & refreshes LVGL.
        3. Scales & center-crops to `142x148` (Mode 1: 42,032B RGB565 LE + 21,016B Alpha = 63,048B)
           and streams to Slot `0x40`.
        4. Sets `byte[8] = 1` in Feature Report `0x0D` (20 bytes) and commits via `SetFeatureReport`.
        """
        full_buf = convert_to_rgb565(
            image_source,
            width=LCD_WIDTH,
            height=LCD_HEIGHT,
            include_alpha=False,
        )
        thumb_buf = convert_to_rgb565(
            image_source,
            width=THUMB_WIDTH,
            height=THUMB_HEIGHT,
            include_alpha=True,
        )
        total_bytes = len(full_buf) + len(thumb_buf)

        def _cb_main(msg_or_done, pct_or_total=0) -> None:
            if isinstance(msg_or_done, str):
                scaled_pct = int(pct_or_total * 0.85)
                self._invoke_progress(
                    progress_callback,
                    f"Uploading 480x800 Wallpaper (Slot 0x00): {pct_or_total}%",
                    scaled_pct,
                    int(len(full_buf) * pct_or_total / 100),
                    total_bytes,
                )
            else:
                done = int(msg_or_done)
                pct = int(done * 85 / max(1, len(full_buf)))
                self._invoke_progress(
                    progress_callback,
                    f"Uploading 480x800 Wallpaper (Slot 0x00): {pct}%",
                    pct,
                    done,
                    total_bytes,
                )

        def _cb_thumb(msg_or_done, pct_or_total=0) -> None:
            if isinstance(msg_or_done, str):
                scaled_pct = 90 + int(pct_or_total * 0.10)
                self._invoke_progress(
                    progress_callback,
                    f"Uploading 142x148 Thumbnail (Slot 0x40): {pct_or_total}%",
                    scaled_pct,
                    len(full_buf) + int(len(thumb_buf) * pct_or_total / 100),
                    total_bytes,
                )
            else:
                done = int(msg_or_done)
                pct = 90 + int(done * 10 / max(1, len(thumb_buf)))
                self._invoke_progress(
                    progress_callback,
                    f"Uploading 142x148 Thumbnail (Slot 0x40): {pct}%",
                    pct,
                    len(full_buf) + done,
                    total_bytes,
                )

        self.upload_raw_buffer(full_buf, slot_id=0x00, progress_callback=_cb_main)
        self._invoke_progress(
            progress_callback,
            "Applying wallpaper in MCU flash (waiting 5s as in Swarm II)...",
            88,
            len(full_buf),
            total_bytes,
        )
        time.sleep(5.0)
        self.upload_raw_buffer(thumb_buf, slot_id=0x40, progress_callback=_cb_thumb)

        # Force Sonix MCU to invalidate cache and reload new wallpaper from SPI flash into LVGL canvas
        self.set_background_mode(0)
        time.sleep(0.15)
        self.set_background_mode(1)
        time.sleep(0.15)
        self.set_active_page(2)
        time.sleep(0.2)
        self.set_active_page(1)

        self._invoke_progress(
            progress_callback,
            "Theme active on KB7 display!",
            100,
            total_bytes,
            total_bytes,
        )
        return True

    # ------------------------------------------------------------------
    # Display Configuration (Report 0x0D, 20 bytes)
    # ------------------------------------------------------------------

    def get_display_config(self) -> bytearray:
        """
        Read the 20-byte Display Config (`Report ID 0x0D`, `device + 0x2358` in `COMMAND_KB7.dll`).
        - `buf[0]`: `0x0D`
        - `buf[1]`: `0x14` (20 bytes)
        - `buf[2]`: Screen Timeout (`0x235A`)
        - `buf[3]`: Screen Brightness / 10 (`0x235B`, range `0..10` for `0%..100%`)
        - `buf[8]`: Custom Wallpaper Active flag (`0x2360`, `1` when custom BG is set)
        """
        try:
            buf = self.get_feature_report(REPORT_ID_DISPLAY_CONFIG, 20)
            if len(buf) == 20 and buf[0] == REPORT_ID_DISPLAY_CONFIG and buf[1] == 0x14:
                return buf
        except Exception:
            pass
        buf = bytearray(20)
        buf[0] = REPORT_ID_DISPLAY_CONFIG
        buf[1] = 0x14
        buf[2] = 0     # Timeout (0 = never/default)
        buf[3] = 10    # Brightness 100% (10 * 10)
        buf[8] = 1     # Custom wallpaper enabled
        append_checksum16(buf)
        return buf

    def set_brightness(self, brightness: int) -> bool:
        """
        Set LCD screen brightness (`0`..`100`).
        Replicates `0x00267743`..`0x0026776C` in `COMMAND_KB7.dll`:
        Divides `brightness` by `10.0` and stores in `buf[3]` (`device + 0x235B`) of Report `0x0D`.
        """
        buf = self.get_display_config()
        level = max(0, min(10, int(round(brightness / 10.0))))
        buf[3] = level
        return self.send_feature_report(buf, add_checksum=True)

    def set_timeout(self, sleep_timeout_sec: int = 300, dim_timeout_sec: int = 60) -> bool:
        """
        Set LCD screen timeout in `buf[2]` (`device + 0x235A`) of Report `0x0D`.
        Replicates `0x002677F3`..`0x0026780F` in `COMMAND_KB7.dll`.
        """
        buf = self.get_display_config()
        if sleep_timeout_sec <= 0:
            timeout_byte = 0
        elif sleep_timeout_sec <= 255:
            timeout_byte = int(sleep_timeout_sec)
        else:
            timeout_byte = min(255, int(round(sleep_timeout_sec / 60.0)))
        buf[2] = timeout_byte
        return self.send_feature_report(buf, add_checksum=True)

    # ------------------------------------------------------------------
    # LCD Page & Widget Layout Configuration (Reports 0x25, 0x29, 0x35)
    # ------------------------------------------------------------------

    @staticmethod
    def _is_valid_lcd_settings(buf: bytearray) -> bool:
        """
        Verify that a 164-byte `0x25` buffer has a valid header and valid firmware
        `(w_type, w_id)` slots (detecting any prior corruption of offsets 10..22).
        """
        if len(buf) != 164 or buf[0] != REPORT_ID_LCD_SETTINGS or buf[1] != 0xA4:
            return False
        valid_wtypes = {wt for wt, _ in APP_ID_TO_FIRMWARE.values()} | {0, 1, 2, 3, 5}
        for page_idx in range(3):
            for slot_idx in range(12):
                off = 10 + page_idx * 52 + slot_idx * 4
                wt, wid = struct.unpack_from("<HH", buf, off)
                if wt not in valid_wtypes or wid > 100:
                    return False
        return True

    def get_lcd_settings(self) -> LCDSettingsBuffer:
        """
        Read the 164-byte (`0xA4`) LCD Configuration (`Report ID 0x25`).
        If the hardware buffer was previously corrupted (e.g. invalid `w_type` at
        bytes 10..22), automatically falls back to `FACTORY_LCD_SETTINGS`.
        """
        bri = 80
        to_sec = 60
        try:
            cfg = self.get_display_config()
            bri = min(100, max(0, int(cfg[3]) * 10))
            to_sec = int(cfg[2]) if cfg[2] > 0 else 60
        except Exception:
            pass

        try:
            buf = self.get_feature_report(REPORT_ID_LCD_SETTINGS, 164)
            if self._is_valid_lcd_settings(buf):
                return LCDSettingsBuffer(buf, brightness=bri, timeout_sec=to_sec)
        except Exception:
            pass
        return LCDSettingsBuffer(FACTORY_LCD_SETTINGS, brightness=bri, timeout_sec=to_sec)

    def get_screen_keys(self) -> List[ScreenKeyEntry]:
        """Return the 36 ScreenKey entries from Report `0x29` (`584` bytes)."""
        try:
            raw = self.get_feature_report(REPORT_ID_SCREEN_KEYS, 584)
            if len(raw) == 584 and raw[0] == REPORT_ID_SCREEN_KEYS:
                self._screen_keys_cache = bytearray(raw)
        except Exception:
            pass
        entries: List[ScreenKeyEntry] = []
        for idx in range(36):
            off = 6 + idx * 16
            chunk = self._screen_keys_cache[off : off + 16]
            key_code = chunk[2]
            modifiers = chunk[3]
            label = chunk[5:].split(b"\x00", 1)[0].decode("ascii", errors="ignore")
            entries.append(ScreenKeyEntry(idx, key_code, modifiers, label))
        return entries

    def restore_factory_layout(self) -> bool:
        """
        Restore the exact factory 3-page widget layout (`CommandKB7LCD` `0x25` and
        `CommandKB7ScreenKeys` `0x29` from `Command_KB7_Profile_Mgr.dat`):
        - Page 0: 12-tile Home ("Default 1 / 6-Island")
        - Page 1: "NUMPAD"
        - Page 2: "Default 2" (PC Telemetry & Shortcuts)
        """
        self._screen_keys_cache = bytearray(FACTORY_SCREEN_KEYS)
        self.send_feature_report(self._screen_keys_cache, add_checksum=True, post_delay_sec=0.050)
        return self.send_feature_report(bytearray(FACTORY_LCD_SETTINGS), add_checksum=True, post_delay_sec=0.050)

    def set_active_page(self, page_index: int) -> bool:
        """
        Switch the active LCD page (`0`..`2` or `1`..`3`).
        """
        lcd_buf = self.get_lcd_settings()
        lcd_buf[6] = 1
        return self.send_feature_report(lcd_buf, add_checksum=True)

    def _update_screen_key_slot(self, page_index: int, slot_index: int, app_id: int) -> None:
        """
        Update the 16-byte entry in Report `0x29` (`ScreenKeys`, 584 bytes) at
        `offset = 6 + (page_index * 12 + slot_index) * 16` (`0x00295650` in `COMMAND_KB7.dll`).
        """
        if not (0 <= page_index < 3 and 0 <= slot_index < 12):
            return
        off = 6 + (page_index * 12 + slot_index) * 16
        self._screen_keys_cache[off : off + 16] = b"\x00" * 16
        if app_id in SCREEN_KEY_BINDINGS:
            hid_code, label = SCREEN_KEY_BINDINGS[app_id]
            self._screen_keys_cache[off + 2] = hid_code
            self._screen_keys_cache[off + 3] = 0x0C
            enc = label.encode("ascii")[:11]
            self._screen_keys_cache[off + 5 : off + 5 + len(enc)] = enc
        append_checksum16(self._screen_keys_cache)

    def assign_widget(
        self,
        arg1: int,
        arg2: int,
        arg3: Optional[int] = None,
        page_index: Optional[int] = None,
    ) -> bool:
        """
        Assign a widget (`app_id`) to a slot on `page_index` (`0`..`2`), `slot_index` (`0`..`11`).
        Supports both call signatures:
        - `assign_widget(page_index, slot_index, app_id)` (used by `KB7Daemon` and `KB7CommandCenterApp`)
        - `assign_widget(slot_index, app_id, page_index=0)` (used by CLI)
        """
        if page_index is not None:
            slot_idx = arg1
            app_id = arg2
            p_idx = page_index
        elif arg3 is not None:
            p_idx = arg1
            slot_idx = arg2
            app_id = arg3
        else:
            p_idx = 0
            slot_idx = arg1
            app_id = arg2

        p_idx = max(0, min(2, int(p_idx)))
        if not 0 <= slot_idx < 12:
            raise ValueError(f"slot_index must be between 0 and 11, got {slot_idx}.")

        w_type, w_id = APP_ID_TO_FIRMWARE.get(app_id, (0, 0))

        # 1. Update and send Report 0x29 (ScreenKeys, 584B)
        self._update_screen_key_slot(p_idx, slot_idx, app_id)
        self.send_feature_report(self._screen_keys_cache, add_checksum=True, post_delay_sec=0.030)

        # 2. Update Report 0x25 (LCDSettings, 164B) at 10 + page_index * 52 + slot_index * 4
        lcd_buf = self.get_lcd_settings()
        lcd_buf[6] = 1
        slot_off = 10 + (p_idx * 52) + (slot_idx * 4)
        struct.pack_into("<HH", lcd_buf, slot_off, w_type, w_id)
        struct.pack_into("<HH", lcd_buf, 10 + 12 * 4, 2, 0)
        struct.pack_into("<HH", lcd_buf, 62 + 12 * 4, 3, 0)
        self.send_feature_report(lcd_buf, add_checksum=True, post_delay_sec=0.030)

        # 3. Send Report 0x35 (12-byte single-slot notification, 0x0029CB15)
        slot_buf = bytearray(12)
        slot_buf[0] = REPORT_ID_SLOT_UPDATE
        slot_buf[1] = 0x0C
        slot_buf[2] = 0x00
        slot_buf[3] = p_idx & 0xFF
        slot_buf[4] = slot_idx & 0xFF
        slot_buf[5] = 0x00
        struct.pack_into("<HH", slot_buf, 6, w_type, w_id)
        return self.send_feature_report(slot_buf, add_checksum=True, post_delay_sec=0.030)

    def apply_template(
        self,
        arg1: Union[int, str, List[int]],
        arg2: Optional[Union[int, str, List[int]]] = None,
        page_index: Optional[int] = None,
    ) -> bool:
        """
        Apply a 12-slot template of `app_id`s to `page_index` (`0`..`2`).
        Supports both call signatures:
        - `apply_template(page_index, template_name_or_list)` (used by `KB7Daemon` and `KB7CommandCenterApp`)
        - `apply_template(template_name_or_list, page_index=0)` (used by CLI)
        """
        if isinstance(arg1, int):
            p_idx = arg1
            tmpl = arg2
        else:
            tmpl = arg1
            p_idx = page_index if page_index is not None else (arg2 if isinstance(arg2, int) else 0)

        if isinstance(tmpl, str):
            if tmpl.lower() == "factory" and int(p_idx) == 0:
                return self.restore_factory_layout()
            app_ids = LAYOUT_TEMPLATES.get(tmpl) or LAYOUT_TEMPLATES.get(tmpl.lower())
            if app_ids is None:
                raise ValueError(f"Unknown template: {tmpl!r}")
        elif isinstance(tmpl, (list, tuple)):
            app_ids = list(tmpl)
        else:
            raise ValueError(f"Invalid template specification: {tmpl!r}")

        p_idx = max(0, min(2, int(p_idx)))
        lcd_buf = self.get_lcd_settings()
        lcd_buf[6] = 1

        padded_ids = (list(app_ids) + [0] * 12)[:12]
        for slot_idx, app_id in enumerate(padded_ids):
            w_type, w_id = APP_ID_TO_FIRMWARE.get(app_id, (0, 0))
            slot_off = 10 + (p_idx * 52) + (slot_idx * 4)
            struct.pack_into("<HH", lcd_buf, slot_off, w_type, w_id)
            self._update_screen_key_slot(p_idx, slot_idx, app_id)

        struct.pack_into("<HH", lcd_buf, 10 + 12 * 4, 2, 0)
        struct.pack_into("<HH", lcd_buf, 62 + 12 * 4, 3, 0)

        self.send_feature_report(self._screen_keys_cache, add_checksum=True, post_delay_sec=0.040)
        return self.send_feature_report(lcd_buf, add_checksum=True, post_delay_sec=0.050)

    def read_page_widgets(self, page_index: int = 0) -> List[int]:
        """Read the 12 widget `app_id`s currently configured on `page_index` (`0`..`2`)."""
        page_index = max(0, min(2, page_index))
        lcd_buf = self.get_lcd_settings()
        result: List[int] = []
        for slot_idx in range(12):
            off = 10 + (page_index * 52) + (slot_idx * 4)
            wt, wid = struct.unpack_from("<HH", lcd_buf, off)
            result.append(FIRMWARE_TO_APP_ID.get((wt, wid), 0))
        return result

    def read_touch_event(self, timeout_ms: int = 50) -> Optional[dict]:
        """Poll for touch events on `self.touch_handle` (`0xFF02`)."""
        if not self.touch_handle:
            return None
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

    # ------------------------------------------------------------------
    # Keyboard RGB Backlight Control (Report ID 0x11, 348 bytes)
    # ------------------------------------------------------------------

    def set_keyboard_rgb(self, r: int, g: int, b: int, brightness: int = 100) -> bool:
        """
        Set the KB7 keyboard backlight to a static RGB color (`r`, `g`, `b` in `0..255`).
        Uses Feature Report `0x11` (348 bytes, extracted from `Command_KB7_Profile_Mgr.dat`).
        """
        try:
            buf = self.get_feature_report(REPORT_ID_LIGHTING, 348)
            if len(buf) != 348 or buf[0] != REPORT_ID_LIGHTING:
                raise ValueError("Invalid 0x11 report")
        except Exception:
            buf = bytearray(348)
            buf[0] = REPORT_ID_LIGHTING
            buf[1] = 0x5C
            buf[2] = 0x01

        buf[4] = 0x01  # Mode 1 = Static / Wave preset
        buf[5] = 0x06  # Speed
        buf[6] = max(0, min(100, int(brightness)))
        buf[7] = 0x00  # Custom RGB color index
        buf[8] = 0x01

        rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | ((b & 0xF8) >> 3)
        for i in range(10, 346, 2):
            struct.pack_into("<H", buf, i, rgb565)

        return self.send_feature_report(buf, add_checksum=True, post_delay_sec=0.015, wait_sync=False)

    # ------------------------------------------------------------------
    # Live System Telemetry & Volume Mixer Push (Report ID 0x16, 104B)
    # ------------------------------------------------------------------

    def send_telemetry_report(
        self,
        cpu_usage: int = 0,
        cpu_temp: int = 0,
        gpu_usage: int = 0,
        gpu_temp: int = 0,
        ram_usage: int = 0,
        net_up_kbps: int = 0,
        net_down_kbps: int = 0,
        master_vol: int = 100,
        mic_vol: int = 100,
        app_volumes: Optional[List[Tuple[str, int]]] = None,
    ) -> bool:
        """
        Build and send the 104-byte (`0x68`) Live Telemetry & Audio Mixer report (`0x16`).
        """
        buf = bytearray(104)
        buf[0] = REPORT_ID_SYS_METRICS
        buf[1] = 0x68

        now = time.localtime()
        struct.pack_into("<H", buf, 2, now.tm_year)
        buf[4] = now.tm_mon
        buf[5] = now.tm_mday
        buf[6] = now.tm_hour
        buf[7] = now.tm_min
        buf[8] = now.tm_sec
        buf[9] = now.tm_wday

        buf[10] = max(0, min(100, int(cpu_usage)))
        buf[11] = max(0, min(120, int(cpu_temp)))
        buf[12] = max(0, min(100, int(gpu_usage)))
        buf[13] = max(0, min(120, int(gpu_temp)))
        buf[14] = max(0, min(100, int(ram_usage)))

        struct.pack_into("<I", buf, 16, max(0, int(net_up_kbps)))
        struct.pack_into("<I", buf, 20, max(0, int(net_down_kbps)))

        buf[24] = max(0, min(100, int(master_vol)))
        buf[25] = max(0, min(100, int(mic_vol)))

        if app_volumes:
            offset = 28
            for name, vol in app_volumes[:4]:
                if offset + 16 > 102:
                    break
                buf[offset] = max(0, min(100, int(vol)))
                encoded = name.encode("utf-8", errors="ignore")[:14]
                buf[offset + 1 : offset + 1 + len(encoded)] = encoded
                offset += 16

        return self.send_feature_report(buf, add_checksum=True, post_delay_sec=0.005, wait_sync=False)
