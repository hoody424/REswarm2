# Turtle Beach KB7 - USB HID Interfaces Breakdown

USB Device IDs:
* **Vendor ID (VID):** `0x10F5`
* **Product ID (PID):** `0x5038`

The device exposes 9 distinct HID collection paths across 4 USB interfaces (`mi_00` to `mi_03`):

---

### Interface 0: Low-Level ISP & Hardware Config (`mi_00`)
* **Path:** `\\?\hid#vid_10f5&pid_5038&mi_00...`
* **Usage Page:** `0xFF90` (Vendor-defined)
* **Usage:** `0xFF00`
* **Report Lengths:**
  * Input Report: 65 bytes
  * Output Report: 65 bytes
  * Feature Report: 65 bytes
* **Description:** Direct link to Sonix MCU for bootloader status, hardware reset, ISP commands, and mode switching.

---

### Interface 1: Display Streaming Controller (`mi_01`)
* **Path:** `\\?\hid#vid_10f5&pid_5038&mi_01...`
* **Usage Page:** `0xFF00` (Vendor-defined)
* **Usage:** `0x0001`
* **Report Lengths:**
  * Input Report: 65 bytes
  * Output Report: 65 bytes
  * Feature Report: 0 bytes
* **Description:** Dedicated bidirectional data pipeline for streaming LCD wallpapers ($800 \times 480$ RGB565), widget icons, and display state machines.

---

### Interface 2: Composite Peripherals & Events (`mi_02`)

Interface 2 contains 6 separate top-level collections:

#### Collection 01 (`COL01`): Consumer Control
* **Usage Page:** `0x000C` (Consumer Device)
* **Usage:** `0x0001` (Consumer Control)
* **Input Report:** 4 bytes
* **Description:** Standard consumer multimedia keys (Volume Up/Down, Mute, Play/Pause, Next, Previous).

#### Collection 02 (`COL02`): System Control
* **Usage Page:** `0x0001` (Generic Desktop)
* **Usage:** `0x0080` (System Control)
* **Input Report:** 2 bytes
* **Description:** Host system power management (Sleep, Wake, Power Off).

#### Collection 03 (`COL03`): Event Stream 1
* **Usage Page:** `0xFF01` (Vendor-defined)
* **Usage:** `0x0001`
* **Input Report:** 8 bytes
* **Description:** Hardware telemetry, profile switch notifications, dial/knob rotation ticks.

#### Collection 04 (`COL04`): Touch & Widget Interaction
* **Usage Page:** `0xFF02` (Vendor-defined)
* **Usage:** `0x0001`
* **Input Report:** 12 bytes
* **Description:** Real-time multi-touch digitizer reports, touch coordinates ($X, Y$), widget presses, and swipe events.

#### Collection 05 (`COL05`): Extra Macro Keys
* **Usage Page:** `0x0001` (Generic Desktop)
* **Usage:** `0x0006` (Keyboard)
* **Input Report:** 21 bytes
* **Description:** Extended macro keys, Easy-Shift[+] trigger signals, and secondary function keys.

#### Collection 06 (`COL06`): Lighting & Feature Configuration
* **Usage Page:** `0xFF03` (Vendor-defined)
* **Usage:** `0x0001`
* **Feature Report:** 1,044 bytes
* **Description:** Large memory payload block for per-key RGB lighting animations (AIMO), actuation point tables, and onboard memory profiles.

---

### Interface 3: Standard Gaming Keyboard (`mi_03`)
* **Path:** `\\?\hid#vid_10f5&pid_5038&mi_03...\kbd`
* **Usage Page:** `0x0001` (Generic Desktop)
* **Usage:** `0x0006` (Keyboard)
* **Input Report:** 9 bytes
* **Output Report:** 2 bytes (LED indicators: Num Lock, Caps Lock, Scroll Lock)
* **Description:** Primary ultra-fast 8,000 Hz USB HID keyboard report interface for standard keypress scanning.
