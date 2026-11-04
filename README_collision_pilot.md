# Collision-anticipation affect task

`collision_pilot.py` is a pygame experiment that studies how emotional
experience changes continuously while people anticipate a pleasant or an
unpleasant event.

On every trial, two same-coloured circles move toward each other along a
horizontal line. On some trials they collide and a sound plays. On the others
they stop just short of touching and move apart. The **circle colour** tells
the participant what kind of sound a collision would bring (for example, red =
pleasant, blue = unpleasant). While each trial runs, the participant
continuously reports how they feel by moving a white dot on a
**valence (left-right) by arousal (bottom-top)** grid. After the trials, every
sound is replayed and rated on two Affective Slider scales.

An interactive tutorial for participants, `collision_pilot_tutorial.py`, has
its own README (`README.md`).

## Session structure

1. **Participant dialog**: ID, gender, handedness.
2. **Instructions**, then a **practice phase** (neutral sounds).
3. **Instructions**, then the **main phase** (pleasant and unpleasant sounds).
4. **Rating phase**: every sound is replayed once and rated for valence and
   arousal.

Each phase has two blocks of trials that differ in collision probability:

| Phase | Trials per block | High-probability block | Low-probability block |
|-------|------------------|------------------------|-----------------------|
| Practice | 20 | 70% of trials end in a collision | 30% |
| Main | 100 | 70% | 30% |

Within each block, half the trials use the pleasant colour and half the
unpleasant colour, intermixed, and the collision probability applies *within*
each colour. So the colour carries no information about whether a collision
will happen, only about the sound it would bring. No more than four trials in
a row use the same colour.

A trial is 10 s long, preceded by a 2 s fixation cross. The circles move at a
constant speed, freeze for 1 s at contact (or at the closest approach on a
near miss), and then retreat. The freeze is the same length for collisions
and near misses, so it does not signal the outcome. Contact happens about 5 s
into the trial, jittered by the circles' start positions. The circle size is
5% of the screen height. A break of at least 5 s follows each block.

### Counterbalancing

Two factors are counterbalanced by the **last digit of the participant ID**
(an ID with no digits is treated as ending in 1):

| Last digit | Colour mapping | Block order |
|------------|----------------|-------------|
| 1, 5, 9 | red = pleasant, blue = unpleasant | high-probability block first |
| 2, 6 | red = pleasant, blue = unpleasant | low-probability block first |
| 3, 7 | blue = pleasant, red = unpleasant | high-probability block first |
| 0, 4, 8 | blue = pleasant, red = unpleasant | low-probability block first |

## Requirements

