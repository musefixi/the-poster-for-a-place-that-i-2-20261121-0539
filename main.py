#!/usr/bin/env python3
"""VELDARA - a travel poster for a place that isn't there.

A pure Python 3 standard-library program: no network, no PIL, no image
assets. It keeps a 1024x1024 RGB framebuffer, paints a sunset sky, a sea
of clouds, drifting islands, a lighthouse and an airship with its own
drawing primitives and a hand-made vector stroke font, then encodes the
result as a PNG with zlib and writes it to
$MAKEFUN_OUTPUT_DIR/entry.png (default /output/entry.png).

The poster sells Veldara, the Drifting Isles: islands that float above a
sea of cloud, reached only by airship. There are no roads, no maps, and
no such place - which is the whole point.

The output is deterministic: the same bytes on every run.
"""

import math
import os
import struct
import zlib

W = 1024
H = 1024
MAX_BYTES = 1048576


# ---------------------------------------------------------------- PNG -----


def png_bytes(width, height, rgb):
    """Encode an RGB bytearray as a PNG (filter 0 rows, zlib level 9)."""
    raw = bytearray()
    stride = width * 3
    for y in range(height):
        raw.append(0)
        raw += rgb[y * stride:(y + 1) * stride]
    comp = zlib.compress(bytes(raw), 9)

    def chunk(tag, data):
        out = struct.pack(">I", len(data)) + tag + data
        out += struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return out

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", comp) + chunk(b"IEND", b""))


# ------------------------------------------------------------- Canvas -----


class Canvas:
    def __init__(self, width, height, bg):
        self.w = width
        self.h = height
        self.px = bytearray(width * height * 3)
        self.fill_all(bg)

    def fill_all(self, color):
        row = bytes(color) * self.w
        for y in range(self.h):
            self.px[y * self.w * 3:(y + 1) * self.w * 3] = row

    def set_px(self, x, y, color):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i:i + 3] = bytes(color)

    def fill_rect(self, x0, y0, x1, y1, color):
        x0 = max(0, int(x0))
        y0 = max(0, int(y0))
        x1 = min(self.w, int(x1))
        y1 = min(self.h, int(y1))
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(color) * (x1 - x0)
        for y in range(y0, y1):
            i = (y * self.w + x0) * 3
            self.px[i:i + len(row)] = row

    def stamp(self, cx, cy, r, color):
        """Filled disc of radius r centred at (cx, cy)."""
        cx = int(round(cx))
        cy = int(round(cy))
        r = int(round(r))
        if r <= 0:
            self.set_px(cx, cy, color)
            return
        for dy in range(-r, r + 1):
            span = int((r * r - dy * dy) ** 0.5)
            self.fill_rect(cx - span, cy + dy, cx + span + 1, cy + dy + 1,
                           color)

    def line(self, x0, y0, x1, y1, color, r=1):
        """Thick line: discs stamped along the segment."""
        dx = x1 - x0
        dy = y1 - y0
        steps = max(1, int(max(abs(dx), abs(dy)) * 2))
        for i in range(steps + 1):
            t = i / steps
            self.stamp(x0 + dx * t, y0 + dy * t, r, color)

    def polyline(self, points, color, r=1, close=False):
        pts = list(points)
        if close and pts:
            pts.append(pts[0])
        for a, b in zip(pts, pts[1:]):
            self.line(a[0], a[1], b[0], b[1], color, r)

    def fill_polygon(self, points, color):
        """Scanline even-odd fill of a polygon."""
        ys = [p[1] for p in points]
        y_lo = max(0, int(min(ys)))
        y_hi = min(self.h - 1, int(max(ys)))
        n = len(points)
        for y in range(y_lo, y_hi + 1):
            xs = []
            for i in range(n):
                x0, y0 = points[i]
                x1, y1 = points[(i + 1) % n]
                if (y0 <= y < y1) or (y1 <= y < y0):
                    xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                self.fill_rect(int(xs[i]), y, int(xs[i + 1]) + 1, y + 1,
                               color)

    def fill_ellipse(self, cx, cy, rx, ry, color):
        """Filled axis-aligned ellipse."""
        for dy in range(-int(ry), int(ry) + 1):
            t = dy / ry if ry else 0
            span = int(rx * (1 - t * t) ** 0.5)
            self.fill_rect(cx - span, cy + dy, cx + span + 1, cy + dy + 1,
                           color)

    def circle(self, cx, cy, rad, color, r=1):
        pts = []
        steps = max(12, int(rad * 2))
        for i in range(steps):
            a = 2 * math.pi * i / steps
            pts.append((cx + rad * math.cos(a), cy + rad * math.sin(a)))
        self.polyline(pts, color, r, close=True)


