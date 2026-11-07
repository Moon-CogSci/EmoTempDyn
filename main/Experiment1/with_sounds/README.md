# Experiment 1: collision-anticipation affect task (with sounds)

This folder contains the **with-sounds** version of the collision-anticipation
affect task. On each trial, two same-coloured circles move toward each other.
On some trials they collide and a sound plays; on others they stop just short
and move apart. The **circle colour** tells the participant what kind of
sound a collision would result in playing (pleasant or unpleasant). The color 
mapping is counter-balanced across participants. It does not tell them
whether a collision will happen. While the trial runs, the participant
continuously reports how they feel by moving a white dot on a
**valence (left–right) by arousal (bottom–top)** grid. The aim is to 
computationally model how the emotion builds leading upto the emotional event
(pleasant/unpleasant sound) and dies out post hearing the sound.

The sounds are one-second clips from the IADS-E database: 10 pleasant and 10
unpleasant in the main phase, and 10 neutral in practice and in the tutorial.
The audio files are not included in this repository.

## What is in this folder


| Folder                                                  | Contents                                                                                                                                                                                                  |
| ------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `[tutorial/](tutorial/README.md)`                       | Interactive walkthrough that teaches the grid and the stimuli before the session. It does not save data.                                                                                                  |
| `[main_task/](main_task/README.md)`                     | The experiment itself (`collision_pilot.py`): practice, main phase, and a post-task rating of every sound.                                                                                                |
| `[selection_of_sounds/](selection_of_sounds/README.md)` | How the 30 clips were chosen, cut to one second, and checked by listening. The sounds actually used are listed in `[selection_of_sounds/IADS_final_clips.csv](selection_of_sounds/IADS_final_clips.csv)`. |




## Session, in outline

1. **Tutorial.** The participant learns the affect grid and sees example trials (neutral sounds only).
2. **Practice.** Two blocks with neutral sounds, one with a high chance of collision and one with a low chance.
3. **Main phase.** The same structure, with pleasant and unpleasant sounds. Colour is counterbalanced across participants, as is which probability block comes first.
4. **Ratings.** Each sound is replayed once and rated for valence and arousal.

Trial timing, controls, counterbalancing, and the CSV outputs are described in the [main-task README](main_task/README.md).