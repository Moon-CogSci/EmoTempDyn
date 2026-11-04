"""Collision-anticipation affect task (pygame).

Participants watch two same-coloured circles move toward each other along a
horizontal line. On some trials the circles collide and a sound plays; on
others they stop just short and move apart. The circle colour tells the
participant whether a collision would produce a PLEASANT or an UNPLEASANT
sound. While each trial runs, the participant continuously reports how they
feel by moving a dot on a valence (left-right) by arousal (bottom-top) grid.

Session structure:
  1. Participant dialog (ID, gender, handedness).
  2. Instructions, then a practice phase (neutral sounds).
  3. Instructions, then the main phase (pleasant / unpleasant sounds).
     Each phase has a high-collision-probability block and a low one.
  4. Post-task rating: every sound is replayed once and rated for valence and
     arousal with two Affective Slider scales.

Input is a gamepad (DualSense layout) if one is connected, otherwise mouse
and keyboard. Data are written as CSV files under collision_pilot_practice/,
collision_pilot_main/ and collision_pilot_rating/. See README.md for details.

Requirements: Python 3.8+, pygame, numpy, tkinter.
Run with:  python collision_pilot.py   (Esc quits at any time)
"""

import pygame
import numpy as np
import random
import math
import time
import csv
import os
import tkinter as tk

pygame.init()
pygame.joystick.init()

# ---------------------------------------------------------
# AUDIO OUTPUT DEVICE
# ---------------------------------------------------------
# A connected DualSense registers as an audio output on Windows and often
# becomes the system default, so pygame would play sound "into" the controller
# (silent). Pick a non-controller output device instead, falling back to the
# default if none is found or the targeted device fails to open.

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

print("[collision_pilot] Audio output:", _audio_device or "default")

# =========================================================
# PARTICIPANT INFO DIALOG
# =========================================================

participant_info = {}

def submit():

    participant_info["id"] = id_entry.get().strip()
    participant_info["gender"] = gender_var.get().strip().lower()
    participant_info["handedness"] = hand_var.get().strip().lower()

    root.destroy()

root = tk.Tk()

root.title("Participant Information")
root.geometry("380x300")
root.resizable(False, False)

# ---------------------------------------------------------
# PARTICIPANT ID
# ---------------------------------------------------------

tk.Label(
    root,
    text="Participant ID:"
).pack(pady=(15, 0))

id_entry = tk.Entry(root, width=25)
id_entry.pack()

# ---------------------------------------------------------
# GENDER
# ---------------------------------------------------------

tk.Label(
    root,
    text="Gender:"
).pack(pady=(10, 0))

gender_var = tk.StringVar(value="M")

gender_menu = tk.OptionMenu(
    root,
    gender_var,
    "M",
    "F",
    "Other"
)

gender_menu.pack()

# ---------------------------------------------------------
# HANDEDNESS
# ---------------------------------------------------------

tk.Label(
    root,
    text="Handedness:"
).pack(pady=(10, 0))

hand_var = tk.StringVar(value="Right")

hand_menu = tk.OptionMenu(
    root,
    hand_var,
    "Right",
    "Left"
)

hand_menu.pack()

# ---------------------------------------------------------
# SUBMIT
# ---------------------------------------------------------

tk.Button(
    root,
    text="Start Experiment",
    command=submit,
    padx=20,
    pady=8
).pack(pady=20)

root.mainloop()

# ---------------------------------------------------------
# EXTRACT VALUES
# ---------------------------------------------------------

participant_id = participant_info.get("id", "")

gender = participant_info.get(
    "gender",
    ""
)

handedness = participant_info.get(
    "handedness",
    ""
)

# Safety check

if participant_id == "":
    raise SystemExit

# ---------------------------------------------------------
# COUNTERBALANCING
# ---------------------------------------------------------
# Two factors are counterbalanced across participants, crossed over every four
# consecutive IDs:
#   * block order   -> high-probability first vs low-probability first
#   * colour mapping-> red = pleasant / blue = unpleasant, or the reverse

digits = ''.join(
    [c for c in participant_id if c.isdigit()]
)

if len(digits) == 0:
    last_digit = 1
else:
    last_digit = int(digits[-1])

# "hf" = high-probability block first, "lf" = low-probability first.
block_order = "hf" if ((last_digit - 1) % 2) == 0 else "lf"

# "rp" = red is pleasant, "bp" = blue is pleasant.
colour_map = "rp" if ((last_digit - 1) % 4) // 2 == 0 else "bp"

# =========================================================
# WINDOW
# =========================================================

info = pygame.display.Info()

WIDTH = info.current_w
HEIGHT = info.current_h

screen = pygame.display.set_mode(
    (WIDTH, HEIGHT),
    pygame.FULLSCREEN
)

clock = pygame.time.Clock()

# =========================================================
# PARAMETERS
# =========================================================

TRIAL_DURATION = 10        # seconds of animation per trial
ITI_DURATION = 2           # fixation cross between trials
BLOCK_BREAK = 5            # minimum seconds on the between-block break screen

TRIALS_PER_BLOCK = 100

# 20 rather than 10, so that 70 % and 30 % come out as whole trials in both
# conditions (14 = 7 + 7 collisions, and 6 = 3 + 3).
PRACTICE_TRIALS_PER_BLOCK = 20

SAMPLING_RATE = 10         # affect-rating log rate (Hz)
RENDER_RATE = 60

# Collision probability per block.
P_COLLIDE = {
    "high": 0.70,
    "low": 0.30
}

# No more than this many consecutive trials of the same condition
# (pleasant / unpleasant), so the intermixed sequence never blocks up.
MAX_CONDITION_RUN = 4

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 80, 80)
GREY_RAIL = (200, 200, 200)
GREY_DIM = (110, 110, 110)

# ---------------------------------------------------------
# DISPLAY MARGIN AND CONTENT RECTANGLE
# ---------------------------------------------------------
# Coordinates follow the Cartesian convention: x is the screen WIDTH, y is the
# screen HEIGHT.
#
# A uniform blank margin is removed from all four sides FIRST, and every other
# position in the task is then laid out inside the remaining content
# rectangle:
#
#   p_x = x/32,   p_y = y/18
#   x' = x - 2 p_x = 15x/16,    y' = y - 2 p_y = 8y/9
#
# On a 1920x1080 screen p_x = p_y = 60 px, so the margin is uniform on all
# four sides and the content rectangle is 1800 x 960.

PAD_X = WIDTH / 32.0
PAD_Y = HEIGHT / 18.0

CONTENT_X0 = PAD_X
CONTENT_Y0 = PAD_Y
CONTENT_W = WIDTH - 2 * PAD_X
CONTENT_H = HEIGHT - 2 * PAD_Y

# ---------------------------------------------------------
# MOTION MODEL  (straight-line head-on approach / retreat)
# ---------------------------------------------------------
# Every trial contains exactly ONE approach event. Two same-coloured circles
# start at opposite ends of an invisible horizontal line running across the
# middle of the TOP HALF of the content rectangle, and travel toward each
# other at a constant speed (no meandering, no noise). Then either
#
#   * COLLISION trial: their edges meet, the circles freeze in contact for
#     FREEZE_DURATION while the outcome sound plays, then they retreat; or
#   * NEAR-MISS trial: they stop closing at a gap of MISS_GAP px, freeze there
#     for the same FREEZE_DURATION (no sound), then they retreat.
#
# Because the speed is fixed for the whole session, the contact TIME is set
# purely by how far apart the circles start: jittering the two starting points
# jitters both the contact time and the contact location, and the two are
# solved together when each trial is planned (see TrialPlan) so contact
# always lands inside CONTACT_TIME_WINDOW.

# Circle radius = 5% of the screen height (1080 px -> 54 px radius).
CIRCLE_RADIUS = max(20, int(round(HEIGHT * 0.05)))

# Surface-to-surface separation (px) at the closest point of a near-miss.
MISS_GAP = (90.0, 100.0)

# Freeze at contact / closest approach. Matched across collision and near-miss
# trials so the freeze itself never signals the outcome. Equals the length of
# the outcome sounds (1 s files).
FREEZE_DURATION = 1.0

# Contact (or closest-approach) time: sampled symmetrically around
# CONTACT_TIME_TARGET so the median is exactly the target.
CONTACT_TIME_TARGET = 5.0
CONTACT_TIME_WINDOW = (3.0, 7.0)