- Python 3.8 or newer (developed and tested on Python 3.8 with pygame 2.6)
- [pygame](https://www.pygame.org/)
- [NumPy](https://numpy.org/)
- `tkinter` (included with most Python installers) for the start-up dialog
- A display. The task runs fullscreen at the native resolution; the layout
  scales with the screen size.
- Optional: a gamepad with a DualSense-style layout
- Sound files (see below)

```
pip install pygame numpy
```

## Sounds

The task reads one-second sound files from three folders and must be run from
the directory that contains `assets/`:

```
assets/collision_sounds/pleasant/      main phase, pleasant collisions
assets/collision_sounds/unpleasant/    main phase, unpleasant collisions
assets/collision_sounds/neutral/       practice phase, all collisions
```

The design assumes **10 files per folder**. In the main phase, each pleasant
and each unpleasant file is played five times, giving 50 collisions per
valence (35 in the high-probability block and 15 in the low). In the practice
phase, the neutral files are split at random between the two blocks and
repeated as evenly as needed. Supported formats are `.wav`, `.ogg` and
`.mp3`. If a folder is empty, the experimenter sees a warning on screen at
the start of the session and the collisions for that condition are silent.

The audio files are **not included** in this repository. Provide your own
sounds that you have the right to use, and check the licence of any stimulus
database before you redistribute its sounds.

The task also avoids playing sound "into" a connected DualSense controller,
which Windows may register as an audio output. It picks a non-controller
output device if one is available.

## Running

```
python collision_pilot.py
```

Press **Esc** at any time to quit.

## Controls

The task uses a gamepad if one is connected. Otherwise it uses the mouse and
keyboard.

| Action | Gamepad (right-handed) | Gamepad (left-handed) | Mouse / keyboard |
|--------|------------------------|-----------------------|------------------|
| Move the white dot | Right stick | Left stick | Hold left mouse button and move the mouse |
| Next instruction screen | X | D-pad Down | Space, Enter or click |
| Previous instruction screen | Triangle | D-pad Up | Backspace |
| Quit | Esc | Esc | Esc |

With the stick fully deflected, the dot moves at the same speed as one
moving circle, and it moves proportionally slower for smaller deflections.

**Rating phase controls** (the same for both hands):

| Action | Gamepad | Mouse / keyboard |
|--------|---------|------------------|
| Set the rating | Stick left / right | Click or drag on the slider |
| Switch between the two sliders | D-pad Up / Down | (both sliders are set directly) |
| Fine adjustment (0.01 steps) | D-pad Left / Right | |
| Confirm and go to the next sound | X | Continue button |
| Replay the sound | Square | R |

Left-handed participants use the left stick for the rating sliders as well.

Button indices follow the pygame mapping for a DualSense controller. If your
controller reports different indices, adjust the `BTN_*` and `*_BTN` constants
in the input sections of the script.

## Output

Each phase writes a CSV file named after the participant ID into its own
folder (created automatically in the working directory):

| Folder | File | Contents |
|--------|------|----------|
| `collision_pilot_practice/` | `collision_pilot_practice_<ID>.csv` | Practice phase |
| `collision_pilot_main/` | `collision_pilot_data_<ID>.csv` | Main phase |
| `collision_pilot_rating/` | `collision_pilot_ratings_<ID>.csv` | Post-task sound ratings |

**Trial files** (practice and main) have one row per sample, logged at 10 Hz
during each trial:

| Column | Meaning |
|--------|---------|
| `participant_id`, `gender`, `handedness` | From the start-up dialog |
| `colour_map`, `block_order` | Counterbalancing codes (`rp` / `bp`; `hf` / `lf`) |
| `block`, `trial` | Block name and trial number within it |
| `condition`, `circle_colour` | Pleasant or unpleasant condition, and the colour shown |
| `collision` | Whether the circles collided on this trial |
| `contact_time`, `gap`, `contact_x` | Planned contact time (s), gap on a near miss (px), contact position (px) |
| `left_start`, `right_start` | Start positions of the circle centres (px) |
| `sound_file` | Sound played on a collision |
| `time`, `motion_phase` | Time into the trial (s) and the phase: approach, freeze, retreat or parked |
| `left_x`, `right_x`, `separation` | Circle positions and gap between them (px) |
| `cursor_x`, `cursor_y` | Position of the white dot (px) |
| `valence`, `arousal` | Dot position on the grid, each from -50 to +50 |

**Rating file**: one row per sound, with `participant_id`, `gender`,
`handedness`, `input_device`, `presentation_order`, `sound_pool`,
`sound_condition`, `sound_file`, `valence`, `arousal` (each from 0 to 1, in
0.01 steps) and `rt_seconds`. The sounds are presented in random order, and
the top-to-bottom order of the two sliders is also randomised per sound.

These files contain participant data. Do not commit them to a public
repository. Add the output folders to your `.gitignore`:

```
collision_pilot_practice/
collision_pilot_main/
collision_pilot_rating/
```

## Customising

Most settings are constants near the top of the script.

| Setting | What it controls |
|---------|------------------|
| `TRIALS_PER_BLOCK`, `PRACTICE_TRIALS_PER_BLOCK` | Trials per block |
| `P_COLLIDE` | Collision probability in the high and low blocks |
| `TRIAL_DURATION`, `ITI_DURATION`, `BLOCK_BREAK` | Trial length, fixation time and minimum break (s) |
| `SAMPLING_RATE` | Logging rate for the dot position (Hz) |
| `CIRCLE_RADIUS` | Circle size (5% of the screen height) |
| `MISS_GAP` | Gap left between the circles on a near miss (px) |
| `FREEZE_DURATION` | Pause at contact or closest approach (s) |
| `CONTACT_TIME_TARGET`, `CONTACT_TIME_WINDOW` | When contact happens (s) |
| `BAND_WIDTH_SCALE` | How widely the start positions are jittered |
| `RETREAT_MODE` | Retreat at the approach speed (`same_speed`) or stretch it to fit the trial (`fit_trial`) |
| `MAX_CONDITION_RUN` | Longest run of one colour in a row |
| `AROUSAL_*_LABEL`, `VALENCE_*_LABEL` | Words around the response grid |

The instruction wording is defined in the "Instruction screen content" section
near the end of the script. The contact timing is calibrated from the screen
size at start-up, and the realised contact-time window is printed to the
console.

## Files

| File | Purpose |
|------|---------|
| `collision_pilot.py` | The task (this document) |
| `collision_pilot_tutorial.py` | Interactive participant tutorial (see `README.md`) |
| `assets/collision_sounds/` | Sound files (not included) |
