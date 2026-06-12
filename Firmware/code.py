import board
import busio
import displayio
import terminalio
import random
from adafruit_display_text import label
from kmk.kmk_keyboard import KMKKeyboard
from kmk.keys import KC, make_key
from kmk.scanners import DiodeOrientation
from kmk.modules.encoder import EncoderHandler
from kmk.extensions.media_keys import MediaKeys
from kmk.extensions import Extension

# =========================
# CONSTANTS
# =========================
WIDTH     = 128
HEIGHT    = 32
MAX_BALLS = 16
MIN_RADIUS = 2
MAX_RADIUS = 12
DEFAULT_RADIUS = 4

# =========================
# OLED SETUP
# =========================
import i2cdisplaybus
import adafruit_displayio_ssd1306

displayio.release_displays()
i2c = busio.I2C(scl=board.SCL, sda=board.SDA)
display_bus = i2cdisplaybus.I2CDisplayBus(i2c, device_address=0x3C)
oled = adafruit_displayio_ssd1306.SSD1306(display_bus, width=WIDTH, height=HEIGHT)
oled.brightness = 0.3

# =========================
# ANIMATION EXTENSION
# =========================
class BouncingBall(Extension):
    def __init__(self):
        # state
        self.balls          = []
        self.ball_tiles     = []
        self.bounces        = 0
        self.speed          = 1.0
        self.paused         = False
        self.inverted       = False
        self.collisions     = False

        # build display group
        self.splash = displayio.Group()
        self._init_background()
        self._add_ball(radius=DEFAULT_RADIUS)
        self._init_labels()
        oled.root_group = self.splash

    # --- setup helpers ---

    def _init_background(self):
        self.bg_bmp = displayio.Bitmap(WIDTH, HEIGHT, 2)
        self.bg_pal = displayio.Palette(2)
        self.bg_pal[0] = 0x000000
        self.bg_pal[1] = 0xFFFFFF
        for i in range(WIDTH * HEIGHT):
            self.bg_bmp[i] = 0
        self.bg_tile = displayio.TileGrid(
            self.bg_bmp, pixel_shader=self.bg_pal, x=0, y=0
        )
        self.splash.append(self.bg_tile)

    def _init_labels(self):
        self.speed_label = label.Label(
            terminalio.FONT,
            text="x1.00",
            color=0xFFFFFF,
            x=2,
            y=4,
        )
        self.bounce_label = label.Label(
            terminalio.FONT,
            text="0",
            color=0xFFFFFF,
            x=2,
            y=18,
        )
        self.splash.append(self.speed_label)
        self.splash.append(self.bounce_label)

    def _make_ball_bitmap(self, radius):
        bmp = displayio.Bitmap(radius * 2, radius * 2, 2)
        pal = displayio.Palette(2)
        pal[0] = 0xFFFFFF if self.inverted else 0x000000
        pal[1] = 0x000000 if self.inverted else 0xFFFFFF
        for px in range(radius * 2):
            for py in range(radius * 2):
                if (px - radius) ** 2 + (py - radius) ** 2 <= radius ** 2:
                    bmp[px, py] = 1
        return bmp, pal

    def _add_ball(self, radius=DEFAULT_RADIUS):
        if len(self.balls) >= MAX_BALLS:
            return
        bmp, pal = self._make_ball_bitmap(radius)
        tile = displayio.TileGrid(
            bmp, pixel_shader=pal,
            x=random.randint(0, WIDTH - radius * 2),
            y=random.randint(0, HEIGHT - radius * 2),
        )
        self.splash.insert(1 + len(self.ball_tiles), tile)
        self.ball_tiles.append(tile)
        self.balls.append({
            "x":      float(random.randint(0, WIDTH - radius * 2)),
            "y":      float(random.randint(0, HEIGHT - radius * 2)),
            "dx":     random.choice([-1, 1]) * random.uniform(0.3, 0.5),
            "dy":     random.choice([-1, 1]) * random.uniform(0.1, 0.2),
            "radius": radius,
        })

    def _rebuild_ball_bitmaps(self):
        for tile in self.ball_tiles:
            self.splash.remove(tile)
        self.ball_tiles = []
        for i, ball in enumerate(self.balls):
            bmp, pal = self._make_ball_bitmap(ball["radius"])
            tile = displayio.TileGrid(
                bmp, pixel_shader=pal,
                x=int(ball["x"]),
                y=int(ball["y"]),
            )
            self.splash.insert(1 + i, tile)
            self.ball_tiles.append(tile)

    # --- ball controls ---

    def add_ball(self):
        r = self.balls[0]["radius"] if self.balls else DEFAULT_RADIUS
        self._add_ball(radius=r)

    def remove_ball(self):
        if len(self.balls) <= 1:
            return
        self.splash.remove(self.ball_tiles[-1])
        self.ball_tiles.pop()
        self.balls.pop()

    def grow_balls(self):
        for ball in self.balls:
            ball["radius"] = min(MAX_RADIUS, ball["radius"] + 1)
        self._rebuild_ball_bitmaps()

    def shrink_balls(self):
        for ball in self.balls:
            ball["radius"] = max(MIN_RADIUS, ball["radius"] - 1)
        self._rebuild_ball_bitmaps()

    def toggle_collisions(self):
        self.collisions = not self.collisions

    # --- display controls ---

    def toggle_invert(self):
        self.inverted = not self.inverted
        self.bg_pal[0], self.bg_pal[1] = self.bg_pal[1], self.bg_pal[0]
        for tile in self.ball_tiles:
            tile.pixel_shader[0], tile.pixel_shader[1] = \
                tile.pixel_shader[1], tile.pixel_shader[0]
        c = 0x000000 if self.inverted else 0xFFFFFF
        self.speed_label.color  = c
        self.bounce_label.color = c

    def brightness_up(self):
        oled.brightness = min(1.0, round(oled.brightness + 0.1, 1))

    def brightness_down(self):
        oled.brightness = max(0.0, round(oled.brightness - 0.1, 1))

    # --- speed controls ---

    def speed_up(self):
        self.speed = min(5.0, round(self.speed + 0.25, 2))
        self.speed_label.text = "x{:.2f}".format(self.speed)

    def speed_down(self):
        self.speed = max(0.1, round(self.speed - 0.25, 2))
        self.speed_label.text = "x{:.2f}".format(self.speed)

    def toggle_pause(self):
        self.paused = not self.paused
        self.speed_label.text = "PAUSE" if self.paused else "x{:.2f}".format(self.speed)

    # --- KMK hooks ---

    def during_bootup(self, keyboard):
        pass

    def before_matrix_scan(self, sandbox):
        if self.paused:
            return

        # move balls and bounce off walls
        for i, ball in enumerate(self.balls):
            r = ball["radius"]
            ball["x"] += ball["dx"] * self.speed
            ball["y"] += ball["dy"] * self.speed

            if ball["x"] <= 0:
                ball["x"] = 0
                ball["dx"] = abs(ball["dx"])
                self.bounces += 1
            elif ball["x"] >= WIDTH - r * 2:
                ball["x"] = WIDTH - r * 2
                ball["dx"] = -abs(ball["dx"])
                self.bounces += 1

            if ball["y"] <= 0:
                ball["y"] = 0
                ball["dy"] = abs(ball["dy"])
                self.bounces += 1
            elif ball["y"] >= HEIGHT - r * 2:
                ball["y"] = HEIGHT - r * 2
                ball["dy"] = -abs(ball["dy"])
                self.bounces += 1

            self.ball_tiles[i].x = int(ball["x"])
            self.ball_tiles[i].y = int(ball["y"])

        # ball-to-ball collisions
        if self.collisions:
            for i in range(len(self.balls)):
                for j in range(i + 1, len(self.balls)):
                    b1 = self.balls[i]
                    b2 = self.balls[j]
                    dx = b1["x"] - b2["x"]
                    dy = b1["y"] - b2["y"]
                    dist = (dx * dx + dy * dy) ** 0.5
                    min_dist = b1["radius"] + b2["radius"]

                    if dist < min_dist and dist > 0:
                        # collision normal (unit vector pointing from b2 to b1)
                        nx = dx / dist
                        ny = dy / dist

                        # relative velocity along the normal
                        dvx = b1["dx"] - b2["dx"]
                        dvy = b1["dy"] - b2["dy"]
                        dot = dvx * nx + dvy * ny

                        # only resolve if balls are moving toward each other
                        if dot < 0:
                            # elastic collision impulse (equal mass assumed)
                            b1["dx"] -= dot * nx
                            b1["dy"] -= dot * ny
                            b2["dx"] += dot * nx
                            b2["dy"] += dot * ny

                        # push apart to prevent sticking
                        overlap = min_dist - dist
                        b1["x"] += nx * overlap * 0.5
                        b1["y"] += ny * overlap * 0.5
                        b2["x"] -= nx * overlap * 0.5
                        b2["y"] -= ny * overlap * 0.5

        self.bounce_label.text = str(self.bounces)

    def after_matrix_scan(self, sandbox):   pass
    def before_hid_send(self, sandbox):     pass
    def after_hid_send(self, sandbox):      pass
    def on_runtime_enable(self, sandbox):   pass
    def on_runtime_disable(self, sandbox):  pass
    def on_powersave_enable(self, sandbox): pass
    def on_powersave_disable(self, sandbox):pass

