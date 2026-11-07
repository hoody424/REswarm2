"""
Turtle Beach Command Series KB7 - Hardware Daemon Service.

Acts as the exclusive single-writer controller for the KB7 keyboard.
Prevents USB endpoint collisions, enforces safe inter-packet delays,
and exposes a lightweight JSON-over-TCP IPC server for custom plugins.
"""

import sys
import time
import json
import socket
import select
import threading
from typing import Dict, Any, List, Optional, Set

from .device import KB7Device
from .widgets import lookup_widget, LAYOUT_TEMPLATES

DEFAULT_DAEMON_HOST = "127.0.0.1"
DEFAULT_DAEMON_PORT = 27878


class KB7Daemon:
    """
    Background single-writer daemon for Turtle Beach KB7.
    """

    def __init__(self, host: str = DEFAULT_DAEMON_HOST, port: int = DEFAULT_DAEMON_PORT):
        self.host = host
        self.port = port
        self.running = False
        self.device: Optional[KB7Device] = None
        self.lock = threading.Lock()

        # Clients and subscriptions
        self.clients: Set[socket.socket] = set()
        self.subscribers: Set[socket.socket] = set()

        # Server socket
        self.server_socket: Optional[socket.socket] = None

        # Threads
        self.server_thread: Optional[threading.Thread] = None
        self.touch_thread: Optional[threading.Thread] = None

    def start(self):
        """Starts the daemon service and connects to the hardware."""
        print(f"[*] Starting KB7 Daemon on {self.host}:{self.port}...")
        self.running = True

        # Initialize hardware connection
        self._connect_hardware()

        # Start IPC Server
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(10)
        self.server_socket.setblocking(False)

        # Thread for accepting client connections and messages
        self.server_thread = threading.Thread(target=self._run_server, daemon=True)
        self.server_thread.start()

        # Thread for polling touch events from hardware
        self.touch_thread = threading.Thread(target=self._run_touch_poller, daemon=True)
        self.touch_thread.start()

        print(f"[+] KB7 Daemon active and listening for plugins on port {self.port}!")

    def _connect_hardware(self):
        """Attempts connection to the physical KB7 keyboard."""
        try:
            with self.lock:
                if self.device:
                    try:
                        self.device.disconnect()
                    except Exception:
                        pass
                self.device = KB7Device()
                self.device.connect()
            print("[+] Connected to KB7 hardware successfully.")
        except Exception as e:
            print(f"[!] Warning: Initial hardware connection failed: {e}. Will retry in background.")

    def stop(self):
        """Stops the daemon and releases all hardware handles."""
        print("[*] Stopping KB7 Daemon...")
        self.running = False

        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass

        with self.lock:
            for s in list(self.clients):
                try:
                    s.close()
                except Exception:
                    pass
            self.clients.clear()
            self.subscribers.clear()

            if self.device:
                try:
                    self.device.disconnect()
                except Exception:
                    pass
                self.device = None

        print("[+] KB7 Daemon stopped.")

    def _run_server(self):
        """Main non-blocking socket server loop."""
        inputs = [self.server_socket]
        client_buffers: Dict[socket.socket, bytes] = {}

        while self.running:
            try:
                readable, _, exceptional = select.select(inputs, [], inputs, 0.1)
            except (select.error, ValueError):
                break

            for s in readable:
                if s is self.server_socket:
                    try:
                        conn, addr = self.server_socket.accept()
                        conn.setblocking(False)
                        inputs.append(conn)
                        self.clients.add(conn)
                        client_buffers[conn] = b""
                    except Exception:
                        pass
                else:
                    try:
                        data = s.recv(4096)
                        if data:
                            client_buffers[s] += data
                            # Process line-delimited JSON commands (\n)
                            while b"\n" in client_buffers[s]:
                                line, client_buffers[s] = client_buffers[s].split(b"\n", 1)
                                line = line.strip()
                                if line:
                                    self._handle_client_message(s, line.decode("utf-8", errors="ignore"))
                        else:
                            # Client disconnected
                            self._cleanup_client(s, inputs, client_buffers)
                    except (ConnectionResetError, BrokenPipeError):
                        self._cleanup_client(s, inputs, client_buffers)
                    except Exception as e:
                        print(f"[!] Socket read error: {e}")
                        self._cleanup_client(s, inputs, client_buffers)

            for s in exceptional:
                self._cleanup_client(s, inputs, client_buffers)

    def _cleanup_client(self, s: socket.socket, inputs: list, client_buffers: dict):
        """Cleans up a disconnected client."""
        if s in inputs:
            inputs.remove(s)
        self.clients.discard(s)
        self.subscribers.discard(s)
        client_buffers.pop(s, None)
        try:
            s.close()
        except Exception:
            pass

    def _handle_client_message(self, client: socket.socket, message_str: str):
        """Processes an incoming JSON command from a plugin."""
        try:
            req = json.loads(message_str)
        except Exception as e:
            self._send_reply(client, {"status": "error", "message": f"Malformed JSON: {e}"})
            return

        cmd = req.get("cmd")
        req_id = req.get("req_id")

        try:
            reply = self._execute_command(client, cmd, req)
        except Exception as e:
            reply = {"status": "error", "message": str(e)}

        if req_id is not None:
            reply["req_id"] = req_id

        self._send_reply(client, reply)

    def _execute_command(self, client: socket.socket, cmd: str, req: Dict[str, Any]) -> Dict[str, Any]:
        """Executes a validated command on the hardware thread."""
        if cmd == "ping":
            return {"status": "ok", "message": "pong", "time": time.time()}

        elif cmd == "subscribe":
            self.subscribers.add(client)
            return {"status": "ok", "message": "Subscribed to touch events"}

        elif cmd == "unsubscribe":
            self.subscribers.discard(client)
            return {"status": "ok", "message": "Unsubscribed from touch events"}

        with self.lock:
            if not self.device:
                self._connect_hardware()
                if not self.device:
                    return {"status": "error", "message": "KB7 hardware not connected"}

            if cmd == "set_brightness":
                val = int(req.get("value", 70))
                ok = self.device.set_brightness(val)
                return {"status": "ok" if ok else "error", "brightness": val}

            elif cmd == "set_timeout":
                sec = int(req.get("seconds", 60))
                ok = self.device.set_timeout(sec)
                return {"status": "ok" if ok else "error", "timeout_seconds": sec}

            elif cmd == "set_page":
                p = int(req.get("page", 1))
                ok = self.device.set_active_page(p)
                return {"status": "ok" if ok else "error", "active_page": p}

            elif cmd == "get_settings":
                settings = self.device.get_lcd_settings()
                return {
                    "status": "ok",
                    "settings": {
                        "active_page": settings.active_page,
                        "brightness": settings.brightness,
                        "timeout_seconds": settings.timeout_seconds,
                        "dim_timeout_seconds": settings.dim_timeout_seconds,
                        "slots_count": len(settings.widget_slots)
                    }
                }

            elif cmd == "get_slots":
                settings = self.device.get_lcd_settings()
                page_filter = req.get("page")
                results = []
                for i, (w_type, w_id) in enumerate(settings.widget_slots):
                    p_num = (i // 12) + 1
                    s_idx = i % 12
                    if page_filter is not None and p_num != page_filter:
                        continue
                    w_def = lookup_widget(w_id)
                    results.append({
                        "index": i,
                        "page": p_num,
                        "slot": s_idx,
                        "type": w_type,
                        "app_id": w_id,
                        "name": w_def.name,
                        "category": w_def.category,
                        "runtime_update": w_def.runtime_update
                    })
                return {"status": "ok", "slots": results}

            elif cmd == "restore_factory_layout":
                ok = self.device.restore_factory_layout()
                return {"status": "ok" if ok else "error"}

            elif cmd == "get_keys":
                keys = self.device.get_screen_keys()
                return {
                    "status": "ok",
                    "keys": [
                        {"index": k.index, "key_code": k.key_code, "modifiers": k.modifiers, "label": k.label}
                        for k in keys
                    ]
                }

            elif cmd == "assign_widget":
                page = int(req.get("page", 1))
                slot = int(req.get("slot", 0))
                app_id = int(req.get("app_id", 0))
                w_def = lookup_widget(app_id)
                ok = self.device.assign_widget(page - 1, slot, app_id)
                return {
                    "status": "ok" if ok else "error",
                    "page": page,
                    "slot": slot,
                    "app_id": app_id,
                    "name": w_def.name
                }

            elif cmd == "apply_template":
                page = int(req.get("page", 1))
                tmpl_name = str(req.get("name", "")).lower()
                ok = self.device.apply_template(page - 1, tmpl_name)
                return {"status": "ok" if ok else "error", "page": page, "template": tmpl_name}

            elif cmd == "set_background_mode":
                mode = int(req.get("mode", 1))
                ok = self.device.set_background_mode(mode)
                self.device.refresh_screen()
                return {"status": "ok" if ok else "error", "mode": mode}

            elif cmd == "get_background_mode":
                mode = self.device.get_background_mode()
                return {"status": "ok", "mode": mode}

            elif cmd == "refresh_screen":
                ok = self.device.refresh_screen()
                return {"status": "ok" if ok else "error"}

            elif cmd == "apply_theme":
                preset = req.get("name")
                img_path = req.get("path")
                from .theme_generator import THEME_PRESETS
                from PIL import Image

                if img_path:
                    im = Image.open(img_path)
                elif preset in THEME_PRESETS:
                    im = THEME_PRESETS[preset]()
                else:
                    return {"status": "error", "message": f"Unknown theme preset '{preset}'"}

                ok = self.device.upload_theme(im)
                return {"status": "ok" if ok else "error", "theme": preset or img_path}

            else:
                return {"status": "error", "message": f"Unknown command: '{cmd}'"}

    def _send_reply(self, client: socket.socket, reply: Dict[str, Any]):
        """Transmits a JSON reply followed by newline."""
        try:
            line = (json.dumps(reply) + "\n").encode("utf-8")
            client.sendall(line)
        except Exception:
            pass

    def _broadcast_event(self, event_data: Dict[str, Any]):
        """Broadcasts an event message to all subscribed plugins."""
        if not self.subscribers:
            return
        msg = (json.dumps({"event": "touch", "data": event_data}) + "\n").encode("utf-8")
        dead_clients = []
        for s in list(self.subscribers):
            try:
                s.sendall(msg)
            except Exception:
                dead_clients.append(s)

        for s in dead_clients:
            self.subscribers.discard(s)

    def _run_touch_poller(self):
        """Background thread polling for touch events and broadcasting to subscribers."""
        while self.running:
            if not self.subscribers:
                time.sleep(0.05)
                continue

            event = None
            with self.lock:
                if self.device and self.device.touch_handle:
                    try:
                        event = self.device.read_touch_event(timeout_ms=50)
                    except Exception:
                        pass

            if event:
                self._broadcast_event(event)

            time.sleep(0.01)


def run_daemon(host: str = DEFAULT_DAEMON_HOST, port: int = DEFAULT_DAEMON_PORT):
    """Entry point to start the daemon in foreground."""
    daemon = KB7Daemon(host=host, port=port)
    try:
        daemon.start()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[!] Keyboard interrupt received.")
    finally:
        daemon.stop()