# --------------------------------------------------------------- Font -----
# A hand-drawn vector stroke font, written for this poster. Each glyph is
# a list of strokes; each stroke is a string of "x,y" points on a 0..10
# wide, 0..10 tall cell where y=0 is the cap top and y=10 is the
# baseline. A single-point stroke is a dot. Lowercase letters render as
# small caps through the text engine.

FONT = {
    'A': ["0,10 5,0 10,10", "2.5,6.5 7.5,6.5"],
    'B': ["0,0 0,10", "0,0 6,0 8,2 8,4 6,5 0,5",
          "0,5 6.5,5 9,7 9,8.5 6.5,10 0,10"],
    'C': ["9,2.5 7,0.5 4,0 2,1 0.5,3 0.5,7 2,9.5 4.5,10 7,9.5 9,7.5"],
    'D': ["0,0 0,10", "0,0 5,0 8.5,2.5 8.5,7.5 5,10 0,10"],
    'E': ["9,0 0,0 0,10 9,10", "0,5 6.5,5"],
    'F': ["9,0 0,0 0,10", "0,5 6,5"],
    'G': ["9,3 7,0.5 4,0 2,1 0.5,3 0.5,7 2,9.5 4.5,10 7,10 9,8 9,5.5 6,5.5"],
    'H': ["0,0 0,10", "10,0 10,10", "0,5 10,5"],
    'I': ["5,0 5,10", "2,0 8,0", "2,10 8,10"],
    'J': ["9,0 9,7.5 7.5,9.5 4.5,10 1.5,9 0.5,7"],
    'K': ["0,0 0,10", "9,0 1,5.5", "2.5,4.5 9,10"],
    'L': ["0,0 0,10 9,10"],
    'M': ["0,10 0,0 5,6.5 10,0 10,10"],
    'N': ["0,10 0,0 10,10 10,0"],
    'O': ["5,0 7.5,0.5 9.5,2.5 9.5,7.5 7.5,10 5,10 2.5,10 0.5,7.5 "
          "0.5,2.5 2.5,0.5 5,0"],
    'P': ["0,10 0,0", "0,0 6,0 8.5,2 8.5,4.5 6,6.5 0,6.5"],
    'Q': ["5,0 7.5,0.5 9.5,2.5 9.5,7.5 7.5,10 5,10 2.5,10 0.5,7.5 "
          "0.5,2.5 2.5,0.5 5,0", "6,7.5 10,11.5"],
    'R': ["0,10 0,0", "0,0 6,0 8.5,2 8.5,4.5 6,6.5 0,6.5", "5,6.5 9.5,10"],
    'S': ["9,2.5 7,0.5 4,0 1.5,1.5 1,3.5 2.5,5 7,6 9,7.5 8.5,9.5 "
          "5.5,10.5 2.5,10 0.5,8.5"],
    'T': ["0,0 10,0", "5,0 5,10"],
    'U': ["0,0 0,7.5 1.5,9.5 4,10 6.5,10 9,9.5 10,7.5 10,0"],
    'V': ["0,0 5,10 10,0"],
    'W': ["0,0 2.2,10 5,4 7.8,10 10,0"],
    'X': ["0,0 10,10", "10,0 0,10"],
    'Y': ["0,0 5,5.5", "10,0 5,5.5", "5,5.5 5,10"],
    'Z': ["0,0 10,0 0,10 10,10"],
    '0': ["5,0 7.5,0.5 9,2.5 9,7.5 7.5,10 5,10 2.5,10 1,7.5 1,2.5 "
          "2.5,0.5 5,0"],
    '1': ["3,3 6,0 6,10", "2.5,10 9.5,10"],
    '2': ["1,3 2.5,0.8 5.5,0 8,1.5 8.5,3.5 7,5.5 0.5,10 9.5,10"],
    '3': ["1,2 3.5,0 6.5,0 8.5,2 6.5,4.5 3.5,4.8",
          "6.5,4.5 8.8,6.5 8.5,8.8 6,10 3,10 0.8,8.5"],
    '4': ["6.5,10 6.5,0 0.5,7.5 10,7.5"],
    '5': ["9,0 2,0 1,5 3.5,4.2 6.5,4.2 8.8,6.2 8.5,8.8 6,10 2.5,10 0.5,8.8"],
    '6': ["8.8,2.5 6,0.5 3,1.2 1,4 0.8,7 2,9.5 4.5,10.5 7.5,10 9,8 "
          "8.8,5.8 7,4.5 4.2,4.5 1,5.8"],
    '7': ["0.5,0 9.5,0 4,10"],
    '8': ["5,5 2.5,4 1.8,2 3,0.5 6.5,0.5 8,2 7.2,4 5,5",
          "5,5 2,6.5 1.5,8.8 3.2,10.5 6.8,10.5 8.5,8.8 8,6.5 5,5"],
    '9': ["1.2,7.5 3.5,9.8 6.5,9.5 8.8,7 9.3,4 8.2,1.5 5.8,0 3,0.5 "
          "1.2,2.5 1.5,4.8 3.2,6 5.8,6 9,4.8"],
    '.': ["5,9.8"],
    ',': ["5,9.8", "5.4,10 4.4,12"],
    ':': ["5,2.5", "5,9.8"],
    '-': ["1.5,5 8.5,5"],
    '\u00b7': ["5,5"],
    '!': ["5,0 5,7", "5,9.8"],
    '?': ["1.5,2.5 3,0.5 6,0.5 8.3,2 8,4.2 5.2,5.8 5,7.5", "5,9.8"],
    '&': ["8.5,9.5 4,5 2,3 2.5,1 5,0.5 6.5,2.2 5.5,4.2 1,7 1.8,9.5 "
          "4.5,10.5 7,9.5 8.5,7"],
    '/': ["1.5,10 8.5,0"],
    '(': ["7.5,0 5,2.5 4,5 5,7.5 7.5,10"],
    ')': ["2.5,0 5,2.5 6,5 5,7.5 2.5,10"],
    "'": ["5,0 4.6,2.5"],
    ' ': [],
}

