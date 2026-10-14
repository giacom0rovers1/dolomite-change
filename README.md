# Dolomite change: data analysis

*Dolomite change. Un viaggio in montagna attraverso vent'anni di cambiamenti* is a
short film by Marco Frilli and Giacomo Roversi (2026). In July 2005 the two authors
spent a week trekking in the Dolomites above Cortina d'Ampezzo, between Cinque
Torri, Lagazuoi and Tofane, in rain, frost and two snowfalls. In July 2025 they
walked the same route again, in a single day.

This repository contains the data analysis cited in the film: the data, the scripts
that download and analyse them, and a notebook that recomputes every table and
figure. The same scripts produce the film's animations.

## Contents

| | |
|---|---|
| `analysis.ipynb` | the analysis, with tables and figures |
| `scripts/` | download, analysis and animation scripts |
| `data/era5/` | ERA5 freezing level, summers 1950-2025, and hourly data for July 2005 |
| `data/arpav/` | ARPAV monthly bulletins 1994-2024 for 211 stations in Veneto, zipped |
| `data/openmeteo/` | daily ERA5 series for 2005, from Open-Meteo |
| `data/risultati/` | results in csv, read by the notebook |

## Main results

Summer days on which snow could fall (snow level 300 m below the freezing level),
per summer:

| | 1970s | 2020-25 |
|---|---:|---:|
| Passo Falzarego (2105 m) | 6.2 | 0.2 |
| Rifugio Lagazuoi (2752 m) | 29.9 | 9.7 |
| Tofana di Rozes (3225 m) | 61.8 | 32.7 |

The lowest freezing level of each summer averaged 2003 m in the 1970s, below Passo
Falzarego, and 2555 m in 2020-2025, above it. It last dropped below the pass in 2006.

Over 2005-2024 all 158 ARPAV stations with enough data warmed in summer, with a
median trend of +1.05 °C per decade.

July 2005 was itself exceptional: with 2 snow days it is the sixth snowiest July
since 1950.

## Running the analysis

Python with `numpy`, `xarray`, `netcdf4`, `matplotlib`, `requests`, Jupyter, and
`ffmpeg` for the animations; `cdsapi` only to download ERA5 again:

```bash
conda create -n dolomite-change -c conda-forge python=3.12 numpy xarray netcdf4 \
    matplotlib requests jupyterlab nbconvert "ffmpeg=*=gpl*"
conda activate dolomite-change
pip install cdsapi
```

`ffmpeg=*=gpl*` selects the build with libx264, needed for the MP4 files. On Windows,
activate the environment or use `conda run -n dolomite-change python ...`.

The data are in the repository, so the notebook runs as it is. Open it from the
repository root; on the first run it extracts the ARPAV csv files.

```bash
jupyter lab analysis.ipynb

# or the scripts one by one
python scripts/zero_termico.py --soglie --serie --csv   # freezing level and days with possible snow
python scripts/edw_arpav.py --finestra 2005 2024 --csv  # summer trend of the ARPAV stations
python scripts/diario_2005.py                           # the 2005 week, day by day
python scripts/anim_giorni_neve.py                      # -> video/giorni_neve.mp4
```

The animations are written to `video/` at 1920×1080: `stazioni_arpav.mp4`,
`zero_termico.mp4` and `giorni_neve.mp4`; with `--alfa`, as ProRes 4444 MOV files
with a transparent background. Their labels are in Italian, as in the film. The
Inter font is in `scripts/fonts/` (OFL licence). Code comments are in Italian.

Downloading ERA5 again requires a free Climate Data Store account and a
`~/.cdsapirc` file (see the header of `scripts/download_era5.py`).

## Data and attribution

- ERA5, Copernicus Climate Change Service (C3S) / ECMWF, hourly data on pressure
  levels: [doi:10.24381/cds.bd0915c6](https://doi.org/10.24381/cds.bd0915c6).
  Contains modified Copernicus Climate Change Service information 2026. Neither the
  European Commission nor ECMWF is responsible for any use that may be made of the
  Copernicus information or data it contains.
- ARPAV, Principali variabili meteorologiche 1994-2024, open data
  [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/):
  <https://www.arpa.veneto.it/dati-ambientali/open-data/clima/principali-variabili-meteorologiche>
- Open-Meteo historical archive (ERA5 and ERA5-Land), CC BY 4.0: weather data by
  [Open-Meteo.com](https://open-meteo.com/).
- Securo, A., Del Gobbo, C., Baccolo, G., Barbante, C., Citterio, M., De Blasi, F.,
  Marcer, M., Valt, M., and Colucci, R. R.: The glaciers of the Dolomites: the last
  40 years of melting, The Cryosphere, 19, 1335-1352, 2025,
  <https://doi.org/10.5194/tc-19-1335-2025>.

## Licence

The code is released under the MIT licence (see `LICENSE`). The data keep their own
licences, listed above; the Inter font is under the OFL (`scripts/fonts/LICENSE.txt`).

Documentation written with Anthropic Claude Opus 5.5.
