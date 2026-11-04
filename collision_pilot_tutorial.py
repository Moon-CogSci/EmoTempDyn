"""Interactive tutorial for the collision-anticipation affect task.

A step-by-step walkthrough (16 steps) that familiarises a participant with
the task before the main experiment (collision_pilot.py):

  * the stimuli: two coloured circles that move toward each other and either
    collide (a sound plays) or stop just short and move apart;
  * the continuous affect-report overlay: a valence (left-right) by arousal
    (bottom-top) grid in which the participant moves a white dot;
  * quadrant quizzes that check the participant understands the grid;
  * four example trials (collision / near miss, pleasant / unpleasant colour).

Requirements: Python 3.8+, pygame, numpy, tkinter.

Usage:

    python collision_pilot_tutorial.py

A small dialog asks for a participant ID and handedness. The ID's last digit
only selects the colour mapping (which colour signals a pleasant sound), using
the same rule as the main task. Input is a gamepad (DualSense layout) if one
is connected, otherwise keyboard and mouse. Nothing is logged to disk, and
Escape quits at any time.

Optional: place short sound files (.wav, .ogg or .mp3) in
assets/collision_sounds/neutral/ to hear a sound on collision in the example
trials. Without them the tutorial runs silently.
"""

import math
import os
import random
import time
import tkinter as tk

import numpy as np
import pygame

pygame.init()
pygame.joystick.init()


def _choose_output_device():
    try:
        from pygame._sdl2 import audio
        names = audio.get_audio_device_names(False)
    except Exception:
        return None
    if not names:
        return None
    blocked = ("controller", "dualsense", "wireless", "gamepad")
    non_controller = [
        n for n in names
        if not any(b in n.lower() for b in blocked)
    ]
    return non_controller[0] if non_controller else None


_audio_device = _choose_output_device()
try:
    if _audio_device:
        pygame.mixer.init(devicename=_audio_device)
    else:
        pygame.mixer.init()
except pygame.error:
    pygame.mixer.init()


# ---------------------------------------------------------
# PARTICIPANT INFO DIALOG (participant ID and handedness)
# ---------------------------------------------------------

handedness = "right"
participant_id = ""

def _submit_info():
    global handedness, participant_id
    handedness = hand_var.get().strip().lower()
    participant_id = id_entry.get().strip()
    root.destroy()

root = tk.Tk()
root.title("Tutorial")
root.geometry("420x290")
root.resizable(False, False)
tk.Label(
    root,
    text="Welcome to a walkthrough of the upcoming task.\n",
    justify="center"
).pack(pady=(18, 4))
tk.Label(root, text="Participant ID:").pack()
id_entry = tk.Entry(root, width=25)
id_entry.pack()
tk.Label(root, text="Handedness:").pack(pady=(10, 0))
hand_var = tk.StringVar(value="Right")
tk.OptionMenu(root, hand_var, "Right", "Left").pack()
tk.Button(root, text="Start tutorial", command=_submit_info).pack(pady=16)
root.mainloop()

if participant_id == "":
    raise SystemExit

# Colour mapping, counterbalanced across participants by the last digit of the
# ID (same rule as the main task):
#   "rp" = red circles signal a pleasant sound, blue unpleasant;
#   "bp" = blue circles signal a pleasant sound, red unpleasant.
_digits = "".join(c for c in participant_id if c.isdigit())
_last_digit = int(_digits[-1]) if _digits else 1
colour_map = "rp" if ((_last_digit - 1) % 4) // 2 == 0 else "bp"


# =========================================================
# WINDOW AND LAYOUT  (same geometry as the main task)
# =========================================================

info = pygame.display.Info()
WIDTH = info.current_w
HEIGHT = info.current_h
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN)
pygame.display.set_caption("Collision task tutorial")
clock = pygame.time.Clock()

# Trial parameters (mirror the main task so the examples look identical).
RENDER_RATE = 60                    # frames per second
TRIAL_DURATION = 10                 # seconds per example trial
FREEZE_DURATION = 1.0               # seconds the circles stay still at contact
MISS_GAP = (90.0, 100.0)            # px gap left between circles on a near miss
CONTACT_TIME_TARGET = 5.0           # seconds from trial start to contact
CONTACT_TIME_WINDOW = (3.0, 7.0)    # allowed range for the contact time
BAND_WIDTH_SCALE = 1.0              # width of the circles' start-position bands

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GREY_RAIL = (200, 200, 200)
COACH_BG = (18, 22, 32)
COACH_EDGE = (90, 140, 210)
OK_GREEN = (70, 190, 110)
HINT_AMBER = (230, 190, 80)
HIGHLIGHT = (40, 90, 70)

PAD_X = WIDTH / 32.0
PAD_Y = HEIGHT / 18.0
CONTENT_X0 = PAD_X
CONTENT_Y0 = PAD_Y
CONTENT_W = WIDTH - 2 * PAD_X
CONTENT_H = HEIGHT - 2 * PAD_Y

