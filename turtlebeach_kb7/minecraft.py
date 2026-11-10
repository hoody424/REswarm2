"""
Minecraft ATM10 Companion & Live Telemetry Module for the Turtle Beach Command Series KB7.

Integrates with:
- Modpack: All the Mods 10 (ATM10) / NeoForge 1.21.1
- Live KubeJS client script exporting to ~/.kb7_minecraft_stats.json
- 12-Slot Compact Stream Deck hardware tiles (Page 3 or Page 2)
- High-Res 800x480 (480x800 portrait encoded) procedural Live HUD
- SteelSeries Aerox 3 & KB7 RGB lighting synchronization (Diamond Cyan & Low-Health Red Alert)
"""

from dataclasses import dataclass
import json
import math
from pathlib import Path
import time
from typing import List, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont

from .streamdeck import StreamDeckTile
from .image import LCD_WIDTH, LCD_HEIGHT

MINECRAFT_STATS_PATH = Path.home() / ".kb7_minecraft_stats.json"


@dataclass
class MinecraftStats:
    timestamp: float
    player: str
    health: float
    max_health: float
    health_pct: int
    food: int
    saturation: float
    armor: int
    xp_level: int
    xp_progress: int
    dimension: str
    coords: Tuple[int, int, int]
    diamonds: int
    allthemodium: int
    vibranium: int
    unobtainium: int
    netherite: int
    ancient_debris: int
    gold: int
    iron: int
    main_hand_name: str
    main_hand_durability: str
    main_hand_durability_pct: int

    @property
    def is_live(self) -> bool:
        """Returns True if the data was written within the last 15 seconds."""
        # Stats file timestamp is in milliseconds
        now_ms = time.time() * 1000.0
        return abs(now_ms - self.timestamp) < 15000.0

    @property
    def is_low_health(self) -> bool:
        """Returns True if player health is critical (<= 30% or <= 6 HP)."""
        return self.health_pct <= 30 or self.health <= 6.0


def load_minecraft_stats() -> Optional[MinecraftStats]:
    """
    Load live telemetry exported by the KubeJS companion script.
    Returns None if file is missing or unparseable.
    """
    if not MINECRAFT_STATS_PATH.exists():
        return None

    try:
        raw_text = MINECRAFT_STATS_PATH.read_text(encoding="utf-8")
        if not raw_text.strip():
            return None
        data = json.loads(raw_text)

        inv = data.get("inventory", {})
        coords_d = data.get("coords", {})
        mh = data.get("main_hand", {})

        return MinecraftStats(
            timestamp=float(data.get("timestamp", 0)),
            player=str(data.get("player", "Player")),
            health=float(data.get("health", 20.0)),
            max_health=float(data.get("max_health", 20.0)),
            health_pct=int(data.get("health_pct", 100)),
            food=int(data.get("food", 20)),
            saturation=float(data.get("saturation", 20.0)),
            armor=int(data.get("armor", 0)),
            xp_level=int(data.get("xp_level", 0)),
            xp_progress=int(data.get("xp_progress", 0)),
            dimension=str(data.get("dimension", "Overworld")),
            coords=(
                int(coords_d.get("x", 0)),
                int(coords_d.get("y", 64)),
                int(coords_d.get("z", 0)),
            ),
            diamonds=int(inv.get("diamonds", 0)),
            allthemodium=int(inv.get("allthemodium", 0)),
            vibranium=int(inv.get("vibranium", 0)),
            unobtainium=int(inv.get("unobtainium", 0)),
            netherite=int(inv.get("netherite", 0)),
            ancient_debris=int(inv.get("ancient_debris", 0)),
            gold=int(inv.get("gold", 0)),
            iron=int(inv.get("iron", 0)),
            main_hand_name=str(mh.get("name", "Empty")),
            main_hand_durability=str(mh.get("durability", "100%")),
            main_hand_durability_pct=int(mh.get("durability_pct", 100)),
        )
    except Exception:
        return None