# Per-glyph advance widths, in font units (default 11.3).
ADV = {'I': 6.5, '1': 8.0, ' ': 6.0, '.': 5.0, ',': 5.0, ':': 5.0,
       "'": 4.0, '\u00b7': 5.0, '!': 5.0, '(': 7.0, ')': 7.0,
       '/': 7.0, 'J': 8.5, 'M': 12.5, 'W': 12.5, '?': 9.5}

_parsed = {}


def glyph(ch):
    """Return the parsed stroke list for a character (cached)."""
    if ch not in _parsed:
        strokes = []
        for raw in FONT.get(ch, []):
            pts = []
            for pair in raw.split():
                xs, ys = pair.split(',')
                pts.append((float(xs), float(ys)))
            strokes.append(pts)
        _parsed[ch] = strokes
    return _parsed[ch]


# -------------------------------------------------------- Text engine -----

CAP_UNITS = 10.0  # glyph cap height spans y=0..10


def _adv(ch, unit):
    return ADV.get(ch, 11.3) * unit


def text_width(text, size, sx=1.0):
    """Width in pixels of a string at the given cap-height size."""
    unit = size / CAP_UNITS
    total = 0.0
    for ch in text:
        total += _adv(ch.upper(), unit)
    return total * sx


def draw_text(cv, x, top, text, size, color, bold=False, sx=1.0,
              align='left'):
    """Draw one line of text. (x, top) is the cap-height top-left.

    Lowercase letters render as small caps. Returns the drawn width.
    """
    unit = size / CAP_UNITS
    pen = max(0.6, size * (0.075 if bold else 0.052))
    width = text_width(text, size, sx)
    if align == 'center':
        x = x - width / 2
    elif align == 'right':
        x = x - width
    cx = x
    for ch in text:
        up = ch.upper()
        strokes = glyph(up)
        if ch.islower():
            gx_s, gy_s = 0.82, 0.74
        else:
            gx_s, gy_s = 1.0, 1.0
        adv = _adv(up, unit) * sx
        if strokes:
            for pts in strokes:
                mapped = []
                for gx, gy in pts:
                    px = cx + gx * unit * gx_s * sx
                    py = top + gy * unit * gy_s
                    if gy_s < 1:  # small caps sit on the same baseline
                        py += size * (1 - gy_s)
                    mapped.append((px, py))
                if len(mapped) == 1:
                    cv.stamp(mapped[0][0], mapped[0][1], pen * 1.05, color)
                else:
                    cv.polyline(mapped, color, pen)
        cx += adv
    return width


