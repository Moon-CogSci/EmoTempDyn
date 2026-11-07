# Selection of sound stimuli

The collision task uses **10 pleasant**, **10 unpleasant** and **10
neutral** one-second clips taken from the IADS-E database (International
Affective Digitized Sounds, Expanded). Pleasant and unpleasant sounds
are played on collision in the main phase of `collision_pilot.py`.
Neutral sounds are used in the practice phase and in the tutorial.

The sounds that were retained, the one-second interval taken from each
original recording, and the IADS-E ratings are listed in
[`IADS_final_clips.csv`](IADS_final_clips.csv).

The IADS-E recordings themselves are not included here; they must be
obtained separately from the IADS-E authors.

The stimuli were obtained in three stages. The documents linked below
give the full method, scores and code.

## 1. Choosing 30 IADS-E recordings

Sounds were ranked from the IADS-E mean ratings: a composite of
arousal, valence and happiness for the pleasant set; arousal,
reversed valence and fear for the unpleasant set; and distance from
a mid-valence, low-arousal point for the neutral set. Candidates
listed in the ratings sheet but missing from the sound folders, or
whose listed category did not match the file that carried that ID,
were skipped, and the next-ranked valid sound was taken instead,
until 10 sounds had been retained in each set.

Details: [`IADS_most_suitable_sounds.md`](IADS_most_suitable_sounds.md)
(script: `IADS_most_suitable_sounds.R`).

## 2. Cutting a one-second window

IADS-E files are 6 seconds long; the experiment plays 1 second at
each collision. Overlapping one-second windows (every 100 ms) were
described with acoustic features and ranked with a category-specific
score. The highest-ranked window of each track was taken as the
candidate clip.

Details: [`IADS_analysis.md`](IADS_analysis.md)
(script: `IADS_analysis.R`).

## 3. Listening check and final clips

Each candidate clip was checked by listening. Where another portion of
the recording was judged more suitable, that portion was used instead
and the acoustic ranking for that sound was disregarded.

The 30 sounds that were retained, the one-second interval taken from
each original recording, and the IADS-E valence, arousal, happiness,
fear and sadness ratings are listed in
[`IADS_final_clips.csv`](IADS_final_clips.csv).