def generate_minecraft_tiles(stats: Optional[MinecraftStats] = None) -> List[StreamDeckTile]:
    """
    Generate 12 dynamic compact 1x1 Stream Deck tiles based on live Minecraft statistics.
    If stats is None, generates default placeholders ready for live sync.
    """
    if stats is None:
        stats = MinecraftStats(
            timestamp=time.time() * 1000.0,
            player="Waiting...",
            health=20.0,
            max_health=20.0,
            health_pct=100,
            food=20,
            saturation=20.0,
            armor=0,
            xp_level=0,
            xp_progress=0,
            dimension="Waiting...",
            coords=(0, 0, 0),
            diamonds=0,
            allthemodium=0,
            vibranium=0,
            unobtainium=0,
            netherite=0,
            ancient_debris=0,
            gold=0,
            iron=0,
            main_hand_name="Empty",
            main_hand_durability="100%",
            main_hand_durability_pct=100,
        )

    # Health Color: Green/Cyan if full, Yellow if mid, Red if low/critical
    if stats.is_low_health:
        hp_col = "#ff1e32"
        hp_rgb = (255, 30, 50)
    elif stats.health_pct < 60:
        hp_col = "#ffab00"
        hp_rgb = (255, 171, 0)
    else:
        hp_col = "#00e575"
        hp_rgb = (0, 229, 117)

    # Diamonds formatting
    dia_txt = f"{stats.diamonds}x" if stats.diamonds > 0 else "0"
    dia_sub = "Im Inventar" if stats.diamonds > 0 else "Keine Diamanten"

    # Endgame Metals (Allthemodium & Netherite)
    metal_txt = f"ATM:{stats.allthemodium} N:{stats.netherite}"
    metal_sub = f"Debris:{stats.ancient_debris}" if stats.ancient_debris > 0 else "ATM / Netherite"

    # Coordinates formatting
    cx, cy, cz = stats.coords
    coords_txt = f"{cx}, {cz}"
    coords_sub = f"Y: {cy} (Höhe)"

    # Tool durability formatting
    tool_txt = stats.main_hand_durability or "100%"
    tool_sub = stats.main_hand_name[:12] if stats.main_hand_name else "Empty"

    return [
        # Slot 0: 💎 Diamonds in Inventory
        StreamDeckTile(
            slot=0,
            icon="💎",
            title=f"DIAMONDS: {dia_txt}",
            subtitle=dia_sub,
            color="#00e5ff",
            action_id="none",
            hw_app_id=12,
            hw_label=f"DIA {dia_txt}"[:11],
            rgb_sync=(0, 229, 255),
        ),
        # Slot 1: 🪙 Allthemodium & Netherite
        StreamDeckTile(
            slot=1,
            icon="🪙",
            title=metal_txt,
            subtitle=metal_sub,
            color="#ffb800",
            action_id="none",
            hw_app_id=13,
            hw_label=f"ATM:{stats.allthemodium} N:{stats.netherite}"[:11],
            rgb_sync=(255, 184, 0),
        ),
        # Slot 2: ❤️ Health / HP
        StreamDeckTile(
            slot=2,
            icon="❤️",
            title=f"HP: {stats.health:g}/{stats.max_health:g}",
            subtitle=f"{stats.health_pct}% Leben",
            color=hp_col,
            action_id="none",
            hw_app_id=14,
            hw_label=f"HP {int(stats.health)}/{int(stats.max_health)}"[:11],
            rgb_sync=hp_rgb,
        ),
        # Slot 3: 🛡️ Armor
        StreamDeckTile(
            slot=3,
            icon="🛡️",
            title=f"ARMOR: {stats.armor}",
            subtitle="Schutzwert",
            color="#00e5ff",
            action_id="none",
            hw_app_id=15,
            hw_label=f"ARMOR {stats.armor}"[:11],
            rgb_sync=(0, 229, 255),
        ),
        # Slot 4: ✨ XP Level
        StreamDeckTile(
            slot=4,
            icon="✨",
            title=f"XP: LVL {stats.xp_level}",
            subtitle=f"Progress: {stats.xp_progress}%",
            color="#00ff66",
            action_id="none",
            hw_app_id=16,
            hw_label=f"XP LVL {stats.xp_level}"[:11],
            rgb_sync=(0, 255, 102),
        ),
        # Slot 5: 🧭 Coordinates (X, Z) & Height (Y)
        StreamDeckTile(
            slot=5,
            icon="🧭",
            title=coords_txt,
            subtitle=coords_sub,
            color="#00e575",
            action_id="hotkey_clipboard",
            hw_app_id=17,
            hw_label=f"{cx},{cz}"[:11],
            rgb_sync=(0, 229, 117),
        ),
        # Slot 6: 🌍 Dimension
        StreamDeckTile(
            slot=6,
            icon="🌍",
            title=stats.dimension.upper()[:12],
            subtitle="Dimension",
            color="#a020f0",
            action_id="none",
            hw_app_id=18,
            hw_label=stats.dimension[:11].upper(),
            rgb_sync=(160, 32, 240),
        ),
        # Slot 7: ⚔️ Weapon / Tool Durability
        StreamDeckTile(
            slot=7,
            icon="⚔️",
            title=tool_txt,
            subtitle=tool_sub,
            color="#ffab00",
            action_id="none",
            hw_app_id=19,
            hw_label=f"DUR {stats.main_hand_durability_pct}%"[:11],
            rgb_sync=(255, 171, 0),
        ),
        # Slot 8: 🍖 Food & Saturation
        StreamDeckTile(
            slot=8,
            icon="🍖",
            title=f"HUNGER: {stats.food}/20",
            subtitle=f"Sat: {stats.saturation:g}",
            color="#ff9100",
            action_id="none",
            hw_app_id=20,
            hw_label=f"FOOD {stats.food}"[:11],
            rgb_sync=(255, 145, 0),
        ),
        # Slot 9: 📸 Screenshot / Snip
        StreamDeckTile(
            slot=9,
            icon="📸",
            title="SCREENSHOT",
            subtitle="Win+Shift+S / F2",
            color="#00e5ff",
            action_id="hotkey_screenshot",
            hw_app_id=26,
            hw_label="SCREENSHOT",
            rgb_sync=(0, 229, 255),
        ),
        # Slot 10: 🎙️ Discord Mic Mute
        StreamDeckTile(
            slot=10,
            icon="🎙️",
            title="DISC MUTE",
            subtitle="Ctrl+Shift+M",
            color="#5865f2",
            action_id="hotkey_discord_mute",
            hw_app_id=21,
            hw_label="DISC MUTE",
            rgb_sync=(88, 101, 242),
        ),
        # Slot 11: ⚡ Rapid Trigger
        StreamDeckTile(
            slot=11,
            icon="⚡",
            title="RAPID TRIGGER",
            subtitle="Hall-Effekt Speed",
            color="#00e5ff",
            action_id="none",
            hw_app_id=3005,
            hw_label="RAPID TRG",
            rgb_sync=(0, 229, 255),
        ),
    ]


