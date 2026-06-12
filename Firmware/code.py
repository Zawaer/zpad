import board
import busio
import displayio
import terminalio
import supervisor
import random
import math
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
WIDTH          = 128
HEIGHT         = 32
MAX_BALLS      = 16
MIN_RADIUS     = 2
MAX_RADIUS     = 12
DEFAULT_RADIUS = 4
NUM_SCENES     = 4  # balls, starfield, matrix, sine wave

# =========================
# OLED SETUP
# =========================
import i2cdisplaybus
import adafruit_displayio_ssd1306

displayio.release_displays()
i2c = busio.I2C(scl=board.SCL, sda=board.SDA)
display_bus = i2cdisplaybus.I2CDisplayBus(i2c, device_address=0x3C)
oled = adafruit_displayio_ssd1306.SSD1306(display_bus, width=WIDTH, height=HEIGHT)
oled.brightness = 0.0

# =========================
# ANIMATION EXTENSION
# =========================
class AnimationExtension(Extension):
    def __init__(self):
        # shared state
        self.scene             = 0
        self.inverted          = False
        self.bright_on         = False
        self.frame             = 0
        self.hud_visible = False
        self.paused            = False
        self.speed             = 1.0

        # ball scene state
        self.balls             = []
        self.ball_tiles        = []
        self.bounces           = 0
        self.collisions        = False

        # starfield state
        self.stars = [
            {
                "x":     float(random.randint(0, WIDTH - 1)),
                "y":     float(random.randint(0, HEIGHT - 1)),
                "speed": random.uniform(0.5, 3.0),
            }
            for _ in range(30)
        ]

        # sine wave state
        self.sine_offset = 0.0

        # build display group FIRST
        self.splash = displayio.Group()
        self._init_background()
        self._add_ball(radius=DEFAULT_RADIUS)

        # matrix rain — AFTER splash exists
        MATRIX_NUM_COLS = 20
        self.matrix_labels = []
        for i in range(MATRIX_NUM_COLS):
            x = i * (WIDTH // MATRIX_NUM_COLS)
            lbl = label.Label(
                terminalio.FONT,
                text=random.choice("01"),
                color=0xFFFFFF,
                x=-20,
                y=random.randint(0, HEIGHT),
            )
            self.matrix_labels.append({
                "label": lbl,
                "speed": random.uniform(0.5, 2.0),
                "y":     float(random.randint(-HEIGHT, 0)),
                "x":     x,
            })
            self.splash.append(lbl)

        self._init_labels()

        # HUD overlay — temporary speed/pause indicator for non-ball scenes
        self.hud_label = label.Label(
            terminalio.FONT,
            text="",
            color=0x000000,  # hidden by default
            x=40,
            y=16,
        )
        self.hud_visible_until = 0
        self.splash.append(self.hud_label)

        oled.root_group = self.splash

    # =========================
    # SHARED DISPLAY HELPERS
    # =========================

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

    def _clear_background(self):
        for i in range(WIDTH * HEIGHT):
            self.bg_bmp[i] = 0

    def _set_pixel(self, x, y, val=1):
        if 0 <= x < WIDTH and 0 <= y < HEIGHT:
            self.bg_bmp[y * WIDTH + x] = val

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

    def _show_labels(self, show):
        if not show:
            # always hide using current background color
            c = 0xFFFFFF if self.inverted else 0x000000
        else:
            # show using current foreground color
            c = 0x000000 if self.inverted else 0xFFFFFF
        self.speed_label.color  = c
        self.bounce_label.color = c

    def _show_hud(self, text):
        self.hud_label.text    = text
        self.hud_label.color   = 0x000000 if self.inverted else 0xFFFFFF
        self.hud_visible_until = supervisor.ticks_ms() + 1000  # 1000ms = 1 second
        self.hud_visible       = True

    def _hide_hud(self):
        self.hud_label.color = 0xFFFFFF if self.inverted else 0x000000
        self.hud_visible     = False

    # =========================
    # BALL SCENE HELPERS
    # =========================

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

    def _hide_balls(self):
        for tile in self.ball_tiles:
            tile.x = -100
            tile.y = -100

    def _show_balls(self):
        for i, ball in enumerate(self.balls):
            self.ball_tiles[i].x = int(ball["x"])
            self.ball_tiles[i].y = int(ball["y"])

    # =========================
    # SCENE RENDERING
    # =========================

    def _render_starfield(self):
        for star in self.stars:
            self._set_pixel(int(star["x"]), int(star["y"]), 0)
            star["x"] -= star["speed"] * self.speed
            if star["x"] < 0:
                star["x"] = float(WIDTH - 1)
                star["y"] = float(random.randint(0, HEIGHT - 1))
                star["speed"] = random.uniform(0.5, 3.0)
            self._set_pixel(int(star["x"]), int(star["y"]), 1)

    def _render_matrix(self):
        for col in self.matrix_labels:
            col["y"] += col["speed"] * self.speed
            lbl = col["label"]
            lbl.y = int(col["y"])
            lbl.text = random.choice("01")
            if col["y"] > HEIGHT + 8:
                col["y"] = float(random.randint(-HEIGHT, -8))
                col["speed"] = random.uniform(0.5, 2.0)

    def _hide_matrix(self):
        for col in self.matrix_labels:
            col["label"].x = -20

    def _show_matrix(self):
        for col in self.matrix_labels:
            col["label"].x = col["x"]

    def _render_sine(self):
        prev_offset = self.sine_offset
        self.sine_offset += 0.1 * self.speed

        for x in range(WIDTH):
            # erase old pixels
            y1_old = int(HEIGHT / 2 + 10 * math.sin(x * 0.08 + prev_offset))
            y2_old = int(HEIGHT / 2 + 5  * math.sin(x * 0.15 + prev_offset * 1.5))
            y3_old = int(HEIGHT / 2 + 3  * math.sin(x * 0.25 + prev_offset * 2.0))
            self._set_pixel(x, y1_old, 0)
            self._set_pixel(x, y2_old, 0)
            self._set_pixel(x, y3_old, 0)
            # draw new pixels
            y1 = int(HEIGHT / 2 + 10 * math.sin(x * 0.08 + self.sine_offset))
            y2 = int(HEIGHT / 2 + 5  * math.sin(x * 0.15 + self.sine_offset * 1.5))
            y3 = int(HEIGHT / 2 + 3  * math.sin(x * 0.25 + self.sine_offset * 2.0))
            self._set_pixel(x, y1, 1)
            self._set_pixel(x, y2, 1)
            self._set_pixel(x, y3, 1)

    # =========================
    # KEY CONTROLS
    # =========================

    def next_scene(self):
        if self.scene == 2:
            self._hide_matrix()
        self._hide_hud()
        self.scene = (self.scene + 1) % NUM_SCENES
        self._clear_background()
        if self.scene == 0:
            self._show_balls()
            self._show_labels(True)
        elif self.scene == 2:
            self._show_matrix()
            self._hide_balls()
            self._show_labels(False)
        else:
            self._hide_balls()
            self._show_labels(False)

    def toggle_brightness(self):
        self.bright_on  = not self.bright_on
        oled.brightness = 1.0 if self.bright_on else 0.0

    def toggle_invert(self):
        self.inverted = not self.inverted
        self.bg_pal[0], self.bg_pal[1] = self.bg_pal[1], self.bg_pal[0]

        # always update ball shaders regardless of current scene
        for tile in self.ball_tiles:
            tile.pixel_shader[0], tile.pixel_shader[1] = \
                tile.pixel_shader[1], tile.pixel_shader[0]

        if self.scene == 0:
            c = 0x000000 if self.inverted else 0xFFFFFF
            self.speed_label.color  = c
            self.bounce_label.color = c
        else:
            self._show_labels(False)

        # update matrix label colors regardless of scene
        matrix_color = 0x000000 if self.inverted else 0xFFFFFF
        for col in self.matrix_labels:
            col["label"].color = matrix_color

        self._hide_hud()

    def speed_up(self):
        self.speed = min(5.0, round(self.speed + 0.25, 2))
        if self.scene == 0:
            self.speed_label.text = "x{:.2f}".format(self.speed)
        else:
            self._show_hud("x{:.2f}".format(self.speed))

    def speed_down(self):
        self.speed = max(0.1, round(self.speed - 0.25, 2))
        if self.scene == 0:
            self.speed_label.text = "x{:.2f}".format(self.speed)
        else:
            self._show_hud("x{:.2f}".format(self.speed))

    def toggle_pause(self):
        self.paused = not self.paused
        if self.scene == 0:
            self.speed_label.text = "PAUSE" if self.paused else "x{:.2f}".format(self.speed)
        else:
            self._show_hud("PAUSE" if self.paused else "RESUME")

    # ball controls (only meaningful in scene 0)
    def add_ball(self):
        if self.scene != 0:
            return
        r = self.balls[0]["radius"] if self.balls else DEFAULT_RADIUS
        self._add_ball(radius=r)

    def remove_ball(self):
        if self.scene != 0 or len(self.balls) <= 1:
            return
        self.splash.remove(self.ball_tiles[-1])
        self.ball_tiles.pop()
        self.balls.pop()

    def grow_balls(self):
        if self.scene != 0:
            return
        for ball in self.balls:
            ball["radius"] = min(MAX_RADIUS, ball["radius"] + 1)
        self._rebuild_ball_bitmaps()

    def shrink_balls(self):
        if self.scene != 0:
            return
        for ball in self.balls:
            ball["radius"] = max(MIN_RADIUS, ball["radius"] - 1)
        self._rebuild_ball_bitmaps()

    def toggle_collisions(self):
        if self.scene != 0:
            return
        self.collisions = not self.collisions

    # =========================
    # KMK HOOKS
    # =========================

    def during_bootup(self, keyboard):
        pass

    def before_matrix_scan(self, sandbox):
        self.frame += 1

        # hide HUD after timeout
        if self.hud_visible and supervisor.ticks_ms() >= self.hud_visible_until:
            self._hide_hud()

        if self.scene == 0:
            self._tick_balls()
        elif not self.paused:
            if self.scene == 1:
                self._render_starfield()
            elif self.scene == 2:
                self._render_matrix()
            elif self.scene == 3:
                self._render_sine()

    def _tick_balls(self):
        if self.paused:
            return

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
                        nx = dx / dist
                        ny = dy / dist
                        dvx = b1["dx"] - b2["dx"]
                        dvy = b1["dy"] - b2["dy"]
                        dot = dvx * nx + dvy * ny
                        if dot < 0:
                            b1["dx"] -= dot * nx
                            b1["dy"] -= dot * ny
                            b2["dx"] += dot * nx
                            b2["dy"] += dot * ny
                        overlap = min_dist - dist
                        b1["x"] += nx * overlap * 0.5
                        b1["y"] += ny * overlap * 0.5
                        b2["x"] -= nx * overlap * 0.5
                        b2["y"] -= ny * overlap * 0.5

        self.bounce_label.text = str(self.bounces)

    def after_matrix_scan(self, sandbox):    pass
    def before_hid_send(self, sandbox):      pass
    def after_hid_send(self, sandbox):       pass
    def on_runtime_enable(self, sandbox):    pass
    def on_runtime_disable(self, sandbox):   pass
    def on_powersave_enable(self, sandbox):  pass
    def on_powersave_disable(self, sandbox): pass

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
anim = AnimationExtension()
keyboard.extensions.append(anim)

# =========================
# CUSTOM KEYS
# =========================
make_key(names=("ADD_BALL",),          on_press=lambda *a: anim.add_ball())
make_key(names=("REMOVE_BALL",),       on_press=lambda *a: anim.remove_ball())
make_key(names=("GROW",),              on_press=lambda *a: anim.grow_balls())
make_key(names=("SHRINK",),            on_press=lambda *a: anim.shrink_balls())
make_key(names=("TOGGLE_COLLISIONS",), on_press=lambda *a: anim.toggle_collisions())
make_key(names=("INVERT",),            on_press=lambda *a: anim.toggle_invert())
make_key(names=("CHANGE_SCENE",),      on_press=lambda *a: anim.next_scene())
make_key(names=("BRIGHTNESS_TOGGLE",), on_press=lambda *a: anim.toggle_brightness())
make_key(names=("SPD_UP",),            on_press=lambda *a: anim.speed_up())
make_key(names=("SPD_DN",),            on_press=lambda *a: anim.speed_down())
make_key(names=("PAUSE",),             on_press=lambda *a: anim.toggle_pause())

# =========================
# ENCODER — speed + pause
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
# row 1:  add ball | grow   | toggle collisions | change scene
# row 2:  rem ball | shrink | invert            | brightness toggle
# =========================
keyboard.keymap = [
    [
        KC.ADD_BALL,    KC.GROW,   KC.TOGGLE_COLLISIONS, KC.CHANGE_SCENE,
        KC.REMOVE_BALL, KC.SHRINK, KC.INVERT,            KC.BRIGHTNESS_TOGGLE,
    ]
]

if __name__ == "__main__":
    keyboard.go()
