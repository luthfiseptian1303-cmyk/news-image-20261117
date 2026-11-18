#!/usr/bin/env python3
"""news-image-20261117 — one image summing up Tuesday 17 November 2026.

A deterministic, stdlib-only Python 3.13 program. It draws a newspaper
front page (1024x1024 PNG) entirely procedurally — vector shapes plus a
hand-built 5x7 bitmap font — and writes it to /output/entry.png
(or $MAKEFUN_OUTPUT_DIR/entry.png). No network, no randomness, no clock:
two runs write byte-identical files.

Stories pictured (all happened, or were first reported, on 17 Nov 2026):
  1. Ukraine hits the Crimean (Kerch) Bridge again — second strike in
     under 24 hours — as Russian missiles hit Kyiv's North and South
     bridges overnight. (Reuters / Al Jazeera / Just Security)
  2. Iran fires drones at a US radar system at Sheikh Isa base, Bahrain;
     Bahrain and US Central Command say they were intercepted, no
     casualties or damage. (Reuters, 17 Nov 2026)
  3. President Trump in Manila for ASEAN ahead of the Xi-Trump-Putin
     trilateral meeting set for Thursday in Shenzhen. (Reuters)
  4. Two suspected Russian aircraft violate Japanese airspace near
     Okinoshima; Japan scrambles fighters and lodges a stern protest.
     (CNA / Nikkei, 17 Nov 2026)
  5. A wave of tech outages: Microsoft, an FAA ground stop, JPMorgan
     systems, and the NSA reporting brief degradation. (Reuters, 17 Nov)
  6. The Pentagon fails its financial audit for a ninth straight year.
     (Zark News daily briefing, 17 Nov 2026)

SPDX-License-Identifier: MIT
"""

import math
import os
import struct
import zlib

W, H = 1024, 1024

# ---------------------------------------------------------------- palette
CREAM = (245, 239, 224)   # newsprint
PAPER = (255, 253, 245)   # panel paper
INK = (26, 26, 26)
RED = (179, 38, 30)       # headline red
NAVY = (24, 42, 68)       # lead band / night sky
SKY_TOP = (38, 58, 92)
SKY_MID = (96, 92, 110)
HORIZON = (226, 138, 66)  # dusk orange
SEA = (30, 52, 74)
SEA_LT = (64, 98, 122)
GOLD = (232, 178, 44)
BLUE = (31, 78, 121)
TEAL = (18, 110, 105)
GREY = (110, 110, 104)
SMOKE = (150, 148, 140)
WHITE = (255, 255, 255)

