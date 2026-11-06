"""
Turtle Beach KB7 - Universal Windows Audio Mixer Engine.

Provides comprehensive enumeration and per-application volume control
across ALL active audio output devices (SteelSeries Sonar, Voicemeeter, Realtek, USB headsets, etc.).
Fixes the limitations of the original Swarm II implementation, which failed to detect
Win32 apps lacking AUMIDs and ignored non-default audio routing endpoints.
"""

import time
import threading
import warnings
from typing import List, Dict, Any, Optional, Callable

# Suppress pycaw comtypes 3.15 warnings
warnings.filterwarnings("ignore")

try:
    import psutil
    from pycaw.pycaw import (
        AudioUtilities,
        AudioDeviceState,
        IAudioSessionControl2,
        AudioSession,
        IAudioEndpointVolume
    )
except ImportError:
    psutil = None
    AudioUtilities = None


class AudioSessionItem:
    """
    Represents an individual application audio session.
    """

    def __init__(self, session_obj: Any, device_name: str, device_id: str):
        self._session = session_obj
        self.device_name = device_name
        self.device_id = device_id
        self.pid = session_obj.ProcessId or 0

        # Resolve human-readable name
        raw_name = ""
        if self.pid and psutil:
            try:
                raw_name = psutil.Process(self.pid).name()
            except Exception:
                raw_name = session_obj.Process.name() if session_obj.Process else "Unknown"
        else:
            raw_name = session_obj.DisplayName or "System Sounds"

        if raw_name.lower().endswith(".exe"):
            self.name = raw_name[:-4].capitalize()
        elif raw_name.startswith("@%SystemRoot%") or "AudioSrv" in raw_name:
            self.name = "System Sounds"
        elif not raw_name or raw_name == "Unknown":
            self.name = f"Process [{self.pid}]" if self.pid else "System Sounds"
        else:
            self.name = raw_name

    @property
    def volume(self) -> int:
        """Current volume level (0 to 100%)."""
        try:
            vol = self._session.SimpleAudioVolume
            if vol:
                return int(round(vol.GetMasterVolume() * 100))
        except Exception:
            pass
        return 0

    @volume.setter
    def volume(self, val: int):
        """Sets application volume level (0 to 100%)."""
        try:
            val = max(0, min(100, int(val)))
            vol = self._session.SimpleAudioVolume
            if vol:
                vol.SetMasterVolume(val / 100.0, None)
        except Exception:
            pass

    @property
    def muted(self) -> bool:
        """Whether this session is currently muted."""
        try:
            vol = self._session.SimpleAudioVolume
            if vol:
                return bool(vol.GetMute())
        except Exception:
            pass
        return False

    @muted.setter
    def muted(self, val: bool):
        """Mutes or unmutes this application session."""
        try:
            vol = self._session.SimpleAudioVolume
            if vol:
                vol.SetMute(bool(val), None)
        except Exception:
            pass

    def toggle_mute(self) -> bool:
        """Toggles mute state and returns the new state."""
        new_state = not self.muted
        self.muted = new_state
        return new_state

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pid": self.pid,
            "name": self.name,
            "device": self.device_name,
            "volume": self.volume,
            "muted": self.muted,
        }

    def __repr__(self):
        return f"<AudioSessionItem '{self.name}' [PID {self.pid}] Vol={self.volume}% Muted={self.muted} Dev='{self.device_name[:20]}'>"


class AudioDeviceItem:
    """
    Represents a physical or virtual Windows playback device.
    """

    def __init__(self, device_obj: Any, is_default: bool = False):
        self._dev = device_obj
        self.id = getattr(device_obj, "id", "")
        self.name = getattr(device_obj, "FriendlyName", "Unknown Audio Device")
        self.is_default = is_default

    @property
    def volume(self) -> int:
        """Master volume of this device (0 to 100%)."""
        try:
            if hasattr(self._dev, "volume_percent"):
                return int(round(self._dev.volume_percent))
            if hasattr(self._dev, "EndpointVolume") and self._dev.EndpointVolume:
                return int(round(self._dev.EndpointVolume.GetMasterVolumeLevelScalar() * 100))
        except Exception:
            pass
        return 0

    @volume.setter
    def volume(self, val: int):
        """Sets master volume of this device (0 to 100%)."""
        try:
            val = max(0, min(100, int(val)))
            if hasattr(self._dev, "EndpointVolume") and self._dev.EndpointVolume:
                self._dev.EndpointVolume.SetMasterVolumeLevelScalar(val / 100.0, None)
        except Exception:
            pass

    @property
    def muted(self) -> bool:
        """Whether this device is master-muted."""
        try:
            if hasattr(self._dev, "EndpointVolume") and self._dev.EndpointVolume:
                return bool(self._dev.EndpointVolume.GetMute())
        except Exception:
            pass
        return False

    @muted.setter
    def muted(self, val: bool):
        """Mutes or unmutes this device."""
        try:
            if hasattr(self._dev, "EndpointVolume") and self._dev.EndpointVolume:
                self._dev.EndpointVolume.SetMute(bool(val), None)
        except Exception:
            pass

    def toggle_mute(self) -> bool:
        new_state = not self.muted
        self.muted = new_state
        return new_state

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "is_default": self.is_default,
            "volume": self.volume,
            "muted": self.muted,
        }

    def __repr__(self):
        return f"<AudioDeviceItem '{self.name[:25]}' Vol={self.volume}% Muted={self.muted} Default={self.is_default}>"


