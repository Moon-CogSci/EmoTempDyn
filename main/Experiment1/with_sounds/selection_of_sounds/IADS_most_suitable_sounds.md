Selecting the Most Suitable IADS-E Sounds for the Collision Task
================

- [1. Purpose](#1-purpose)
- [2. Method overview](#2-method-overview)
- [3. Setup](#3-setup)
- [4. Locating a sound file (the screening
  step)](#4-locating-a-sound-file-the-screening-step)
- [5. Recursive selection of the top *n* valid
  sounds](#5-recursive-selection-of-the-top-n-valid-sounds)
- [6. Selection of the three sets](#6-selection-of-the-three-sets)
  - [6.1 Ten unpleasant sounds (main
    phase)](#61-ten-unpleasant-sounds-main-phase)
  - [6.2 Ten pleasant sounds (main
    phase)](#62-ten-pleasant-sounds-main-phase)
  - [6.3 Ten neutral, low-arousal sounds (practice phase and
    tutorial)](#63-ten-neutral-low-arousal-sounds-practice-phase-and-tutorial)
- [7. Verification and saving of the
  results](#7-verification-and-saving-of-the-results)
- [8. Copying the selected sounds into the experiment’s
  assets](#8-copying-the-selected-sounds-into-the-experiments-assets)
  - [Final check of the destination
    folders](#final-check-of-the-destination-folders)
- [9. Reproducibility](#9-reproducibility)

# 1. Purpose

This document describes how the emotional sounds used in the **collision
experiment** (`collision_pilot.py`, with its tutorial
`collision_pilot_tutorial.py`) were chosen from the **IADS-E**
(International Affective Digitized Sounds, Expanded) database.

In the task, participants watch two moving circles and hear a sound if
they collide. The sound can be **pleasant**, **unpleasant** or (in
practice) **neutral**. We therefore need three small, clean sets of
sounds:

| Set | \# sounds | Used in | Destination folder |
|----|----|----|----|
| Pleasant | 10 | **Main phase** of `collision_pilot.py` | `assets/collision_sounds/pleasant/` |
| Unpleasant | 10 | **Main phase** of `collision_pilot.py` | `assets/collision_sounds/unpleasant/` |
| Neutral (low-arousal) | 10 | **Practice phase** of `collision_pilot.py` and example trials of `collision_pilot_tutorial.py` | `assets/collision_sounds/neutral/` |

How the Python scripts use these folders:

- **Main phase** – 50 pleasant and 50 unpleasant collisions. Each of the
  10 files in a folder is scheduled exactly five times, in shuffled
  order.
- **Practice phase** – all 10 neutral files are used. A random 6–8 are
  assigned to the high-collision-probability block and the rest to the
  low-probability block, with files repeated as evenly as needed.
- **Tutorial** – example-trial collisions always play a neutral sound,
  whatever the trial’s condition.

# 2. Method overview

The IADS-E spreadsheet (`Sound Ratings.xlsx`) contains mean normative
ratings for every sound. The columns used here are:

| Column | Meaning |
|----|----|
| `Sound ID` | Numeric / alphanumeric sound ID (e.g. `815`, `1115_b`) |
| `Category` | Sound category (matches a sub-folder of the sound directory) |
| `ValMN` | Mean **valence** rating (1 = very unpleasant, 9 = very pleasant) |
| `AroMN` | Mean **arousal** rating (1 = calm, 9 = excited) |
| `HapMN` | Mean **happiness** rating |
| `FearMN` | Mean **fear** rating |

**Ranking scores**

- **Unpleasant score** `n_score = AroMN + (9 - ValMN) + FearMN` – high
  for sounds that are arousing, low in valence and frightening.
- **Pleasant score** `p_score = AroMN + ValMN + HapMN` – high for sounds
  that are arousing, high in valence and happy.
- **Neutral distance** `sqrt((ValMN - 5)^2 + (AroMN - 1)^2)` – distance
  from the “neutral, calm” point of the valence–arousal space (mid
  valence, lowest arousal). *Smaller is better.*

**Why a screening step is needed**

The spreadsheet and the actual sound folders do not fully agree:

1.  Some sounds listed in the spreadsheet **do not exist** in the
    downloaded sound folders.
2.  For some IDs, the spreadsheet’s description/category **does not
    match** the sound that actually carries that ID in the folders.

So we cannot just take the top 10 rows of each ranking. Instead, each
ranked candidate is **verified** before it is accepted: its sound ID
must be found as a `.wav` file **inside the sub-folder named after the
category the spreadsheet lists for it**. A candidate failing this check
is skipped, and the next-ranked sound is tried, until 10 valid sounds
are collected for each set.

> **Limitation:** this check establishes only that the ID/category pair
> is consistent with the folder structure. It does not assess whether
> the audio content actually corresponds to its description.

**Pipeline**

1.  The ratings were read and the three scores computed.
2.  The sounds were ranked by each score.
3.  Each ranking was traversed with a recursive function, retaining only
    candidates whose `.wav` file was found in the correct category
    folder, until 10 were retained.
4.  The existence of the files was verified and each set was saved to
    CSV.
5.  The 30 selected `.wav` files were copied into the experiment’s
    `assets` folders.

# 3. Setup

``` r
library(readxl)   # read the Excel ratings sheet
library(dplyr)    # data manipulation
library(stringr)  # string helpers for matching sound IDs
```

All paths are supplied through the `params` in the YAML header of this
file (or through `rmarkdown::render(params = list(...))`).

``` r
# Root folder that contains one sub-folder per IADS-E category
sound_root <- params$sound_root

# Column names in the ratings sheet
id_col       <- "Sound ID"
category_col <- "Category"

# Ratings are read and the ranking scores computed
iads <- read_xlsx(params$ratings_xlsx) %>%
  mutate(
    # Unpleasant: high arousal + low valence (reversed on the 1-9 scale) + high fear
    n_score = AroMN + (9 - ValMN) + FearMN,
    # Pleasant: high arousal + high valence + high happiness
    p_score = AroMN + ValMN + HapMN
  )
```

# 4. Locating a sound file (the screening step)

`find_sound_file()` returns the full path of the `.wav` file for a given
`id` **only if it is in the folder of the stated `category`**; otherwise
it returns `NA`. This is what removes sounds that are missing or whose
spreadsheet description does not match the sound folders.

``` r
find_sound_file <- function(id, category) {

  # Missing ID or category -> cannot be verified
  if (is.na(id) || is.na(category)) {
    return(NA_character_)
  }

  id       <- trimws(as.character(id))
  category <- trimws(as.character(category))

  # The category folder is located, ignoring case
  folders <- list.dirs(
    sound_root,
    recursive = FALSE,
    full.names = TRUE
  )

  category_folder <- folders[
    tolower(basename(folders)) == tolower(category)
  ]

  # The candidate is rejected if the required category folder does not exist
  if (length(category_folder) == 0) {
    return(NA_character_)
  }

  # WAV files are searched for only inside the correct category folder
  files <- list.files(
    category_folder[1],
    pattern = "\\.wav$",
    recursive = TRUE,
    full.names = TRUE,
    ignore.case = TRUE
  )

  if (length(files) == 0) {
    return(NA_character_)
  }

  # Extensions and the conventional "_2" suffix are removed from file names
  stems <- tools::file_path_sans_ext(basename(files))
  stems <- str_remove(stems, regex("_2$", ignore_case = TRUE))

  # Zero-padded numeric IDs are also considered, e.g. 815 -> 0815
  candidates <- id

  if (str_detect(id, "^\\d+$")) {
    candidates <- unique(c(
      id,
      sprintf("%04d", as.numeric(id))
    ))
  }

  # Exact ID match (identifiers such as 1115_b are preserved)
  matched <- which(
    tolower(stems) %in% tolower(candidates)
  )

  if (length(matched) == 0) {
    return(NA_character_)
  }

  # The matching file from this category only is returned
  files[matched[1]]
}
```

# 5. Recursive selection of the top *n* valid sounds

`select_top_recursive()` takes a data frame **already sorted from best
to worst**. It examines one candidate at a time:

- if a valid `.wav` is found, the row (plus a new `wav_path` column) is
  added to `selected`;
- otherwise it is skipped (and logged);
- it then calls itself on the next row, stopping once `n` sounds have
  been selected or the candidates run out.

``` r
select_top_recursive <- function(
    data,
    n = 10,
    index = 1,
    selected = NULL) {

  # Recursion ends once n valid sounds are selected or the data are exhausted
  if (index > nrow(data) ||
      (!is.null(selected) && nrow(selected) >= n)) {

    # An empty, correctly shaped data frame is returned if nothing was selected
    if (is.null(selected)) {
      selected <- data[0, , drop = FALSE]
      selected$wav_path <- character(0)
    }

    return(selected)
  }

  # Current candidate in ranked order
  current <- data[index, , drop = FALSE]

  sound_id <- current[[id_col]][1]
  category <- current[[category_col]][1]

  # Both ID and category must match a real file
  sound_path <- find_sound_file(sound_id, category)

  if (!is.na(sound_path)) {

    current$wav_path <- sound_path

    if (is.null(selected)) {
      selected <- current
    } else {
      selected <- bind_rows(selected, current)
    }

    message(
      "SELECTED | ID: ", sound_id,
      " | Category: ", category,
      " | File: ", basename(sound_path)
    )

  } else {

    message(
      "SKIPPED | ID: ", sound_id,
      " | Expected folder: ", category,
      " | Reason: no matching file in correct category folder"
    )
  }

  # The next candidate is examined
  select_top_recursive(
    data = data,
    n = n,
    index = index + 1,
    selected = selected
  )
}
```

# 6. Selection of the three sets

## 6.1 Ten unpleasant sounds (main phase)

Ranked by `n_score`, highest first.

``` r
iads_negative_sorted <- iads %>%
  arrange(desc(n_score))

top10_negative_sounds <- select_top_recursive(
  data = iads_negative_sorted,
  n = 10
)
```

## 6.2 Ten pleasant sounds (main phase)

Ranked by `p_score`, highest first.

``` r
iads_positive_sorted <- iads %>%
  arrange(desc(p_score))

top10_positive_sounds <- select_top_recursive(
  data = iads_positive_sorted,
  n = 10
)
```

## 6.3 Ten neutral, low-arousal sounds (practice phase and tutorial)

Ranked by distance from the point valence = 5, arousal = 1 (emotionally
neutral and calm), smallest first. Low arousal was chosen deliberately
so that practice and tutorial sounds would not induce emotion that could
contaminate the main-phase ratings.

``` r
iads_neutral_sorted <- iads %>%
  mutate(
    neutral_distance = sqrt(
      (ValMN - 5)^2 +
        (AroMN - 1)^2
    )
  ) %>%
  arrange(neutral_distance)

top10_neutral_sounds <- select_top_recursive(
  data = iads_neutral_sorted,
  n = 10
)
```

# 7. Verification and saving of the results

The script halts with an error if any selected file is missing.
Otherwise, one CSV per set is saved (all rating columns plus the
`wav_path` of the sound file).

``` r
stopifnot(
  all(file.exists(top10_negative_sounds$wav_path)),
  all(file.exists(top10_positive_sounds$wav_path)),
  all(file.exists(top10_neutral_sounds$wav_path))
)

write.csv(
  top10_negative_sounds,
  file.path(params$output_dir, "top10_negative_sounds.csv"),
  row.names = FALSE
)

write.csv(
  top10_positive_sounds,
  file.path(params$output_dir, "top10_positive_sounds.csv"),
  row.names = FALSE
)

write.csv(
  top10_neutral_sounds,
  file.path(params$output_dir, "top10_neutral_sounds.csv"),
  row.names = FALSE
)

# Final selection counts (each is expected to be 10)
cat("\nNegative sounds selected:", nrow(top10_negative_sounds), "\n")
cat("Positive sounds selected:", nrow(top10_positive_sounds), "\n")
cat("Neutral sounds selected:",  nrow(top10_neutral_sounds),  "\n")
```

The chosen sounds and their ratings are listed below.

``` r
cols <- c(id_col, category_col, "ValMN", "AroMN", "HapMN", "FearMN")

cat("Unpleasant (main phase)\n")
print(top10_negative_sounds[, intersect(cols, names(top10_negative_sounds))])

cat("\nPleasant (main phase)\n")
print(top10_positive_sounds[, intersect(cols, names(top10_positive_sounds))])

cat("\nNeutral (practice / tutorial)\n")
print(top10_neutral_sounds[, intersect(cols, names(top10_neutral_sounds))])
```

# 8. Copying the selected sounds into the experiment’s assets

`collision_pilot.py` reads three flat folders under
`assets/collision_sounds/`. The sounds are copied there, **keeping their
original file names**.

``` r
pleasant_folder   <- file.path(params$assets_dir, "pleasant")
unpleasant_folder <- file.path(params$assets_dir, "unpleasant")
neutral_folder    <- file.path(params$assets_dir, "neutral")

dir.create(pleasant_folder,   recursive = TRUE, showWarnings = FALSE)
dir.create(unpleasant_folder, recursive = TRUE, showWarnings = FALSE)
dir.create(neutral_folder,    recursive = TRUE, showWarnings = FALSE)
```

`copy_selected_sounds()` first **deletes any old `.wav` files** in the
destination folder so only the new selection remains, then copies the
new files and reports whether each copy succeeded.

``` r
copy_selected_sounds <- function(data, destination_folder, category) {

  if (!"wav_path" %in% names(data)) {
    stop(category, ": wav_path column is missing.")
  }

  if (nrow(data) != 10) {
    warning(
      category, ": Expected 10 selected sounds, but received ",
      nrow(data), "."
    )
  }

  # Old WAV files are removed so that only the new selection remains
  old_files <- list.files(
    destination_folder,
    pattern = "\\.wav$",
    full.names = TRUE,
    ignore.case = TRUE
  )

  if (length(old_files) > 0) {
    file.remove(old_files)
  }

  # The newly selected source paths are collected
  source_files <- unique(data$wav_path)

  # Only existing source files are retained
  source_files <- source_files[
    !is.na(source_files) & file.exists(source_files)
  ]

  if (length(source_files) == 0) {
    stop(category, ": No valid source sound files found.")
  }

  # Original filenames are preserved
  destination_files <- file.path(
    destination_folder,
    basename(source_files)
  )

  # The selected files are copied
  copied <- file.copy(
    from = source_files,
    to = destination_files,
    overwrite = TRUE
  )

  results <- data.frame(
    category = category,
    source = source_files,
    destination = destination_files,
    copied = copied
  )

  print(results)

  cat(
    "\n", category, ": ",
    sum(copied), " of ", length(source_files),
    " files copied successfully.\n",
    sep = ""
  )

  if (any(!copied)) {
    warning("Some files failed to copy for ", category)
  }

  invisible(results)
}
```

``` r
pleasant_results <- copy_selected_sounds(
  data = top10_positive_sounds,
  destination_folder = pleasant_folder,
  category = "Pleasant"
)

unpleasant_results <- copy_selected_sounds(
  data = top10_negative_sounds,
  destination_folder = unpleasant_folder,
  category = "Unpleasant"
)

neutral_results <- copy_selected_sounds(
  data = top10_neutral_sounds,
  destination_folder = neutral_folder,
  category = "Neutral"
)
```

## Final check of the destination folders

Each folder is expected to contain exactly 10 `.wav` files.

``` r
folders_to_check <- list(
  Pleasant   = pleasant_folder,
  Unpleasant = unpleasant_folder,
  Neutral    = neutral_folder
)

for (label in names(folders_to_check)) {
  files <- list.files(
    folders_to_check[[label]],
    pattern = "\\.wav$",
    ignore.case = TRUE
  )
  cat("\n---", label, "sounds ---\n")
  print(files)
  cat("Total:", length(files), "\n")
}
```

# 9. Reproducibility

The analysis requires the IADS-E database (the `Sound Ratings.xlsx` file
and the `IADS-E_sounds` folder, with one sub-folder per category) and
the R packages `readxl`, `dplyr`, `stringr` and `rmarkdown`. The
document can be rendered with user-specific paths as follows:

``` r
rmarkdown::render(
  "IADS_most_suitable_sounds.Rmd",
  params = list(
    run          = TRUE,
    sound_root   = "path/to/IADS-E/IADS-E_sounds",
    ratings_xlsx = "path/to/IADS-E/Sound Ratings.xlsx",
    output_dir   = "path/to/IADS-E",
    assets_dir   = "path/to/exp/assets/collision_sounds"
  )
)
```

`collision_pilot.py` loads the sounds automatically from
`assets/collision_sounds/{pleasant,unpleasant,neutral}`.

> **Note:** the IADS-E sound files are distributed under their own
> licence and are not included in this repository; they must be obtained
> separately from the IADS-E authors.