# ---------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.px = bytearray(bg) * (w * h)

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i], self.px[i + 1], self.px[i + 2] = c

    def rect(self, x, y, w, h, c):
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.w, x + w), min(self.h, y + h)
        for yy in range(y0, y1):
            i = (yy * self.w + x0) * 3
            for xx in range(x0, x1):
                self.px[i], self.px[i + 1], self.px[i + 2] = c
                i += 3

    def hline(self, x0, x1, y, c, t=1):
        for yy in range(y, y + t):
            for xx in range(x0, x1 + 1):
                self.set(xx, yy, c)

    def vline(self, x, y0, y1, c, t=1):
        for xx in range(x, x + t):
            for yy in range(y0, y1 + 1):
                self.set(xx, yy, c)

    def line(self, x0, y0, x1, y1, c, t=1):
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        x, y = x0, y0
        while True:
            for a in range(t):
                for b in range(t):
                    self.set(x + a, y + b, c)
            if x == x1 and y == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy

    def circle(self, cx, cy, r, c):
        for yy in range(cy - r, cy + r + 1):
            for xx in range(cx - r, cx + r + 1):
                if (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r:
                    self.set(xx, yy, c)

    def ring(self, cx, cy, r, c, t=2):
        for yy in range(cy - r - 1, cy + r + 2):
            for xx in range(cx - r - 1, cx + r + 2):
                d = ((xx - cx) ** 2 + (yy - cy) ** 2) ** 0.5
                if r - t < d <= r:
                    self.set(xx, yy, c)

    def ellipse(self, cx, cy, rx, ry, c):
        for yy in range(cy - ry, cy + ry + 1):
            for xx in range(cx - rx, cx + rx + 1):
                if ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 <= 1.0:
                    self.set(xx, yy, c)

    def triangle(self, pts, c):
        (x0, y0), (x1, y1), (x2, y2) = pts
        ymin, ymax = min(y0, y1, y2), max(y0, y1, y2)
        for yy in range(ymin, ymax + 1):
            xs = []
            for (ax, ay), (bx, by) in (((x0, y0), (x1, y1)),
                                       ((x1, y1), (x2, y2)),
                                       ((x2, y2), (x0, y0))):
                if ay == by:
                    continue
                if min(ay, by) <= yy < max(ay, by):
                    xs.append(ax + (yy - ay) * (bx - ax) / (by - ay))
            if len(xs) >= 2:
                for xx in range(int(min(xs)), int(max(xs)) + 1):
                    self.set(xx, yy, c)

    def vgrad(self, x, y, w, h, top, bot):
        for yy in range(h):
            f = yy / max(1, h - 1)
            c = tuple(int(top[i] + (bot[i] - top[i]) * f) for i in range(3))
            self.rect(x, y + yy, w, 1, c)


# ---------------------------------------------------------------- 5x7 font
# Each glyph: 7 rows of 5 bits, written as strings, '#' = on.
FONT = {
    'A': ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    'B': ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    'C': ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    'D': ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    'E': ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    'F': ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    'G': ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    'H': ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    'I': ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    'J': ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    'K': ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    'L': ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    'M': ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    'N': ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    'O': ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    'P': ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    'Q': ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    'R': ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    'S': ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    'T': ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    'U': ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    'V': ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    'W': ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    'X': ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    'Y': ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    'Z': ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    '0': ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    '1': ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    '2': ("01110", "10001", "00001", "00110", "01000", "10000", "11111"),
    '3': ("11111", "00010", "00100", "00010", "00001", "10001", "01110"),
    '4': ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    '5': ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    '6': ("00110", "01000", "10000", "11110", "10001", "10001", "01110"),
    '7': ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    '8': ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    '9': ("01110", "10001", "10001", "01111", "00001", "00010", "01100"),
    ' ': ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    '-': ("00000", "00000", "00000", "01110", "00000", "00000", "00000"),
    '.': ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    ',': ("00000", "00000", "00000", "00000", "01100", "00100", "01000"),
    "'": ("00100", "00100", "01000", "00000", "00000", "00000", "00000"),
    ':': ("00000", "01100", "01100", "00000", "01100", "01100", "00000"),
    ';': ("00000", "01100", "01100", "00000", "01100", "00100", "01000"),
    '!': ("00100", "00100", "00100", "00100", "00100", "00000", "00100"),
    '?': ("01110", "10001", "00001", "00110", "00100", "00000", "00100"),
    '/': ("00001", "00010", "00010", "00100", "01000", "01000", "10000"),
    '(': ("00010", "00100", "01000", "01000", "01000", "00100", "00010"),
    ')': ("01000", "00100", "00010", "00010", "00010", "00100", "01000"),
    '&': ("01100", "10010", "10100", "01000", "10101", "10010", "01101"),
    '+': ("00000", "00100", "00100", "11111", "00100", "00100", "00000"),
    '%': ("11001", "11010", "00010", "00100", "01000", "01011", "10011"),
    '=': ("00000", "00000", "11111", "00000", "11111", "00000", "00000"),
    '"': ("01010", "01010", "00000", "00000", "00000", "00000", "00000"),
    '*': ("00000", "10101", "01110", "10101", "00000", "00000", "00000"),
}

ADV = 6  # advance per glyph, in font units (5 + 1 space)


def text_w(s, scale):
    return (len(s) * ADV - 1) * scale


def draw_text(cv, x, y, s, scale, color):
    s = s.upper()
    cx = x
    for ch in s:
        g = FONT.get(ch, FONT[' '])
        for r, row in enumerate(g):
            for c, bit in enumerate(row):
                if bit == '1':
                    cv.rect(cx + c * scale, y + r * scale, scale, scale, color)
        cx += ADV * scale
    return cx


def draw_text_center(cv, cx, y, s, scale, color):
    draw_text(cv, cx - text_w(s, scale) // 2, y, s, scale, color)


def wrap(s, max_chars):
    """Greedy word wrap; returns lines of at most max_chars characters."""
    words = s.split(' ')
    lines, cur = [], ''
    for w in words:
        trial = (cur + ' ' + w).strip()
        if len(trial) <= max_chars:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _starburst(cv, cx, cy, r_out, r_in, points, color):
    """Jagged explosion star: alternating long/short spikes, drawn as a
    triangle fan so it reads as a blast, not a sun."""
    import math as _m
    pts = []
    for i in range(points * 2):
        a = _m.radians(i * 180.0 / points - 90)
        r = r_out if i % 2 == 0 else r_in
        pts.append((cx + int(r * _m.cos(a)), cy + int(r * _m.sin(a))))
    for i in range(1, len(pts) - 1):
        cv.triangle([(cx, cy), pts[i], pts[i + 1]], color)
    cv.triangle([(cx, cy), pts[-1], pts[0]], color)


# ---------------------------------------------------------------- PNG writer
def write_png(path, cv):
    def chunk(kind, data):
        c = struct.pack('>I', len(data)) + kind + data
        return c + struct.pack('>I', zlib.crc32(kind + data) & 0xFFFFFFFF)

    ihdr = struct.pack('>IIBBBBB', cv.w, cv.h, 8, 2, 0, 0, 0)
    raw = bytearray()
    for y in range(cv.h):
        raw.append(0)  # filter: none
        raw += cv.px[y * cv.w * 3:(y + 1) * cv.w * 3]
    png = (b'\x89PNG\r\n\x1a\n'
           + chunk(b'IHDR', ihdr)
           + chunk(b'IDAT', zlib.compress(bytes(raw), 9))
           + chunk(b'IEND', b''))
    with open(path, 'wb') as f:
        f.write(png)
    return len(png)


# ---------------------------------------------------------------- drawing
def draw_masthead(cv):
    # top kicker
    draw_text_center(cv, W // 2, 36, "THE WORLD IN ONE DAY", 2, RED)
    # the date, large
    draw_text_center(cv, W // 2, 62, "17 NOVEMBER 2026", 6, INK)
    # flanking small labels on the date line
    draw_text(cv, 30, 84, "TUESDAY", 2, INK)
    draw_text(cv, W - 30 - text_w("WORLD NEWS", 2), 84, "WORLD NEWS", 2, INK)
    # double rule
    cv.hline(28, 995, 128, INK, 3)
    cv.hline(28, 995, 134, INK, 1)


def draw_lead(cv):
    x0, y0, x1, y1 = 28, 148, 996, 452
    # dusk sky
    cv.vgrad(x0, y0, x1 - x0, 150, SKY_TOP, SKY_MID)
    cv.vgrad(x0, y0 + 150, x1 - x0, 60, SKY_MID, HORIZON)
    # low sun
    cv.circle(830, 300, 34, GOLD)
    cv.circle(830, 300, 26, (244, 200, 90))
    # sea
    cv.rect(x0, y0 + 210, x1 - x0, 92, SEA)
    for i in range(9):
        yy = y0 + 222 + i * 9
        cv.hline(x0 + 40 + i * 30, x1 - 60 - i * 18, yy, SEA_LT, 2)
    # sun reflection
    for i in range(6):
        cv.hline(800 - i * 6, 862 + i * 6, y0 + 224 + i * 11, GOLD, 3)
    # bridge deck
    deck_y = y0 + 196
    cv.rect(x0, deck_y, x1 - x0, 10, INK)
    cv.rect(x0, deck_y + 10, x1 - x0, 3, (60, 60, 60))
    # pylons (cable-stayed)
    for px in (220, 700):
        cv.rect(px, y0 + 62, 12, deck_y - y0 - 62, INK)
        cv.rect(px - 4, y0 + 54, 20, 10, INK)
        for k in range(1, 6):
            cv.line(px + 6, y0 + 66, x0 + 20 + k * 62, deck_y, (200, 200, 190), 1)
            cv.line(px + 6, y0 + 66, x1 - 20 - k * 62, deck_y, (200, 200, 190), 1)
    # broken span: gap in the deck near the blast
    cv.rect(470, deck_y, 90, 10, HORIZON)
    cv.line(470, deck_y, 452, deck_y + 46, INK, 3)
    cv.line(560, deck_y, 578, deck_y + 46, INK, 3)
    # explosion: jagged starburst at the break (kept inside the panel)
    bx, by = 515, deck_y - 30
    _starburst(cv, bx, by, 66, 30, 12, (226, 110, 30))
    _starburst(cv, bx, by, 46, 20, 12, (240, 160, 50))
    _starburst(cv, bx, by, 28, 12, 10, (250, 205, 80))
    cv.circle(bx, by, 12, (255, 230, 140))
    # smoke puffs, rising but staying below the panel top
    for (sx, sy, r) in ((452, 196, 24), (492, 176, 30), (548, 188, 26),
                        (586, 210, 20), (428, 220, 16)):
        cv.circle(sx, sy, r, SMOKE)
        cv.circle(sx - 6, sy - 6, r - 8, (170, 168, 160))
    # debris dots
    for (dx, dy) in ((400, 210), (610, 200), (430, 240), (590, 235), (360, 250)):
        cv.circle(dx, dy, 3, INK)
    # headline band
    cv.rect(x0, y1 - 82, x1 - x0, 82, NAVY)
    cv.hline(x0, x1 - 1, y1 - 82, RED, 4)
    draw_text(cv, x0 + 18, y1 - 70, "EUROPE - WAR IN UKRAINE", 2, GOLD)
    draw_text(cv, x0 + 18, y1 - 46, "UKRAINE HITS CRIMEA BRIDGE AGAIN", 3, WHITE)
    draw_text(cv, x0 + 18, y1 - 20, "SECOND STRIKE IN A DAY - KYIV BRIDGES HIT TOO", 2,
              (200, 210, 225))


def panel_frame(cv, x, y, w, h, accent):
    cv.rect(x, y, w, h, PAPER)
    cv.rect(x, y, w, 6, accent)
    for xx in (x, x + w - 1):
        cv.vline(xx, y, y + h - 1, INK, 1)
    cv.hline(x, x + w - 1, y, INK, 1)
    cv.hline(x, x + w - 1, y + h - 1, INK, 1)


def panel_text(cv, x, y, w, kicker, headline, sub, kcolor):
    draw_text(cv, x, y, kicker, 2, kcolor)
    lines = wrap(headline, w // 12)
    yy = y + 24
    for ln in lines:
        draw_text(cv, x, yy, ln, 2, INK)
        yy += 22
    draw_text(cv, x, yy + 4, sub, 2, GREY)


def draw_bahrain(cv, x, y, w, h):
    panel_frame(cv, x, y, w, h, RED)
    ix, iy = x + 22, y + 58
    # radar dish on a mast: tilted open dish, not a ring
    cv.line(ix + 40, iy + 90, ix + 40, iy + 30, INK, 4)
    cv.line(ix + 40, iy + 30, ix + 66, iy + 6, INK, 3)
    cv.ellipse(ix + 52, iy + 16, 26, 12, PAPER)
    cv.ring(ix + 52, iy + 16, 26, INK, 2)
    cv.line(ix + 30, iy + 10, ix + 74, iy + 22, INK, 2)
    # sweep beam
    cv.line(ix + 52, iy + 16, ix + 104, iy - 8, GOLD, 3)
    cv.line(ix + 52, iy + 16, ix + 108, iy + 6, GOLD, 2)
    # incoming drones (small deltas)
    for (dx, dy) in ((ix + 96, iy + 34), (ix + 112, iy + 52), (ix + 88, iy + 62)):
        cv.triangle([(dx, dy), (dx + 18, dy + 5), (dx, dy + 10)], INK)
    # interception burst
    cv.circle(ix + 116, iy + 30, 8, GOLD)
    cv.circle(ix + 116, iy + 30, 4, WHITE)
    # ground line + base
    cv.hline(ix - 6, ix + 138, iy + 92, INK, 3)
    panel_text(cv, x + 168, y + 22, w - 190, "MIDDLE EAST",
               "IRAN DRONES TARGET US RADAR IN BAHRAIN",
               "INTERCEPTED, NO DAMAGE", RED)


def draw_manila(cv, x, y, w, h):
    panel_frame(cv, x, y, w, h, BLUE)
    ix, iy = x + 22, y + 58
    # globe
    cv.circle(ix + 60, iy + 48, 46, (120, 180, 210))
    cv.ring(ix + 60, iy + 48, 46, INK, 2)
    cv.ellipse(ix + 60, iy + 48, 46, 14, (70, 140, 90))
    cv.ellipse(ix + 60, iy + 48, 14, 46, (70, 140, 90))
    # land blobs
    cv.circle(ix + 44, iy + 32, 12, (90, 170, 110))
    cv.circle(ix + 76, iy + 62, 10, (90, 170, 110))
    # plane above the globe: fuselage, swept wings, tail fin
    px, py = ix + 88, iy - 4
    cv.line(px, py + 8, px + 46, py + 8, INK, 5)
    cv.triangle([(px + 46, py + 4), (px + 56, py + 8), (px + 46, py + 12)], INK)
    cv.triangle([(px + 12, py + 8), (px + 26, py + 22), (px + 30, py + 8)], INK)
    cv.triangle([(px + 30, py + 8), (px + 40, py - 2), (px + 42, py + 8)], INK)
    cv.triangle([(px + 2, py + 8), (px + 8, py - 6), (px + 12, py + 8)], INK)
    cv.circle(px + 40, py + 6, 2, WHITE)
    # ground line
    cv.hline(ix - 6, ix + 138, iy + 98, INK, 3)
    panel_text(cv, x + 168, y + 22, w - 190, "ASIA-PACIFIC",
               "TRUMP IN MANILA AHEAD OF XI-PUTIN SUMMIT",
               "TALKS SET FOR THURSDAY", BLUE)


def draw_japan(cv, x, y, w, h):
    panel_frame(cv, x, y, w, h, RED)
    ix, iy = x + 22, y + 58
    # red sun
    cv.circle(ix + 62, iy + 44, 40, RED)
    cv.circle(ix + 62, iy + 44, 32, (200, 60, 50))
    # two jets crossing the sun: pale silhouettes so they read on red
    for (jx, jy) in ((ix + 22, iy + 26), (ix + 72, iy + 58)):
        cv.line(jx, jy + 6, jx + 40, jy + 6, WHITE, 5)
        cv.triangle([(jx + 40, jy + 2), (jx + 50, jy + 6), (jx + 40, jy + 10)],
                    WHITE)
        cv.triangle([(jx + 10, jy + 6), (jx + 22, jy + 18), (jx + 26, jy + 6)],
                    WHITE)
        cv.triangle([(jx + 26, jy + 6), (jx + 34, jy - 2), (jx + 36, jy + 6)],
                    WHITE)
        cv.triangle([(jx + 2, jy + 6), (jx + 8, jy - 4), (jx + 10, jy + 6)],
                    WHITE)
    # sea + island
    cv.rect(ix - 6, iy + 92, 150, 8, SEA)
    cv.ellipse(ix + 62, iy + 90, 34, 10, (90, 170, 110))
    panel_text(cv, x + 168, y + 22, w - 190, "ASIA-PACIFIC",
               "RUSSIAN JETS ENTER JAPAN AIRSPACE",
               "TOKYO SCRAMBLES JETS", RED)


def draw_tech(cv, x, y, w, h):
    panel_frame(cv, x, y, w, h, TEAL)
    ix, iy = x + 22, y + 58
    # server rack
    cv.rect(ix + 14, iy + 2, 84, 96, INK)
    for k in range(3):
        yy = iy + 12 + k * 30
        cv.rect(ix + 22, yy, 68, 20, (52, 62, 72))
        cv.circle(ix + 30, yy + 10, 3, (120, 220, 120))
        cv.circle(ix + 40, yy + 10, 3, RED)
        cv.rect(ix + 52, yy + 7, 30, 6, (180, 190, 200))
    # warning triangle over the rack
    tx, ty = ix + 96, iy + 18
    cv.triangle([(tx, ty), (tx + 34, ty + 44), (tx - 6, ty + 44)], GOLD)
    cv.rect(tx + 12, ty + 16, 6, 16, INK)
    cv.rect(tx + 12, ty + 36, 6, 6, INK)
    # lightning bolt: one clean zigzag polygon
    _bolt = [(ix + 118, iy + 50), (ix + 100, iy + 82), (ix + 111, iy + 82),
             (ix + 102, iy + 104), (ix + 126, iy + 74), (ix + 114, iy + 74),
             (ix + 128, iy + 50)]
    for i in range(1, len(_bolt) - 1):
        cv.triangle([_bolt[0], _bolt[i], _bolt[i + 1]], GOLD)
    panel_text(cv, x + 168, y + 22, w - 190, "TECHNOLOGY",
               "TECH OUTAGES HIT MICROSOFT, FAA, BANKS",
               "NSA BRIEFLY DEGRADED", TEAL)


def draw_footer(cv):
    y0, y1 = 934, 988
    cv.rect(28, y0, 968, y1 - y0, NAVY)
    draw_text(cv, 46, y0 + 16,
              "ALSO: PENTAGON FAILS FINANCIAL AUDIT FOR 9TH STRAIGHT YEAR",
              2, WHITE)
    draw_text_center(cv, W // 2, 996,
                     "SOURCES: REUTERS - CNA - NIKKEI - JUST SECURITY", 1, GREY)


def build():
    cv = Canvas(W, H, CREAM)
    # outer double border
    cv.rect(8, 8, W - 16, H - 16, INK)
    cv.rect(12, 12, W - 24, H - 24, CREAM)
    draw_masthead(cv)
    draw_lead(cv)
    gx, gy = 28, 470
    pw, ph, gap = 476, 214, 16
    draw_bahrain(cv, gx, gy, pw, ph)
    draw_manila(cv, gx + pw + gap, gy, pw, ph)
    draw_japan(cv, gx, gy + ph + gap, pw, ph)
    draw_tech(cv, gx + pw + gap, gy + ph + gap, pw, ph)
    draw_footer(cv)
    return cv


def main():
    out = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, "entry.png")
    cv = build()
    n = write_png(path, cv)
    print(f"wrote {path} ({n} bytes, {W}x{H})")


if __name__ == "__main__":
    main()
