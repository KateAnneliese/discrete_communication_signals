# Discrete Signals

Extracts acoustic parameters (element length, inter-element interval, inter-burst interval,
elements per burst) from cricket and katydid call recordings archived on the
[Singing Insects of North America (SINA)](https://orthsoc.org/sina) database, plus frog
call recordings from [Xeno-Canto](https://xeno-canto.org). The pipeline is: **web scraping
→ image/audio processing → a browsable viewer.**

This README covers the web scraping and cricket processing code. See inline notebook
comments for the katydid and frog pipelines.

## Setup
pip install requests beautifulsoup4 pandas numpy matplotlib pillow opencv-python pytesseract librosa scipy

Tesseract OCR must also be installed system-side (`brew install tesseract` on macOS) —
`pytesseract` is just a wrapper around the `tesseract` binary.

Set an environment variable before running `Webscraping.ipynb`:
export XENO_CANTO_API_KEY="your-key-here"

(Free key from [xeno-canto.org](https://xeno-canto.org); only needed for the frog metadata pull.)

## Notebook run order

1. **`Webscraping.ipynb`** — scrapes SINA + Xeno-Canto, downloads files, stores `cricket_df` / `katydid_df` / `frog_df`
2. **`Code/Processing_Cricket_Spectrograms.ipynb`** — restores `cricket_df`, processes spectrogram images, stores `cricket_final`
3. **`Code/Processing_Katydid_Spectrograms.ipynb`** — restores `katydid_df`, processes oscillogram images, stores `katydid_final`
4. **`Code/Display_Function.ipynb`** — restores `cricket_final`, launches an interactive viewer widget

Notebooks pass DataFrames between each other with IPython's `%store` magic. If a
notebook errors on `%store -r some_df`, the upstream notebook hasn't been run yet in
this kernel session.

---

## `Webscraping.ipynb`

### Cricket / katydid scraping loop

For each species on the SINA list page (`cricklist.htm` / `katylist.htm`), the notebook
visits the species' own page and pulls out:

- the **range map** — found either via the page's standard image table, or by falling
  back to scanning table rows for a caption containing the word "map"
- every **recording block** (`<div class="recording">`) on the page, from which it grabs:
  - the **spectrogram/oscillogram image** (matched by looking for the words
    "spectrogram", "sonogram", "waveform", "graph", etc. in the image's `src`, `alt`,
    or surrounding text)
  - the **audio file** (`<audio><source>` tag)
  - **temperature** (extracted around the "°" character) and **location** (extracted
    around the words "from"/"in") from the recording's description text

A short courtesy `time.sleep()` runs between species requests so the SINA server isn't hammered.

Each recording becomes one row in `cricket_grouped_data` / `katydid_grouped_data`, which
is turned into `cricket_df` / `katydid_df` and stored with `%store` for the processing notebooks.

### Frog metadata pull

Loops over all 57 pages of the Xeno-Canto REST API for the `grp:frogs` query, flattens
the nested JSON into `frog_df` (genus, species, location, coordinates, call type, audio
file URL, spectrogram URL).

### Downloading files

- **`download_file(url, path, headers)`** — safely downloads a URL to disk, but first
  inspects the response `Content-Type` and body to reject HTML error pages that SINA
  sometimes serves in place of the actual image (so a 404 page never gets saved with a
  `.gif` extension).
- **`get_file_id(url)`** — extracts the filename (no extension) from a URL, used as a
  unique ID so a species with multiple recordings doesn't have its files overwritten.
- **Cricket/katydid download loops** — iterate `cricket_df` / `katydid_df` row by row,
  create a `Genus_species` subfolder under `Crickets/` or `Katydids/`, and download the
  spectrogram, audio clip, and range map into it, named
  `{Genus_species}_{spectrogram|audio|map}_{file_id}.{ext}`.
- **`download_frogs(frog_df, base_folder, headers)`** — same idea for frog audio, with a
  per-species running counter (`_audio_1`, `_audio_2`, ...) since Xeno-Canto doesn't
  supply a stable per-recording ID.

---

## `Code/Processing_Cricket_Spectrograms.ipynb`

Turns each downloaded cricket spectrogram image into four numbers:
`Element_Length`, `Inter-Element_Interval`, `Inter-Burst_Interval`, `Elements_Per_Burst`.

### Pipeline (`cricket_process`)

1. **OCR the x-axis** (`read_x_axis_seconds`) to find the time span the image represents.
   Finds the axis line by scanning for a long dark horizontal run, then OCRs the
   numeric labels at each end (falling back to interior sample points and a linear fit
   if the end labels aren't readable). Some files have unreliable axes entirely — for
   those, `MANUAL_MAX_SECONDS` supplies the time span directly, skipping OCR.
2. **Compute `pixel_time`** = seconds represented by one pixel of image width.
3. **Locate the dominant frequency band** (`locate_signal_band`) — cricket calls are
   narrowband, so the row range containing the signal is found and everything else discarded.
4. **Re-normalize ink** within that band so faint elements aren't washed out by
   normalizing against the full image's contrast range.
5. **Adaptive hysteresis thresholding** (`detect_signal_list_adaptive`) turns the ink
   intensity into a clean binary on/off column signal. It tries a descending cascade of
   threshold pairs and scores each candidate, picking the one that best balances signal
   completeness against noise.
6. **Trim leading/trailing silence**, then run-length encode the signal into
   `(state, duration)` time buckets.
7. **Classify gaps** (`classify_intervals`) — splits gap durations into two clusters
   (inter-element vs. inter-burst) using exhaustive-silhouette k-means, with several
   guard conditions to avoid declaring false burst structure on trill species.

### Species-specific patches

Real-world spectrograms are messy, and a handful of species needed special-casing:

- **`MANUAL_MAX_SECONDS`** — files where OCR can't read the x-axis at all; time span
  supplied by hand (tick-mark counting or comparison with a similar species' image).
- **`MANUAL_RESULTS`** — a few species where the image resolution is too low for the
  algorithm to reliably separate elements/bursts even with the pipeline steps above
  (e.g. gaps that are sub-pixel, faint first elements that vanish at every threshold,
  three-cluster gap structures that the two-cluster classifier can't represent). Values
  here were determined by visual inspection and are returned directly, bypassing the
  image pipeline.
- **`FAINT_ELEMENT_THRESHOLD`** — a few species have one very faint first element that's
  only visible at a lower detection threshold than the pipeline's default scorer picks
  (which favors the highest threshold that still gives a clean signal). These entries
  force the pipeline to use a specific lower threshold instead.
- **Excluded species** (`Hapithus_melodius`, `Gryllus_cayensis`, `Gryllus_ovisopis`) —
  skipped entirely in the batch run because their songs (accelerating chirps,
  courtship song, two-male fighting recordings) don't fit the four-parameter model at all.

### Batch run and merge

The last few cells process every spectrogram under `Crickets/`, write
`Crickets/cricket_results.csv`, then join the results back onto `cricket_df` (from
`Webscraping.ipynb`) using a shared spectrogram ID extracted from both the SINA URL and
the local filename via regex. The joined result, `cricket_final`, is stored with
`%store` for `Display_Function.ipynb`.

---

## Final DataFrame schema

`cricket_final` (and the equivalent `katydid_final`) columns:

| Column | Description |
|---|---|
| `Genus`, `Species` | Parsed from the SINA "Genus species" name |
| `Temperature` | Recording temperature (°C) |
| `Location` | Recording location |
| `Description` | Audio file description from SINA |
| `Map` | URL to the SINA range map image |
| `File_ID` | Spectrogram identifier from the SINA URL, used to link images to rows |
| `Element_Length` | Mean pulse duration (s) |
| `Inter-Element_Interval` | Mean within-burst gap (s) |
| `Inter-Burst_Interval` | Mean between-burst gap (s); 0 for trill/single-element species |
| `Elements_Per_Burst` | Median elements per burst; 1 for trill species |

These exact column names are required by `Display_Function.ipynb` — don't rename them
without updating the viewer too.