# ------------------------------------------------------------ Palette -----

INK = (28, 34, 66)        # deep indigo, for bottom copy
CREAM = (255, 243, 214)   # poster cream
PAPER = (247, 239, 224)   # cloud-sea paper
CLOUD_A = (255, 250, 238)
CLOUD_B = (238, 222, 190)
CLOUD_C = (222, 200, 162)
SUN = (255, 226, 158)
SUN_HALO = (255, 196, 118)
CORAL = (232, 106, 74)
CORAL_DARK = (198, 74, 52)
ROCK = (58, 74, 94)
ROCK_DARK = (40, 52, 70)
ROCK_WARM = (107, 74, 58)
GRASS = (78, 122, 74)
GRASS_LT = (111, 160, 90)
SKY_BIRD = (30, 44, 80)
BEAM = (255, 238, 180)
WATER = (168, 208, 228)
WATER_LT = (214, 236, 244)
WHITE = (250, 248, 242)
RED = (196, 52, 44)


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


# --------------------------------------------------------- The poster -----


def sky(cv):
    """Sunset gradient: indigo at the top, warm peach at the horizon."""
    top = (24, 32, 74)
    mid = (58, 110, 140)
    low = (240, 170, 110)
    for y in range(0, 712):
        if y < 380:
            t = y / 380.0
            col = lerp(top, mid, t)
        else:
            t = (y - 380) / 332.0
            col = lerp(mid, low, t)
        cv.fill_rect(0, y, W, y + 1, col)


def sparkle(cv, cx, cy, r, color):
    """A four-point star sparkle."""
    cv.fill_polygon([(cx, cy - r), (cx + r * 0.28, cy - r * 0.28),
                     (cx + r, cy), (cx + r * 0.28, cy + r * 0.28),
                     (cx, cy + r), (cx - r * 0.28, cy + r * 0.28),
                     (cx - r, cy), (cx - r * 0.28, cy - r * 0.28)], color)


def sun(cv):
    cv.stamp(870, 392, 90, SUN_HALO)
    cv.stamp(870, 392, 72, SUN)
    cv.stamp(870, 392, 56, (255, 240, 200))


def bird(cv, x, y, s, color):
    cv.polyline([(x, y), (x + s, y + s * 0.55), (x + 2 * s, y)], color, 2)


def cloud_puff(cv, cx, cy, s, colors):
    """A soft distant cloud: a row of overlapping discs, flat bottom."""
    n = 5
    for i in range(n):
        t = i / (n - 1)
        x = cx - s + 2 * s * t
        r = s * (0.42 + 0.30 * (1 - abs(t - 0.5) * 2))
        cv.stamp(x, cy, r, colors[i % len(colors)])
    cv.fill_rect(cx - s, cy, cx + s, cy + s * 0.28, colors[1])