# Width of the starting-point jitter band at each end of the line, as a
# multiple of the default band width (2x' - y') / 8. The band width limits the
# spread of contact times: at 1.0 a 1920x1080 screen with the current circle
# size reaches about 3.85-6.15 s, and a larger value is needed to reach the
# full CONTACT_TIME_WINDOW. The realised window is printed at startup by the
# CONTACT TIMING CALIBRATION block below.
BAND_WIDTH_SCALE = 1.0

# "same_speed" -> retreat at the approach speed; a late contact means the trial
#                 ends while the circles are still on their way back.
# "fit_trial"  -> retreat is stretched/compressed so the circles always reach
#                 their starting points exactly at trial end (retreat speed
#                 then varies across trials).
RETREAT_MODE = "same_speed"

# ---------------------------------------------------------
# GEOMETRY  (laid out inside the content rectangle)
# ---------------------------------------------------------
# All of the following is measured from the content rectangle, never from the
# screen edge, so the uniform margin above is preserved on all four sides:
#
#   affect overlay: y'/2 by y'/2, filling the middle of the LOWER half of the
#     content rectangle, which leaves (2x' - y')/4 of blank content on each
#     side and puts its bottom edge p_y above the bottom of the screen;
#   motion line: centred in the free space above the overlay's top label
#     (about y'/4 below the top of the content rectangle, raised slightly
#     because the circles are large);
#   jitter bands: (2x' - y')/8 wide at each end of the line.

