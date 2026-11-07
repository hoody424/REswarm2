"""
Turtle Beach Command Series KB7 - Plugin Client SDK.

Lightweight, high-level client interface for custom plugins.
Connects to the KB7 single-writer daemon over local IPC (TCP socket)
to query and update display state and listen for real-time touch events.
"""

import json
import socket
import threading
import time
from typing import Dict, Any, List, Optional, Callable, Tuple

DEFAULT_DAEMON_HOST = "127.0.0.1"
DEFAULT_DAEMON_PORT = 27878


class KB7Client:
    """
    Client library for connecting to the KB7 Daemon.
    """

    def __init__(self, host: str = DEFAULT_DAEMON_HOST, port: int = DEFAULT_DAEMON_PORT):
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None
        self.running = False
        self._lock = threading.Lock()
        self._req_id = 0
        self._pending_responses: Dict[int, Any] = {}

        # Event dispatching
        self._touch_callbacks: List[Tuple[Optional[int], Optional[str], Callable]] = []
        self._listener_thread: Optional[threading.Thread] = None

    def connect(self, timeout: float = 5.0) -> bool:
        """Connects to the running KB7 Daemon."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(timeout)
        self.sock.connect((self.host, self.port))
        self.sock.settimeout(None)  # Reset to blocking mode for background listener loop
        self.running = True

        # Start listener thread for incoming replies & events
        self._listener_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._listener_thread.start()
        return True

    def close(self):
        """Closes the connection to the daemon."""
        self.running = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _send_command(self, cmd: str, timeout: float = 5.0, **kwargs) -> Dict[str, Any]:
        """Sends a synchronous command and waits for reply."""
        if not self.sock or not self.running:
            raise ConnectionError("KB7Client is not connected to daemon.")

        with self._lock:
            self._req_id += 1
            req_id = self._req_id

        req = {"cmd": cmd, "req_id": req_id, **kwargs}
        line = (json.dumps(req) + "\n").encode("utf-8")

        event = threading.Event()
        self._pending_responses[req_id] = event

        try:
            self.sock.sendall(line)
        except Exception as e:
            self._pending_responses.pop(req_id, None)
            raise ConnectionError(f"Failed to transmit to KB7 Daemon: {e}")

        # Wait up to timeout seconds for response
        if not event.wait(timeout=timeout):
            self._pending_responses.pop(req_id, None)
            raise TimeoutError(f"Command '{cmd}' timed out awaiting daemon reply.")

        response = self._pending_responses.pop(req_id, None)
        if isinstance(response, dict) and response.get("status") == "error":
            raise RuntimeError(response.get("message", "Unknown error from daemon"))

        return response

    def _listen_loop(self):
        """Reads stream from daemon and routes replies and push events."""
        buf = b""
        while self.running:
            try:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line.decode("utf-8", errors="ignore"))
                        self._handle_incoming_message(msg)
                    except Exception as e:
                        print(f"[!] Client parse error: {e}")
            except Exception:
                break
        self.running = False

    def _handle_incoming_message(self, msg: Dict[str, Any]):
        """Dispatches replies to waiting requests or touch events to subscribers."""
        if "req_id" in msg and msg["req_id"] in self._pending_responses:
            req_id = msg["req_id"]
            ev = self._pending_responses[req_id]
            self._pending_responses[req_id] = msg
            ev.set()
        elif msg.get("event") == "touch":
            data = msg.get("data", {})
            slot = data.get("slot_id")
            gesture = data.get("gesture")
            for filter_slot, filter_gesture, callback in self._touch_callbacks:
                if filter_slot is not None and filter_slot != slot:
                    continue
                if filter_gesture is not None and filter_gesture != gesture:
                    continue
                try:
                    callback(data)
                except Exception as e:
                    print(f"[!] Error in touch callback: {e}")

    # =========================================================================
    # HIGH-LEVEL PLUGIN API
    # =========================================================================

    def ping(self) -> bool:
        """Pings the daemon."""
        res = self._send_command("ping")
        return res.get("message") == "pong"

    def set_brightness(self, value: int) -> int:
        """Sets screen backlight brightness (0 to 100%)."""
        res = self._send_command("set_brightness", value=value)
        return res.get("brightness", value)

    def set_timeout(self, seconds: int) -> int:
        """Sets screen sleep timeout in seconds."""
        res = self._send_command("set_timeout", seconds=seconds)
        return res.get("timeout_seconds", seconds)

    def set_page(self, page_num: int) -> int:
        """Switches active display page (1 to 5)."""
        res = self._send_command("set_page", page=page_num)
        return res.get("active_page", page_num)

    def get_settings(self) -> Dict[str, Any]:
        """Retrieves active display settings."""
        res = self._send_command("get_settings")
        return res.get("settings", {})

    def get_slots(self, page: Optional[int] = None) -> List[Dict[str, Any]]:
        """Retrieves configured widget slots, optionally filtered by page number."""
        res = self._send_command("get_slots", page=page)
        return res.get("slots", [])

    def get_keys(self) -> List[Dict[str, Any]]:
        """Retrieves defined virtual touch keys (numpad/macros)."""
        res = self._send_command("get_keys")
        return res.get("keys", [])

    def assign_widget(self, page: int, slot: int, app_id: int) -> Dict[str, Any]:
        """
        Dynamically assigns a widget to a specific page and slot.
        
        Args:
            page: 1-indexed page number (1 to 5)
            slot: 0-indexed slot on page (0 to 12)
            app_id: App ID from WIDGET_CATALOG (e.g. 1006 for CPU, 1007 for GPU)
        """
        return self._send_command("assign_widget", page=page, slot=slot, app_id=app_id)

    def apply_template(self, page: int, template_name: str) -> bool:
        """Applies a layout template (e.g. 'numpad', 'telemetry', 'gaming') to a page."""
        res = self._send_command("apply_template", page=page, name=template_name)
        return res.get("status") == "ok"

    def set_background_mode(self, mode: int = 1) -> bool:
        """Sets custom background mode (1=custom wallpaper, 0=built-in default)."""
        res = self._send_command("set_background_mode", mode=mode)
        return res.get("status") == "ok"

    def get_background_mode(self) -> int:
        """Reads custom background mode (1=custom wallpaper, 0=built-in default)."""
        res = self._send_command("get_background_mode")
        return res.get("mode", 0)

    def refresh_screen(self) -> bool:
        """Forces an LVGL canvas refresh on the KB7 display."""
        res = self._send_command("refresh_screen")
        return res.get("status") == "ok"

    def apply_theme(self, name: Optional[str] = None, path: Optional[str] = None) -> bool:
        """Uploads and activates a theme via daemon (timeout 60s)."""
        res = self._send_command("apply_theme", timeout=60.0, name=name, path=path)
        return res.get("status") == "ok"

    def on_touch(self, slot: Optional[int] = None, gesture: Optional[str] = None):
        """
        Decorator to subscribe to touch events.
        
        Example:
            @client.on_touch(slot=0, gesture="tap")
            def on_slot_tap(event):
                print(f"Slot 0 was tapped at ({event['x']}, {event['y']})")
        """
        def decorator(func: Callable[[Dict[str, Any]], None]):
            if not self._touch_callbacks:
                # Automatically subscribe on daemon when first callback is registered
                try:
                    self._send_command("subscribe")
                except Exception:
                    pass
            self._touch_callbacks.append((slot, gesture, func))
            return func
        return decorator
