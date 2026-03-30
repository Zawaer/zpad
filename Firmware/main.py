# main.py
# Hackpad firmware for:
# - XIAO RP2040
# - 2x4 key matrix
# - EC11 rotary encoder
# - 0.91" I2C OLED
#
# Requires KMK + SSD1306 extension support on the board.

import board
import busio

from kmk.kmk_keyboard import KMKKeyboard
from kmk.keys import KC
from kmk.scanners import DiodeOrientation

from kmk.modules.encoder import EncoderHandler
from kmk.extensions.display import Display, TextDisplay, SSD1306

keyboard = KMKKeyboard()

# =========================
# MATRIX PINS
# =========================
# 2x4 layout
keyboard.col_pins = (board.GP3, board.GP2, board.GP1, board.GP0)
keyboard.row_pins = (board.GP8, board.GP9)

# Change if your diodes are reversed
keyboard.diode_orientation = DiodeOrientation.COL2ROW

# =========================
# ENCODER
# =========================
encoder_handler = EncoderHandler()
keyboard.modules.append(encoder_handler)

encoder_handler.pins = (
    (board.GP4, board.GP5, board.GP6, False),  # (A, B, button_pin, reversed)
)

# =========================
# OLED
# =========================
i2c = busio.I2C(scl=board.GP10, sda=board.GP9)

display = Display(
    display=SSD1306(
        i2c=i2c,
        device_address=0x3C,
        width=128,
        height=32,
    ),
    # very simple text pages
    entries=[
        TextDisplay(text="Hackpad", x=0, y=0, show=True),
        TextDisplay(text="Layer 0", x=0, y=12, show=True),
        TextDisplay(text="2x4 + OLED + ENC", x=0, y=24, show=True),
    ],
)
keyboard.extensions.append(display)

# =========================
# KEYMAP
# =========================
keyboard.keymap = [
    [
        KC.ESC,   KC.Q,    KC.W,    KC.E,
        KC.A,     KC.S,    KC.D,    KC.F,
    ]
]

# =========================
# ENCODER ACTIONS
# =========================

# Rotate left / right actions:
encoder_handler.map = [
    ((KC.VOLD, KC.VOLU, KC.MUTE),),
]

if __name__ == '__main__':
    keyboard.go()