OVERLAY_SIZE = int(CONTENT_H // 2)
OVERLAY_X = int(round(CONTENT_X0 + (CONTENT_W - OVERLAY_SIZE) / 2.0))
OVERLAY_Y = int(round(CONTENT_Y0 + CONTENT_H - OVERLAY_SIZE))

# The motion line is centred in the free band between the top of the content
# rectangle and the "Excited" label above the overlay (label centre sits
# PAD_Y/2 above the overlay, ~14 px half-height), so the large circles keep
# equal clearance above and below and never touch the overlay's labels.
_OVERLAY_LABEL_TOP = OVERLAY_Y - int(round(PAD_Y / 2.0)) - 14
MOTION_Y = int(round(0.5 * (CONTENT_Y0 + _OVERLAY_LABEL_TOP)))

BAND_WIDTH = BAND_WIDTH_SCALE * (2 * CONTENT_W - CONTENT_H) / 8.0

# Circle-centre ranges for the left and right starting points. The circles are
# inset by their own radius, so no circle ever crosses into the margin.
LEFT_BAND = (
    CONTENT_X0 + CIRCLE_RADIUS,
    CONTENT_X0 + CIRCLE_RADIUS + BAND_WIDTH
)

RIGHT_BAND = (
    CONTENT_X0 + CONTENT_W - CIRCLE_RADIUS - BAND_WIDTH,
    CONTENT_X0 + CONTENT_W - CIRCLE_RADIUS
)

if BAND_WIDTH < 40 or RIGHT_BAND[0] <= LEFT_BAND[1]:
    pygame.quit()
    raise SystemExit(
        "[collision_pilot] Screen too narrow for this layout "
        "(band width = {:.0f} px). Use a wider display or lower "
        "BAND_WIDTH_SCALE.".format(BAND_WIDTH)
    )

# ---------------------------------------------------------
# CONTACT TIMING CALIBRATION  (done once, from the screen size)
# ---------------------------------------------------------
# Centre separation shrinks at 2 * SPEED. Contact / closest approach happens
# when the separation reaches (2 * radius + gap), so
#
#       t_contact = (D_start - 2 * radius - gap) / (2 * SPEED)
#
# SPEED is chosen so that the MIDDLE of both jitter bands gives
# t_contact = CONTACT_TIME_TARGET.

_L_MID = 0.5 * (LEFT_BAND[0] + LEFT_BAND[1])
_R_MID = 0.5 * (RIGHT_BAND[0] + RIGHT_BAND[1])

_D_MID = _R_MID - _L_MID
_GAP_REF = 0.5 * (0.0 + 0.5 * (MISS_GAP[0] + MISS_GAP[1]))

SPEED = (_D_MID - 2 * CIRCLE_RADIUS - _GAP_REF) / (2.0 * CONTACT_TIME_TARGET)

# Extreme start separations the bands allow.
_D_MIN = RIGHT_BAND[0] - LEFT_BAND[1]
_D_MAX = RIGHT_BAND[1] - LEFT_BAND[0]

def contact_time(d_start, gap):

    return (d_start - 2 * CIRCLE_RADIUS - gap) / (2.0 * SPEED)

def start_separation(t_contact, gap):

    return 2 * CIRCLE_RADIUS + gap + 2.0 * SPEED * t_contact

# The reachable window is the intersection over every gap value used, so
# collision and near-miss trials share one identical timing distribution.
_T_REACHABLE_LO = contact_time(_D_MIN, 0.0)
_T_REACHABLE_HI = contact_time(_D_MAX, MISS_GAP[1])

_T_HALF = min(
    CONTACT_TIME_TARGET - max(CONTACT_TIME_WINDOW[0], _T_REACHABLE_LO),
    min(CONTACT_TIME_WINDOW[1], _T_REACHABLE_HI) - CONTACT_TIME_TARGET
)

CONTACT_TIME_LO = CONTACT_TIME_TARGET - _T_HALF
CONTACT_TIME_HI = CONTACT_TIME_TARGET + _T_HALF

print(
    "[collision_pilot] Screen {}x{} | margin {:.0f}x{:.0f} px | "
    "content {:.0f}x{:.0f} px | radius {} px | "
    "speed {:.1f} px/s per circle | "
    "start bands {:.0f}-{:.0f} and {:.0f}-{:.0f} px | "
    "contact time {:.2f}-{:.2f} s (median {:.1f})".format(
        WIDTH, HEIGHT, PAD_X, PAD_Y, CONTENT_W, CONTENT_H, CIRCLE_RADIUS,
        SPEED,
        LEFT_BAND[0], LEFT_BAND[1], RIGHT_BAND[0], RIGHT_BAND[1],
        CONTACT_TIME_LO, CONTACT_TIME_HI, CONTACT_TIME_TARGET
    )
)

# =========================================================
# CONDITIONS AND COLOURS
# =========================================================
# Circle colour is the cue: one colour means "a collision on this trial plays a
# PLEASANT sound", the other means "UNPLEASANT". The mapping is counterbalanced
# across participants.

CIRCLE_RED = (225, 65, 65)
CIRCLE_BLUE = (65, 105, 225)

if colour_map == "rp":
    CONDITION_COLOUR = {"pleasant": CIRCLE_RED, "unpleasant": CIRCLE_BLUE}
    CONDITION_COLOUR_NAME = {"pleasant": "red", "unpleasant": "blue"}
else:
    CONDITION_COLOUR = {"pleasant": CIRCLE_BLUE, "unpleasant": CIRCLE_RED}
    CONDITION_COLOUR_NAME = {"pleasant": "blue", "unpleasant": "red"}

# =========================================================
# BLOCKS
# =========================================================

ORDERS = {

    "hf": [
        "collide_high",
        "collide_low"
    ],

    "lf": [
        "collide_low",
        "collide_high"
    ]
}

BLOCK_ORDER = ORDERS[block_order]

BLOCKS = {

    "collide_high": {
        "p_collide": P_COLLIDE["high"]
    },

    "collide_low": {
        "p_collide": P_COLLIDE["low"]
    }
}

BLOCK_LABELS = {
    "collide_high": "High Probability Block",
    "collide_low": "Low Probability Block",
}

# =========================================================
# OUTPUT FOLDERS
# =========================================================
# Each phase writes its CSV into its own folder inside the project directory.

MAIN_DIR = "collision_pilot_main"
PRACTICE_DIR = "collision_pilot_practice"
RATING_DIR = "collision_pilot_rating"

for _d in (MAIN_DIR, PRACTICE_DIR, RATING_DIR):
    os.makedirs(_d, exist_ok=True)

# =========================================================
# SOUNDS
# =========================================================
# Three flat folders under assets/collision_sounds:
#
#   assets/collision_sounds/pleasant/    main-phase pleasant collisions
#   assets/collision_sounds/unpleasant/  main-phase unpleasant collisions
#   assets/collision_sounds/neutral/     practice collisions (no emotional quality)
#
# Main phase: 50 pleasant and 50 unpleasant collisions. Each of the 10 files
# in a folder is scheduled exactly five times, order shuffled.
#
# Practice: all 10 neutral files are used. A random 6–8 of them are assigned
# to the high-probability block and the rest (2–4) to the low-probability
# block. Each file is then repeated as evenly as needed to cover that block's
# collisions (14 and 6 with 20 trials/block, so a 7/3 split plays each file
# twice). Colour still marks the trial's condition; it does not pick the
# practice sound.

ASSET_DIR = os.path.join("assets", "collision_sounds")

PLEASANT_DIR = os.path.join(ASSET_DIR, "pleasant")
UNPLEASANT_DIR = os.path.join(ASSET_DIR, "unpleasant")
NEUTRAL_DIR = os.path.join(ASSET_DIR, "neutral")

CONDITIONS = ("pleasant", "unpleasant")

def load_folder(folder):

    os.makedirs(folder, exist_ok=True)

    files = sorted(
        f for f in os.listdir(folder)
        if f.lower().endswith((".wav", ".ogg", ".mp3"))
    )

    pairs = []

    for f in files:
        snd = pygame.mixer.Sound(os.path.join(folder, f))
        if snd.get_length() > FREEZE_DURATION + 0.05:
            print(
                "[collision_pilot] WARNING: {} is {:.2f} s, longer than "
                "the {:.2f} s freeze.".format(
                    f, snd.get_length(), FREEZE_DURATION
                )
            )
        pairs.append((f, snd))

    if not pairs:
        print("[collision_pilot] NO SOUNDS in", folder)
    else:
        print(
            "[collision_pilot] Loaded {} sound(s) from {}".format(
                len(pairs), folder
            )
        )

    return pairs

def even_play_queue(pairs, n_plays):

    # n_plays tokens, as even as possible across the files, then shuffled.
    if not pairs or n_plays <= 0:
        return []

    items = list(pairs)
    random.shuffle(items)
    base, extra = divmod(n_plays, len(items))
    bag = []
    for i, item in enumerate(items):
        bag.extend([item] * (base + (1 if i < extra else 0)))
    random.shuffle(bag)
    return bag

def make_queue_picker(queues, key_from_block_and_condition):

    def next_sound(block_name, condition):
        key = key_from_block_and_condition(block_name, condition)
        q = queues.get(key, [])
        if not q:
            return None, None
        return q.pop()

    return next_sound

pleasant_pool = load_folder(PLEASANT_DIR)
unpleasant_pool = load_folder(UNPLEASANT_DIR)
neutral_pool = load_folder(NEUTRAL_DIR)

# Main: 50 collisions per valence (35 high-p + 15 low-p), 10 files x 5 plays.
_MAIN_N_COL = {
    "pleasant": 0,
    "unpleasant": 0
}
for _bn in BLOCK_ORDER:
    _n_col = int(round(BLOCKS[_bn]["p_collide"] * TRIALS_PER_BLOCK))
    _MAIN_N_COL["pleasant"] += _n_col // 2
    _MAIN_N_COL["unpleasant"] += _n_col // 2

MAIN_NEXT_SOUND = make_queue_picker(
    {
        "pleasant": even_play_queue(pleasant_pool, _MAIN_N_COL["pleasant"]),
        "unpleasant": even_play_queue(unpleasant_pool, _MAIN_N_COL["unpleasant"]),
    },
    lambda block_name, condition: condition
)

# Practice: split the 10 neutral files between the two probability blocks.
_neutral = list(neutral_pool)
random.shuffle(_neutral)

if len(_neutral) <= 1:
    _n_high = len(_neutral)
else:
    _n_high = random.randint(6, 8)
    _n_high = max(1, min(_n_high, len(_neutral) - 1))

_high_files = _neutral[:_n_high]
_low_files = _neutral[_n_high:]

_PRAC_N_COL = {
    "collide_high": int(round(P_COLLIDE["high"] * PRACTICE_TRIALS_PER_BLOCK)),
    "collide_low": int(round(P_COLLIDE["low"] * PRACTICE_TRIALS_PER_BLOCK))
}

print(
    "[collision_pilot] Practice neutral split: {} high-p file(s), "
    "{} low-p file(s)".format(len(_high_files), len(_low_files))
)

PRACTICE_NEXT_SOUND = make_queue_picker(
    {
        "collide_high": even_play_queue(_high_files, _PRAC_N_COL["collide_high"]),
        "collide_low": even_play_queue(_low_files, _PRAC_N_COL["collide_low"]),
    },
    lambda block_name, condition: block_name
)

# =========================================================
# INPUT
# =========================================================

USE_GAMEPAD = False

# Stick axis indices for the PS5 DualSense (CFI-ZCT1W) under this SDL/pygame
# build: left stick = axes (0, 1), right stick = axes (2, 3).
LEFT_STICK_AXES = (0, 1)
RIGHT_STICK_AXES = (2, 3)

# Right-handers respond with the right stick; left-handers with the left stick.
STICK_AXES = LEFT_STICK_AXES if handedness == "left" else RIGHT_STICK_AXES

if pygame.joystick.get_count() > 0:

    joystick = pygame.joystick.Joystick(0)
    joystick.init()

    USE_GAMEPAD = True

    # Safety fallback for a controller without the right-stick axes.
    if max(STICK_AXES) >= joystick.get_numaxes():
        STICK_AXES = LEFT_STICK_AXES

# With a gamepad connected the mouse is never used, so hide the cursor for the
# whole session. Mouse participants keep a visible cursor.
pygame.mouse.set_visible(not USE_GAMEPAD)

# =========================================================
# OVERLAY
# =========================================================
# Continuous affect report: a dot the participant keeps moving inside a square
# grid. Valence on the horizontal axis, arousal on the vertical axis.
#
# The box fills the middle of the lower half of the content rectangle. The
# uniform margin leaves a blank strip (height PAD_Y) below it and a
# wide blank column on either side, so all four axis words sit OUTSIDE the
# box, centred in the margin / padding around it. They are deliberately
# neutral grey: red / blue text would compete with the colour cue carried by
# the circles.

AROUSAL_HIGH_LABEL = "Excited"
AROUSAL_LOW_LABEL = "Calm"
VALENCE_LOW_LABEL = "Unpleasant"
VALENCE_HIGH_LABEL = "Pleasant"

# Distance from a box edge to the centre of the label outside it. Half the
# vertical margin centres the bottom label in the blank strip below the box.
OVERLAY_LABEL_GAP = int(round(PAD_Y / 2.0))
OVERLAY_LABEL_ALPHA = 105       # 0-255; low so the words stay faint
OVERLAY_LABEL_COLOUR = (215, 215, 215)

# White cursor (never red / blue, to keep it distinct from the circles).
CURSOR_COLOUR = WHITE
CURSOR_RADIUS = 8

_overlay_label_font = pygame.font.SysFont("Arial", 24, bold=True)

def _overlay_label(text, rotate=0):

    surf = _overlay_label_font.render(
        text, True, OVERLAY_LABEL_COLOUR
    ).convert_alpha()

    # Multiply the per-pixel alpha down so the antialiased text is translucent.
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


class Overlay:

    def __init__(self):

        self.size = OVERLAY_SIZE

        self.x = OVERLAY_X
        self.y = OVERLAY_Y

        self.cx = self.x + self.size / 2
        self.cy = self.y + self.size / 2

        self.path = []

    def update(self):

        if USE_GAMEPAD:

            # ---------------------------------------------
            # GAMEPAD RELATIVE CONTROL
            # ---------------------------------------------

            rx = joystick.get_axis(STICK_AXES[0])
            ry = joystick.get_axis(STICK_AXES[1])

            # deadzone
            if abs(rx) < 0.08:
                rx = 0

            if abs(ry) < 0.08:
                ry = 0

            # Full stick deflection moves the dot at exactly the speed of one
            # moving circle (SPEED px/s); partial deflection is proportionally
            # slower. The deflection vector is capped at length 1 so diagonals
            # are no faster than straight pushes.
            mag = (rx * rx + ry * ry) ** 0.5

            if mag > 1.0:
                rx /= mag
                ry /= mag

            gain = SPEED / RENDER_RATE

            self.cx += rx * gain
            self.cy += ry * gain

        else:

            # ---------------------------------------------
            # RELATIVE MOUSE TRACKING
            # ---------------------------------------------

            if pygame.mouse.get_pressed()[0]:

                rel_x, rel_y = pygame.mouse.get_rel()

                self.cx += rel_x
                self.cy += rel_y

            else:

                pygame.mouse.get_rel()

        # -------------------------------------------------
        # BOUNDS (virtual window -- applies to both devices)
        # -------------------------------------------------

        self.cx = np.clip(
            self.cx,
            self.x,
            self.x + self.size
        )

        self.cy = np.clip(
            self.cy,
            self.y,
            self.y + self.size
        )

        # -------------------------------------------------
        # STORE TRAJECTORY (both devices)
        # -------------------------------------------------

        self.path.append(
            (int(self.cx), int(self.cy))
        )

    def affect(self):

        # Map the cursor position in the box to valence / arousal, each in
        # [-50, 50]. Valence: left negative -> right positive.
        # Arousal: bottom low -> top high (screen y grows downward).
        half = self.size / 2

        cx0 = self.x + half
        cy0 = self.y + half

        valence = (self.cx - cx0) / half * 50
        arousal = (cy0 - self.cy) / half * 50

        return valence, arousal

    def draw(self):

        surf = pygame.Surface(
            (self.size, self.size),
            pygame.SRCALPHA
        )

        surf.fill((0, 0, 0, 120))

        pygame.draw.rect(
            surf,
            (255, 255, 255),
            (0, 0, self.size, self.size),
            2
        )

        pygame.draw.line(
            surf,
            (180, 180, 180),
            (self.size // 2, 0),
            (self.size // 2, self.size),
            2
        )

        pygame.draw.line(
            surf,
            (180, 180, 180),
            (0, self.size // 2),
            (self.size, self.size // 2),
            2
        )

        screen.blit(surf, (self.x, self.y))

        # Axis labels, centred just outside each edge of the box.
        cx = self.x + self.size // 2
        cy = self.y + self.size // 2

        gap = OVERLAY_LABEL_GAP

        screen.blit(
            _LBL_AROUSAL_HIGH,
            _LBL_AROUSAL_HIGH.get_rect(
                center=(cx, self.y - gap)
            )
        )
        screen.blit(
            _LBL_AROUSAL_LOW,
            _LBL_AROUSAL_LOW.get_rect(
                center=(cx, self.y + self.size + gap)
            )
        )
        screen.blit(
            _LBL_VALENCE_LOW,
            _LBL_VALENCE_LOW.get_rect(
                center=(self.x - gap, cy)
            )
        )
        screen.blit(
            _LBL_VALENCE_HIGH,
            _LBL_VALENCE_HIGH.get_rect(
                center=(self.x + self.size + gap, cy)
            )
        )

        pygame.draw.circle(
            screen,
            CURSOR_COLOUR,
            (int(self.cx), int(self.cy)),
            CURSOR_RADIUS
        )

        pygame.draw.circle(
            screen,
            BLACK,
            (int(self.cx), int(self.cy)),
            CURSOR_RADIUS,
            2
        )

# =========================================================
# TRIAL PLANNING
# =========================================================
# One approach event per trial, fully determined before the trial starts:
# where the circles start, when contact / closest approach happens, and where
# on the line it happens.

class TrialPlan:

    def __init__(self, condition, should_collide):

        self.condition = condition
        self.should_collide = should_collide

        self.gap = 0.0 if should_collide else random.uniform(*MISS_GAP)

        # Contact time: symmetric triangular around the target, so the median
        # is CONTACT_TIME_TARGET and the tails stay inside the reachable window.
        t_contact = random.triangular(
            CONTACT_TIME_LO,
            CONTACT_TIME_HI,
            CONTACT_TIME_TARGET
        )

        d_start = start_separation(t_contact, self.gap)

        # Keep the pair inside both jitter bands; re-derive the time if the
        # separation had to be clipped (only possible at the extreme tails).
        d_start = min(max(d_start, _D_MIN), _D_MAX)

        self.t_contact = contact_time(d_start, self.gap)

        # Starting points: any left position whose partner also lands inside
        # the right band. This jitters WHERE contact happens along the line,
        # independently of WHEN it happens.
        lo_x = max(LEFT_BAND[0], RIGHT_BAND[0] - d_start)
        hi_x = min(LEFT_BAND[1], RIGHT_BAND[1] - d_start)

        self.left_start = random.uniform(lo_x, max(lo_x, hi_x))
        self.right_start = self.left_start + d_start

        # Distance each circle covers before the freeze, and the midpoint of
        # the encounter (contact point / point of closest approach).
        self.travel = SPEED * self.t_contact
        self.contact_x = 0.5 * (self.left_start + self.right_start)

        self.freeze_end = self.t_contact + FREEZE_DURATION

        if RETREAT_MODE == "fit_trial":
            remaining = max(0.1, TRIAL_DURATION - self.freeze_end)
            self.retreat_speed = self.travel / remaining
        else:
            self.retreat_speed = SPEED

    def positions(self, t):

        # Returns (left_x, right_x, motion_phase) for motion time t.

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

def schedule_block(n_trials, p_collide):

    # Builds the trial list for one block: conditions intermixed (half
    # pleasant, half unpleasant) with the collision probability applied
    # WITHIN each condition, so the colour cue carries no information about
    # collision likelihood.

    n_pleasant = n_trials // 2

    if n_trials % 2:
        n_pleasant += random.choice((0, 1))

    per_condition = {
        "pleasant": n_pleasant,
        "unpleasant": n_trials - n_pleasant
    }

    n_collisions = int(round(p_collide * n_trials))

    base = n_collisions // 2
    extra = n_collisions - 2 * base

    collisions = {"pleasant": base, "unpleasant": base}

    if extra:
        collisions[random.choice(CONDITIONS)] += extra

    trials = []

    for cond in CONDITIONS:

        n_col = min(collisions[cond], per_condition[cond])

        trials += [
            (cond, True)
        ] * n_col

        trials += [
            (cond, False)
        ] * (per_condition[cond] - n_col)

    # Shuffle, rejecting sequences with a long run of one condition.
    for _ in range(500):

        random.shuffle(trials)

        run = 1
        longest = 1

        for i in range(1, len(trials)):

            if trials[i][0] == trials[i - 1][0]:
                run += 1
                longest = max(longest, run)
            else:
                run = 1

        if longest <= MAX_CONDITION_RUN:
            break

    return trials

# =========================================================
# DRAWING
# =========================================================

def draw_circles(plan, left_x, right_x):

    # Flat, solid-filled circles (no outline).
    colour = CONDITION_COLOUR[plan.condition]

    for x in (left_x, right_x):

        pygame.draw.circle(
            screen,
            colour,
            (int(round(x)), MOTION_Y),
            CIRCLE_RADIUS
        )

font = pygame.font.SysFont("Arial", 32)

def message(text, duration):

    start = time.perf_counter()

    while time.perf_counter() - start < duration:

        for event in pygame.event.get():

            if event.type == pygame.QUIT:
                pygame.quit()
                raise SystemExit

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    raise SystemExit

        screen.fill(BLACK)

        surf = font.render(
            text,
            True,
            WHITE
        )

        rect = surf.get_rect(
            center=(WIDTH // 2, HEIGHT // 2)
        )

        screen.blit(surf, rect)

        pygame.display.flip()


# Fixation cross: a vector "+" whose width and height equal the diameter of
# the stimulus circles, drawn at the centre of the screen.
FIXATION_SIZE = 2 * CIRCLE_RADIUS
FIXATION_THICKNESS = max(4, int(round(FIXATION_SIZE / 14.0)))


def fixation(duration):

    start = time.perf_counter()

    while time.perf_counter() - start < duration:

        for event in pygame.event.get():

            if event.type == pygame.QUIT:
                pygame.quit()
                raise SystemExit

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    raise SystemExit

        screen.fill(BLACK)

        cx = WIDTH // 2
        cy = HEIGHT // 2
        half = FIXATION_SIZE // 2

        pygame.draw.line(
            screen, WHITE,
            (cx - half, cy), (cx + half, cy),
            FIXATION_THICKNESS
        )

        pygame.draw.line(
            screen, WHITE,
            (cx, cy - half), (cx, cy + half),
            FIXATION_THICKNESS
        )

        pygame.display.flip()

# =========================================================
# AFFECTIVE SLIDER (POST-TASK SOUND RATING)
# =========================================================
# After the main task, each sound is replayed once and the participant rates
# how it made them feel on two Affective Slider scales: arousal and pleasure
# (valence). Each slider returns a value in [0, 1] snapped to two decimals
# (101 possible ratings). The vertical order of the two sliders is randomised
# per sound, as is the order in which the sounds are presented.

font_title = pygame.font.SysFont("Arial", 40)
font_instr = pygame.font.SysFont("Arial", 26)
font_label = pygame.font.SysFont("Arial", 24)
font_small = pygame.font.SysFont("Arial", 20)

RATING_TRACK_W = int(WIDTH * 0.5)
RATING_MAXH = 55
RATING_HANDLE_R = 15
FACE_R = 34

# ---------------------------------------------------------
# RATING GAMEPAD MAPPING
# ---------------------------------------------------------
# The rating uses the horizontal axis of the handedness-appropriate stick.
# On the DualSense (SDL2 mapping): left stick X = axis 0, right stick X = axis 2.
RATING_STICK_X = 0 if handedness == "left" else 2

BTN_CONFIRM = 0     # Cross (X)   -> confirm / continue
BTN_REPLAY = 2      # Square      -> replay the current sound
DPAD_UP_BTN = 11    # D-pad Up    -> select top slider
DPAD_DOWN_BTN = 12  # D-pad Down  -> select bottom slider
DPAD_LEFT_BTN = 13  # D-pad Left  -> fine decrease
DPAD_RIGHT_BTN = 14 # D-pad Right -> fine increase

DEADZONE = 0.08
RATING_SPEED = 0.6      # value units / second at full stick deflection
FINE_STEP = 0.01        # D-pad left/right increment (fine adjustment)
STEP_COOLDOWN = 0.12    # seconds between repeated fine steps when held


def quit_all(rfile=None):

    if rfile is not None:
        rfile.close()

    pygame.quit()
    raise SystemExit


def clamp01(v):
    return min(max(v, 0.0), 1.0)


def draw_face(cx, cy, r, kind):

    pygame.draw.circle(screen, WHITE, (cx, cy), r, 3)

    ex = r // 3
    ey = cy - r // 5
    er = max(2, r // 10)

    if kind == "excited":
        pygame.draw.circle(screen, WHITE, (cx - ex, ey), r // 5, 2)
        pygame.draw.circle(screen, WHITE, (cx + ex, ey), r // 5, 2)
    else:
        pygame.draw.circle(screen, WHITE, (cx - ex, ey), er)
        pygame.draw.circle(screen, WHITE, (cx + ex, ey), er)

    mrect = pygame.Rect(0, 0, r, r // 2)

    if kind == "happy":
        mrect.center = (cx, cy + r // 4)
        pygame.draw.arc(screen, WHITE, mrect, math.pi, 2 * math.pi, 3)
    elif kind == "sad":
        mrect.center = (cx, cy + r // 2)
        pygame.draw.arc(screen, WHITE, mrect, 0, math.pi, 3)
    elif kind == "excited":
        pygame.draw.circle(screen, WHITE, (cx, cy + r // 3), r // 7, 2)
    else:  # calm
        pygame.draw.line(
            screen, WHITE,
            (cx - r // 4, cy + r // 3),
            (cx + r // 4, cy + r // 3),
            3
        )


def draw_slider(scale, x0, x1, cy, value, touched, active=False):

    label = "Level of arousal" if scale == "arousal" else "Level of pleasure"

    xc = (x0 + x1) // 2

    # Rail.
    rail = pygame.Rect(x0, cy - 5, x1 - x0, 10)
    pygame.draw.rect(screen, GREY_RAIL, rail, border_radius=5)

    # Label above the scale (highlighted when this slider is the active one).
    lbl = font_label.render(label, True, RED if active else WHITE)
    screen.blit(lbl, lbl.get_rect(center=(xc, cy - RATING_MAXH - 28)))

    # End faces.
    left_kind = "calm" if scale == "arousal" else "sad"
    right_kind = "excited" if scale == "arousal" else "happy"
    draw_face(x0 - 70, cy, FACE_R, left_kind)
    draw_face(x1 + 70, cy, FACE_R, right_kind)

    # Word under each face.
    left_word = "Calm" if scale == "arousal" else "Unpleasant"
    right_word = "Excited" if scale == "arousal" else "Pleasant"
    word_y = cy + FACE_R + 16
    lw = font_small.render(left_word, True, WHITE)
    screen.blit(lw, lw.get_rect(center=(x0 - 70, word_y)))
    rw = font_small.render(right_word, True, WHITE)
    screen.blit(rw, rw.get_rect(center=(x1 + 70, word_y)))

    # Handle (red, thicker outline when active).
    hx = int(x0 + value * (x1 - x0))
    pygame.draw.circle(screen, WHITE, (hx, cy), RATING_HANDLE_R)
    pygame.draw.circle(
        screen,
        RED if active else GREY_DIM,
        (hx, cy),
        RATING_HANDLE_R,
        4 if active else 2
    )

    # Current value once the participant has touched this slider.
    if touched:
        vt = font_small.render("{:.2f}".format(round(value, 2)), True, WHITE)
        screen.blit(vt, vt.get_rect(center=(hx, cy + RATING_MAXH + 20)))


# =========================================================
# INSTRUCTION SCREENS (banner style, matching the companion tutorial script)
# =========================================================
# Every instruction screen is a dark rounded banner with a progress line, a
# title, wrapped body text and a navigation hint at the bottom right.
#
# Buttons (gamepad):
#   right-handed:  X = next screen,        Triangle = previous screen
#   left-handed:   D-pad Down = next,      D-pad Up = previous
# Keyboard/mouse:  Space / Enter / click = next,  Backspace = previous.
# (The rating phase itself keeps its own controls, see run_rating_phase.)

COACH_BG = (18, 22, 32)
COACH_EDGE = (90, 140, 210)

LEFT_HANDED = handedness == "left"
NAV_BTN_NEXT = DPAD_DOWN_BTN if LEFT_HANDED else 0     # D-pad Down / Cross (X)
NAV_BTN_BACK = DPAD_UP_BTN if LEFT_HANDED else 3       # D-pad Up   / Triangle

NAV_NEXT = "next"
NAV_PREV = "prev"

# The triangle is drawn as a vector shape (Arial has no glyph for it);
# TRIANGLE is only a placeholder character inside hint strings.
TRIANGLE = "\u25B3"
NEXT_NAME = "D-pad Down" if LEFT_HANDED else "X"
BACK_NAME = "D-pad Up" if LEFT_HANDED else TRIANGLE

bn_font_title = pygame.font.SysFont("Arial", 34, bold=True)
bn_font_body = pygame.font.SysFont("Arial", 24)
bn_font_hint = pygame.font.SysFont("Arial", 22)
bn_font_small = pygame.font.SysFont("Arial", 20)

_BN_PAD_X = 22
_BN_LINE_H = 28
_BN_SPACER_H = 14


def _sym_width(font):
    return int(font.get_height() * 0.85)


def _split_syms(text):
    out, cur = [], ""
    for ch in text:
        if ch == TRIANGLE:
            out.append(("t", cur))
            out.append(("s", ch))
            cur = ""
        else:
            cur += ch
    out.append(("t", cur))
    return [(k, v) for k, v in out if not (k == "t" and v == "")]


def sym_text_width(font, text):
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
            pts = [
                (x + sw // 2, int(h * 0.20)),
                (x + pad, int(h * 0.78)),
                (x + sw - pad, int(h * 0.78)),
            ]
            pygame.draw.polygon(out, colour, pts, 2)
            x += sw
    return out


def nav_hint(next_label="go to the next screen", allow_prev=False):
    if USE_GAMEPAD:
        nxt = "Press {} to {}".format(NEXT_NAME, next_label)
        prv = "Press {} to go to the previous screen".format(BACK_NAME)
    else:
        nxt = "Click or press Space to {}".format(next_label)
        prv = "Press Backspace to go to the previous screen"
    return nxt + ("  |  " + prv if allow_prev else "")


def _banner_layout(progress, title, lines, hint, centered):
    inner_w = int(CONTENT_W) - 2 * _BN_PAD_X
    rows = []                       # wrapped text, or None for a spacer
    for line in lines:
        if line == "":
            rows.append(None)
        else:
            rows.extend(wrap_sym(bn_font_body, line, inner_w))
    top = 12 + bn_font_small.get_height() + 8 + bn_font_title.get_height() + 12
    body_h = sum(_BN_LINE_H if r else _BN_SPACER_H for r in rows)
    hint_lines = wrap_sym(bn_font_hint, hint, inner_w) if hint else []
    hint_h = (22 * len(hint_lines) + 16) if hint_lines else 24
    rect = pygame.Rect(
        int(PAD_X), int(PAD_Y * 0.4), int(CONTENT_W), int(top + body_h + hint_h)
    )
    if centered:
        rect.center = (WIDTH // 2, HEIGHT // 2)
    return rect, rows, top, hint_lines


def draw_banner(progress, title, lines, hint, show_hint, centered=True):
    # `hint` is always used for the layout so the box never changes size;
    # it is only drawn once show_hint is True. Returns the banner rect.
    rect, rows, body_y, hint_lines = _banner_layout(
        progress, title, lines, hint, centered
    )
    pygame.draw.rect(screen, COACH_BG, rect, border_radius=10)
    pygame.draw.rect(screen, COACH_EDGE, rect, 2, border_radius=10)

    if progress:
        p = bn_font_small.render(progress, True, COACH_EDGE)
        screen.blit(p, (rect.x + _BN_PAD_X, rect.y + 12))

    t = bn_font_title.render(title, True, WHITE)
    screen.blit(
        t, (rect.x + _BN_PAD_X, rect.y + 12 + bn_font_small.get_height() + 8)
    )

    y = rect.y + body_y
    for r in rows:
        if r is None:
            y += _BN_SPACER_H
            continue
        s = render_sym(bn_font_body, r, GREY_RAIL)
        screen.blit(s, (rect.x + _BN_PAD_X, y))
        y += _BN_LINE_H

    if show_hint and hint_lines:
        hy = rect.bottom - 16 - 22 * (len(hint_lines) - 1)
        for line in hint_lines:
            h = render_sym(bn_font_hint, line, WHITE)
            screen.blit(h, h.get_rect(midright=(rect.right - _BN_PAD_X, hy)))
            hy += 22
    return rect


def _poll_nav(ready, allow_prev):
    # Returns NAV_NEXT / NAV_PREV / None. Next needs `ready` (minimum reading
    # time elapsed); previous is available immediately when allowed.
    result = None
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            quit_all()
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                quit_all()
            if ready and event.key in (pygame.K_SPACE, pygame.K_RETURN):
                result = NAV_NEXT
            if allow_prev and event.key == pygame.K_BACKSPACE:
                result = NAV_PREV
        if event.type == pygame.MOUSEBUTTONDOWN and not USE_GAMEPAD:
            if ready:
                result = NAV_NEXT
        if USE_GAMEPAD and event.type == pygame.JOYBUTTONDOWN:
            if ready and event.button == NAV_BTN_NEXT:
                result = NAV_NEXT
            elif allow_prev and event.button == NAV_BTN_BACK:
                result = NAV_PREV
        if USE_GAMEPAD and LEFT_HANDED and event.type == pygame.JOYHATMOTION:
            # Some drivers report the D-pad as a hat instead of buttons.
            hx, hy = event.value
            if hy == -1 and ready:
                result = NAV_NEXT
            elif hy == 1 and allow_prev:
                result = NAV_PREV
    return result


def instruction_screen(title, lines, min_visible=3.0, progress="",
                       next_label="go to the next screen", allow_prev=False,
                       centered=True, extra_draw=None):

    # Generic instruction screen, reused for every phase. The next-screen hint
    # is hidden (and next is disabled) until `min_visible` seconds have passed.
    # `extra_draw(banner_rect)` can add graphics below the banner.
    # Returns NAV_NEXT or NAV_PREV.

    start = time.perf_counter()
    hint = nav_hint(next_label, allow_prev)

    while True:

        clock.tick(RENDER_RATE)

        ready = (time.perf_counter() - start) >= min_visible

        nav = _poll_nav(ready, allow_prev)
        if nav:
            return nav

        screen.fill(BLACK)

        rect = draw_banner(
            progress, title, lines, hint, ready, centered=centered
        )

        if extra_draw is not None:
            extra_draw(rect)

        pygame.display.flip()


def _cue_swatches(rect):

    # One row of two circles per condition, below the banner, so the
    # participant sees the actual colour cue.
    # Smaller than the task circles so both rows fit under the banner.
    sr = min(CIRCLE_RADIUS, 40)
    row_y = rect.bottom + sr * 2 + 10

    for cond in CONDITIONS:

        colour = CONDITION_COLOUR[cond]

        cx = WIDTH // 2 - 120

        for dx in (-sr - 6, sr + 6):
            pygame.draw.circle(screen, colour, (cx + dx, row_y), sr)

        txt = font_instr.render(
            "collide  ->  {} sound".format(cond.upper()), True, WHITE
        )
        screen.blit(txt, txt.get_rect(midleft=(WIDTH // 2 + 40, row_y)))

        row_y += int(sr * 3)


def run_screens(items, label="Instructions"):

    # items: list of dicts with title, lines and optional min_visible,
    # next_label, cue (bool). The participant can go back with Triangle /
    # D-pad Up (Backspace on keyboard) on every screen except the first.
    i = 0
    n = len(items)

    while i < n:

        it = items[i]

        res = instruction_screen(
            it["title"],
            it["lines"],
            min_visible=it.get("min_visible", 3.0),
            progress="{}  \u00b7  screen {} of {}".format(label, i + 1, n),
            next_label=it.get("next_label", "go to the next screen"),
            allow_prev=(i > 0),
            centered=not it.get("cue", False),
            extra_draw=_cue_swatches if it.get("cue", False) else None
        )

        if res == NAV_PREV and i > 0:
            i -= 1
        else:
            i += 1


def run_rating_phase():

    # Every loaded sound is rated once, in a random order.
    order = []

    for pool_name, pairs in (
        ("pleasant", pleasant_pool),
        ("unpleasant", unpleasant_pool),
        ("neutral", neutral_pool),
    ):
        for name, snd in pairs:
            order.append((pool_name, pool_name, name, snd))

    if not order:
        message("No sounds found in assets/collision_sounds.", 4)
        return

    random.shuffle(order)

    pygame.mouse.set_visible(not USE_GAMEPAD)

    rfile = open(
        os.path.join(
            RATING_DIR,
            "collision_pilot_ratings_{}.csv".format(participant_id)
        ),
        "w",
        newline=""
    )

    rwriter = csv.writer(rfile)

    rwriter.writerow([
        "participant_id",
        "gender",
        "handedness",
        "input_device",
        "presentation_order",
        "sound_pool",
        "sound_condition",
        "sound_file",
        "valence",
        "arousal",
        "rt_seconds"
    ])

    device = "gamepad" if USE_GAMEPAD else "mouse"

    x0 = (WIDTH - RATING_TRACK_W) // 2
    x1 = x0 + RATING_TRACK_W

    def value_at(mx):
        return round(clamp01((mx - x0) / (x1 - x0)), 2)

    hint = (
        "Stick L/R: rate  |  D-pad Up/Down: switch  |  D-pad L/R: fine  |  X: continue  |  Square: replay"
        if USE_GAMEPAD else
        "Click or drag to rate  |  R to replay the sound"
    )

    for idx, (pool_name, cond, name, snd) in enumerate(order):

        # Randomise which scale sits on top for this sound.
        rows = ["arousal", "valence"]
        random.shuffle(rows)

        ypos = {
            rows[0]: int(HEIGHT * 0.42),
            rows[1]: int(HEIGHT * 0.64)
        }

        values = {"arousal": 0.5, "valence": 0.5}
        touched = {"arousal": False, "valence": False}

        dragging = None        # mouse
        focus_index = 0        # gamepad: 0 = top row, 1 = bottom row
        last_step = 0.0        # gamepad: fine-step repeat timer

        btn = pygame.Rect(0, 0, 260, 60)
        btn.center = (WIDTH // 2, int(HEIGHT * 0.85))

        snd.play()
        t_start = time.perf_counter()

        rating_done = False

        while not rating_done:

            dt = clock.tick(RENDER_RATE) / 1000.0
            now = time.perf_counter()

            mx, my = pygame.mouse.get_pos()

            for event in pygame.event.get():

                if event.type == pygame.QUIT:
                    quit_all(rfile)

                if event.type == pygame.KEYDOWN:

                    # ESC always quits (experimenter safety).
                    if event.key == pygame.K_ESCAPE:
                        quit_all(rfile)

                    # Other keys respond only in mouse mode.
                    if not USE_GAMEPAD:

                        if event.key == pygame.K_r:
                            snd.play()

                        if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            if all(touched.values()):
                                rating_done = True

                # ---------------- MOUSE ----------------
                if not USE_GAMEPAD:

                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:

                        if btn.collidepoint(mx, my) and all(touched.values()):
                            rating_done = True
                        else:
                            for s in ("arousal", "valence"):
                                cy = ypos[s]
                                if (
                                    x0 - RATING_HANDLE_R <= mx <= x1 + RATING_HANDLE_R
                                    and abs(my - cy) <= RATING_MAXH + RATING_HANDLE_R
                                ):
                                    dragging = s
                                    values[s] = value_at(mx)
                                    touched[s] = True
                                    break

                    if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                        dragging = None

                    if event.type == pygame.MOUSEMOTION and dragging:
                        values[dragging] = value_at(mx)

                # ---------------- GAMEPAD (buttons / D-pad) ----------------
                # Only the five mapped controls respond; every other button
                # (Circle, Triangle, L1/R1, triggers, stick clicks, PS,
                # touchpad, etc.) is intentionally ignored.
                if USE_GAMEPAD and event.type == pygame.JOYBUTTONDOWN:

                    if event.button == BTN_CONFIRM:
                        if all(touched.values()):
                            rating_done = True

                    elif event.button == BTN_REPLAY:
                        snd.play()

                    elif event.button == DPAD_UP_BTN:
                        focus_index = 0

                    elif event.button == DPAD_DOWN_BTN:
                        focus_index = 1

            # ---------------- GAMEPAD (polled stick + fine step) ----------------
            active = None

            if USE_GAMEPAD:

                active = rows[focus_index]

                # Horizontal stick only: right increases, left decreases.
                ax = joystick.get_axis(RATING_STICK_X)

                if abs(ax) < DEADZONE:
                    ax = 0.0

                if ax != 0:
                    values[active] = clamp01(
                        values[active] + ax * RATING_SPEED * dt
                    )
                    touched[active] = True

                # D-pad Left / Right: fine adjustment in 0.01 steps
                # (held down repeats at STEP_COOLDOWN intervals).
                if now - last_step >= STEP_COOLDOWN:

                    if joystick.get_button(DPAD_LEFT_BTN):
                        values[active] = clamp01(round(values[active] - FINE_STEP, 2))
                        touched[active] = True
                        last_step = now

                    elif joystick.get_button(DPAD_RIGHT_BTN):
                        values[active] = clamp01(round(values[active] + FINE_STEP, 2))
                        touched[active] = True
                        last_step = now

            # -------------------------------------------------
            # DRAW
            # -------------------------------------------------

            screen.fill(BLACK)

            line1 = font_instr.render(
                "Please listen to the sound, then rate it using BOTH sliders.",
                True, WHITE
            )
            screen.blit(line1, line1.get_rect(center=(WIDTH // 2, int(HEIGHT * 0.14))))

            line2 = font_small.render(hint, True, GREY_RAIL)
            screen.blit(line2, line2.get_rect(center=(WIDTH // 2, int(HEIGHT * 0.19))))

            for s in ("arousal", "valence"):
                draw_slider(
                    s, x0, x1, ypos[s],
                    values[s], touched[s],
                    active=(USE_GAMEPAD and s == active)
                )

            enabled = all(touched.values())

            pygame.draw.rect(
                screen,
                WHITE if enabled else GREY_DIM,
                btn,
                border_radius=8,
                width=0 if enabled else 2
            )

            if enabled:
                btn_txt = "Continue (X)" if USE_GAMEPAD else "Continue"
            else:
                btn_txt = "Adjust both sliders"

            bt = font_label.render(
                btn_txt, True,
                BLACK if enabled else GREY_DIM
            )
            screen.blit(bt, bt.get_rect(center=btn.center))

            prog = font_small.render(
                "Sound {} / {}".format(idx + 1, len(order)),
                True, GREY_RAIL
            )
            screen.blit(prog, prog.get_rect(center=(WIDTH // 2, int(HEIGHT * 0.91))))

            pygame.display.flip()

        rt = time.perf_counter() - t_start
        snd.stop()

        rwriter.writerow([
            participant_id,
            gender,
            handedness,
            device,
            idx + 1,
            pool_name,
            cond,
            name,
            round(values["valence"], 2),
            round(values["arousal"], 2),
            round(rt, 3)
        ])

    rfile.close()

    message("Thank you!", 4)

# =========================================================
# PHASE RUNNER
# =========================================================
# The block/trial loop is identical for practice and main, so it lives in one
# function. Each phase logs to its own CSV file and uses its own sound pools.

LOG_HEADER = [
    "participant_id",
    "gender",
    "handedness",
    "colour_map",
    "block_order",
    "block",
    "trial",
    "condition",
    "circle_colour",
    "collision",
    "contact_time",
    "gap",
    "contact_x",
    "left_start",
    "right_start",
    "sound_file",
    "time",
    "motion_phase",
    "left_x",
    "right_x",
    "separation",
    "cursor_x",
    "cursor_y",
    "valence",
    "arousal"
]

def run_phase(blocks_in_order, blocks_cfg, trials_per_block, log_path,
              next_sound, phase_label=None):

    logfile = open(log_path, "w", newline="")
    writer = csv.writer(logfile)
    writer.writerow(LOG_HEADER)

    if phase_label:
        message(phase_label, 3)

    for block_name in blocks_in_order:

        block = blocks_cfg[block_name]

        sched = schedule_block(
            trials_per_block,
            block["p_collide"]
        )

        message(BLOCK_LABELS.get(block_name, block_name), 3)

        for trial, (condition, should_collide) in enumerate(sched):

            fixation(ITI_DURATION)

            plan = TrialPlan(condition, should_collide)

            overlay = Overlay()

            sound_fired = False
            sound_name = ""
            pending_sound = None

            if should_collide:
                pending_sound = next_sound(block_name, condition)

            colour_name = CONDITION_COLOUR_NAME[condition]

            start = time.perf_counter()

            # Log at SAMPLING_RATE Hz, independent of the render rate.
            log_interval = 1.0 / SAMPLING_RATE
            next_log_time = 0.0

            while True:

                clock.tick(RENDER_RATE)

                elapsed = time.perf_counter() - start

                if elapsed >= TRIAL_DURATION:
                    break

                for event in pygame.event.get():

                    if event.type == pygame.QUIT:
                        logfile.close()
                        pygame.quit()
                        raise SystemExit

                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE:
                            logfile.close()
                            pygame.quit()
                            raise SystemExit

                left_x, right_x, motion_phase = plan.positions(elapsed)

                # The outcome sound fires once, on the frame the circles reach
                # contact (collision trials only).
                if (
                    plan.should_collide
                    and not sound_fired
                    and motion_phase != "approach"
                ):
                    sound_fired = True

                    if pending_sound is not None:
                        name, snd = pending_sound
                        pending_sound = None
                        if snd is not None:
                            snd.play()
                            sound_name = name

                overlay.update()

                screen.fill(BLACK)

                draw_circles(plan, left_x, right_x)

                overlay.draw()

                pygame.display.flip()

                # Throttle data logging to SAMPLING_RATE.
                if elapsed >= next_log_time:

                    valence, arousal = overlay.affect()

                    writer.writerow([
                        participant_id,
                        gender,
                        handedness,
                        colour_map,
                        block_order,
                        block_name,
                        trial + 1,
                        condition,
                        colour_name,
                        int(should_collide),
                        round(plan.t_contact, 3),
                        round(plan.gap, 1),
                        round(plan.contact_x, 1),
                        round(plan.left_start, 1),
                        round(plan.right_start, 1),
                        sound_name,
                        round(elapsed, 3),
                        motion_phase,
                        round(left_x, 1),
                        round(right_x, 1),
                        round(right_x - left_x - 2 * CIRCLE_RADIUS, 1),
                        int(overlay.cx),
                        int(overlay.cy),
                        round(valence, 2),
                        round(arousal, 2)
                    ])

                    next_log_time += log_interval

        # Break after each block: shown for at least BLOCK_BREAK seconds, then
        # the participant advances at their own pace (X on gamepad / Space on
        # mouse).
        instruction_screen(
            "Break",
            [
                "Take a short break.",
                "",
                "When you are ready, continue to the next block.",
            ],
            min_visible=BLOCK_BREAK
        )

    logfile.close()

# =========================================================
# INSTRUCTION SCREEN CONTENT
# =========================================================
# The wording shown to participants. Edit the text below to adapt the task.
# Unless a screen sets min_visible, it stays up for at least 3 seconds before
# the participant may advance.

# Device/handedness-specific line describing how to move the dot.
_dot_line = (
    "by moving the white dot with the {} stick on your gamepad:".format(
        "right" if handedness != "left" else "left"
    )
    if USE_GAMEPAD else
    "by moving the white dot with your mouse:"
)

_pleasant_colour = CONDITION_COLOUR_NAME["pleasant"].upper()
_unpleasant_colour = CONDITION_COLOUR_NAME["unpleasant"].upper()

_REPORT_LINE = (
    "Keep reporting continuously HOW YOU FEEL in real time using the grid "
    "overlay in the LOWER MIDDLE of the screen, " + _dot_line
)

_AXIS_LINES = [
    "Left  <-->  Right   :   how UNPLEASANT / PLEASANT you feel",
    "(left = unpleasant,  right = pleasant)",
    "Down  <-->  Up      :  how {} / {} you feel".format(
        AROUSAL_LOW_LABEL.upper(), AROUSAL_HIGH_LABEL.upper()
    ),
    "(bottom = {},  top = {})".format(
        AROUSAL_LOW_LABEL.lower(), AROUSAL_HIGH_LABEL.lower()
    ),
]

PRACTICE_AFFECT_LINES = [
    "While you watch the moving circles, focus on what sound you might hear "
    "if they collide.",
    _REPORT_LINE,
    "",
] + _AXIS_LINES

MAIN_AFFECT_LINES = [
    "While you watch the moving circles, focus on what sound you might hear "
    "if they collide. Pleasant or unpleasant.",
    _REPORT_LINE,
    "",
] + _AXIS_LINES

# Each screen is a dict: title, lines (strings are wrapped; "" = small gap),
# and optionally min_visible (seconds), next_label, cue (adds colour swatches).

MAIN_INTRO_ITEM = {
    "title": "Instructions",
    "lines": [
        "Hi! Welcome to the task.",
        "",
        "This task is divided into three phases: Practice, Main and Rating. "
        "You will receive instructions for the Rating phase later.",
        "",
        "The Practice and the Main phases consist of several trials each. "
        "In each trial you will watch two coloured circles move toward each "
        "other horizontally, just like the tutorial.",
        "In some trials they collide. If they touch, you ",
        "hear a sound. The sound can be pleasant or unpleasant. In some "
        "trials they stop just short of touching and move back.",
        "",
        "While you watch, your task is to keep reporting HOW YOU FEEL in real "
        "time on the affect overlay.",
        "Using the gamepad" if USE_GAMEPAD else "Using the mouse",
    ],
}

CUE_ITEM = {
    "title": "The Colour Cue",
    "lines": [
        "The colour of the circles indicate whether you'll hear a "
        "pleasant sound or unpleasant sound on collision.",
        "",
        "{} circles  -> PLEASANT sound".format(
            _pleasant_colour
        ),
        "{} circles  -> UNPLEASANT sound".format(
            _unpleasant_colour
        ),
        "",
        "Note: In the PRACTICE phase collision plays a NEUTRAL sound instead.",
    ],
    "min_visible": 4.0,
    "cue": True,
}

PRACTICE_INSTRUCTION_ITEMS = [
    {
        "title": "Practice Phase",
        "lines": [
            "The practice phase starts after this.",
            "",
            "This phase consists of two blocks of {} trials each. The High "
            "probability block has more trials in which the circles collide. "
            "The Low probability block has fewer.".format(
                PRACTICE_TRIALS_PER_BLOCK
            ),
            "",
            "If the circles collide, you will hear a sound.",
            "",
            "Each trial is {} seconds long, with a {}-second gap between "
            "trials. There is a break after each block.".format(
                TRIAL_DURATION, ITI_DURATION
            ),
        ],
    },
    {"title": "Practice Phase", "lines": PRACTICE_AFFECT_LINES},
]

MAIN_INSTRUCTION_ITEMS = [
    {
        "title": "Main Phase",
        "lines": [
            "The main phase starts after this.",
            "",
            "This phase consists of two blocks of {} trials each. The High "
            "probability block has more trials in which the circles touch. "
            "The Low probability block has fewer.".format(TRIALS_PER_BLOCK),
            "",
            "Each trial is {} seconds long, with a {}-second gap between "
            "trials. There is a break after each block.".format(
                TRIAL_DURATION, ITI_DURATION
            ),
            "",
            "Reminder: the colour of the circles tells you what sound you "
            "will hear if they collide.",
        ],
        # Draw the coloured circle swatches (colour mapping) under the text.
        "cue": True,
    },
    {"title": "Main Phase", "lines": MAIN_AFFECT_LINES},
]

# =========================================================
# MAIN
# =========================================================

# An empty sound folder would otherwise only show up as a console warning, so
# tell the experimenter on screen before the session starts. Collisions still
# freeze for FREEZE_DURATION, they are just silent.
_missing = [
    folder
    for folder, pairs in (
        (PLEASANT_DIR, pleasant_pool),
        (UNPLEASANT_DIR, unpleasant_pool),
        (NEUTRAL_DIR, neutral_pool),
    )
    if not pairs
]

if _missing:
    instruction_screen(
        "Setup warning (experimenter)",
        [
            "These sound folders are empty:",
            "",
        ] + _missing + [
            "",
            "Collisions in those conditions will be SILENT.",
            "Drop 1-second .wav files into each folder and restart.",
        ],
        min_visible=3.0
    )

# Overall task instructions, the colour cue (with live swatches) and the two
# practice screens, as one sequence the participant can step back through.
run_screens([MAIN_INTRO_ITEM, CUE_ITEM] + PRACTICE_INSTRUCTION_ITEMS)

# Practice phase (separate log file, separate sound pools, same counterbalancing).
run_phase(
    BLOCK_ORDER,
    BLOCKS,
    PRACTICE_TRIALS_PER_BLOCK,
    os.path.join(
        PRACTICE_DIR,
        "collision_pilot_practice_{}.csv".format(participant_id)
    ),
    PRACTICE_NEXT_SOUND
)

# Two instruction screens before the main phase (3 s minimum each).
run_screens(MAIN_INSTRUCTION_ITEMS)

# Main phase.
run_phase(
    BLOCK_ORDER,
    BLOCKS,
    TRIALS_PER_BLOCK,
    os.path.join(
        MAIN_DIR,
        "collision_pilot_data_{}.csv".format(participant_id)
    ),
    MAIN_NEXT_SOUND
)

# Post-task: show rating instructions (two screens, like the other phases),
# then replay each sound and collect Affective Slider ratings.

# Screen 1: what the task is and what the two scales mean (device-independent).
_rating_intro_lines = [
    "You will hear a list of sounds one by one. Rate each sound on the basis "
    "of how it makes you feel, using the two sliders on screen: arousal and "
    "pleasure.",
    "",
    "The more pleasant a sound feels, the higher you rate it on pleasure; "
    "if it sounds unpleasant, mark it lower.",
    "",
    "If a sound makes you feel excited/agitated, mark it higher on arousal; "
    "if it makes you feel calm/bored, mark it lower.",
]

# Screen 2: how to control the sliders (device-specific).
if USE_GAMEPAD:
    _rating_controls_title = "Rating Task - Controller Instructions"
    _rating_controls_lines = [
        "Stick Right :  increase the rating   |   Stick Left :  decrease it",
        "D-pad Up / Down :  switch between the two sliders",
        "D-pad Left / Right :  fine adjustment (0.01 steps)",
        "X button :  confirm and continue to the next sound",
        "Square button :  replay the current sound",
        "",
        "Please pay attention to which slider you're marking [Valence/Arousal] "
        "as their relative positions change every trial. The slider "
        "highlighted in red is the active one."
    ]
else:
    _rating_controls_title = "Rating Task - Mouse Instructions"
    _rating_controls_lines = [
        "Click or drag on a slider to set your rating.",
        "Set BOTH sliders before continuing.",
        "Click 'Continue' to move on to the next sound.",
        "Press R to replay the current sound.",
    ]

run_screens(
    [
        {
            "title": "Rating Task - Instructions",
            "lines": _rating_intro_lines,
        },
        {
            "title": _rating_controls_title,
            "lines": _rating_controls_lines,
            "next_label": "begin the rating task",
        },
    ],
    label="Rating instructions"
)
run_rating_phase()

pygame.quit()
