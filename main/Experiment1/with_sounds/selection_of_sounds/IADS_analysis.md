Acoustic Analysis and One-Second Clip Extraction for the IADS-E Stimuli
================

- [1. Purpose](#1-purpose)
- [2. Method overview](#2-method-overview)
  - [2.1 Acoustic features](#21-acoustic-features)
  - [2.2 Category-specific ranking
    scores](#22-category-specific-ranking-scores)
- [3. Setup](#3-setup)
  - [3.1 Paths and settings](#31-paths-and-settings)
  - [3.2 Helper function: safe
    z-scores](#32-helper-function-safe-z-scores)
- [4. Feature extraction for one
  window](#4-feature-extraction-for-one-window)
- [5. Analysis of a whole track](#5-analysis-of-a-whole-track)
- [6. Discovery of the stimulus
  files](#6-discovery-of-the-stimulus-files)
- [7. Window features for all tracks](#7-window-features-for-all-tracks)
- [8. Category-specific ranking and selection of the candidate
  windows](#8-category-specific-ranking-and-selection-of-the-candidate-windows)
  - [8.1 Ranking scores](#81-ranking-scores)
  - [8.2 Export of the full analysis and the rank-1
    windows](#82-export-of-the-full-analysis-and-the-rank-1-windows)
- [9. Extraction of exactly one second at each selected start
  time](#9-extraction-of-exactly-one-second-at-each-selected-start-time)
- [10. Backup of the original recordings and replacement by the
  clips](#10-backup-of-the-original-recordings-and-replacement-by-the-clips)
- [11. Verification of the final
  files](#11-verification-of-the-final-files)
- [12. Outputs and reproducibility](#12-outputs-and-reproducibility)

# 1. Purpose

This document describes how a single **one-second clip** was obtained
from each of the 30 emotional and neutral sounds used in the collision
experiment (`collision_pilot.py` and `collision_pilot_tutorial.py`).

The 30 sounds (10 pleasant, 10 unpleasant, 10 neutral) were previously
selected from the **IADS-E** database (see
`IADS_most_suitable_sounds.Rmd`). The IADS-E stimuli are **6 seconds**
long, whereas the experiment requires a sound of **1 second** to be
played at each collision. The most suitable one-second portion of every
recording was therefore identified in two stages:

1.  **Automated acoustic analysis** (this document). Every possible
    one-second window of a recording was described by a set of acoustic
    features and ranked with a category-specific scoring rule. The
    highest-ranked window of each track was taken as the candidate clip.
2.  **Manual verification** by the experimenter. Each candidate clip was
    checked by listening. Where another portion of the sound was judged
    more suitable, the experimenter’s choice was used and the acoustic
    ranking for that particular sound was disregarded.

# 2. Method overview

| Step | Description |
|----|----|
| 1 | The `pleasant`, `unpleasant` and `neutral` stimulus folders were scanned for `.wav` files. |
| 2 | Each track was converted to mono, normalised to approximately \[-1, 1\] and DC-corrected. |
| 3 | Overlapping **1-s windows** were generated every **100 ms**. |
| 4 | Acoustic features were computed for every window. |
| 5 | Windows were ranked **within each track** with a category-specific score. |
| 6 | The rank-1 window of each track was exported as the candidate clip. |
| 7 | Original recordings were backed up. |
| 8 | Originals were replaced by the selected one-second clips. |
| 9 | The final files were verified to be exactly one second (one sample-rate’s worth of samples) long. |

**Analysis settings**

| Setting | Value | Meaning |
|----|----|----|
| `window_seconds` | 1 s | Length of each candidate window |
| `step_seconds` | 0.1 s | Hop between consecutive window start times (a 6-s track yields about 51 windows) |
| `frame_seconds` | 0.1 s | Length of the non-overlapping sub-frames (10 per window) used for spectral and energy features |
| `silence_threshold_dbfs` | -45 dBFS | Provisional level below which a neutral window is penalised as near-silent |

## 2.1 Acoustic features

Features were computed for each window from ten non-overlapping 100-ms
frames, and then summarised over the window.

| Feature | Definition |
|----|----|
| `rms`, `rms_dbfs` | Root-mean-square amplitude of the window, and its level in dB relative to full scale |
| `peak`, `peak_dbfs` | Peak absolute amplitude of the window, and its level in dBFS |
| `centroid_hz` | Spectral centroid (power-weighted mean frequency, DC excluded), averaged over frames; a correlate of brightness |
| `spectral_flux` | Mean Euclidean distance between the normalised power spectra of consecutive frames; a measure of spectral change |
| `spectral_flatness` | Geometric mean divided by arithmetic mean of the power spectrum, averaged over frames (1 = noise-like, 0 = tonal) |
| `tonality` | `1 - spectral_flatness` |
| `rms_cv` | Coefficient of variation of the frame RMS values; a measure of energy variability |
| `onset_strength` | Largest frame-to-frame increase in RMS, divided by the mean frame RMS |
| `zcr` | Zero-crossing rate, averaged over frames |

## 2.2 Category-specific ranking scores

Each feature that enters a score was first converted to a **z-score
within its own track** (that is, relative to all windows of the same
recording). The rankings therefore identify the best window *within* a
recording; scores are not comparable between recordings.

| Category | Score | Rationale |
|----|----|----|
| Unpleasant | `z_rms + z_flux + z_onset + 0.25 * z_centroid` | Favours salient energy changes and spectral activity |
| Pleasant | `z_tonality - 0.75 * z_flux - 0.50 * z_onset - 0.25 * z_rms_cv` | Favours tonal and relatively continuous sections |
| Neutral | `-z_flux - z_rms_cv - z_onset - 0.5 * silence_penalty` | Favours stable sections, while penalising near-silence |

where `silence_penalty = max(0, (-45 - rms_dbfs) / 10)`.

The scores are heuristic combinations of acoustic features. Because they
are not validated against listener judgements, the automated choice was
checked manually (see Section 1).

> **Caution:** Section 10 overwrites the original recordings with the
> extracted clips (after backing them up). Re-running the pipeline on
> files that have already been trimmed would analyse one-second tracks
> with a single window each, and would overwrite the analysis tables.
> For this reason the replacement steps are guarded by the
> `replace_originals` parameter.

# 3. Setup

``` r
library(tuneR)    # reading and writing WAV files
library(dplyr)    # data manipulation
library(purrr)    # functional iteration over folders
library(stringr)  # string helpers
library(readr)    # writing CSV files
```

## 3.1 Paths and settings

``` r
base_folder <- params$base_folder

category_folders <- c(
  pleasant   = file.path(base_folder, "pleasant"),
  unpleasant = file.path(base_folder, "unpleasant"),
  neutral    = file.path(base_folder, "neutral")
)

output_folder <- file.path(base_folder, "window_analysis")

# A unique, time-stamped backup folder is used for each run
backup_folder <- file.path(
  output_folder,
  paste0("originals_backup_", format(Sys.time(), "%Y%m%d_%H%M%S"))
)

dir.create(output_folder, recursive = TRUE, showWarnings = FALSE)

window_seconds <- 1    # length of each candidate window
step_seconds   <- 0.1  # hop between window start times
frame_seconds  <- 0.1  # sub-frame length for spectral / energy features

# Provisional neutral-window silence threshold
silence_threshold_dbfs <- -45
```

## 3.2 Helper function: safe z-scores

A z-score is undefined when a feature has zero (or non-finite) variance
within a track. In that case a vector of zeros is returned, so that the
feature contributes nothing to the ranking instead of producing `NaN`.

``` r
z_safe <- function(x) {

  s <- sd(x, na.rm = TRUE)

  if (!is.finite(s) || s == 0) {
    return(rep(0, length(x)))
  }

  (x - mean(x, na.rm = TRUE)) / s
}
```

# 4. Feature extraction for one window

`window_features()` receives the samples of one one-second window and
returns the features listed in Section 2.1. The window is divided into
100-ms frames; a spectrum is obtained for each frame with an FFT, and
frame-level values are then summarised over the window.

``` r
window_features <- function(x, sample_rate) {

  eps <- 1e-12  # avoids division by zero and log(0)
  frame_n <- round(frame_seconds * sample_rate)

  # Start index of each non-overlapping frame
  frame_starts <- seq(
    from = 1,
    to = length(x) - frame_n + 1,
    by = frame_n
  )

  frames <- lapply(frame_starts, function(start) {
    x[start:(start + frame_n - 1)]
  })

  # ---- Frame-level quantities --------------------------------
  frame_results <- lapply(frames, function(frame) {

    n <- length(frame)

    # One-sided power spectrum
    spectrum <- Mod(fft(frame))[seq_len(floor(n / 2) + 1)]
    power <- spectrum^2

    frequencies <- (0:floor(n / 2)) * sample_rate / n

    # The DC component is excluded
    power <- power[-1]
    frequencies <- frequencies[-1]

    # Spectral centroid (brightness)
    centroid <- sum(frequencies * power) /
      (sum(power) + eps)

    # Spectral flatness (geometric mean / arithmetic mean)
    flatness <- exp(mean(log(power + eps))) /
      (mean(power) + eps)

    # Normalised power distribution, used for spectral flux
    distribution <- power / (sum(power) + eps)

    list(
      rms = sqrt(mean(frame^2)),
      centroid = centroid,
      flatness = flatness,
      distribution = distribution
    )
  })

  frame_rms <- vapply(
    frame_results, `[[`, numeric(1), "rms"
  )

  frame_centroid <- vapply(
    frame_results, `[[`, numeric(1), "centroid"
  )

  frame_flatness <- vapply(
    frame_results, `[[`, numeric(1), "flatness"
  )

  distributions <- lapply(
    frame_results, `[[`, "distribution"
  )

  # ---- Spectral flux between consecutive 100-ms frames -------
  if (length(distributions) > 1) {

    flux_values <- vapply(
      seq_len(length(distributions) - 1),
      function(i) {
        sqrt(sum(
          (distributions[[i]] - distributions[[i + 1]])^2
        ))
      },
      numeric(1)
    )

    spectral_flux <- mean(flux_values)

  } else {
    spectral_flux <- 0
  }

  # ---- Energy variability and onset strength -----------------
  rms_mean <- mean(frame_rms)

  rms_cv <- sd(frame_rms) / (rms_mean + eps)

  onset_strength <- max(
    c(0, diff(frame_rms))
  ) / (rms_mean + eps)

  # ---- Window-level level measures ---------------------------
  window_rms <- sqrt(mean(x^2))
  window_peak <- max(abs(x))

  rms_dbfs <- 20 * log10(window_rms + eps)
  peak_dbfs <- 20 * log10(window_peak + eps)

  # ---- Zero-crossing rate (mean over frames) -----------------
  zcr <- mean(vapply(
    frames,
    function(f) {
      mean(f[-1] * f[-length(f)] < 0)
    },
    numeric(1)
  ))

  c(
    rms = window_rms,
    rms_dbfs = rms_dbfs,
    peak = window_peak,
    peak_dbfs = peak_dbfs,
    centroid_hz = mean(frame_centroid),
    spectral_flux = spectral_flux,
    spectral_flatness = mean(frame_flatness),
    tonality = 1 - mean(frame_flatness),
    rms_cv = rms_cv,
    onset_strength = onset_strength,
    zcr = zcr
  )
}
```

# 5. Analysis of a whole track

`analyse_track()` reads one recording, prepares the signal, slides a
one-second window along it in 100-ms steps and calls `window_features()`
for each position. One row per window is returned, including the
window’s start and end time (used later to cut the clip).

Signal preparation:

- stereo recordings are averaged to mono (for analysis only; the
  extracted clips keep the original channels);
- PCM integer samples are scaled to approximately \[-1, 1\];
- the DC offset is removed.

``` r
analyse_track <- function(path, category) {

  message("Analysing: ", category, " | ", basename(path))

  # Unreadable files are reported and skipped
  wave <- tryCatch(
    readWave(path, header = FALSE),
    error = function(e) {
      warning(
        "Could not read ", path, ": ",
        conditionMessage(e)
      )
      return(NULL)
    }
  )

  if (is.null(wave)) {
    return(NULL)
  }

  # Conversion to mono for feature analysis
  left <- as.numeric(wave@left)

  if (wave@stereo) {
    audio <- (left + as.numeric(wave@right)) / 2
  } else {
    audio <- left
  }

  sample_rate <- wave@samp.rate

  # PCM samples are scaled to approximately [-1, 1]
  audio <- audio / (2^(wave@bit - 1))

  # DC offset is removed
  audio <- audio - mean(audio)

  window_n <- round(window_seconds * sample_rate)
  step_n <- round(step_seconds * sample_rate)

  if (length(audio) < window_n) {
    warning("Track shorter than one second: ", basename(path))
    return(NULL)
  }

  # First-sample index of every window
  starts <- seq(
    from = 1,
    to = length(audio) - window_n + 1,
    by = step_n
  )

  rows <- lapply(starts, function(start) {

    end <- start + window_n - 1
    x <- audio[start:end]

    features <- window_features(x, sample_rate)

    data.frame(
      category = category,
      source_file = basename(path),
      source_path = normalizePath(
        path, winslash = "/", mustWork = TRUE
      ),
      sample_rate = sample_rate,
      start_sec = (start - 1) / sample_rate,
      end_sec = start / sample_rate +
        (window_n - 1) / sample_rate,
      duration_sec = length(x) / sample_rate,
      as.list(features),
      check.names = FALSE
    )
  })

  bind_rows(rows)
}
```

# 6. Discovery of the stimulus files

All `.wav` files in the three category folders are listed. The script
stops if a folder is missing or if no files are found at all.

``` r
file_table <- imap_dfr(
  category_folders,
  function(folder, category) {

    if (!dir.exists(folder)) {
      stop("Folder not found: ", folder)
    }

    paths <- list.files(
      folder,
      pattern = "\\.wav$",
      recursive = TRUE,
      full.names = TRUE,
      ignore.case = TRUE
    )

    if (length(paths) == 0) {
      warning("No WAV files found in: ", folder)
      return(tibble())
    }

    tibble(
      category = category,
      path = paths
    )
  }
)

if (nrow(file_table) == 0) {
  stop("No WAV files found in the category folders.")
}

cat("\nFiles found by category:\n")
print(count(file_table, category))
```

# 7. Window features for all tracks

Every track is analysed and the window tables are combined into a single
data frame (`all_windows`).

``` r
window_list <- lapply(seq_len(nrow(file_table)), function(i) {

  analyse_track(
    path = file_table$path[i],
    category = file_table$category[i]
  )
})

all_windows <- bind_rows(window_list)

if (nrow(all_windows) == 0) {
  stop("No windows were successfully analysed.")
}
```

# 8. Category-specific ranking and selection of the candidate windows

## 8.1 Ranking scores

Features are standardised within each track
(`group_by(category, source_path)`), the three scores of Section 2.2 are
computed, and the appropriate score is used as `ranking_score` according
to the track’s category. Windows are then ranked from best to worst
within each track (`rank_within_track`).

``` r
ranked_windows <- all_windows %>%
  group_by(category, source_path) %>%
  mutate(
    z_rms = z_safe(rms_dbfs),
    z_flux = z_safe(spectral_flux),
    z_centroid = z_safe(centroid_hz),
    z_tonality = z_safe(tonality),
    z_rms_cv = z_safe(rms_cv),
    z_onset = z_safe(onset_strength),

    # Unpleasant: salient energy changes and spectral activity
    unpleasant_score =
      z_rms + z_flux + z_onset + 0.25 * z_centroid,

    # Pleasant: tonal and relatively continuous sections
    pleasant_score =
      z_tonality - 0.75 * z_flux -
      0.50 * z_onset - 0.25 * z_rms_cv,

    # Neutral: stable sections, with near-silence penalised
    silence_penalty = pmax(
      0,
      (silence_threshold_dbfs - rms_dbfs) / 10
    ),

    neutral_score =
      -z_flux - z_rms_cv - z_onset -
      0.5 * silence_penalty
  ) %>%
  ungroup() %>%
  mutate(
    # The score matching the track's category is the ranking score
    ranking_score = case_when(
      category == "pleasant" ~ pleasant_score,
      category == "unpleasant" ~ unpleasant_score,
      category == "neutral" ~ neutral_score
    )
  ) %>%
  group_by(category, source_path) %>%
  arrange(desc(ranking_score), .by_group = TRUE) %>%
  mutate(rank_within_track = row_number()) %>%
  ungroup() %>%
  arrange(category, source_file, rank_within_track)
```

## 8.2 Export of the full analysis and the rank-1 windows

The complete table (all windows, all features, scores and ranks) is
saved so that every selection can be inspected. The highest-ranked
window of each track is saved separately as the automated candidate.

``` r
write_csv(
  ranked_windows,
  file.path(output_folder, "all_window_features_and_ranks.csv")
)

# Only the highest-ranked window of each track is retained
top_candidates <- ranked_windows %>%
  filter(rank_within_track == 1) %>%
  arrange(category, source_file)

write_csv(
  top_candidates,
  file.path(output_folder, "selected_one_second_windows.csv")
)

cat("\nTracks with selected windows:\n")
print(count(top_candidates, category))

# Every track should yield exactly one candidate
if (nrow(top_candidates) != nrow(file_table)) {
  warning(
    "Some files may not have been analysed. Check warnings and results."
  )
}
```

The columns of interest in `selected_one_second_windows.csv` are
`category`, `source_file`, `start_sec` and `end_sec` (the position of
the selected window), together with the feature values and
`ranking_score`.

# 9. Extraction of exactly one second at each selected start time

Sections 9 to 11 document how the automated candidates were cut from the
recordings and written back into the stimulus folders.

All clips are built and verified **before** any original file is
touched. Each clip is written to a temporary file in the source folder,
and its sample count is checked to equal the sample rate (i.e. exactly 1
s). The clip keeps the original sample rate, bit depth, PCM format and
channel layout.

``` r
# Every temporary clip is built before any original is replaced
temp_files <- character(nrow(top_candidates))
original_files <- top_candidates$source_path

for (i in seq_len(nrow(top_candidates))) {

  source_file <- original_files[i]
  start_sec <- top_candidates$start_sec[i]

  message(
    "\nPreparing: ", basename(source_file),
    " | Start: ", round(start_sec, 4), " seconds"
  )

  wave <- readWave(source_file, header = FALSE)

  # First sample of the selected window
  start_sample <- round(start_sec * wave@samp.rate) + 1

  # Exactly one second of samples
  window_n <- wave@samp.rate
  end_sample <- start_sample + window_n - 1

  if (
    start_sample < 1 ||
    end_sample > length(wave@left)
  ) {
    stop(
      "Cannot extract a complete one-second clip from: ",
      basename(source_file)
    )
  }

  # Left channel
  left_segment <- wave@left[start_sample:end_sample]

  # Right channel (stereo files only)
  if (wave@stereo) {

    if (end_sample > length(wave@right)) {
      stop(
        "Right channel is too short: ",
        basename(source_file)
      )
    }

    right_segment <- wave@right[start_sample:end_sample]

  } else {
    right_segment <- numeric(0)
  }

  # The extracted clip
  clip <- Wave(
    left = left_segment,
    right = right_segment,
    samp.rate = wave@samp.rate,
    bit = wave@bit,
    pcm = wave@pcm
  )

  # The clip is written to a temporary file in the source folder
  temp_file <- tempfile(
    pattern = "selected_clip_",
    tmpdir = dirname(source_file),
    fileext = ".wav"
  )

  writeWave(clip, filename = temp_file)

  # The exact number of samples is verified
  check_clip <- readWave(temp_file, header = FALSE)

  if (length(check_clip@left) != window_n) {
    stop(
      "Incorrect sample count in extracted clip: ",
      basename(source_file)
    )
  }

  if (
    wave@stereo &&
    length(check_clip@right) != window_n
  ) {
    stop(
      "Incorrect right-channel sample count: ",
      basename(source_file)
    )
  }

  temp_files[i] <- temp_file
}
```

# 10. Backup of the original recordings and replacement by the clips

Before any replacement, every original recording is copied into the
time-stamped backup folder, with the category prepended to the file name
(`<category>__<file>.wav`). The backup never overwrites an existing
file, and if any backup fails, the script halts **before** replacing
anything.

``` r
dir.create(
  backup_folder,
  recursive = TRUE,
  showWarnings = FALSE
)

for (i in seq_along(original_files)) {

  backup_name <- paste0(
    top_candidates$category[i],
    "__",
    basename(original_files[i])
  )

  backup_path <- file.path(backup_folder, backup_name)

  success <- file.copy(
    from = original_files[i],
    to = backup_path,
    overwrite = FALSE
  )

  if (!success) {
    stop(
      "Could not back up original file: ",
      original_files[i],
      ". No originals have been replaced."
    )
  }
}

cat("\nAll original files have been backed up.\n")
```

The originals are then overwritten with the extracted clips.

``` r
for (i in seq_along(original_files)) {

  success <- file.copy(
    from = temp_files[i],
    to = original_files[i],
    overwrite = TRUE
  )

  if (!success) {
    stop(
      "Could not replace original file: ",
      original_files[i],
      ". Restore it from the backup folder if necessary."
    )
  }

  message(
    "Replaced: ", basename(original_files[i]),
    " [", top_candidates$category[i], "]"
  )
}
```

# 11. Verification of the final files

Every replaced file is re-read, and its sample count is required to
equal its sample rate (that is, a duration of exactly one second). The
verification table is saved and the temporary files are removed.

``` r
verification <- lapply(seq_along(original_files), function(i) {

  path <- original_files[i]
  wave <- readWave(path, header = FALSE)

  data.frame(
    category = top_candidates$category[i],
    file = basename(path),
    sample_rate = wave@samp.rate,
    sample_count = length(wave@left),
    duration_sec = length(wave@left) / wave@samp.rate,
    file_exists = file.exists(path)
  )
}) %>%
  bind_rows()

print(verification)

# Exact sample-count verification
stopifnot(
  all(verification$sample_count == verification$sample_rate),
  all(verification$file_exists)
)

write_csv(
  verification,
  file.path(output_folder, "final_clip_verification.csv")
)

# Temporary files are removed
file.remove(temp_files)

cat("\n============================================================\n")
cat("SUCCESS: All selected tracks are exactly one second long.\n")
cat("Analysis tables and verification saved to:\n")
cat(output_folder, "\n")
cat("Original recordings backed up to:\n")
cat(backup_folder, "\n")
cat("============================================================\n")
```

# 12. Outputs and reproducibility

The following files are written to `<base_folder>/window_analysis/`:

| File | Content |
|----|----|
| `all_window_features_and_ranks.csv` | Every window of every track with all features, z-scores, scores and within-track rank |
| `selected_one_second_windows.csv` | The rank-1 (automated) window of each track |
| `final_clip_verification.csv` | Sample rate, sample count and duration of every final clip |
| `originals_backup_<timestamp>/` | Copies of the original 6-s recordings |

The analysis depends on the R packages `tuneR`, `dplyr`, `purrr`,
`stringr`, `readr` and `rmarkdown`. The document can be rendered as
follows (analysis only, leaving the stimulus files untouched):

``` r
rmarkdown::render(
  "IADS_analysis.Rmd",
  params = list(
    run               = TRUE,
    replace_originals = FALSE,
    base_folder       = "path/to/exp/assets/collision_sounds"
  )
)
```

> **Note:** the IADS-E sound files are distributed under their own
> licence and are not included in this repository; they must be obtained
> separately from the IADS-E authors.
