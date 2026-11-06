library(readxl)
library(dplyr)
library(stringr)

# --------------------------------------------------
# 1. SETTINGS
# --------------------------------------------------

sound_root <- "C:/Users/Acer/Downloads/IADS-E/IADS-E_sounds"

id_col <- "Sound ID"
category_col <- "Category"

# Read dataset and calculate scores
iads <- read_xlsx(
  "C:/Users/Acer/Downloads/IADS-E/Sound Ratings.xlsx"
) %>%
  mutate(
    n_score = AroMN + (9 - ValMN) + FearMN,
    p_score = AroMN + ValMN + HapMN
  )

# --------------------------------------------------
# 2. FIND FILE ONLY INSIDE THE CORRECT CATEGORY FOLDER
# --------------------------------------------------

find_sound_file <- function(id, category) {
  
  if (is.na(id) || is.na(category)) {
    return(NA_character_)
  }
  
  id <- trimws(as.character(id))
  category <- trimws(as.character(category))
  
  # Locate the category folder, ignoring case
  folders <- list.dirs(
    sound_root,
    recursive = FALSE,
    full.names = TRUE
  )
  
  category_folder <- folders[
    tolower(basename(folders)) == tolower(category)
  ]
  
  # Reject if the required category folder does not exist
  if (length(category_folder) == 0) {
    return(NA_character_)
  }
  
  # Search WAV files only inside the correct category folder
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
  
  # Remove extensions and the conventional _2 suffix
  stems <- tools::file_path_sans_ext(basename(files))
  stems <- str_remove(stems, regex("_2$", ignore_case = TRUE))
  
  # Handle zero-padded numeric IDs, e.g. 815 -> 0815
  candidates <- id
  
  if (str_detect(id, "^\\d+$")) {
    candidates <- unique(c(
      id,
      sprintf("%04d", as.numeric(id))
    ))
  }
  
  # Exact ID match, preserving identifiers such as 1115_b
  matched <- which(
    tolower(stems) %in% tolower(candidates)
  )
  
  if (length(matched) == 0) {
    return(NA_character_)
  }
  
  # Return the matching file from this category only
  files[matched[1]]
}


# --------------------------------------------------
# 3. RECURSIVE SELECTION FUNCTION
# --------------------------------------------------

select_top_recursive <- function(
    data,
    n = 10,
    index = 1,
    selected = NULL) {
  
  # Stop after selecting n valid sounds or exhausting data
  if (index > nrow(data) ||
      (!is.null(selected) && nrow(selected) >= n)) {
    
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
  
  # Require both ID and category to match
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
  
  # Examine the next candidate
  select_top_recursive(
    data = data,
    n = n,
    index = index + 1,
    selected = selected
  )
}


# --------------------------------------------------
# 4. SELECT TOP 10 NEGATIVE SOUNDS
# --------------------------------------------------

iads_negative_sorted <- iads %>%
  arrange(desc(n_score))

top10_negative_sounds <- select_top_recursive(
  data = iads_negative_sorted,
  n = 10
)


# --------------------------------------------------
# 5. SELECT TOP 10 POSITIVE SOUNDS
# --------------------------------------------------

iads_positive_sorted <- iads %>%
  arrange(desc(p_score))

top10_positive_sounds <- select_top_recursive(
  data = iads_positive_sorted,
  n = 10
)


# --------------------------------------------------
# 6. SELECT TOP 10 NEUTRAL, LOW-AROUSAL SOUNDS
# --------------------------------------------------

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


# --------------------------------------------------
# 7. VERIFY AND SAVE RESULTS
# --------------------------------------------------

stopifnot(
  all(file.exists(top10_negative_sounds$wav_path)),
  all(file.exists(top10_positive_sounds$wav_path)),
  all(file.exists(top10_neutral_sounds$wav_path))
)

write.csv(
  top10_negative_sounds,
  "C:/Users/Acer/Downloads/IADS-E/top10_negative_sounds.csv",
  row.names = FALSE
)

write.csv(
  top10_positive_sounds,
  "C:/Users/Acer/Downloads/IADS-E/top10_positive_sounds.csv",
  row.names = FALSE
)

write.csv(
  top10_neutral_sounds,
  "C:/Users/Acer/Downloads/IADS-E/top10_neutral_sounds.csv",
  row.names = FALSE
)

# Final selection counts
cat("\nNegative sounds selected:",
    nrow(top10_negative_sounds), "\n")

cat("Positive sounds selected:",
    nrow(top10_positive_sounds), "\n")

cat("Neutral sounds selected:",
    nrow(top10_neutral_sounds), "\n")

# ==========================================
# COPY SELECTED SOUNDS INTO EXP ASSETS
# ==========================================


library(dplyr)


pleasant_folder <- "C:/Users/Acer/Downloads/exp/assets/collision_sounds/pleasant"
unpleasant_folder <- "C:/Users/Acer/Downloads/exp/assets/collision_sounds/unpleasant"
neutral_folder <- "C:/Users/Acer/Downloads/exp/assets/collision_sounds/neutral"

dir.create(pleasant_folder, recursive = TRUE, showWarnings = FALSE)
dir.create(unpleasant_folder, recursive = TRUE, showWarnings = FALSE)
dir.create(neutral_folder, recursive = TRUE, showWarnings = FALSE)


# ==========================================
# 2. COPY NEWLY SELECTED SOUNDS
# ==========================================

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
  
  # Remove old WAV files so only the new selection remains
  old_files <- list.files(
    destination_folder,
    pattern = "\\.wav$",
    full.names = TRUE,
    ignore.case = TRUE
  )
  
  if (length(old_files) > 0) {
    file.remove(old_files)
  }
  
  # Get the new selected source paths
  source_files <- unique(data$wav_path)
  
  # Retain only existing source files
  source_files <- source_files[
    !is.na(source_files) & file.exists(source_files)
  ]
  
  if (length(source_files) == 0) {
    stop(category, ": No valid source sound files found.")
  }
  
  # Preserve original filenames
  destination_files <- file.path(
    destination_folder,
    basename(source_files)
  )
  
  # Copy the selected files
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


# ==========================================
# 3. COPY THE NEW TOP 10 SELECTIONS
# ==========================================

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


# ==========================================
# 4. VERIFY FINAL FILE COUNTS
# ==========================================

cat("\n--- Pleasant sounds ---\n")
print(list.files(pleasant_folder, pattern = "\\.wav$", ignore.case = TRUE))
cat("Total:", length(list.files(pleasant_folder, pattern = "\\.wav$", ignore.case = TRUE)), "\n")

cat("\n--- Unpleasant sounds ---\n")
print(list.files(unpleasant_folder, pattern = "\\.wav$", ignore.case = TRUE))
cat("Total:", length(list.files(unpleasant_folder, pattern = "\\.wav$", ignore.case = TRUE)), "\n")

cat("\n--- Neutral sounds ---\n")
print(list.files(neutral_folder, pattern = "\\.wav$", ignore.case = TRUE))
cat("Total:", length(list.files(neutral_folder, pattern = "\\.wav$", ignore.case = TRUE)), "\n")
