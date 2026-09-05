# Discrete Signals

A four-stage pipeline for cricket, katydid, and frog recordings: scrape
recordings and metadata from SINA and Xeno-Canto, generate or OCR each
recording's spectrogram, run it through image-processing detection to extract
acoustic parameters (pulse length, gap timing, burst structure), then browse
the results in an interactive viewer.

Everything lives in "Code/"; paths below are relative to that folder
unless noted.

## Setup

```bash
pip install -r requirements.txt
```

- **Tesseract** (for the cricket pipeline's x-axis OCR) is a separate install:
  `brew install tesseract` on macOS.
- **`XENO_CANTO_API_KEY`**: a free key from [xeno-canto.org](https://xeno-canto.org/),
  needed for the frog metadata pull in `Webscraping.ipynb`.
  `export XENO_CANTO_API_KEY="your-key"`

The notebooks read and write under `~/Discrete_Signals/`--downloaded
recordings, generated images, result CSVs. None of that is in the repo;
`Webscraping.ipynb` recreates it from scratch.

## Run order

Three independent tracks--crickets, katydids, frogs--each run top to
bottom. Katydids and frogs each have a "single-burst" and a
"multiple-burst-type" notebook; the multi-burst ones are standalone copies
that never touch the single-burst notebooks' files, so run whichever
variant(s) you actually want.

```
Webscraping.ipynb                                   (run first--feeds all three tracks)
│
├─ Crickets:  Processing_Cricket_Spectrograms.ipynb
│             range_map_processing.ipynb    (optional--cricket range-map coverage/overlap)
│
├─ Katydids:  Processing_Katydid_Spectrograms.ipynb                 (single-burst)
│             Processing_Katydid_Spectrograms_Multiple_Bursts.ipynb (multi-burst-type)
│
└─ Frogs:     Frog_Clip_Log.ipynb
              → Processing_Frog_Spectrograms.ipynb                  (single-burst)
              → Processing_Frog_Spectrograms_Multiple_Bursts.ipynb  (multi-burst-type)

Viewers (run after the pipeline they read from):
  Display_Function.ipynb               : cricket / katydid(multi) / frog(multi) browsers
  Katydid_Genus_Display_Function.ipynb : katydid genus spot-checker
  Frog_Genus_Display_Function.ipynb    : frog genus spot-checker
  Frog_Species_Display_Function.ipynb  : frog species spot-checker
```

DataFrames pass between notebooks via IPython's `%store`, which only lives
for one kernel session--if a notebook errors on `%store -r`, run its
upstream notebook first in the same session. The frog pipeline is the
exception: both frog processing notebooks rebuild `clips_ready` straight from
`frog_clip_log.csv` on disk instead.

## Pipeline stages

### 1. `Webscraping.ipynb`

Crickets and katydids come from [SINA](https://orthsoc.org/sina/), one page
per species. Frogs come from the [Xeno-Canto](https://xeno-canto.org) API
instead, which returns clean JSON--no HTML to parse. Produces `cricket_df`,
`katydid_df`, `frog_df`, then downloads every referenced spectrogram, audio
file, and range map into `~/Discrete_Signals/{Crickets,Katydids,Frogs}/`.

| DataFrame | Key columns | Consumed by |
|---|---|---|
| `cricket_df` | Species, URL, Spectrogram, Audio_Link, Description of Whole Audio File, Temperature (°C), Location, Map | `Processing_Cricket_Spectrograms.ipynb` |
| `katydid_df` | Species, URL, Spectrogram, Audio_Link, Description, Temperature (°C), Location, Map | Both katydid notebooks |
| `frog_df` | Genus, Species, Country, Location, Latitude, Longitude, Call Type, File, Spectrogram | `Frog_Clip_Log.ipynb` |

**Functions:**
- `scrape_sina(list_url)`: scrapes every species on a SINA list page into one DataFrame, built from the helpers below it.
- `get_species_list`, `fetch_soup`, `find_range_map_url`, `parse_temperature`, `parse_location`, `extract_recordings`: the pieces `scrape_sina` is made of.
- `review_locations` / `apply_reviewed_locations`: the manual location cleanup pass, and the loader that re-applies its saved results from `data/*_locations_reviewed.csv`.
- `fetch_frog_recordings()`: pages through the Xeno-Canto `grp:frogs` results.
- `file_id_from_url`, `download_asset`, `download_sina_assets`, `download_frog_audio`: download everything a scraped row points to into the right folder.

---

### 2. `Processing_Cricket_Spectrograms.ipynb` (crickets)

Reads every downloaded spectrogram, OCRs the x-axis to get the time span, and
runs it through detection to get four numbers per file. Hapithus melodius
is skipped--its chirps speed up over a call, and the model here assumes a
steady rhythm.

| Column | Description |
|---|---|
| `Element_Length` | Mean element (pulse) duration in seconds |
| `Inter-Element_Interval` | Mean within-burst gap in seconds; equals mean gap for trill species |
| `Inter-Burst_Interval` | Mean between-burst gap in seconds; 0 for trill/single-element species |
| `Elements_Per_Burst` | Median elements per burst; 1 for trill species |

**Output:** `Crickets/cricket_results.csv` (raw), `cricket.csv` (merged, final).

**Functions:**
- `read_x_axis_seconds` (+ `ocr_number_from_crop`): reads the time span off the image via OCR, with a fallback line fit across several labels.
- `locate_signal_band`: crickets are narrowband, so this finds the row range where the call's energy actually lives.
- `detect_signal_list_adaptive`: turns ink into a binary on/off signal by trying a ladder of thresholds and keeping the best-scoring one.
- `classify_intervals`: splits the off-gaps into inter-element vs. inter-burst and returns the four numbers above.
- `cricket_process`: runs one file through the whole thing.
- `gaussian_filter1d`, `silhouette`, `kmeans2`, `choose_k`, `rle`, `clean_signal_runs`, `group_consecutive`: small shared helpers (smoothing, clustering, run-length encoding).
- `spec_id_from_url` / `spec_id_from_filename`: pull the join key out of a SINA URL or local filename.

---

### 3. `Processing_Katydid_Spectrograms.ipynb` (katydids, single-burst)

SINA's katydid spectrograms are too inconsistent to OCR reliably, so this
notebook generates its own oscillogram from each species' downloaded audio
instead. Audio gets cropped to its active span first, which frees up enough
resolution to catch the short gaps between elements. Same four numbers as the
cricket pipeline, plus the min and max elements found in any one burst.

**Output:** `Katydids/katydid_results.csv` (raw), `katydid_single_burst_type.csv` (merged, final).

**Functions:**
- `compute_signal_crop`: finds where the real signal starts and ends, so lead-in/lead-out silence gets trimmed without touching the inter-burst gaps being measured.
- `generate_spectrogram_image`: bandpass-filters the clip around its dominant frequency and saves a filled oscillogram.
- `extract_outer_band_ink` / `find_centerline_row`: measure ink while excluding just a thin band around the baseline, so quiet elements near zero amplitude still register.
- `detect_signal_list_adaptive`: same threshold-ladder idea as crickets, with an extra fallback stage for continuous trills.
- `rescue_quiet_bursts`: recovers a burst that's real but too quiet next to a much louder one in the same recording.
- `classify_intervals`: same as crickets, plus min/max elements per burst.
- `detect_audio_elements` / `select_crop_window`: pick a clean crop window for the handful of species whose recordings are too long or multi-scale for normal detection.
- `katydid_process`: runs one audio file through the whole thing; `process_eremopedes_covilleae` is a one-off variant for a species whose gaps the default settings were merging.
- `spec_id_from_url`, `spec_id_from_filename`, `audio_id_from_url`, `audio_id_from_filename`, `generated_spectrogram_path`: id/path helpers for the join and the generated-image cache.
- Shared with crickets: `gaussian_filter1d`, `silhouette`, `kmeans2`, `choose_k`, `rle`, `clean_signal_runs`, `group_consecutive`, `find_dominant_frequency`.

Species-specific tuning (why certain species need a different threshold) is
documented next to the constant that encodes it.

---

### 4. `Processing_Katydid_Spectrograms_Multiple_Bursts.ipynb` (katydids, multi-burst-type)

Some species alternate between different kinds of bursts in one recording--a pattern like A, B, C, B, A--that notebook #3 has no way to see, since it
collapses everything into one summary. This standalone variant reuses #3's
image generation and detection unchanged, and adds:

- **Burst-type clustering**: group each burst by element count/length/spacing and cluster with k-means + silhouette scoring, the same technique used for gap classification, generalized to more than one feature and more than two groups.
- **Low-volume burst rescue**: a quiet burst can lose to a much louder one in the same recording, since ink is normalized against the whole image; this re-thresholds anything the global pass missed, locally.

Produces one row per `(file, burst type)`--see the output table below.

**Output:** `Katydids/katydid_results_multi_bursts.csv` (raw), `katydid_multi_burst_type.csv` (merged, final).

**New functions on top of #3's:**
- `segment_bursts`: #3's `classify_intervals`, refactored to return every burst's own stats instead of one recording-wide summary.
- `kmeans_nd`, `silhouette_nd`, `choose_k_burst_types`, `classify_burst_types`: the multi-dimensional, multi-cluster generalization of the gap-clustering logic, used to sort bursts into types.
- `compute_burst_frequencies`: pulls each burst's own dominant pitch as an optional 4th clustering feature, for cases count/length/spacing alone can't separate.
- `render_raw_crop_png`, `find_missed_element_regions`, `analyze_missed_element_region`, `rescued_regions_to_bursts`: the missed-element rescue mechanism--find a secondary burst straight from the raw audio (bypassing whatever erased it from the image), analyze it as its own crop, and merge it in.
- `katydid_process_multi`: runs one file through the whole thing and returns a list of results, one per burst type.

| Output Column | Description |
|---|---|
| `Element_Length`, `Inter-Element_Interval`, `Elements_Per_Burst`, `Min/Max_Elements_Per_Burst` | Same as #3, computed per burst type |
| `Inter-Burst_Interval` | Mean between-burst gap for the whole clip |
| `Burst_Type` | Letter (A, B, C...) for this burst type, in order of first appearance |
| `Burst_Pattern` | The clip's full burst-type sequence, e.g. `"ABCBA"` |
| `N_Bursts_This_Type` / `N_Burst_Types_Detected` | How many bursts of this type, and how many types total |

---

### 5. `Frog_Clip_Log.ipynb` (frogs, stage 1)

Frog calls come from Xeno-Canto as long, unclipped recordings rather than
SINA's ready-made spectrograms, so a separate step (not in this repo) trims
each one down to its active call window and logs the result. This notebook
just loads that log, checks how the clips turned out, and hands the good ones
off as `clips_ready`.

**Input:** `Frogs/`. **Output:** `Cropped_Frogs_Audios/` (flat `.wav` clips + `frog_clip_log.csv`).

---

### 6. `Processing_Frog_Spectrograms.ipynb` (frogs, single-burst)

Generates a bandpass-filtered oscillogram per clip and measures the same four
numbers as the katydid pipeline. No OCR--`pixel_time` comes straight from
the clip log instead of being read off the image.

| Column | Description |
|---|---|
| `Element_Length` | Mean element (pulse) duration in seconds |
| `Inter-Element_Interval` | Mean within-burst gap in seconds |
| `Inter-Burst_Interval` | Mean between-burst gap in seconds; 0 for species with no burst structure |
| `Elements_Per_Burst` | Median elements per burst; 1 for non-burst species |
| `Min_Elements_Per_Burst` / `Max_Elements_Per_Burst` | Range across bursts of the recording; 1/1 for non-burst species |

**Output:** `Cropped_Frogs_Specs/` (oscillogram PNGs + `frog_results.csv`), `frog_single_burst_type.csv` (merged, final).

**Functions:** `generate_spectrogram_image`, `extract_outer_band_ink`,
`find_centerline_row`, `detect_signal_list_adaptive`, `classify_intervals`,
`frog_process`: same roles as the katydid pipeline's equivalents, tuned for
oscillogram noise instead of generated-spectrogram artifacts. Shared helpers:
`gaussian_filter1d`, `silhouette`, `kmeans2`, `choose_k`, `rle`,
`clean_signal_runs`, `find_dominant_frequency`.

---

### 7. `Processing_Frog_Spectrograms_Multiple_Bursts.ipynb` (frogs, multi-burst-type)

The frog equivalent of #4--same burst-type clustering and low-volume rescue,
architecturally identical to the katydid version. The main difference: its
overrides are mostly **file-scoped** rather than species-scoped (a single
frog species can have both a recording that needs a fix and one that
doesn't), plus a couple of frog-specific mechanisms for splitting elements
that got merged together or catching real gaps between calls.

Same ten output columns as #4. **Output:** `Cropped_Frogs_Specs/frog_results_multi_bursts.csv`, `frog_multi_burst_type.csv` (merged, final).

**Functions beyond #4's equivalents:** `true_silence_split` /
`try_split_on_true_silence`: split a burst at a gap that genuinely drops to
silence. `split_signal_on_valleys`: split an on-run at an internal dip deep
enough to be two close-together elements. `frog_process_multi`: the
per-clip entry point, returning one result per burst type.

---

## Viewers

All viewer classes live in
[`Code/spectrogram_viewer.py`](Code/spectrogram_viewer.py). Each notebook is
a thin wrapper: import the class, restore its DataFrame with `%store -r`,
instantiate it.

- **`SpectrogramViewer`**: pages through every species and spectrogram in order, showing each row's numbers next to its image. Used by `Display_Function.ipynb` (`CricketViewer`, `KatydidViewer`, `FrogViewer`).
- **`RandomSpectrogramViewer`**: shows one random spectrogram per group and lets you re-roll--a quick spot check rather than an exhaustive browse. Used by the three spot-checker notebooks (`KatydidGenusViewer`, `FrogGenusViewer`, `FrogSpeciesViewer`).

`KatydidViewer` matches images by `Spec_ID`, not `File_ID`--`File_ID` traces
back to the audio source for the CSV's sake, but the locally generated PNG is
named after the SINA spectrogram, which is what `Spec_ID` preserves.

---

## Shared detection approach

All five processing notebooks work the same basic way: reduce a spectrogram
to a column of "ink" (how dark each column is), threshold that into a binary
on/off signal, then cluster the resulting gap durations into short (within a
burst) and long (between bursts) using an exhaustive k-means-style split
scored by silhouette. Quirks--quiet elements, continuous trills, oddly long
recordings--get handled through species- or file-scoped override
dictionaries rather than one-off branches, so the shared logic stays the same
for everyone.

## Range-map analysis (crickets)

`range_map_processing.ipynb` is a standalone extra: it reads the cricket
range-map GIFs from `Webscraping.ipynb` and works out, per species, how much
of the map its occurrence dots cover and how much its range overlaps with
every other species. Colored dots are told apart from the neutral background,
county lines, and text by saturation alone--every SINA map shares the same
canvas and legend, so one test works for all of them.

**Output:** `Crickets/species_range_proportions_pct.csv`, `species_overlap_matrix_pct.csv`.

## Output files

| File | Produced by |
|---|---|
| `cricket.csv` | `Processing_Cricket_Spectrograms.ipynb` |
| `katydid_single_burst_type.csv` | `Processing_Katydid_Spectrograms.ipynb` |
| `katydid_multi_burst_type.csv` | `Processing_Katydid_Spectrograms_Multiple_Bursts.ipynb` |
| `frog_single_burst_type.csv` | `Processing_Frog_Spectrograms.ipynb` |
| `frog_multi_burst_type.csv` | `Processing_Frog_Spectrograms_Multiple_Bursts.ipynb` |

Each is the final joined table--one row (or one row per burst type) per
recording--that the viewers read from. They're kept out of version control
here since this data isn't published yet.

## Notes

- **`%store` is per-session.** If a notebook can't find its input DataFrame, run the notebook that's supposed to produce it, in the same running kernel.
- **GIFs can be animated.** A few SINA files are, so PIL needs `img.seek(0)` to get the first frame.
- **Species names:** `Webscraping.ipynb`'s `Species` column is `"Genus species"`; the processing notebooks split it into separate `Genus`/`Species` columns on the first space.
- Every threshold and override list has been individually regression-tested before landing, so a species- or file-specific exception is deliberate, not a stray hack.
