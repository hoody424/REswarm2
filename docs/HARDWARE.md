# Turtle Beach Command Series KB7 - Hardware Architecture

## 1. Physical Device & Display Specifications

The **Turtle Beach Command Series KB7** is an ultra-premium mechanical gaming keyboard equipped with an onboard capacitive touch command display.

* **Display Type:** 4.3-inch Full Color TFT LCD with capacitive multi-touch overlay
* **Resolution:** 800 × 480 pixels (WVGA aspect ratio 5:3)
* **Pixel Density:** ~217 PPI
* **Color Depth:** 16-bit True Color (RGB565, 65,536 colors)
* **Switch Technology:** Titan Low-Profile Magnetic / Hall-Effect Switches (Analog continuous sensing from 0.1 mm to 3.2 mm actuation depth)
* **Polling Rate:** Up to 8,000 Hz USB report rate (0.125 ms interval)

---

## 2. Microcontroller Architecture

The keyboard uses a distributed dual-microcontroller architecture connected via an internal high-speed bus.

```
       +-------------------------------------------------------+
       |                 Turtle Beach KB7                      |
       |                                                       |
       |   +-------------------+       +-------------------+   |
       |   |       MCU 1       |       |       MCU 2       |   |
       |   |   Sonix SNC73xx   |       |   Artery AT423    |   |
       |   | (Display/USB Host)|       |  (Analog Matrix)  |   |
       |   +---------+---------+       +---------+---------+   |
       |             |                           |             |
       |             v                           v             |
       |    [ 800x480 Touch LCD ]       [ 84 Hall Switches ]   |
       +-------------+---------------------------+-------------+
                     |                           |
                     +-------------+-------------+
                                   |
                                   v
                         [ Integrated USB Hub ]
                           (PID: 0x503D)
                                   |
                             USB-C to PC
```

### MCU 1: Sonix SNC73xx Series (LCD & System Controller)
* **Function:** Serves as the primary USB composite device interface to the operating system, handles the 4.3" touch display controller, stores and manages onboard graphics widgets, and executes the embedded graphics stack.
* **Firmware:** `KB7_V1.39.bin` (located in Swarm II package: `Data\Firmware\COMMAND_KB7\10f5_5038\139\KB7_V1.39.bin`)
* **Graphics Library:** Embedded **LVGL (Light and Versatile Graphics Library)**. LVGL manages screens, slots, widgets, and animation buffers onboard.
* **Storage Mode:** The device can switch dynamically to a USB Mass Storage device (`PID: 0x5037`) for flashing assets directly into flash memory.

### MCU 2: Artery AT423 / AT32F423 (Analog Switch Controller)
* **Function:** Dedicated real-time high-speed microcontroller responsible for analog Hall-effect switch matrix scanning, rapid trigger actuation detection, SOCD processing, and 8,000 Hz keyboard report transmission.
* **Firmware:** `AP_AT423_V1.15.bin`
* **Flash Base Address:** `0x08004000` (Erase sector size: 2048 bytes)

---

## 3. Firmware Update & ISP Mechanisms
Firmware updating is facilitated via:
* **Sonix ISP SDK:** `SNC73xx_Series_ISP_SDK.dll`
* **Bootloader Command Header:**
  `AA 55 A5 5A FF 00 33 CC` on interface `mi_00`
* **Address Range:** Memory programming base `0x60000000` for the Sonix image and `0x08004000` for the Artery switch controller.