def cloud_sea(cv):
    """The sea of clouds the islands float above."""
    cv.fill_rect(0, 700, W, H, PAPER)
    # far soft band
    cv.fill_rect(0, 700, W, 726, CLOUD_B)
    puffs = [
        (120, 742, 74), (330, 768, 92), (560, 742, 80), (790, 770, 96),
        (950, 748, 66), (40, 830, 88), (250, 858, 104), (500, 836, 92),
        (740, 862, 108), (930, 838, 84), (150, 946, 96), (420, 962, 110),
        (690, 948, 100), (900, 966, 92),
    ]
    shades = [CLOUD_A, CLOUD_B, CLOUD_A, CLOUD_C]
    for i, (x, y, r) in enumerate(puffs):
        cv.stamp(x, y, r, shades[i % 4])
        cv.stamp(x - r * 0.55, y + r * 0.18, r * 0.72, shades[(i + 1) % 4])
        cv.stamp(x + r * 0.55, y + r * 0.18, r * 0.72, shades[(i + 2) % 4])
    # soft shading under the puffs
    for (x, y, r) in puffs:
        cv.fill_ellipse(x, y + r * 0.55, r * 0.95, r * 0.22, CLOUD_C)


def distant_isle(cv, cx, cy, s, rock, grass):
    """A hazy little island on the horizon."""
    cv.fill_polygon([(cx - s, cy), (cx - s * 0.72, cy + s * 0.55),
                     (cx - s * 0.3, cy + s * 0.9), (cx, cy + s * 1.05),
                     (cx + s * 0.3, cy + s * 0.9), (cx + s * 0.72, cy + s * 0.55),
                     (cx + s, cy)], rock)
    cv.fill_ellipse(cx, cy, s, s * 0.22, grass)


def island(cv, cx, top, w, rock, grass, grass_lt):
    """A floating island: jagged rock, grassy top, warm under-shadow."""
    hw = w / 2.0
    cv.fill_polygon([
        (cx - hw, top), (cx - hw * 0.82, top + w * 0.16),
        (cx - hw * 0.55, top + w * 0.30), (cx - hw * 0.28, top + w * 0.46),
        (cx, top + w * 0.62), (cx + hw * 0.28, top + w * 0.46),
        (cx + hw * 0.55, top + w * 0.30), (cx + hw * 0.82, top + w * 0.16),
        (cx + hw, top)], rock)
    # warm-lit underside on the sun side
    cv.fill_polygon([
        (cx + hw * 0.1, top + w * 0.18), (cx + hw * 0.55, top + w * 0.30),
        (cx + hw * 0.28, top + w * 0.46), (cx, top + w * 0.62),
        (cx + hw * 0.05, top + w * 0.34)], ROCK_WARM)
    # grass cap, gently domed
    cv.fill_ellipse(cx, top, hw, w * 0.10, grass)
    cv.fill_ellipse(cx, top - w * 0.02, hw * 0.8, w * 0.07, grass_lt)


def lighthouse(cv, x, base_y):
    """White lighthouse with a red cap and two beams of light."""
    # beams first, so the tower sits over them
    cv.fill_polygon([(x, base_y - 92), (x, base_y - 76),
                     (x - 190, base_y - 120), (x - 190, base_y - 100)], BEAM)
    cv.fill_polygon([(x, base_y - 92), (x, base_y - 76),
                     (x + 170, base_y - 116), (x + 170, base_y - 96)], BEAM)
    # tower
    cv.fill_polygon([(x - 15, base_y), (x - 11, base_y - 78),
                     (x + 11, base_y - 78), (x + 15, base_y)], WHITE)
    cv.fill_rect(x - 13, base_y - 62, x + 13, base_y - 54, RED)
    cv.fill_rect(x - 14, base_y - 34, x + 14, base_y - 26, RED)
    # gallery + lamp room + cap
    cv.fill_rect(x - 16, base_y - 82, x + 16, base_y - 76, INK)
    cv.fill_rect(x - 10, base_y - 98, x + 10, base_y - 82, (255, 214, 120))
    cv.fill_polygon([(x - 13, base_y - 98), (x, base_y - 112),
                     (x + 13, base_y - 98)], RED)
    cv.stamp(x, base_y - 90, 4, (255, 244, 200))