class UniversalAudioMixer:
    """
    High-level engine that aggregates and controls all audio sessions and devices.
    """

    def __init__(self):
        if not AudioUtilities:
            raise RuntimeError("pycaw is required. Install with: pip install pycaw")

    def get_default_device(self) -> Optional[AudioDeviceItem]:
        """Returns the default Windows audio playback device."""
        try:
            speakers = AudioUtilities.GetSpeakers()
            if speakers:
                return AudioDeviceItem(speakers, is_default=True)
        except Exception:
            pass
        return None

    def get_playback_devices(self) -> List[AudioDeviceItem]:
        """Returns all active audio playback devices."""
        devices = []
        try:
            default_dev = self.get_default_device()
            default_id = default_dev.id if default_dev else ""

            all_devs = AudioUtilities.GetAllDevices()
            for d in all_devs:
                if hasattr(d, "state") and d.state == AudioDeviceState.Active:
                    is_def = (d.id == default_id)
                    devices.append(AudioDeviceItem(d, is_default=is_def))
        except Exception:
            pass
        return devices

    def get_sessions(
        self,
        device_name_filter: Optional[str] = None,
        include_all_devices: bool = True
    ) -> List[AudioSessionItem]:
        """
        Enumerates all audio sessions across all active devices.
        
        Args:
            device_name_filter: Optional substring to match device name.
            include_all_devices: If True, iterates all active output endpoints (e.g. Sonar Chat,
                                 Sonar Gaming, Voicemeeter, Speakers).
        """
        sessions: List[AudioSessionItem] = []
        seen_keys = set()

        if include_all_devices:
            targets = self.get_playback_devices()
        else:
            def_dev = self.get_default_device()
            targets = [def_dev] if def_dev else []

        for dev_item in targets:
            if not dev_item or not hasattr(dev_item, "_dev"):
                continue
            if device_name_filter and device_name_filter.lower() not in dev_item.name.lower():
                continue

            try:
                mgr = dev_item._dev.AudioSessionManager
                if not mgr:
                    continue
                enum = mgr.GetSessionEnumerator()
                count = enum.GetCount()
                for i in range(count):
                    ctl = enum.GetSession(i)
                    if not ctl:
                        continue
                    ctl2 = ctl.QueryInterface(IAudioSessionControl2)
                    if not ctl2:
                        continue
                    s = AudioSession(ctl2)
                    item = AudioSessionItem(s, dev_item.name, dev_item.id)
                    # Deduplicate sessions by (pid, name, device)
                    key = (item.pid, item.name, dev_item.name)
                    if key not in seen_keys:
                        seen_keys.add(key)
                        sessions.append(item)
            except Exception:
                pass

        # Sort: System Sounds last, others alphabetically
        sessions.sort(key=lambda s: (s.name == "System Sounds", s.name.lower()))
        return sessions

    def get_grouped_apps(self) -> List["AppGroup"]:
        """
        Groups sessions by application name so the user gets a clean, single slider
        per application (e.g. Discord, Spotify, Steam, Chrome) even if routed across multiple devices.
        """
        raw_sessions = self.get_sessions(include_all_devices=True)
        groups: Dict[str, AppGroup] = {}

        for s in raw_sessions:
            if s.name not in groups:
                groups[s.name] = AppGroup(s.name)
            groups[s.name].add_session(s)

        # Sort: applications alphabetically, System Sounds last
        res = list(groups.values())
        res.sort(key=lambda g: (g.name == "System Sounds", g.name.lower()))
        return res

    def set_app_volume(self, name_or_pid: Any, volume: int) -> bool:
        """Sets volume for all sessions matching name or PID."""
        success = False
        for s in self.get_sessions(include_all_devices=True):
            if (isinstance(name_or_pid, int) and s.pid == name_or_pid) or \
               (isinstance(name_or_pid, str) and name_or_pid.lower() in s.name.lower()):
                s.volume = volume
                success = True
        return success

    def toggle_app_mute(self, name_or_pid: Any) -> Optional[bool]:
        """Toggles mute for all sessions matching name or PID."""
        for s in self.get_sessions(include_all_devices=True):
            if (isinstance(name_or_pid, int) and s.pid == name_or_pid) or \
               (isinstance(name_or_pid, str) and name_or_pid.lower() in s.name.lower()):
                return s.toggle_mute()
        return None


class AppGroup:
    """
    Aggregates multiple sessions belonging to the same application into a unified control.
    """

    def __init__(self, name: str):
        self.name = name
        self.sessions: List[AudioSessionItem] = []

    def add_session(self, session: AudioSessionItem):
        self.sessions.append(session)

    @property
    def pids(self) -> List[int]:
        return sorted(list(set(s.pid for s in self.sessions if s.pid)))

    @property
    def devices(self) -> List[str]:
        return sorted(list(set(s.device_name for s in self.sessions)))

    @property
    def volume(self) -> int:
        if not self.sessions:
            return 0
        return self.sessions[0].volume

    @volume.setter
    def volume(self, val: int):
        for s in self.sessions:
            s.volume = val

    @property
    def muted(self) -> bool:
        if not self.sessions:
            return False
        return any(s.muted for s in self.sessions)

    @muted.setter
    def muted(self, val: bool):
        for s in self.sessions:
            s.muted = val

    def toggle_mute(self) -> bool:
        new_state = not self.muted
        self.muted = new_state
        return new_state

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "pids": self.pids,
            "devices": self.devices,
            "volume": self.volume,
            "muted": self.muted,
        }

    def __repr__(self):
        return f"<AppGroup '{self.name}' Vol={self.volume}% Muted={self.muted} Devices={len(self.devices)}>"