# =========================
# KEYBOARD SETUP
# =========================
keyboard = KMKKeyboard()
keyboard.extensions.append(MediaKeys())

keyboard.col_pins = (board.D0, board.D1, board.D2, board.D3)
keyboard.row_pins = (board.D7, board.D8)
keyboard.diode_orientation = DiodeOrientation.COL2ROW

# =========================
# ANIMATION
# =========================
ball_ext = BouncingBall()
keyboard.extensions.append(ball_ext)

# =========================
# CUSTOM KEYS
# =========================
make_key(names=("ADD_BALL",),          on_press=lambda *a: ball_ext.add_ball())
make_key(names=("REMOVE_BALL",),       on_press=lambda *a: ball_ext.remove_ball())
make_key(names=("GROW",),              on_press=lambda *a: ball_ext.grow_balls())
make_key(names=("SHRINK",),            on_press=lambda *a: ball_ext.shrink_balls())
make_key(names=("TOGGLE_COLLISIONS",), on_press=lambda *a: ball_ext.toggle_collisions())
make_key(names=("INVERT",),            on_press=lambda *a: ball_ext.toggle_invert())
make_key(names=("BRIGHTNESS_UP",),     on_press=lambda *a: ball_ext.brightness_up())
make_key(names=("BRIGHTNESS_DOWN",),   on_press=lambda *a: ball_ext.brightness_down())
make_key(names=("SPD_UP",),            on_press=lambda *a: ball_ext.speed_up())
make_key(names=("SPD_DN",),            on_press=lambda *a: ball_ext.speed_down())
make_key(names=("PAUSE",),             on_press=lambda *a: ball_ext.toggle_pause())

# =========================
# ENCODER — speed control
# =========================
encoder_handler = EncoderHandler()
encoder_handler.pins = (
    (board.D9, board.D10, board.D6, False, 4),
)
encoder_handler.map = [
    ((KC.SPD_DN, KC.SPD_UP, KC.PAUSE),),
]
keyboard.modules.append(encoder_handler)

# =========================
# KEYMAP
# row 1:  add ball | grow  | toggle collisions | brightness up
# row 2:  rem ball | shrink| invert            | brightness down
# =========================
keyboard.keymap = [
    [
        KC.ADD_BALL,    KC.GROW,   KC.TOGGLE_COLLISIONS, KC.BRIGHTNESS_UP,
        KC.REMOVE_BALL, KC.SHRINK, KC.INVERT,            KC.BRIGHTNESS_DOWN,
    ]
]

if __name__ == "__main__":
    keyboard.go()