def waterfall(cv, x, y0, y1):
    """A thin fall of water spilling off an island edge into the clouds."""
    for dx, col in ((-6, WATER), (0, WATER_LT), (6, WATER)):
        pts = []
        for i in range(13):
            t = i / 12.0
            pts.append((x + dx + 5 * math.sin(t * 5.2), y0 + (y1 - y0) * t))
        cv.polyline(pts, col, 2)
    cv.stamp(x, y1, 10, WATER_LT)
    cv.stamp(x - 12, y1 + 4, 7, WATER_LT)
    cv.stamp(x + 12, y1 + 4, 7, WATER_LT)


def tree(cv, x, y, s):
    cv.fill_rect(x - 2, y, x + 2, y + s * 0.9, (90, 60, 40))
    cv.stamp(x, y - s * 0.25, s * 0.55, GRASS)
    cv.stamp(x - s * 0.35, y, s * 0.38, GRASS_LT)
    cv.stamp(x + s * 0.35, y, s * 0.38, GRASS)


def cottage(cv, x, y, s):
    """A tiny cream cottage with a red roof."""
    cv.fill_rect(x - s * 0.5, y, x + s * 0.5, y + s * 0.55, CREAM)
    cv.fill_polygon([(x - s * 0.62, y), (x, y - s * 0.5),
                     (x + s * 0.62, y)], RED)
    cv.fill_rect(x - s * 0.12, y + s * 0.22, x + s * 0.12, y + s * 0.55, INK)


def airship(cv, cx, cy):
    """A coral airship drifting past the sun."""
    # tail fins
    cv.fill_polygon([(cx + 88, cy - 26), (cx + 118, cy - 6),
                     (cx + 88, cy + 8)], CORAL_DARK)
    cv.fill_polygon([(cx + 88, cy + 26), (cx + 116, cy + 8),
                     (cx + 88, cy - 4)], CORAL_DARK)
    # envelope
    cv.fill_ellipse(cx, cy, 96, 50, CORAL)
    cv.fill_ellipse(cx, cy, 96, 16, CREAM)
    cv.fill_ellipse(cx - 18, cy - 12, 60, 22, (240, 130, 100))
    # ropes + gondola
    cv.line(cx - 42, cy + 40, cx - 30, cy + 66, INK, 2)
    cv.line(cx + 42, cy + 40, cx + 30, cy + 66, INK, 2)
    cv.line(cx, cy + 48, cx, cy + 66, INK, 2)
    cv.fill_rect(cx - 34, cy + 66, cx + 34, cy + 88, (96, 64, 44))
    cv.fill_rect(cx - 34, cy + 66, cx + 34, cy + 72, (70, 46, 30))
    for wx in (-20, 0, 20):
        cv.fill_rect(cx + wx - 5, cy + 74, cx + wx + 5, cy + 84,
                     (255, 226, 158))


def frame(cv):
    cv.fill_rect(22, 22, W - 22, 25, CREAM)
    cv.fill_rect(22, H - 25, W - 22, H - 22, CREAM)
    cv.fill_rect(22, 22, 25, H - 22, CREAM)
    cv.fill_rect(W - 25, 22, W - 22, H - 22, CREAM)
    cv.fill_rect(36, 36, W - 36, 37, CREAM)
    cv.fill_rect(36, H - 37, W - 36, H - 36, CREAM)
    cv.fill_rect(36, 36, 37, H - 36, CREAM)
    cv.fill_rect(W - 37, 36, W - 36, H - 36, CREAM)


