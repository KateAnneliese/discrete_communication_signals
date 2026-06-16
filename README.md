# Discrete Communication Signals in Nature

This repository contains the code used for the research project **Discrete Communication Signals in Nature**. The project investigates patterns in animal acoustic communication by extracting temporal signal characteristics from the calls of crickets, katydids, and frogs.

The code uses a combination of web scraping, API integration, image processing, and audio analysis to collect and process data across species. Data are obtained from:

- The [Singing Insects of North America](https://songsofinsects.com/) website
- The [Xeno-Canto](https://xeno-canto.org/) API

For each species, the code extracts signal parameters from spectrograms and combines them with metadata such as taxonomy, location, temperature, and range information.

## Extracted Signal Parameters

The processing pipeline measures four temporal characteristics of each acoustic signal:

- **Element length** – duration of an individual sound element
- **Inter-element interval** – time between consecutive elements
- **Inter-burst interval** – time between bursts (groups of elements)
- **Elements per burst** – number of elements contained within a burst

Species that produce continuous sequences of elements rather than distinct bursts are assigned:

- **Inter-burst interval = 0**
- **Elements per burst = 0**

## Crickets

The cricket workflow uses spectrograms obtained from the Singing Insects of North America website.

1. Spectrograms and associated metadata are scraped and downloaded.
2. Spectrogram images are processed to identify signal structure.
3. The four temporal signal parameters are extracted.
4. Results are combined with metadata including:
   - Genus
   - Species
   - Temperature
   - Location
   - Range map information
5. The final dataset is exported as a CSV file.

## Katydids

Katydids follow a workflow similar to that used for crickets. However, the katydid spectrograms available from Singing Insects of North America are generally less uniform and contain more visual noise.

To account for these differences, a separate spectrogram-processing function is used that is tailored to katydid recordings while extracting the same four temporal signal parameters.

## Frogs

Unlike the cricket and katydid datasets, frog data are obtained from audio recordings through the Xeno-Canto API.

The workflow is:

1. Download audio recordings.
2. Generate spectrograms from the audio files.
3. Apply preprocessing and noise-reduction techniques.
4. Extract the same four temporal signal parameters:
   - Element length
   - Inter-element interval
   - Inter-burst interval
   - Elements per burst
5. Export the processed results for further analysis.

## Output

The final output of each pipeline is a structured dataset containing:

- Taxonomic information
- Geographic information
- Environmental metadata (when available)
- Extracted acoustic signal parameters

These datasets can be used for comparative analyses of communication signals across species and taxonomic groups.