# Same circle size and motion line as the main task: radius = 5% of the
# screen height, motion line centred between the top margin and the overlay's
# "Excited" label.
CIRCLE_RADIUS = max(20, int(round(HEIGHT * 0.05)))
OVERLAY_SIZE = int(CONTENT_H // 2)
OVERLAY_X = int(round(CONTENT_X0 + (CONTENT_W - OVERLAY_SIZE) / 2.0))
OVERLAY_Y = int(round(CONTENT_Y0 + CONTENT_H - OVERLAY_SIZE))
_OVERLAY_LABEL_TOP = OVERLAY_Y - int(round(PAD_Y / 2.0)) - 14
MOTION_Y = int(round(0.5 * (CONTENT_Y0 + _OVERLAY_LABEL_TOP)))
BAND_WIDTH = BAND_WIDTH_SCALE * (2 * CONTENT_W - CONTENT_H) / 8.0
LEFT_BAND = (
    CONTENT_X0 + CIRCLE_RADIUS,
    CONTENT_X0 + CIRCLE_RADIUS + BAND_WIDTH
)
RIGHT_BAND = (
    CONTENT_X0 + CONTENT_W - CIRCLE_RADIUS - BAND_WIDTH,
    CONTENT_X0 + CONTENT_W - CIRCLE_RADIUS
)

_L_MID = 0.5 * (LEFT_BAND[0] + LEFT_BAND[1])
_R_MID = 0.5 * (RIGHT_BAND[0] + RIGHT_BAND[1])
_D_MID = _R_MID - _L_MID
_GAP_REF = 0.5 * (0.0 + 0.5 * (MISS_GAP[0] + MISS_GAP[1]))
SPEED = (_D_MID - 2 * CIRCLE_RADIUS - _GAP_REF) / (2.0 * CONTACT_TIME_TARGET)
_D_MIN = RIGHT_BAND[0] - LEFT_BAND[1]
_D_MAX = RIGHT_BAND[1] - LEFT_BAND[0]


def contact_time(d_start, gap):
    return (d_start - 2 * CIRCLE_RADIUS - gap) / (2.0 * SPEED)


def start_separation(t_contact, gap):
    return 2 * CIRCLE_RADIUS + gap + 2.0 * SPEED * t_contact


_T_REACHABLE_LO = contact_time(_D_MIN, 0.0)
_T_REACHABLE_HI = contact_time(_D_MAX, MISS_GAP[1])
_T_HALF = min(
    CONTACT_TIME_TARGET - max(CONTACT_TIME_WINDOW[0], _T_REACHABLE_LO),
    min(CONTACT_TIME_WINDOW[1], _T_REACHABLE_HI) - CONTACT_TIME_TARGET
)
CONTACT_TIME_LO = CONTACT_TIME_TARGET - _T_HALF
CONTACT_TIME_HI = CONTACT_TIME_TARGET + _T_HALF

CIRCLE_RED = (225, 65, 65)
CIRCLE_BLUE = (65, 105, 225)
if colour_map == "rp":
    CONDITION_COLOUR = {"pleasant": CIRCLE_RED, "unpleasant": CIRCLE_BLUE}
    CONDITION_COLOUR_NAME = {"pleasant": "red", "unpleasant": "blue"}
else:
    CONDITION_COLOUR = {"pleasant": CIRCLE_BLUE, "unpleasant": CIRCLE_RED}
    CONDITION_COLOUR_NAME = {"pleasant": "blue", "unpleasant": "red"}


AROUSAL_HIGH_LABEL = "Excited"
AROUSAL_LOW_LABEL = "Calm"
VALENCE_LOW_LABEL = "Unpleasant"
VALENCE_HIGH_LABEL = "Pleasant"
OVERLAY_LABEL_GAP = int(round(PAD_Y / 2.0))
OVERLAY_LABEL_ALPHA = 105
OVERLAY_LABEL_COLOUR = (215, 215, 215)
CURSOR_COLOUR = WHITE
CURSOR_RADIUS = 8

# Banner/callout text scales down on screens shorter than 1080 px so the
# banner stays short enough to leave room for the circles above the overlay.
UI_SCALE = min(1.0, HEIGHT / 1080.0)


def _fs(size):
    return max(12, int(round(size * UI_SCALE)))


font_title = pygame.font.SysFont("Arial", _fs(34), bold=True)
font_body = pygame.font.SysFont("Arial", _fs(24))
font_hint = pygame.font.SysFont("Arial", _fs(22))
font_small = pygame.font.SysFont("Arial", _fs(20))
BODY_LINE_H = max(18, int(round(28 * UI_SCALE)))
HINT_LINE_H = max(16, int(round(22 * UI_SCALE)))
_overlay_label_font = pygame.font.SysFont("Arial", 24, bold=True)


def _overlay_label(text, rotate=0):
    surf = _overlay_label_font.render(
        text, True, OVERLAY_LABEL_COLOUR
    ).convert_alpha()
    surf.fill(
        (255, 255, 255, OVERLAY_LABEL_ALPHA),
        special_flags=pygame.BLEND_RGBA_MULT
    )
    if rotate:
        surf = pygame.transform.rotate(surf, rotate)
    return surf


_LBL_AROUSAL_HIGH = _overlay_label(AROUSAL_HIGH_LABEL)
_LBL_AROUSAL_LOW = _overlay_label(AROUSAL_LOW_LABEL)
_LBL_VALENCE_LOW = _overlay_label(VALENCE_LOW_LABEL, rotate=90)
_LBL_VALENCE_HIGH = _overlay_label(VALENCE_HIGH_LABEL, rotate=-90)


def _make_flashlight_spot(diameter=256):
    # Brightest at the centre, fading smoothly to nothing at the rim. The
    # fall-off is gentle (power 1.5) so it covers most of the quadrant while
    # the very edges near the axes/borders stay dark.
    surf = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
    c = diameter // 2
    colour = (255, 236, 160)
    for i in range(c, 0, -1):
        r = i / float(c)
        a = int(225 * (1.0 - r ** 1.5))
        if a > 0:
            pygame.draw.circle(surf, colour + (a,), (c, c), i)
    return surf


FLASHLIGHT_SPOT = _make_flashlight_spot()


def wrap_text(font, text, max_width):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        trial = w if not cur else cur + " " + w
        if font.size(trial)[0] <= max_width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines

LEFT_STICK_AXES = (0, 1)
RIGHT_STICK_AXES = (2, 3)
STICK_AXES = LEFT_STICK_AXES if handedness == "left" else RIGHT_STICK_AXES
LEFT_HANDED = handedness == "left"
# Next / previous step:
#   right-handed -> X / Triangle;  left-handed -> D-pad Down / D-pad Up.
# Start / restart an example trial (steps 12-15), pressed with the index
# finger so the thumb can stay on the thumbstick:
#   right-handed -> right shoulder button (R1);  left-handed -> left shoulder (L1).
if LEFT_HANDED:
    BTN_CONFIRM = 12    # D-pad Down -> next step      (replaces X)
    BTN_BACK = 11       # D-pad Up   -> previous step  (replaces Triangle)
    BTN_ACTION = 9      # Left shoulder (L1)
else:
    BTN_CONFIRM = 0     # Cross (X)  -> next step
    BTN_BACK = 3        # Triangle   -> previous step
    BTN_ACTION = 10     # Right shoulder (R1)
NAV_ACTION = "action"
NAV_NEXT = "next"
NAV_PREV = "prev"
USE_GAMEPAD = False
joystick = None

if pygame.joystick.get_count() > 0:
    joystick = pygame.joystick.Joystick(0)
    joystick.init()
    USE_GAMEPAD = True
    if max(STICK_AXES) >= joystick.get_numaxes():
        STICK_AXES = LEFT_STICK_AXES

pygame.mouse.set_visible(not USE_GAMEPAD)

# The triangle is drawn as a vector shape (Arial has no glyph for it);
# TRIANGLE is only a placeholder character inside hint strings.
TRIANGLE = "\u25B3"
CIRCLE = "\u25CB"

# Names of the three gamepad controls as they appear in on-screen text.
NEXT_NAME = "D-pad Down" if LEFT_HANDED else "X"
BACK_NAME = "D-pad Up" if LEFT_HANDED else TRIANGLE
ACTION_NAME = "left shoulder" if LEFT_HANDED else "right shoulder"

NEXT_HINT = (
    "Press {} to go to the next step".format(NEXT_NAME)
    if USE_GAMEPAD else
    "Click or press Space to go to the next step"
)
PREV_HINT = (
    "Press {} to go to the previous step".format(BACK_NAME)
    if USE_GAMEPAD else
    "Press Backspace to go to the previous step"
)
NAV_HINT = NEXT_HINT + "  |  " + PREV_HINT
MOVE_HINT = (
    "Use the {} stick.".format("left" if handedness == "left" else "right")
    if USE_GAMEPAD else
    "Click and drag to move the white dot."
)


def quit_all():
    pygame.quit()
    raise SystemExit


class Overlay:

    def __init__(self):
        self.size = OVERLAY_SIZE
        self.x = OVERLAY_X
        self.y = OVERLAY_Y
        self.cx = self.x + self.size / 2
        self.cy = self.y + self.size / 2

    def reset(self):
        self.cx = self.x + self.size / 2
        self.cy = self.y + self.size / 2

    def update(self):
        if USE_GAMEPAD:
            rx = joystick.get_axis(STICK_AXES[0])
            ry = joystick.get_axis(STICK_AXES[1])
            if abs(rx) < 0.08:
                rx = 0
            if abs(ry) < 0.08:
                ry = 0
            # Full deflection = speed of one moving circle (SPEED px/s);
            # deflection vector capped at length 1 (no faster diagonals).
            mag = (rx * rx + ry * ry) ** 0.5
            if mag > 1.0:
                rx /= mag
                ry /= mag
            gain = SPEED / RENDER_RATE
            self.cx += rx * gain
            self.cy += ry * gain
        else:
            if pygame.mouse.get_pressed()[0]:
                rel_x, rel_y = pygame.mouse.get_rel()
                self.cx += rel_x
                self.cy += rel_y
            else:
                pygame.mouse.get_rel()

        self.cx = np.clip(self.cx, self.x, self.x + self.size)
        self.cy = np.clip(self.cy, self.y, self.y + self.size)

    def control_active(self):
        if USE_GAMEPAD:
            rx = joystick.get_axis(STICK_AXES[0])
            ry = joystick.get_axis(STICK_AXES[1])
            return abs(rx) >= 0.10 or abs(ry) >= 0.10
        return pygame.mouse.get_pressed()[0]

    def affect(self):
        half = self.size / 2
        cx0 = self.x + half
        cy0 = self.y + half
        valence = (self.cx - cx0) / half * 50
        arousal = (cy0 - self.cy) / half * 50
        return valence, arousal

    def draw(self, highlight=None):
        surf = pygame.Surface((self.size, self.size), pygame.SRCALPHA)
        surf.fill((0, 0, 0, 120))
        if highlight == "right":
            pygame.draw.rect(
                surf, HIGHLIGHT + (90,),
                (self.size // 2, 0, self.size // 2, self.size)
            )
        elif highlight == "left":
            pygame.draw.rect(
                surf, HIGHLIGHT + (90,),
                (0, 0, self.size // 2, self.size)
            )
        elif highlight == "top":
            pygame.draw.rect(
                surf, HIGHLIGHT + (90,),
                (0, 0, self.size, self.size // 2)
            )
        elif highlight == "bottom":
            pygame.draw.rect(
                surf, HIGHLIGHT + (90,),
                (0, self.size // 2, self.size, self.size // 2)
            )
        elif highlight == "quadrants":
            pulse = 0.16 + 0.84 * (
                0.5 * (1.0 + math.sin(time.perf_counter() * 3.2))
            )
            half = self.size / 2.0
            ihalf = int(half)
            radius = max(16, int(half * 0.56))
            spot = pygame.transform.smoothscale(
                FLASHLIGHT_SPOT, (radius * 2, radius * 2)
            )
            spot.fill(
                (255, 255, 255, int(255 * pulse)),
                special_flags=pygame.BLEND_RGBA_MULT
            )
            quads = (
                ((half * 1.5, half * 0.5), (ihalf, 0, ihalf, ihalf)),
                ((half * 0.5, half * 0.5), (0, 0, ihalf, ihalf)),
                ((half * 1.5, half * 1.5), (ihalf, ihalf, ihalf, ihalf)),
                ((half * 0.5, half * 1.5), (0, ihalf, ihalf, ihalf)),
            )
            for cxy, clip in quads:
                surf.set_clip(pygame.Rect(clip))
                surf.blit(spot, spot.get_rect(center=cxy))
            surf.set_clip(None)
        pygame.draw.rect(surf, WHITE, (0, 0, self.size, self.size), 2)
        pygame.draw.line(
            surf, (180, 180, 180),
            (self.size // 2, 0), (self.size // 2, self.size), 2
        )
        pygame.draw.line(
            surf, (180, 180, 180),
            (0, self.size // 2), (self.size, self.size // 2), 2
        )
        screen.blit(surf, (self.x, self.y))

        cx = self.x + self.size // 2
        cy = self.y + self.size // 2
        gap = OVERLAY_LABEL_GAP
        screen.blit(_LBL_AROUSAL_HIGH, _LBL_AROUSAL_HIGH.get_rect(
            center=(cx, self.y - gap)))
        screen.blit(_LBL_AROUSAL_LOW, _LBL_AROUSAL_LOW.get_rect(
            center=(cx, self.y + self.size + gap)))
        screen.blit(_LBL_VALENCE_LOW, _LBL_VALENCE_LOW.get_rect(
            center=(self.x - gap, cy)))
        screen.blit(_LBL_VALENCE_HIGH, _LBL_VALENCE_HIGH.get_rect(
            center=(self.x + self.size + gap, cy)))

        pygame.draw.circle(
            screen, CURSOR_COLOUR, (int(self.cx), int(self.cy)), CURSOR_RADIUS
        )
        pygame.draw.circle(
            screen, BLACK, (int(self.cx), int(self.cy)), CURSOR_RADIUS, 2
        )


class TrialPlan:

    def __init__(self, condition, should_collide, t_contact=None):
        self.condition = condition
        self.should_collide = should_collide
        self.gap = 0.0 if should_collide else random.uniform(*MISS_GAP)
        if t_contact is None:
            t_contact = random.triangular(
                CONTACT_TIME_LO, CONTACT_TIME_HI, CONTACT_TIME_TARGET
            )
        d_start = start_separation(t_contact, self.gap)
        d_start = min(max(d_start, _D_MIN), _D_MAX)
        self.t_contact = contact_time(d_start, self.gap)
        lo_x = max(LEFT_BAND[0], RIGHT_BAND[0] - d_start)
        hi_x = min(LEFT_BAND[1], RIGHT_BAND[1] - d_start)
        self.left_start = random.uniform(lo_x, max(lo_x, hi_x))
        self.right_start = self.left_start + d_start
        self.travel = SPEED * self.t_contact
        self.freeze_end = self.t_contact + FREEZE_DURATION
        self.retreat_speed = SPEED

    def positions(self, t):
        if t < self.t_contact:
            advance = SPEED * t
            phase = "approach"
        elif t < self.freeze_end:
            advance = self.travel
            phase = "freeze"
        else:
            back = self.retreat_speed * (t - self.freeze_end)
            advance = max(0.0, self.travel - back)
            phase = "retreat" if advance > 0.0 else "parked"
        return (
            self.left_start + advance,
            self.right_start - advance,
            phase
        )


def circle_y():
    # Normally on the task's motion line, but pushed down whenever a tall
    # banner would otherwise cover the circles.
    rect = coach.banner_rect()[0]
    bottom = rect.bottom + (0 if coach.hint else 14)   # same height with/without hint
    wanted = bottom + 22 + CIRCLE_RADIUS
    label_top = (
        OVERLAY_Y - OVERLAY_LABEL_GAP - _LBL_AROUSAL_HIGH.get_height()
    )
    limit = label_top - 12 - CIRCLE_RADIUS
    return int(max(MOTION_Y, min(wanted, limit)))


def draw_circles(plan, left_x, right_x):
    # Flat, solid-filled circles (no outline).
    colour = CONDITION_COLOUR[plan.condition]
    y = circle_y()
    for x in (left_x, right_x):
        pygame.draw.circle(
            screen, colour, (int(round(x)), y), CIRCLE_RADIUS
        )


def symmetric_positions(plan, advance=0.0):
    # Circles equidistant from the horizontal centre of the screen.
    half = 0.5 * (plan.right_start - plan.left_start) - advance
    cx = WIDTH / 2.0
    return cx - half, cx + half


def load_demo_sounds():
    # Example-trial collisions always play a neutral sound, whatever the
    # circle colour, because the examples are purely illustrative. Returns an
    # empty list (silent examples) if the folder is missing or empty.
    folder = os.path.join("assets", "collision_sounds", "neutral")
    if not os.path.isdir(folder):
        return []
    files = sorted(
        f for f in os.listdir(folder)
        if f.lower().endswith((".wav", ".ogg", ".mp3"))
    )
    sounds = []
    for f in files:
        try:
            sounds.append(pygame.mixer.Sound(os.path.join(folder, f)))
        except pygame.error:
            pass
    return sounds


DEMO_SOUNDS = load_demo_sounds()


# =========================================================
# COACH BANNER
# =========================================================

def _sym_width(font):
    return int(font.get_height() * 0.85)


def _split_syms(text):
    # Split text into plain chunks and symbol markers (triangle / circle).
    out, cur = [], ""
    for ch in text:
        if ch in (TRIANGLE, CIRCLE):
            out.append(("t", cur))
            out.append(("s", ch))
            cur = ""
        else:
            cur += ch
    out.append(("t", cur))
    return [(k, v) for k, v in out if not (k == "t" and v == "")]


def sym_text_width(font, text):
    # Width of a string whose triangle/circle placeholders are drawn as shapes.
    w = 0
    for kind, v in _split_syms(text):
        w += font.size(v)[0] if kind == "t" else _sym_width(font)
    return w


def wrap_sym(font, text, max_width):
    words = text.split(" ")
    lines, cur = [], ""
    for w in words:
        trial = w if not cur else cur + " " + w
        if sym_text_width(font, trial) <= max_width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def render_sym(font, line, colour=WHITE):
    parts = _split_syms(line)
    sw = _sym_width(font)
    h = font.get_height()
    total_w = sum(font.size(v)[0] if k == "t" else sw for k, v in parts)
    out = pygame.Surface((max(1, total_w), h), pygame.SRCALPHA)
    x = 0
    for kind, v in parts:
        if kind == "t":
            out.blit(font.render(v, True, colour), (x, 0))
            x += font.size(v)[0]
        else:
            pad = max(2, sw // 6)
            if v == TRIANGLE:
                pts = [
                    (x + sw // 2, int(h * 0.20)),
                    (x + pad, int(h * 0.78)),
                    (x + sw - pad, int(h * 0.78)),
                ]
                pygame.draw.polygon(out, colour, pts, 2)
            else:
                r = max(4, int(sw * 0.36))
                pygame.draw.circle(
                    out, colour, (x + sw // 2, int(h * 0.52)), r, 2
                )
            x += sw
    return out


# Hint-line helpers (banner hint uses font_hint).
def wrap_hint(text, max_width):
    return wrap_sym(font_hint, text, max_width)


def render_hint_line(line, colour=WHITE):
    return render_sym(font_hint, line, colour)


class Coach:

    def __init__(self):
        self.step = 1
        self.n_steps = 12
        self.title = ""
        self.lines = []
        self.hint = NAV_HINT
        self.status = ""
        self.status_ok = False

    def set(self, step, title, lines, hint=None, status="", status_ok=False):
        self.step = step
        self.title = title
        self.lines = list(lines)
        if hint is not None:
            self.hint = hint
        self.status = status
        self.status_ok = status_ok

    def banner_rect(self, centered=False):
        pad_x = 22
        inner_w = int(CONTENT_W) - 2 * pad_x
        wrapped = []
        for line in self.lines:
            wrapped.extend(wrap_sym(font_body, line, inner_w))
        line_h = BODY_LINE_H
        progress_h = font_small.get_height()
        title_h = font_title.get_height()
        hint_lines = wrap_hint(self.hint, inner_w) if self.hint else []
        top = 12 + progress_h + 8 + title_h + 12
        body_h = len(wrapped) * line_h
        hint_h = (HINT_LINE_H * len(hint_lines) + 16) if hint_lines else 24
        box_h = top + body_h + hint_h
        rect = pygame.Rect(
            int(PAD_X), int(PAD_Y * 0.4), int(CONTENT_W), int(box_h)
        )
        if centered:
            rect.center = (WIDTH // 2, HEIGHT // 2)
        return rect, wrapped, top

    def draw(self, centered=False):
        rect, wrapped, body_y = self.banner_rect(centered)
        pygame.draw.rect(screen, COACH_BG, rect, border_radius=10)
        pygame.draw.rect(screen, COACH_EDGE, rect, 2, border_radius=10)

        progress = font_small.render(
            "Tutorial  ·  step {} of {}".format(self.step, self.n_steps),
            True, COACH_EDGE
        )
        screen.blit(progress, (rect.x + 22, rect.y + 12))

        t = font_title.render(self.title, True, WHITE)
        screen.blit(t, (rect.x + 22, rect.y + 12 + font_small.get_height() + 8))

        y = rect.y + body_y
        for line in wrapped:
            s = render_sym(font_body, line, GREY_RAIL)
            screen.blit(s, (rect.x + 22, y))
            y += BODY_LINE_H

        if self.status:
            col = OK_GREEN if self.status_ok else HINT_AMBER
            st = font_hint.render(self.status, True, col)
            screen.blit(
                st, st.get_rect(midright=(rect.right - 22, rect.y + int(52 * UI_SCALE)))
            )

        if self.hint:
            inner_w = int(CONTENT_W) - 44
            hint_lines = wrap_hint(self.hint, inner_w)
            hy = rect.bottom - 16 - HINT_LINE_H * (len(hint_lines) - 1)
            for line in hint_lines:
                h = render_hint_line(line, WHITE)
                screen.blit(
                    h, h.get_rect(midright=(rect.right - 22, hy))
                )
                hy += HINT_LINE_H


coach = Coach()
overlay = Overlay()
N_STEPS = 16
coach.n_steps = N_STEPS


def pump_nav(allow_next=False, allow_prev=True, allow_action=False):
    # Poll input and return NAV_NEXT, NAV_PREV, NAV_ACTION or None.
    # allow_action: the shoulder button (gamepad) or Space/click
    # (keyboard + mouse) returns NAV_ACTION instead of NAV_NEXT. On the
    # gamepad, X / D-pad Down never trigger it, so the next-step button cannot
    # start or restart an example trial by accident.
    result = None
    if coach.step <= 1:
        allow_prev = False
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            quit_all()
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                quit_all()
            if event.key in (pygame.K_SPACE, pygame.K_RETURN):
                if allow_action:
                    result = NAV_ACTION
                elif allow_next:
                    result = NAV_NEXT
            if allow_prev and event.key == pygame.K_BACKSPACE:
                result = NAV_PREV
        if event.type == pygame.MOUSEBUTTONDOWN and not USE_GAMEPAD:
            if allow_action:
                result = NAV_ACTION
            elif allow_next:
                result = NAV_NEXT
        if USE_GAMEPAD and event.type == pygame.JOYBUTTONDOWN:
            if allow_action and event.button == BTN_ACTION:
                result = NAV_ACTION
            elif allow_next and event.button == BTN_CONFIRM:
                result = NAV_NEXT
            elif allow_prev and event.button == BTN_BACK:
                result = NAV_PREV
        if USE_GAMEPAD and LEFT_HANDED and event.type == pygame.JOYHATMOTION:
            # Some drivers report the D-pad as a hat instead of buttons.
            hx, hy = event.value
            if hy == -1 and allow_next:
                result = NAV_NEXT
            elif hy == 1 and allow_prev:
                result = NAV_PREV
    return result


def wait_continue(min_visible=1.2, move_overlay=True):
    start = time.perf_counter()
    while True:
        clock.tick(RENDER_RATE)
        ready = time.perf_counter() - start >= min_visible
        nav = pump_nav(allow_next=ready, allow_prev=True)
        if nav:
            return nav
        if move_overlay:
            overlay.update()
        yield ready


def run_step_wait(draw, min_visible=1.2, move_overlay=True):
    gen = wait_continue(min_visible, move_overlay)
    try:
        while True:
            draw(next(gen))
    except StopIteration as err:
        return err.value if err.value else NAV_NEXT


def frame(draw_world, highlight=None):
    screen.fill(BLACK)
    draw_world()
    overlay.draw(highlight=highlight)
    coach.draw()
    pygame.display.flip()


def coach_banner_rect():
    return coach.banner_rect()[0]


def task_screen_rect():
    top = coach_banner_rect().bottom + 16
    bottom_pad = int(PAD_Y * 0.45)
    return pygame.Rect(
        int(PAD_X),
        top,
        int(CONTENT_W),
        HEIGHT - top - bottom_pad
    )


def overlay_split_y():
    # Cover/uncover line sits just above the "Excited" label.
    label_top = (
        overlay.y - OVERLAY_LABEL_GAP - _LBL_AROUSAL_HIGH.get_height() / 2.0
    )
    return int(round(label_top - 8))


def draw_screen_wash(clear="none"):
    # 30% white over the whole display except the banner (and any clear region).
    sw, sh = screen.get_size()
    wash = pygame.Surface((sw + 16, sh + 16), pygame.SRCALPHA)
    wash.fill((255, 255, 255, 76))
    banner = coach_banner_rect()
    wash.fill((0, 0, 0, 0), banner.inflate(6, 6))
    if clear in ("upper", "lower"):
        split = max(overlay_split_y(), banner.bottom)
        if clear == "upper":
            hole = pygame.Rect(0, banner.bottom, sw + 16, split - banner.bottom)
        else:
            hole = pygame.Rect(0, split, sw + 16, sh + 16 - split)
        if hole.height > 0:
            wash.fill((0, 0, 0, 0), hole)
    screen.blit(wash, (0, 0))


def overlay_restore():
    overlay.size = OVERLAY_SIZE
    overlay.x = OVERLAY_X
    overlay.y = OVERLAY_Y
    overlay.reset()


def overlay_quiz_geom():
    # One fixed size/position for steps 6-10, whatever each banner's height:
    # laid out under a reference banner with a two-line body and one hint line.
    ref = Coach()
    ref.lines = ["x", "x"]
    ref.hint = PREV_HINT
    return overlay_expanded_geom(ref.banner_rect()[0])


def overlay_expanded_geom(banner=None):
    if banner is None:
        banner = coach_banner_rect()
    label_space = (
        OVERLAY_LABEL_GAP
        + _LBL_AROUSAL_HIGH.get_height() // 2
        + 22
    )
    top = banner.bottom + label_space
    bottom = int(CONTENT_Y0 + CONTENT_H)
    side = 40
    avail_w = int(CONTENT_W) - 2 * side
    avail_h = bottom - top
    size = int(max(OVERLAY_SIZE, min(avail_w, avail_h)))
    x = int(CONTENT_X0 + (CONTENT_W - size) / 2.0)
    y = int(bottom - size)
    if y < top:
        y = int(top)
        size = int(min(size, bottom - y))
        x = int(CONTENT_X0 + (CONTENT_W - size) / 2.0)
    return x, y, size


def set_overlay_geom(x, y, size, keep_cursor=False):
    old_cx, old_cy = overlay.cx, overlay.cy
    overlay.x = int(x)
    overlay.y = int(y)
    overlay.size = int(size)
    if keep_cursor:
        overlay.cx = float(np.clip(old_cx, overlay.x, overlay.x + overlay.size))
        overlay.cy = float(np.clip(old_cy, overlay.y, overlay.y + overlay.size))
    else:
        overlay.reset()


def _arrow_head(tip, ang, colour=WHITE, size=10):
    pts = []
    for d in (0.45, -0.45):
        pts.append((
            tip[0] - size * math.cos(ang + d),
            tip[1] - size * math.sin(ang + d)
        ))
    pygame.draw.polygon(screen, colour, [tip] + pts)


def _blit_note_box(surfs, box_x, box_y, pad_x, pad_y, gap):
    box_w = max(s.get_width() for s in surfs) + 2 * pad_x
    box_h = sum(s.get_height() for s in surfs) + gap * (len(surfs) - 1) + 2 * pad_y
    box = pygame.Rect(int(box_x), int(box_y), box_w, box_h)
    pygame.draw.rect(screen, (12, 16, 26), box, border_radius=8)
    pygame.draw.rect(screen, COACH_EDGE, box, 2, border_radius=8)
    y = box.y + pad_y
    for s in surfs:
        screen.blit(s, (box.x + pad_x, y))
        y += s.get_height() + gap
    return box


def draw_callout(text, target, side="right"):
    rect = task_screen_rect()
    max_w = int(rect.width * 0.40)
    lines = wrap_text(font_small, text, max_w)
    surfs = [font_small.render(line, True, WHITE) for line in lines]
    pad_x, pad_y, gap = 14, 12, 4
    box_w = max(s.get_width() for s in surfs) + 2 * pad_x
    box_h = sum(s.get_height() for s in surfs) + gap * (len(surfs) - 1) + 2 * pad_y
    split = overlay_split_y()

    if side == "below":
        box_x = target[0] - box_w // 2
        box_x = max(18, min(box_x, WIDTH - box_w - 18))
        box_y = target[1] + 18
        box_y = min(box_y, split - box_h - 10)
        box_y = max(box_y, target[1] + 14)
        stem = (box_x + box_w // 2, box_y)
    elif side == "right":
        box_x = rect.right - box_w - 18
        box_y = target[1] - box_h // 2
        box_y = max(rect.y + 10, min(box_y, rect.centery - box_h - 8))
        stem = (box_x, box_y + box_h // 2)
    else:
        box_x = rect.x + 18
        box_y = target[1] - box_h // 2
        box_y = max(rect.centery + 8, min(box_y, rect.bottom - box_h - 10))
        stem = (box_x + box_w, box_y + box_h // 2)

    box = _blit_note_box(surfs, box_x, box_y, pad_x, pad_y, gap)
    pygame.draw.line(screen, WHITE, stem, target, 2)
    ang = math.atan2(target[1] - stem[1], target[0] - stem[0])
    _arrow_head(target, ang)
    return box


def draw_note_box(text, midleft, max_frac=0.28):
    max_w = int(WIDTH * max_frac)
    lines = wrap_text(font_small, text, max_w)
    surfs = [font_small.render(line, True, WHITE) for line in lines]
    pad_x, pad_y, gap = 14, 12, 4
    box_w = max(s.get_width() for s in surfs) + 2 * pad_x
    box_h = sum(s.get_height() for s in surfs) + gap * (len(surfs) - 1) + 2 * pad_y
    box_x = midleft[0]
    box_y = midleft[1] - box_h // 2
    sw, sh = screen.get_size()
    box_x = min(box_x, sw - box_w - 12)
    box_x = max(12, box_x)
    box_y = max(12, min(box_y, sh - box_h - 12))
    return _blit_note_box(surfs, box_x, box_y, pad_x, pad_y, gap)


# =========================================================
# STEPS
# =========================================================

def step_welcome():
    coach.set(
        1,
        "Welcome",
        [
            "Welcome to a brief overview of the task you will be doing today.",
            "This experiment aims to study continuous changes in emotional "
            "experience as people go through pleasant or unpleasant events.",
        ],
        hint=""
    )

    def draw(ready):
        coach.hint = NEXT_HINT if ready else ""
        screen.fill(BLACK)
        coach.draw(centered=True)
        pygame.display.flip()

    return run_step_wait(draw, 2.0, False)


def step_two_components():
    overlay_restore()
    overlay.reset()
    plan = TrialPlan("pleasant", False, t_contact=5.0)
    lx, rx = symmetric_positions(plan)

    coach.set(
        2,
        "This task has two main components:",
        ["the stimuli and the response overlay."],
        hint=""
    )

    def draw(ready):
        coach.hint = NAV_HINT if ready else ""
        screen.fill(BLACK)
        draw_circles(plan, lx, rx)
        overlay.draw()
        draw_screen_wash(clear="none")
        coach.draw()
        pygame.display.flip()

    return run_step_wait(draw, 2.0, False)


STIMULI_CALLOUT = (
    "THE STIMULI: Two circles, either blue or red, move towards each other "
    "horizontally along a straight line. If they collide, you hear a sound "
    "— pleasant or unpleasant based on the colour of the circles."
)

RESPONSE_CALLOUT = (
    "RESPONSE GRID — This is what you use to continuously report your "
    "emotional state using the {}.".format(
        "gamepad thumbstick" if USE_GAMEPAD else "mouse"
    )
)


def step_stimuli_tour():
    overlay.reset()
    plan = TrialPlan("pleasant", False, t_contact=4.5)
    coach.set(
        3,
        "This task has two main components:",
        ["the stimuli and the response overlay."],
        hint=""
    )

    cycle_s = 2.6
    n_cycles = 3
    start = time.perf_counter()
    min_visible = cycle_s * n_cycles

    while True:
        clock.tick(RENDER_RATE)
        elapsed = time.perf_counter() - start
        ready = elapsed >= min_visible
        nav = pump_nav(allow_next=ready, allow_prev=True)
        if nav:
            return nav

        # To-and-fro: 0 at the starts, 1 at closest approach.
        if elapsed < min_visible:
            u = 0.5 * (1.0 - math.cos(2.0 * math.pi * elapsed / cycle_s))
        else:
            u = 0.0
        lx, rx = symmetric_positions(plan, plan.travel * u)
        target = (int(0.5 * (lx + rx)), circle_y() + CIRCLE_RADIUS + 6)

        coach.hint = NAV_HINT if ready else ""
        screen.fill(BLACK)
        draw_circles(plan, lx, rx)
        overlay.draw()
        draw_screen_wash(clear="upper")
        draw_callout(STIMULI_CALLOUT, target, side="below")
        coach.draw()
        pygame.display.flip()


def step_response_tour():
    overlay.reset()
    plan = TrialPlan("pleasant", False, t_contact=5.0)
    lx, rx = symmetric_positions(plan)
    coach.set(
        4,
        "This task has two main components:",
        ["the stimuli and the response overlay."],
        hint=""
    )
    target = (
        overlay.x + overlay.size // 2,
        overlay.y + 12
    )

    def draw(ready):
        coach.hint = NAV_HINT if ready else ""
        screen.fill(BLACK)
        draw_circles(plan, lx, rx)
        overlay.draw()
        draw_screen_wash(clear="lower")
        draw_callout(RESPONSE_CALLOUT, target, side="left")
        coach.draw()
        pygame.display.flip()

    return run_step_wait(draw, 2.0, False)


def step_meet_grid():
    overlay_restore()
    overlay.reset()
    stick_word = (
        "{} thumbstick".format("left" if handedness == "left" else "right")
        if USE_GAMEPAD else
        "mouse"
    )
    coach.set(
        5, "Meet the overlay",
        [
            "This grid is where you report your emotional state, continuously, during a trial.",
            "More you move to the left = more unpleasant, more towards the right = more pleasant.",
            "More you move to the top = more excited, more towards the bottom = calmer.",
            "Centre represents an emotionally neutral state, "
            "neither more excited nor calmer/bored than usual.",
            "Try moving around the white dot with the {}.".format(stick_word),
        ],
        hint=""
    )
    x0, y0, s0 = overlay.x, overlay.y, overlay.size
    x1, y1, s1 = overlay_expanded_geom()
    anim = 1.2
    start = time.perf_counter()
    move_started = None
    moved_total = 0.0
    last_t = start
    show_dot_note = False
    note_shown_at = None
    NOTE_TO_NEXT_DELAY = 1.0
    while True:
        clock.tick(RENDER_RATE)
        now = time.perf_counter()
        dt = now - last_t
        last_t = now
        elapsed = now - start
        u = min(1.0, elapsed / anim)
        u = 1.0 - (1.0 - u) ** 2
        expanding = elapsed < anim
        set_overlay_geom(
            x0 + (x1 - x0) * u,
            y0 + (y1 - y0) * u,
            s0 + (s1 - s0) * u,
            keep_cursor=not expanding
        )
        if expanding:
            pygame.mouse.get_rel()
        else:
            overlay.update()
            if overlay.control_active():
                moved_total += dt
                if move_started is None:
                    move_started = now
            if move_started is not None and (now - move_started) >= 2.0:
                if not show_dot_note:
                    note_shown_at = now
                show_dot_note = True
        # The right-hand note comes first; "next" is offered 1 s after it
        # has appeared (and only once the dot has been moved >= 1.0 s).
        ready = (
            show_dot_note
            and moved_total >= 1.0
            and (now - note_shown_at) >= NOTE_TO_NEXT_DELAY
        )
        nav = pump_nav(allow_next=ready, allow_prev=True)
        if nav:
            set_overlay_geom(x1, y1, s1, keep_cursor=True)
            return nav
        coach.hint = NAV_HINT if ready else ""
        screen.fill(BLACK)
        overlay.draw()
        if show_dot_note:
            draw_note_box(
                "This white dot represents your emotional state at a "
                "particular instant of time.",
                (
                    overlay.x + overlay.size + OVERLAY_LABEL_GAP + 32,
                    overlay.y + overlay.size // 2
                )
            )
        coach.draw()
        pygame.display.flip()


def step_quadrants_together():
    set_overlay_geom(*overlay_quiz_geom(), keep_cursor=True)
    coach.set(
        6, "Meet the overlay",
        [
            "Your emotional state is reflected by the X and Y axis values taken together. "
            "So you must position the white dot inside the quadrants and not "
            "along the axes so that it fully represents your emotional state "
            "at every instant.",
        ],
        hint=""
    )
    def draw(ready):
        coach.hint = NAV_HINT if ready else ""
        screen.fill(BLACK)
        overlay.draw(highlight="quadrants")
        coach.draw()
        pygame.display.flip()

    return run_step_wait(draw, 2.0)


def _which_quadrant(v, a, dead=14):
    if abs(v) < dead or abs(a) < dead:
        return None
    if v > 0 and a > 0:
        return "pleasant_excited"
    if v > 0 and a < 0:
        return "pleasant_calm"
    if v < 0 and a > 0:
        return "unpleasant_excited"
    return "unpleasant_calm"


def _draw_quiz_frame():
    screen.fill(BLACK)
    overlay.draw()
    if coach.status:
        col = OK_GREEN if coach.status_ok else HINT_AMBER
        fb = font_title.render(coach.status, True, col)
        banner = coach_banner_rect()
        pos = fb.get_rect(
            center=(
                overlay.x + overlay.size // 2,
                overlay.y - OVERLAY_LABEL_GAP - 10 - fb.get_height() // 2
            )
        )
        if pos.top < banner.bottom + 4:
            pos.top = banner.bottom + 4
        screen.blit(fb, pos)
    coach.draw()
    pygame.display.flip()


def _quiz_pause(seconds):
    # Show the current status for a moment; only the Back button is live.
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < seconds:
        clock.tick(RENDER_RATE)
        nav = pump_nav(allow_next=False, allow_prev=True)
        if nav:
            return nav
        pygame.mouse.get_rel()
        _draw_quiz_frame()
    return None


def _quiz_quadrant(step, prompt, target, hold=0.5, wrong_hold=0.6):
    set_overlay_geom(*overlay_quiz_geom(), keep_cursor=False)
    coach.set(
        step, "Meet the overlay",
        [prompt],
        hint=PREV_HINT,
        status="",
        status_ok=False
    )
    held = 0.0
    held_wrong = 0.0
    last = time.perf_counter()
    while True:
        clock.tick(RENDER_RATE)
        now = time.perf_counter()
        dt = now - last
        last = now
        nav = pump_nav(allow_next=False, allow_prev=True)
        if nav:
            return nav
        overlay.update()
        q = _which_quadrant(*overlay.affect())
        if q == target:
            held_wrong = 0.0
            held += dt
            if held >= hold:
                coach.status = "Good job!"
                coach.status_ok = True
                _draw_quiz_frame()
                nav = _quiz_pause(1.0)
                return nav if nav else NAV_NEXT
        elif q is not None:
            held = 0.0
            held_wrong += dt
            if held_wrong >= wrong_hold:
                # Wrong: show feedback, put the dot back in the centre,
                # then let them try again.
                coach.status = "Try again"
                coach.status_ok = False
                overlay.reset()
                _draw_quiz_frame()
                nav = _quiz_pause(1.2)
                if nav:
                    return nav
                coach.status = ""
                held_wrong = 0.0
                last = time.perf_counter()
        else:
            held = 0.0
            held_wrong = 0.0
        _draw_quiz_frame()


def step_quiz_pleasant_excited():
    return _quiz_quadrant(
        7,
        "Let's say you feel pleasantly excited, where will you move the white dot?",
        "pleasant_excited"
    )


def step_quiz_pleasant_calm():
    return _quiz_quadrant(
        8,
        "Let's say you feel pleasantly calm, where will you move the white dot?",
        "pleasant_calm"
    )


def step_quiz_unpleasant_excited():
    return _quiz_quadrant(
        9,
        "Let's say you feel unpleasantly excited, where will you move the white dot?",
        "unpleasant_excited"
    )


def step_quiz_unpleasant_calm():
    return _quiz_quadrant(
        10,
        "Let's say you feel unpleasantly calm (bored), where will you move the white dot?",
        "unpleasant_calm"
    )


def step_meet_circles():
    overlay_restore()
    plan = TrialPlan("pleasant", False, t_contact=5.0)
    lx, rx = symmetric_positions(plan)
    coach.set(
        11, "The circles",
        [
            "In each trial, two coloured circles travel toward each other on a straight line.",
            "You only watch them. You cannot steer them.",
            "Sometimes they collide. Sometimes they miss and move back.",
        ]
    )
    def draw(ready):
        coach.hint = NAV_HINT if ready else ""

        def world():
            draw_circles(plan, lx, rx)

        frame(world)

    return run_step_wait(draw, 1.8)


def _positions_symmetric(plan, t):
    # Same motion as plan.positions(t), but the pair is centred on the screen.
    lx0, _rx0, phase = plan.positions(t)
    advance = lx0 - plan.left_start
    lx, rx = symmetric_positions(plan, advance)
    return lx, rx, phase


def _live_status_collision(t, phase):
    if phase == "approach":
        return "They are approaching... keep rating.", False
    if phase == "freeze":
        return "They collide... keep rating.", True
    return "They move apart again. Keep rating.", False


def _live_status_near_miss(t, phase):
    if phase == "approach":
        return "They are approaching... keep rating.", False
    if phase == "freeze":
        return "They don't collide... keep rating.", True
    return "They are moving apart. Keep reporting how you feel.", False


# Example-trial timing.
#   START_DELAY      wait this long after the start/restart press before the
#                    circles move, so the thumb can get onto the thumbstick;
#   THUMB_MSG_AT     the "thumb on your ... thumbstick!" banner appears this
#                    long after the press and stays until the trial starts;
#   IDLE_LIMIT       longest the dot may sit still before the trial freezes;
#   IDLE_GRACE       extra time after the trial starts before the stillness
#                    check begins (0.0 = checked from the first frame).
START_DELAY = 2.0
THUMB_MSG_AT = 0.5
COUNTDOWN_START = 1.5      # 5-4-3-2-1 runs from here until START_DELAY
COUNTDOWN_FROM = 5
font_countdown = pygame.font.SysFont("Arial", 84, bold=True)
IDLE_LIMIT = 0.3
IDLE_GRACE = 0.5
DONE_HINT_DELAY = 1.0
DULL_YELLOW = (196, 172, 84)


def draw_yellow_banner(specs):
    # Dull-yellow, centre-aligned message box on top of the response overlay.
    # specs: list of (font, text).
    surfs = [render_sym(f, t, (25, 25, 25)) for f, t in specs]
    pad_x, pad_y, gap = 28, 20, 12
    box_w = max(s.get_width() for s in surfs) + 2 * pad_x
    box_h = sum(s.get_height() for s in surfs) + gap * (len(surfs) - 1) + 2 * pad_y
    box = pygame.Rect(0, 0, box_w, box_h)
    box.center = (overlay.x + overlay.size // 2, overlay.y + overlay.size // 2)
    pygame.draw.rect(screen, DULL_YELLOW, box, border_radius=10)
    pygame.draw.rect(screen, (120, 100, 40), box, 3, border_radius=10)
    y = box.y + pad_y
    for s in surfs:
        screen.blit(s, s.get_rect(midtop=(box.centerx, y)))
        y += s.get_height() + gap


def draw_idle_warning():
    stick = "thumbstick" if USE_GAMEPAD else "mouse"
    press = (
        "Press the {} button to restart the example trial".format(ACTION_NAME)
        if USE_GAMEPAD else
        "Click or press Space to restart the example trial"
    )
    draw_yellow_banner([
        (font_title, "You must keep moving the {} continuously !!!".format(stick)),
        (font_body, press),
    ])


def draw_thumb_ready(t):
    # t = seconds since the start/restart press. Banner from THUMB_MSG_AT; from
    # COUNTDOWN_START the 5-4-3-2-1 countdown is added under the message,
    # spread evenly over the time left before the trial starts.
    if USE_GAMEPAD:
        text = "Thumb on your {} thumbstick!".format(
            "left" if handedness == "left" else "right"
        )
    else:
        text = "Hand on the mouse!"
    specs = [(font_title, text)]
    if t >= COUNTDOWN_START:
        step_len = (START_DELAY - COUNTDOWN_START) / float(COUNTDOWN_FROM)
        idx = int((t - COUNTDOWN_START) / step_len)
        number = max(1, COUNTDOWN_FROM - idx)
    else:
        # Reserve the line so the box does not change size when digits start.
        number = None
    specs.append((font_countdown, str(number) if number else " "))
    draw_yellow_banner(specs)


def _example_trial(step, condition, collide):
    overlay_restore()
    overlay.reset()
    plan = TrialPlan(condition, collide, t_contact=5.0)
    live_status = _live_status_collision if collide else _live_status_near_miss

    colour_name = CONDITION_COLOUR_NAME[condition]
    start_line = (
        "Press the {} button to start the example trial.".format(ACTION_NAME)
        if USE_GAMEPAD else
        "Click or press Space to start the example trial."
    )
    coach.set(
        step, "Example {}".format(step - 11),
        [
            "Since the color is {} you will hear a {} sound if the circles "
            "collide.".format(colour_name, condition),
            "Keep moving the white dot.",
            "Keep thinking about the sound you might hear if the circles "
            "collide in this trial and how that would make you feel while "
            "moving the white dot.",
            "Put your thumb on the {} thumbstick.".format(
                "left" if LEFT_HANDED else "right"
            ),
            start_line,
        ],
        hint=PREV_HINT
    )
    coach.status = ""
    coach.status_ok = False

    # waiting -> countdown -> running <-> idle(freeze) ... -> done
    state = "waiting"
    entered = time.perf_counter()
    last = entered
    trial_t = 0.0          # trial clock; stops while frozen
    run_started = None     # wall-clock time of the latest (re)start
    countdown_start = None
    last_active = entered
    done_at = None
    sound_fired = False
    lx, rx = symmetric_positions(plan)
    note = "This was an example of a {} trial where the circles {}.".format(
        condition, "collide" if collide else "come close but don't collide"
    )

    def begin_countdown(now):
        # Start/restart pressed: circles back at their start, dot centred, and
        # a short pause before anything moves.
        nonlocal state, countdown_start, lx, rx, trial_t, sound_fired
        pygame.mixer.stop()
        overlay.reset()
        pygame.mouse.get_rel()
        state = "countdown"
        countdown_start = now
        trial_t = 0.0
        sound_fired = False
        lx, rx = symmetric_positions(plan)
        coach.status = ""
        coach.hint = PREV_HINT

    prev_pos = (overlay.cx, overlay.cy)

    def begin_run(now):
        nonlocal state, run_started, last_active, prev_pos
        pygame.mouse.get_rel()
        state = "running"
        run_started = now
        last_active = now
        prev_pos = (overlay.cx, overlay.cy)

    while True:
        clock.tick(RENDER_RATE)
        now = time.perf_counter()
        dt = now - last
        last = now

        can_start = state == "waiting" and (now - entered) >= 1.0
        can_restart = state == "idle"
        can_next = state == "done" and (now - done_at) >= DONE_HINT_DELAY
        nav = pump_nav(
            allow_next=can_next, allow_prev=True,
            allow_action=(can_start or can_restart)
        )
        if nav == NAV_PREV:
            pygame.mixer.stop()
            return NAV_PREV
        if nav == NAV_NEXT and state == "done":
            return NAV_NEXT
        if nav == NAV_ACTION:
            begin_countdown(now)

        if state == "countdown":
            # Dot stays centred and circles stay put until the delay is over.
            pygame.mouse.get_rel()
            if (now - countdown_start) >= START_DELAY:
                begin_run(now)
        else:
            prev_pos = (overlay.cx, overlay.cy)
            overlay.update()

        if state == "running":
            if USE_GAMEPAD:
                moving = overlay.control_active()
            else:
                moving = (overlay.cx, overlay.cy) != prev_pos
            if moving:
                last_active = now
            if (
                (now - run_started) >= IDLE_GRACE
                and (now - last_active) > IDLE_LIMIT
            ):
                state = "idle"
                pygame.mixer.stop()
                coach.status = ""
            else:
                trial_t += dt
                if trial_t >= TRIAL_DURATION:
                    trial_t = TRIAL_DURATION
                    state = "done"
                    done_at = now
                    coach.status = ""
                    coach.hint = PREV_HINT
                lx, rx, phase = _positions_symmetric(plan, trial_t)
                if collide and (not sound_fired) and phase != "approach":
                    sound_fired = True
                    if DEMO_SOUNDS:
                        random.choice(DEMO_SOUNDS).play()
                if state == "running":
                    coach.status, coach.status_ok = live_status(trial_t, phase)

        if state == "done" and (now - done_at) >= DONE_HINT_DELAY:
            coach.hint = NAV_HINT

        screen.fill(BLACK)
        draw_circles(plan, lx, rx)
        overlay.draw()
        if state == "done":
            draw_note_box(
                note,
                (overlay.x + overlay.size + OVERLAY_LABEL_GAP + 40,
                 overlay.y + overlay.size // 2)
            )
        if state == "idle":
            draw_idle_warning()
        if state == "countdown" and (now - countdown_start) >= THUMB_MSG_AT:
            draw_thumb_ready(now - countdown_start)
        coach.draw()
        pygame.display.flip()


def step_example_pleasant_collision():
    return _example_trial(12, "pleasant", True)


def step_example_unpleasant_collision():
    return _example_trial(13, "unpleasant", True)


def step_example_pleasant_near_miss():
    return _example_trial(14, "pleasant", False)


def step_example_unpleasant_near_miss():
    return _example_trial(15, "unpleasant", False)


def step_finished():
    exit_hint = (
        "Press {} to exit".format(NEXT_NAME)
        if USE_GAMEPAD else
        "Click or press Space to exit"
    )
    coach.set(
        16, "Tutorial complete",
        [
            "You've completed the Tutorial.",
            "You may proceed to the main experiment.",
        ],
        hint=""
    )

    def draw(ready):
        coach.hint = exit_hint if ready else ""
        screen.fill(BLACK)
        coach.draw(centered=True)
        pygame.display.flip()

    return run_step_wait(draw, 1.5, False)


def main():
    steps = [
        step_welcome,
        step_two_components,
        step_stimuli_tour,
        step_response_tour,
        step_meet_grid,
        step_quadrants_together,
        step_quiz_pleasant_excited,
        step_quiz_pleasant_calm,
        step_quiz_unpleasant_excited,
        step_quiz_unpleasant_calm,
        step_meet_circles,
        step_example_pleasant_collision,
        step_example_unpleasant_collision,
        step_example_pleasant_near_miss,
        step_example_unpleasant_near_miss,
        step_finished,
    ]
    i = 0
    while i < len(steps):
        result = steps[i]()
        if result == NAV_PREV:
            i = max(0, i - 1)
        else:
            i += 1
    pygame.quit()


if __name__ == "__main__":
    main()