def build():
    cv = Canvas(W, H, (24, 32, 74))
    sky(cv)

    # sparkles high in the sky
    for (x, y, r) in [(120, 110, 12), (930, 120, 10), (880, 70, 8),
                      (150, 300, 8), (60, 210, 7)]:
        sparkle(cv, x, y, r, (255, 236, 190))

    sun(cv)

    # distant clouds and hazy isles on the horizon
    cloud_puff(cv, 210, 470, 46, [CLOUD_A, CLOUD_B, (250, 226, 196)])
    cloud_puff(cv, 900, 560, 40, [CLOUD_A, CLOUD_B, (250, 226, 196)])
    distant_isle(cv, 130, 640, 46, (96, 116, 142), (110, 140, 100))
    distant_isle(cv, 880, 655, 38, (96, 116, 142), (110, 140, 100))

    # birds
    bird(cv, 180, 340, 9, SKY_BIRD)
    bird(cv, 230, 315, 7, SKY_BIRD)
    bird(cv, 620, 250, 8, SKY_BIRD)
    bird(cv, 560, 300, 6, SKY_BIRD)
    bird(cv, 950, 420, 7, SKY_BIRD)

    # small far island, upper left
    island(cv, 170, 430, 130, ROCK, GRASS, GRASS_LT)
    tree(cv, 170, 424, 26)

    # the airship, sailing right of the sun
    airship(cv, 640, 398)

    # the great island, home of the lighthouse
    island(cv, 400, 560, 330, ROCK, GRASS, GRASS_LT)
    tree(cv, 300, 552, 34)
    tree(cv, 492, 556, 28)
    cv.stamp(340, 548, 3, RED)
    cv.stamp(448, 550, 3, (255, 214, 120))
    cv.stamp(368, 544, 3, (255, 214, 120))
    lighthouse(cv, 400, 566)

    # a second island, lower right, with a cottage
    island(cv, 780, 620, 190, ROCK, GRASS, GRASS_LT)
    cottage(cv, 780, 606, 34)
    tree(cv, 838, 612, 24)

    # water spilling off the great island into the cloud sea
    waterfall(cv, 545, 600, 716)
    waterfall(cv, 850, 648, 716)

    cloud_sea(cv)

    # title block
    draw_text(cv, W // 2, 52, 'THE DRIFTING ISLES', 24, CREAM,
              bold=True, sx=1.7, align='center')
    draw_text(cv, W // 2, 88, 'VELDARA', 104, CREAM, bold=True, sx=1.04,
              align='center')
    cv.fill_rect(W // 2 - 210, 212, W // 2 + 210, 215, CREAM)
    cv.stamp(W // 2, 213, 5, CREAM)
    draw_text(cv, W // 2, 232, 'WHERE THE ISLANDS DRIFT', 27, CREAM,
              bold=True, sx=1.25, align='center')

    # bottom copy, set on the cloud sea
    draw_text(cv, W // 2, 872, 'VISIT THE SKY', 42, INK, bold=True,
              sx=1.1, align='center')
    draw_text(cv, W // 2, 934, 'SAIL THE DRIFTING ISLES \u00b7 BY AIRSHIP '
              'FROM ANYWHERE', 19, INK, bold=True, sx=1.0, align='center')
    draw_text(cv, W // 2, 970, 'NO ROADS \u00b7 NO MAPS \u00b7 NO SUCH PLACE',
              15, (90, 84, 70), bold=True, sx=1.2, align='center')

    frame(cv)
    return cv


def main():
    cv = build()
    data = png_bytes(W, H, cv.px)
    # the gate, checked by the program itself before writing
    if W > 1024 or H > 1024:
        raise SystemExit('gate: image larger than 1024x1024')
    if len(data) > MAX_BYTES:
        raise SystemExit('gate: PNG larger than 1 MiB: %d bytes'
                         % len(data))
    if not data.startswith(b'\x89PNG\r\n\x1a\n'):
        raise SystemExit('gate: not a whole PNG')
    out_dir = os.environ.get('MAKEFUN_OUTPUT_DIR', '/output')
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, 'entry.png'), 'wb') as fh:
        fh.write(data)


if __name__ == '__main__':
    main()