def render_minecraft_hud_canvas(
    stats: Optional[MinecraftStats] = None,
    width: int = LCD_WIDTH,
    height: int = LCD_HEIGHT,
) -> Image.Image:
    """
    Renders a high-resolution 480x800 portrait framebuffer (compatible with Slot 0x00 / KB7 Display)
    featuring an RPG HUD with obsidian texture, glowing diamond crystals, real-time health/hunger,
    XP bar, coordinates, inventory diamond count, and ATM10 status.
    """
    if stats is None:
        stats = load_minecraft_stats()
        if stats is None:
            stats = MinecraftStats(
                timestamp=time.time() * 1000.0,
                player="hoody424",
                health=20.0,
                max_health=20.0,
                health_pct=100,
                food=20,
                saturation=20.0,
                armor=20,
                xp_level=45,
                xp_progress=72,
                dimension="Overworld",
                coords=(124, 68, -420),
                diamonds=64,
                allthemodium=4,
                vibranium=0,
                unobtainium=0,
                netherite=12,
                ancient_debris=8,
                gold=128,
                iron=256,
                main_hand_name="Diamond Pickaxe",
                main_hand_durability="1420/1561",
                main_hand_durability_pct=91,
            )

    # Render at 2x Supersampling for ultra-crisp borders and typography
    scale = 2
    sw, sh = width * scale, height * scale
    im = Image.new("RGB", (sw, sh), (11, 14, 20))
    draw = ImageDraw.Draw(im)

    # 1. Subtle Obsidian / Dark Stone Pattern
    for y in range(0, sh, 16 * scale):
        for x in range(0, sw, 16 * scale):
            # Deterministic noise based on coordinates
            val = ((x * 13 + y * 29) % 17) - 8
            bg_c = (max(0, 14 + val), max(0, 18 + val), max(0, 25 + val))
            draw.rectangle([x, y, x + 15 * scale, y + 15 * scale], fill=bg_c)

    # Outer Decorative Obsidian Border with Diamond Cyan Accent
    border_col = (0, 229, 255)
    border_w = 4 * scale
    draw.rectangle([border_w, border_w, sw - border_w, sh - border_w], outline=border_col, width=border_w)
    draw.rectangle([border_w + 3 * scale, border_w + 3 * scale, sw - border_w - 3 * scale, sh - border_w - 3 * scale], outline=(20, 35, 55), width=2 * scale)

    # Header Card: ATM10 + Player Name
    draw.rectangle([20 * scale, 24 * scale, sw - 20 * scale, 84 * scale], fill=(16, 22, 34), outline=(0, 229, 255), width=2 * scale)
    draw.text((36 * scale, 34 * scale), "MINECRAFT ATM10 LIVE HUD", fill=(0, 229, 255))
    live_badge = "● LIVE" if stats.is_live else "○ OFFLINE"
    live_col = (0, 255, 117) if stats.is_live else (120, 130, 150)
    draw.text((sw - 120 * scale, 34 * scale), live_badge, fill=live_col)
    draw.text((36 * scale, 58 * scale), f"Player: {stats.player} | Dim: {stats.dimension}", fill=(200, 215, 230))

    # Hero Card: 💎 Diamonds in Inventory
    draw.rectangle([20 * scale, 96 * scale, sw - 20 * scale, 210 * scale], fill=(14, 28, 44), outline=(0, 229, 255), width=3 * scale)
    draw.text((36 * scale, 108 * scale), "💎 INVENTORY DIAMONDS", fill=(0, 229, 255))
    draw.text((36 * scale, 134 * scale), f"{stats.diamonds}", fill=(255, 255, 255))
    draw.text((140 * scale, 148 * scale), "Diamanten gezählt (Steine + Blöcke)", fill=(160, 200, 230))
    draw.text((36 * scale, 182 * scale), f"Netherite: {stats.netherite}  |  Debris: {stats.ancient_debris}  |  AllTheModium: {stats.allthemodium}", fill=(255, 184, 0))

    # Health & Armor Section
    hp_y = 224 * scale
    draw.rectangle([20 * scale, hp_y, sw - 20 * scale, hp_y + 90 * scale], fill=(22, 16, 20), outline=(255, 50, 70), width=2 * scale)
    draw.text((36 * scale, hp_y + 10 * scale), "❤️ HEALTH & DEFENSE", fill=(255, 82, 82))
    # HP Bar Background
    bar_x = 36 * scale
    bar_w = sw - 72 * scale
    draw.rectangle([bar_x, hp_y + 36 * scale, bar_x + bar_w, hp_y + 56 * scale], fill=(45, 15, 20))
    # HP Bar Fill
    hp_fill_w = int(bar_w * (max(0.0, min(100.0, stats.health_pct)) / 100.0))
    hp_fill_col = (255, 30, 50) if stats.is_low_health else (255, 60, 80)
    draw.rectangle([bar_x, hp_y + 36 * scale, bar_x + hp_fill_w, hp_y + 56 * scale], fill=hp_fill_col)
    draw.text((bar_x + 8 * scale, hp_y + 40 * scale), f"{stats.health:g} / {stats.max_health:g} HP ({stats.health_pct}%)", fill=(255, 255, 255))
    draw.text((36 * scale, hp_y + 64 * scale), f"🛡️ Armor: {stats.armor}  |  🍖 Food: {stats.food}/20  |  Sat: {stats.saturation:g}", fill=(200, 200, 200))

    # XP Level Section
    xp_y = 326 * scale
    draw.rectangle([20 * scale, xp_y, sw - 20 * scale, xp_y + 70 * scale], fill=(14, 25, 18), outline=(0, 255, 102), width=2 * scale)
    draw.text((36 * scale, xp_y + 10 * scale), f"✨ EXPERIENCE: LEVEL {stats.xp_level}", fill=(0, 255, 102))
    # XP Bar
    draw.rectangle([bar_x, xp_y + 34 * scale, bar_x + bar_w, xp_y + 50 * scale], fill=(20, 45, 25))
    xp_fill_w = int(bar_w * (max(0.0, min(100.0, stats.xp_progress)) / 100.0))
    draw.rectangle([bar_x, xp_y + 34 * scale, bar_x + xp_fill_w, xp_y + 50 * scale], fill=(0, 255, 102))
    draw.text((sw - 120 * scale, xp_y + 10 * scale), f"{stats.xp_progress}% to next", fill=(160, 240, 180))

    # Coordinates & Dimension Card
    pos_y = 408 * scale
    draw.rectangle([20 * scale, pos_y, sw - 20 * scale, pos_y + 80 * scale], fill=(18, 22, 32), outline=(0, 229, 255), width=2 * scale)
    draw.text((36 * scale, pos_y + 10 * scale), "🧭 WORLD POSITION", fill=(0, 229, 255))
    cx, cy, cz = stats.coords
    draw.text((36 * scale, pos_y + 36 * scale), f"X: {cx}    Y: {cy} (Höhe)    Z: {cz}", fill=(255, 255, 255))
    draw.text((36 * scale, pos_y + 58 * scale), f"Aktuelle Dimension: {stats.dimension}", fill=(180, 195, 210))

    # Weapon / Equipped Tool Card
    tool_y = 500 * scale
    draw.rectangle([20 * scale, tool_y, sw - 20 * scale, tool_y + 80 * scale], fill=(24, 20, 16), outline=(255, 171, 0), width=2 * scale)
    draw.text((36 * scale, tool_y + 10 * scale), "⚔️ HAUPTHAND WERKZEUG / WAFFE", fill=(255, 171, 0))
    draw.text((36 * scale, tool_y + 34 * scale), f"{stats.main_hand_name}", fill=(255, 255, 255))
    # Tool Durability Bar
    draw.rectangle([bar_x, tool_y + 54 * scale, bar_x + bar_w, tool_y + 68 * scale], fill=(50, 40, 25))
    dur_fill_w = int(bar_w * (max(0.0, min(100.0, stats.main_hand_durability_pct)) / 100.0))
    draw.rectangle([bar_x, tool_y + 54 * scale, bar_x + dur_fill_w, tool_y + 68 * scale], fill=(255, 184, 0))
    draw.text((bar_x + 8 * scale, tool_y + 55 * scale), f"Haltbarkeit: {stats.main_hand_durability} ({stats.main_hand_durability_pct}%)", fill=(20, 20, 20))

    # Footer Card: KB7 Hardware Touch Controls
    foot_y = 592 * scale
    draw.rectangle([20 * scale, foot_y, sw - 20 * scale, sh - 20 * scale], fill=(14, 18, 28), outline=(60, 75, 100), width=2 * scale)
    draw.text((36 * scale, foot_y + 14 * scale), "TOUCH TASTEN:", fill=(0, 229, 255))
    draw.text((36 * scale, foot_y + 38 * scale), "[S9] Screenshot (Win+Shift+S)   |   [S10] Discord Mute", fill=(200, 215, 230))
    draw.text((36 * scale, foot_y + 60 * scale), "[S5] Coords in Zwischenablage   |   [S11] Rapid Trigger", fill=(200, 215, 230))
    draw.text((36 * scale, foot_y + 82 * scale), "Hardware Stream Deck aktiv auf Seite 3 (12 Kacheln)", fill=(120, 140, 160))

    return im.resize((width, height), Image.Resampling.LANCZOS)
