# Turtle Beach KB7 - Universal Windows Sound Display & Audio Mixer

## 1. Problem Overview & Root Cause Analysis

Many users of the **Turtle Beach Command Series KB7** (and Windows 10/11 gamers in general) noticed that:
1. **The Sound Display / Volume Mixer in Swarm II disappeared or broke completely.**
2. **When it did exist, it missed most apps** (e.g. Discord, games, media players, browser tabs) and could not control their volume.

### Why Did the Original Mixer Fail? (Reverse Engineering Insights)

During reverse engineering of `COMMAND_KB7.dll`, `SystemMedia.dll`, and `PluginManager.dll`, three distinct bugs and architectural flaws were discovered:

```
+-----------------------------------------------------------------------------------------+
|                               SWARM II ARCHITECTURAL FLAWS                              |
+-----------------------------------------------------------------------------------------+
| 1. Win32 Apps Filtered Out:                                                             |
|    SystemMedia.dll checked for Windows AUMIDs (Application User Model ID):               |
|    "No AUMID (Win32...)" -> Ignored! Classic desktop programs (Discord, Steam, Games)    |
|    do not have UWP AUMIDs and were discarded.                                           |
|                                                                                         |
| 2. Single-Device Blindspot:                                                             |
|    Swarm II only queried GetDefaultAudioEndpoint(). In modern setups with               |
|    virtual audio devices (SteelSeries Sonar Chat/Game/Media, Voicemeeter, Elgato Wavelink)|
|    audio is split across multiple endpoints. Swarm II was completely blind to them.    |
|                                                                                         |
| 3. Unstable IPC Crash:                                                                  |
|    Swarm II logs showed "refresh_volume_mixer_list: SYSTEM_MEDIA_PLUGIN not found".     |
|    The internal IPC bridge between the main UI and SystemMedia.dll crashed on launch.   |
+-----------------------------------------------------------------------------------------+
```

Furthermore, **Windows 11** deprecated the classic Windows Volume Mixer (`sndvol.exe`), hiding per-app sliders deep inside the multi-click Windows Settings app.

---

## 2. The Solution: `UniversalAudioMixer` & KB7 GUI

The **Universal Audio Mixer** provides a clean, modern replacement designed specifically for the KB7 keyboard and Windows 10/11:

* **100% Application Coverage:** Uses WASAPI Core Audio (`IAudioSessionManager2` and `ISimpleAudioVolume`) with `psutil` process resolution. Every Win32 executable, background service, game, and UWP app is detected.
* **Multi-Endpoint Routing:** Scans all active playback devices (SteelSeries Sonar Gaming, Sonar Chat, Voicemeeter, USB headsets, Realtek, HDMI).
* **Unified Application Grouping:** Intelligently groups multi-session applications (e.g., Discord or Steam routing voice and notifications across different virtual endpoints) into a single, clean fader.
* **KB7 Hardware Integration:** Directly binds to `KB7Daemon` so you can adjust the active channel's volume using the physical keyboard Rotary Dial or touch display gestures.

---

## 3. Launching the Sound Mixer

### Interactive Dark Mode GUI
```bash
python -m turtlebeach_kb7.cli mixer
```

Features:
* **Master Fader Card:** Controls system-wide master output with real-time level and Mute button.
* **Per-App Channel Faders:** Vertical channel strips for Discord, Steam, Spotify, Chrome, Games, and System Sounds.
* **Hardware Dial Binding:** Click any application card to bind it to the KB7 physical rotary dial / knob.
* **Live Auto-Sync:** Automatically updates when volume is changed externally (via Windows, in-game, or keyboard volume keys).

### Terminal / Command Line Interface (CLI)
```bash
# View table of all running audio sessions
python -m turtlebeach_kb7.cli mixer --cli

# Set application volume directly (e.g. set Discord to 80%)
python -m turtlebeach_kb7.cli mixer --cli --set-app Discord --volume 80

# Toggle mute for an application
python -m turtlebeach_kb7.cli mixer --cli --mute-app Steam

# Toggle Master Output mute
python -m turtlebeach_kb7.cli mixer --cli --mute-master
```

Example CLI Output:
```text
==================================================
 Turtle Beach KB7 - Windows Audio Mixer (CLI)
==================================================
Master Output: SteelSeries Sonar - Gaming (SteelSeries Sonar Virtual Audio Device)
Master Volume: 100% | Muted: False
--------------------------------------------------
Application            | Volume  | Muted  | Target Audio Device(s)
---------------------------------------------------------------------------
Audiodg                |    75% | no     | Lautsprecher (Jabra SPEAK 510 USB)
Discord                |   100% | no     | SteelSeries Sonar - Chat, Sonar - Gaming
Ledkeeper2             |   100% | no     | SteelSeries Sonar - Gaming
Steam                  |   100% | no     | CABLE Input, Headphones (Arctis 7P+)
Steelseriesggclient    |   100% | YES    | Lautsprecher, Microphone (Arctis 7P+)
System Sounds          |   100% | no     | CABLE Input, CABLE Output
--------------------------------------------------
```

---

## 4. Python SDK Usage

You can also use the audio engine programmatically inside your own plugins:

```python
from turtlebeach_kb7 import UniversalAudioMixer

mixer = UniversalAudioMixer()

# 1. Master Output
master = mixer.get_default_device()
print(f"Master: {master.name} at {master.volume}% (Muted: {master.muted})")
master.volume = 80
master.toggle_mute()

# 2. Per-Application Control
for app in mixer.get_grouped_apps():
    print(f"App: {app.name:<15} | Volume: {app.volume}% | Muted: {app.muted}")

# Set Discord volume to 85%
mixer.set_app_volume("Discord", 85)

# Mute/unmute Spotify or a game
mixer.toggle_app_mute("Spotify")
```
