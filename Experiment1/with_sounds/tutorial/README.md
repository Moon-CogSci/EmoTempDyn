# Collision-anticipation affect task: interactive tutorial

`collision_pilot_tutorial.py` is a short, interactive walkthrough that
prepares a participant for a collision-anticipation affect task. In the main
task, two coloured circles move toward each other. If they touch, a pleasant
or unpleasant sound plays. The circle colour signals which kind of sound to
expect. While they watch, participants continuously report how they feel by
moving a white dot on a valence-by-arousal grid.

The tutorial introduces the stimuli, teaches the grid with short quizzes, and
lets the participant practise on four example trials. It is written with
pygame, runs fullscreen, and **does not log or save any data**.

## What the tutorial covers

| Step | Content |
|------|---------|
| 1 | Welcome |
| 2-4 | The two components of the task: the stimuli and the response overlay |
| 5 | Meet the overlay: move the white dot around the grid |
| 6 | The four quadrants (pleasant/unpleasant x excited/calm) |
| 7-10 | Quadrant quizzes: hold the dot in the requested quadrant to continue |
| 11 | The circles: how they move, and that participants cannot steer them |
| 12-15 | Four example trials: collision and near miss, pleasant and unpleasant colour |
| 16 | Tutorial complete |

The affect grid maps left to right as **unpleasant to pleasant** (valence) and
bottom to top as **calm to excited** (arousal). The dot's position is mapped
to values from -50 to +50 on each axis, as in the main task.

In the example trials, the participant presses a shoulder button (or Space)
to start. A short thumb-on-stick reminder and a 5-4-3-2-1 countdown follow,
and then the circles move. If the dot stays still for more than 0.3 s, the
trial freezes and a warning asks the participant to keep moving it and
restart. Back and forward navigation is available on every step except the
first.

## Requirements

- Python 3.8 or newer (developed and tested on Python 3.8 with pygame 2.6)
- [pygame](https://www.pygame.org/)
- [NumPy](https://numpy.org/)
- `tkinter` (included with most Python installers) for the start-up dialog
- A display. The tutorial runs fullscreen at the native resolution.
- Optional: a gamepad with a DualSense-style layout

```
pip install pygame numpy
```

## Running

```
python collision_pilot_tutorial.py
```

A small dialog asks for:

- **Participant ID**: the last digit selects the colour mapping, using the
  same counterbalancing rule as the main task. Digits 1, 2, 5, 6 and 9 give
  red = pleasant and blue = unpleasant. Digits 0, 3, 4, 7 and 8 give the reverse.
  An ID with no digits is treated as ending in 1.
- **Handedness**: the tutorial uses the right stick for right-handed
  participants and the left stick for left-handed participants, and moves the
  navigation buttons to match (see below).

Press **Esc** at any time to quit.

## Controls

The tutorial uses a gamepad if one is connected. Otherwise it uses the
keyboard and mouse.

| Action | Gamepad (right-handed) | Gamepad (left-handed) | Keyboard / mouse |
|--------|------------------------|-----------------------|------------------|
| Move the white dot | Right stick | Left stick | Hold left mouse button and move the mouse |
| Next step | X | D-pad Down | Space, Enter or click |
| Previous step | Triangle | D-pad Up | Backspace |
| Start / restart an example trial | Right shoulder (R1) | Left shoulder (L1) | Space, Enter or click |
| Quit | Esc | Esc | Esc |

Button indices follow the pygame mapping for a DualSense controller (X = 0,
Triangle = 3, L1 = 9, R1 = 10, D-pad Up/Down = 11/12). If your controller
reports different indices, change `BTN_CONFIRM`, `BTN_BACK` and `BTN_ACTION`
near the top of the script. Left-handed D-pad input is also read from a hat
if the driver reports the D-pad that way.

The dot's maximum speed with the stick fully deflected is the same as the
speed of one moving circle, and it moves proportionally slower for smaller
deflections.

## Sounds (optional)

During the example trials, a sound plays when the circles collide. The
tutorial loads sounds from:

```
assets/collision_sounds/neutral/
```

Put short `.wav`, `.ogg` or `.mp3` files there and run the script from the
folder that contains `assets/`. One of them is picked at random for each
collision. The tutorial always plays a neutral sound, whatever the circle
colour, because the examples are only illustrative. If the folder is missing
or empty, the examples run silently.

No audio files are included in this repository. Use sounds that you have the
right to use, and check the licence of any stimulus database before
redistributing it.

## Customising

Most settings are constants near the top of `collision_pilot_tutorial.py`.

| Setting | What it controls |
|---------|------------------|
| `CIRCLE_RADIUS` | Circle size (5% of screen height) |
| `TRIAL_DURATION`, `FREEZE_DURATION` | Length of an example trial and of the pause at contact |
| `MISS_GAP` | Gap left between the circles on a near miss |
| `CONTACT_TIME_TARGET`, `CONTACT_TIME_WINDOW` | When contact happens |
| `START_DELAY`, `THUMB_MSG_AT`, `COUNTDOWN_START`, `COUNTDOWN_FROM` | Pre-trial delay, thumb reminder and countdown timing |
| `IDLE_LIMIT`, `IDLE_GRACE` | How long the dot may stay still before the trial freezes |
| `UI_SCALE` | Banner text scale (shrinks automatically on screens shorter than 1080 px) |

The instruction wording lives in the `step_*` functions. Layout, circle size
and timing match the main task script (`collision_pilot.py`), so keep them in
sync if you change either one.

## Display notes

The banner text is laid out to leave room for the circles above the response
overlay. This was checked at 1920x1080, 1600x900, 1536x864, 1366x768 and
2560x1440. On very small screens the text becomes small.

## Files

| File | Purpose |
|------|---------|
| `collision_pilot_tutorial.py` | The tutorial (this document) |
| `assets/collision_sounds/neutral/` | Optional example-trial sounds (not included) |
