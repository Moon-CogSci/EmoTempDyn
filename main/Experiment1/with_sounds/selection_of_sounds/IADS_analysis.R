
# ============================================================
# COMPLETE AUDIO ANALYSIS AND ONE-SECOND CLIP EXTRACTION
# ============================================================
# 1. Scan pleasant, unpleasant and neutral folders
# 2. Generate overlapping 1-second windows every 100 ms
# 3. Calculate acoustic features
# 4. Rank windows separately for each category
# 5. Select the top candidate from every track
# 6. Back up original recordings
# 7. Replace originals with selected 1-second clips
# 8. Verify the final files
# ============================================================

library(tuneR)
library(dplyr)
library(purrr)
library(stringr)
library(readr)

# ------------------------------------------------------------
# 1. PATHS AND SETTINGS
# ------------------------------------------------------------

base_folder <- "C:/Users/Acer/Downloads/exp/assets/collision_sounds"

category_folders <- c(
  pleasant   = file.path(base_folder, "pleasant"),
  unpleasant = file.path(base_folder, "unpleasant"),
  neutral    = file.path(base_folder, "neutral")
)

output_folder <- file.path(base_folder, "window_analysis")

# Create a unique backup folder for this run
backup_folder <- file.path(
  output_folder,
  paste0("originals_backup_", format(Sys.time(), "%Y%m%d_%H%M%S"))
)

dir.create(output_folder, recursive = TRUE, showWarnings = FALSE)

window_seconds <- 1
step_seconds <- 0.1
frame_seconds <- 0.1

# Provisional neutral-window silence threshold
silence_threshold_dbfs <- -45


# ------------------------------------------------------------
# 2. HELPER FUNCTION: SAFE Z-SCORES
# ------------------------------------------------------------

z_safe <- function(x) {
  
  s <- sd(x, na.rm = TRUE)
  
  if (!is.finite(s) || s == 0) {
    return(rep(0, length(x)))
  }
  
  (x - mean(x, na.rm = TRUE)) / s
}


# ------------------------------------------------------------
# 3. CALCULATE FEATURES FOR EACH ONE-SECOND WINDOW
# ------------------------------------------------------------

window_features <- function(x, sample_rate) {
  
  eps <- 1e-12
  frame_n <- round(frame_seconds * sample_rate)
  
  frame_starts <- seq(
    from = 1,
    to = length(x) - frame_n + 1,
    by = frame_n
  )
  
  frames <- lapply(frame_starts, function(start) {
    x[start:(start + frame_n - 1)]
  })
  
  frame_results <- lapply(frames, function(frame) {
    
    n <- length(frame)
    
    spectrum <- Mod(fft(frame))[seq_len(floor(n / 2) + 1)]
    power <- spectrum^2
    
    frequencies <- (0:floor(n / 2)) * sample_rate / n
    
    # Exclude DC component
    power <- power[-1]
    frequencies <- frequencies[-1]
    
    centroid <- sum(frequencies * power) /
      (sum(power) + eps)
    
    flatness <- exp(mean(log(power + eps))) /
      (mean(power) + eps)
    
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
  
  # Spectral flux between consecutive 100-ms frames
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
  
  # Energy variability and onset strength
  rms_mean <- mean(frame_rms)
  
  rms_cv <- sd(frame_rms) / (rms_mean + eps)
  
  onset_strength <- max(
    c(0, diff(frame_rms))
  ) / (rms_mean + eps)
  
  window_rms <- sqrt(mean(x^2))
  window_peak <- max(abs(x))
  
  rms_dbfs <- 20 * log10(window_rms + eps)
  peak_dbfs <- 20 * log10(window_peak + eps)
  
  # Zero-crossing rate
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


# ------------------------------------------------------------
# 4. ANALYSE A TRACK AND GENERATE ALL WINDOWS
# ------------------------------------------------------------

analyse_track <- function(path, category) {
  
  message("Analysing: ", category, " | ", basename(path))
  
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
  
  # Convert to mono for feature analysis
  left <- as.numeric(wave@left)
  
  if (wave@stereo) {
    audio <- (left + as.numeric(wave@right)) / 2
  } else {
    audio <- left
  }
  
  sample_rate <- wave@samp.rate
  
  # Convert PCM samples to approximately [-1, 1]
  audio <- audio / (2^(wave@bit - 1))
  
  # Remove DC offset
  audio <- audio - mean(audio)
  
  window_n <- round(window_seconds * sample_rate)
  step_n <- round(step_seconds * sample_rate)
  
  if (length(audio) < window_n) {
    warning("Track shorter than one second: ", basename(path))
    return(NULL)
  }
  
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


# ------------------------------------------------------------
# 5. DISCOVER FILES IN THE THREE CATEGORY FOLDERS
# ------------------------------------------------------------

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


# ------------------------------------------------------------
# 6. GENERATE AND COMBINE ALL WINDOW FEATURES
# ------------------------------------------------------------

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


# ------------------------------------------------------------
# 7. CALCULATE CATEGORY-SPECIFIC RANKING SCORES
# ------------------------------------------------------------

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
    
    # Neutral: stable sections, penalizing near-silence
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


# ------------------------------------------------------------
# 8. EXPORT ANALYSIS AND SELECT RANK-1 WINDOWS
# ------------------------------------------------------------

write_csv(
  ranked_windows,
  file.path(output_folder, "all_window_features_and_ranks.csv")
)

# Select only the highest-ranked window from each track
top_candidates <- ranked_windows %>%
  filter(rank_within_track == 1) %>%
  arrange(category, source_file)

write_csv(
  top_candidates,
  file.path(output_folder, "selected_one_second_windows.csv")
)

cat("\nTracks with selected windows:\n")
print(count(top_candidates, category))

if (nrow(top_candidates) != nrow(file_table)) {
  warning(
    "Some files may not have been analysed. Check warnings and results."
  )
}


# ------------------------------------------------------------
# 9. PREPARE EXACTLY ONE SECOND FROM EACH SELECTED START TIME
# ------------------------------------------------------------

# Build every temporary clip before replacing any originals
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
  
  # Extract left channel
  left_segment <- wave@left[start_sample:end_sample]
  
  # Extract right channel if stereo
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
  
  # Create the extracted clip
  clip <- Wave(
    left = left_segment,
    right = right_segment,
    samp.rate = wave@samp.rate,
    bit = wave@bit,
    pcm = wave@pcm
  )
  
  # Write to temporary file in the source folder
  temp_file <- tempfile(
    pattern = "selected_clip_",
    tmpdir = dirname(source_file),
    fileext = ".wav"
  )
  
  writeWave(clip, filename = temp_file)
  
  # Verify the exact number of samples
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


# ------------------------------------------------------------
# 10. BACK UP ORIGINAL RECORDINGS
# ------------------------------------------------------------

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


# ------------------------------------------------------------
# 11. REPLACE ORIGINAL TRACKS WITH ONE-SECOND CLIPS
# ------------------------------------------------------------

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


# ------------------------------------------------------------
# 12. VERIFY THE REPLACED WAV FILES
# ------------------------------------------------------------

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

# Remove temporary files
file.remove(temp_files)

cat("\n============================================================\n")
cat("SUCCESS: All selected tracks are exactly one second long.\n")
cat("Analysis tables and verification saved to:\n")
cat(output_folder, "\n")
cat("Original recordings backed up to:\n")
cat(backup_folder, "\n")
cat("============================================================\n")
