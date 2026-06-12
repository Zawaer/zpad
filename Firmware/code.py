import board
import busio
from kmk.kmk_keyboard import KMKKeyboard
from kmk.keys import KC
from kmk.scanners import DiodeOrientation
from kmk.modules.encoder import EncoderHandler
from kmk.extensions.display import Display, TextEntry
from kmk.extensions.display.ssd1306 import SSD1306
from kmk.extensions.media_keys import MediaKeys

keyboard = KMKKeyboard()
keyboard.extensions.append(MediaKeys())

# =========================
# MATRIX
# =========================
keyboard.col_pins = (board.D0, board.D1, board.D2, board.D3)
keyboard.row_pins = (board.D7, board.D8)
keyboard.diode_orientation = DiodeOrientation.COL2ROW

# =========================
# ENCODER
# =========================
encoder_handler = EncoderHandler()
encoder_handler.pins = (
    (board.D9, board.D10, board.D6, False),
)
encoder_handler.map = [
    ((KC.VOLD, KC.VOLU, KC.MUTE),),
]
keyboard.modules.append(encoder_handler)

# =========================
# OLED
# =========================
i2c = busio.I2C(scl=board.SCL, sda=board.SDA)
display = Display(
    display=SSD1306(
        i2c=i2c,
        device_address=0x3C,
    ),
    width=128,
    height=32,
    entries=[
        TextEntry(text="ZPad",         x=0, y=0),
        TextEntry(text="KMK Firmware", x=0, y=12),
        TextEntry(text="macOS Ready",  x=0, y=24),
    ],
)
keyboard.extensions.append(display)

# =========================
# KEYMAP
# =========================
keyboard.keymap = [
    [
        KC.Q, KC.W, KC.E, KC.R,
        KC.T, KC.Y, KC.U, KC.I,
    ]
]

if __name__ == "__main__":
    keyboard.go()
