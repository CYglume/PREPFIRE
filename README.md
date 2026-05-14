# PREPFIRE

PREPFIRE (PREParation for FIRE simulation) is a Python package for preparing materials for fire simulation and analysis, providing tools for processing fire data, weather conditions, and landscape characteristics. The package implements a complete pipeline for fire risk assessment and simulation.

The output files are intended for the fire spread simulation in FlamMap algorithm.

![PyPI - Downloads](https://img.shields.io/pypi/dw/prepfire)
[![PyPI version](https://img.shields.io/pypi/v/prepfire)](https://pypi.org/project/prepfire/)
<img alt="GitHub last commit" src="https://img.shields.io/github/last-commit/CYglume/PREPFIRE">
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20083868.svg)](https://doi.org/10.5281/zenodo.20083868)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)


## Features

- Fire data processing and analysis
- Landscape file (lcp) component processing
- Weather data integration with ERA5-Land dataset
- Weather type clustering and analysis
- Interactive API key management for weather data
- Ignition probability map
- Fuel Moistures File (.fms) generation
- Project structure setup utility

## Installation

### From PyPI (recommended)

```bash
pip install prepfire
```

### From GitHub Release

Download the `.whl` file from the [Releases page](https://github.com/CYglume/PREPFIRE/releases) and install it:

```bash
pip install prepfire-0.1.1-py3-none-any.whl
```

Or install directly from the release URL:

```bash
pip install https://github.com/CYglume/PREPFIRE/releases/download/v0.1.1/prepfire-0.1.1-py3-none-any.whl
```

### From GitHub

Install the latest development version directly from the repository:

```bash
pip install git+https://github.com/CYglume/PREPFIRE.git
```

### For development

Clone the repository and install in editable mode:

```bash
git clone https://github.com/CYglume/PREPFIRE.git
cd PREPFIRE
pip install -e ".[test]"
```

## Project Structure

```
prepfire_project/
├── input_data/
│   └── region/
│       ├── fires.gpkg              # (Required) Fire ignition points — GeoPackage preferred; .shp also accepted
│       ├── cropping_polygon/       # Optional bounding polygon for the processing extent (one feature)
│       └── lcp_Fuel/
│           ├── elevation.tif       # (Required) File names must match the corresponding string
│           ├── slope.tif           # (Required) File names must match the corresponding string
│           ├── aspect.tif          # (Required) File names must match the corresponding string
│           ├── fuel.tif            # (Required) uint8 fuel-model codes; file names must match
│           ├── canopyCover.tif     # (Required) File names must match the corresponding string
│           ├── canopyHeight.tif    # (Required) File names must match the corresponding string
│           ├── cbh.tif             # (Required) File names must match the corresponding string
│           └── cbd.tif             # (Required) File names must match the corresponding string
└── Processed_data/
    └── region/
        ├── Fires/                  # Spatially filtered fire records (fires_region.gpkg)
        ├── Landscape/              # Reprojected and resampled landscape layers
        ├── Ignition/               # Ignition probability surface (ig_kde.tif) and sample points
        ├── Weather/
        │   ├── CDS/                # Raw ERA5-Land monthly NetCDF downloads
        │   ├── FMS/                # Fuel moisture scenario files (.fms)
        │   ├── p95_extreme_weather_types.csv   # Single-percentile scenario (extreme_percentile=int)
        │   ├── all_mean_weather_types.csv
        │   ├── Extensive_percentile_group_weather_scenarios.csv  # Multi-percentile (extreme_percentile=list)
        │   └── fire_weather_records.csv        # Per-fire extracted weather
        ├── Final/
        │   └── lcp_{region}.tif    # Multi-band landscape file (8 bands)
        └── Sim/                    # Reserved for FlamMap/MTT simulation outputs
```

## Usage

```python
import prepfire

# Set up initial project folder if data is not prepared as desired folder structure
prepfire.setup_project_structure(
    "your_region",               # Required: Name of the region folder
    root_dir="path/to/project",  # Optional: Project root directory (defaults to current directory)
)

# Initialize the pipeline object
user_pipeline = prepfire.PrepFirePipeline(
    region="your_region",           # Required: Name of the region folder
    root_dir="path/to/project",     # Optional: Project root directory (defaults to current directory)
    bound_coords=None,                 # Optional: Bounding box coordinates [xmin, ymin, xmax, ymax]. Default by using extent of fire.shp or cropping polygon (if provided)
    output_crs="EPSG:3035",         # Optional: Output coordinate system
    col_fire_size="Area_ha",        # Optional: Column name for fire size in hectares
    col_fire_date="Date",           # Optional: Column name for fire dates
    extreme_percentile=95,          # Optional: int → single-percentile extreme (e.g. 95 for 95th/5th); list → percentile-group intervals, e.g. [30,60,90] → (0,30],(30,60],(60,90],(90,100]
    lcp_components=[                # Optional: Landscape components for LCP file (Follow the order of landscape file for USGS FlamMap)
        'elevation', 'slope', 'aspect', 'fuel',
        'canopyCover', 'canopyHeight', 'cbh', 'cbd'
    ],
    cds_api_key="your_key",         # Optional: API key for weather data
    time_of_day=["12:00"],          # Optional: Times for weather data download
    buffer_size=20000,              # Optional: Buffer size in meters for weather data
    min_clusters=4,                 # Optional: Minimum number of weather clusters
    max_clusters=10,                # Optional: Maximum number of weather clusters
    fire_months=[5,6,7,8,9,10],     # Optional: Months to consider for fire season
    lcp_resolution=100,             # Optional: Resolution in meters for LCP raster
    done_cds_download=False,        # Optional: Set True to skip ERA5-Land download (merged .nc files already present)
    done_lcp=False,                 # Optional: Set True to skip landscape processing (lcp_{region}.tif already present)
    livePlantMoist = [60, 90],      # Optional: Two values for setting moisture of [live Herbaceous, live Woody] plants in fms file
    weather_variable = [            # Optional: Variable names in fire weather table for data clustering 
        'T', 'RH', 'WS', 'DFMC'
    ],
    fire_weather  = None,           # Optional: Path to an external csv for fire weather information (Only used if skipping CDS download)
    log_level="INFO"                # Optional: Logging level
)

# Start running the process of the pipeline object
results = user_pipeline.prepare_simulation()

# ---------------------------------------------------------------------------------- #

# Or use the quick run function (Run starting from setup_project_structure)
results = prepfire.run_prepare(
    region="your_region",        # Required: Name of the region folder
    root_dir="path/to/project",  # Optional: Project root directory
    **kwargs                     # Optional: Additional keyword arguments for PrepFirePipeline
)
```

### Pipeline Methods

The module provides three main functions:
- `setup_project_structure`: Create the folder structure for input datasets
- `PrepFirePipeline`: Create the pipeline object for quick processing datasets (load local data)
  - `PrepFirePipeline.prepare_simulation()` Main function under pipeline object to run all processing functions
- `run_prepare`: Incorporate the above two functions to provide a single line function for all processes (use all default values from the package)

The `PrepFirePipeline` class object provides the following methods:
1. `process_fire_data()`: Load, spatially filter, and save fire ignition records
2. `process_weather_data()`: Download (or skip) ERA5-Land data, derive weather variables, extract fire weather
3. `generate_weather_types(scenario_tag=None)`: Cluster fire weather and write scenario CSVs
4. `generate_ignition_points()`: Generate 500,000 random sample ignition points within the study area
5. `process_landscape()`: Reproject, resample, and stack all LCP layers into `lcp_{region}.tif`
6. `generate_fmd_and_simpoints()`: Write `.fms` fuel moisture files and produce the KDE ignition probability surface
- `prepare_simulation()`: Run the complete pipeline (steps 1–6) in sequence

See function description for full parameter configuration.

#### `generate_weather_types` — multi-version scenario outputs

By default each call **overwrites** any existing scenario CSV with the same name. To keep multiple scenario runs side by side, pass a `scenario_tag`:

```python
# Keep single-percentile and multi-percentile outputs simultaneously
pipeline.extreme_percentile = 95
pipeline.generate_weather_types(scenario_tag="p95")
# → Weather/p95_extreme_weather_types_p95.csv

pipeline.extreme_percentile = [30, 60, 90]
pipeline.generate_weather_types(scenario_tag="groups")
# → Weather/Extensive_percentile_group_weather_scenarios_groups.csv
```

### CDS API Key

The Copernicus Climate Data Store (CDS) API key can be provided in three ways:

1. Directly in the pipeline initialization:
```python
pipeline = PrepFirePipeline(region="your_region", cds_api_key="your_api_key")
```

2. Environment variable:
```python
import os
os.environ["CDS_API_KEY"] = "your_api_key"
pipeline = PrepFirePipeline(region="your_region")
```

3. Interactive prompt:
If no API key is provided, the program will prompt you to enter it interactively.


### Bounding box
The argument `bound_coords` in `prepfire.PrepFirePipeline` takes care of the extent being used for cropping the processed area:

1. `bound_coords = [xmin, ymin, xmax, ymax]`: Provide quick solution to manually set up bounding coords in degree with default EPSG:4326

2. `bound_coords = None` (default value): leave the argument blank to trigger the following options:
   1. Extra extent geometry (`.shp` or `.gpkg`) existing in folder `input_data/region/cropping_polygon/`:
        Use the polygon (must be only one feature in the file) to set the extent for the whole process 
   2. No extra extent set up:
        Use the whole extent from input fire data for the process

### Fire Weather

The pipeline downloads ERA5-Land data via the Copernicus Climate Data Store (CDS) and extracts per-fire weather at each ignition location. The extracted records are saved to `Processed_data/region/Weather/fire_weather_records.csv` (one row per fire event). Two aggregated scenario tables are also saved:

| `extreme_percentile` type | Output files |
|---------------------------|--------------|
| `int` (e.g. `95`) | `p95_extreme_weather_types.csv` + `all_mean_weather_types.csv` |
| `list` (e.g. `[30, 60, 90]`) | `Extensive_percentile_group_weather_scenarios.csv` |

If you have your own fire weather table, provide it via `fire_weather` to skip ERA5 extraction entirely:

```python
prepfire.PrepFirePipeline(
    col_fire_size    = "Fire_size_in_ha",
    col_fire_date    = "Date",
    weather_variable = ['Temperature', 'RH', 'Wind_speed'],
    fire_weather     = "path/to/fire_weather.csv"   # bypasses CDS download and extraction
)
```

The CSV must contain at minimum one column for fire date, one for fire size in hectares, and columns matching `weather_variable`.

## Testing

Tests verify that the package imports correctly and core functions produce expected outputs using synthetic data — no network access or large input files required.

**Setup** (one-time): install the package in editable mode with test dependencies. This lets you modify source code and test changes without reinstalling.

```bash
cd path/to/PREPFIRE
pip install -e ".[test]"
```

> **Windows note:** If `pip` is not recognized, use `python -m pip` instead (e.g., `python -m pip install -e ".[test]"`). This ensures the correct Python interpreter is used, especially when multiple versions are installed.

> **GDAL on Windows:** If installation fails with build errors on `rasterio` or `geopandas`, these packages require the GDAL C library. The easiest fix is to install pre-built wheels before installing prepfire:
> ```bash
> pip install --only-binary :all: rasterio geopandas
> pip install -e ".[test]"
> ```
> The `--only-binary :all:` flag forces pip to use pre-compiled wheels instead of attempting to build from source. If no compatible wheel is found for your Python version, try upgrading pip (`pip install --upgrade pip`) or use [conda](https://docs.conda.io/) which bundles GDAL automatically.

**Run tests:**

```bash
pytest tests/ -v              # Run all tests with verbose output
pytest tests/ -v -k "Clustering"  # Run only tests matching a keyword
pytest tests/ -v -x           # Stop on first failure (useful for debugging)
```

A successful run prints green `PASSED` for each test. If a test fails, pytest shows the exact assertion and traceback to help locate the issue.

**Local build test:** To verify the full build-and-install cycle of the development version (e.g., when the PyPI release has not yet caught up with recent changes), run the script for your platform from the repository root:

**Windows (Command Prompt):**
```bat
scripts\local_build_test.bat
```

**Linux / macOS / Git Bash:**
```bash
bash scripts/local_build_test.sh
```

> **Prerequisites:** `python` must be on your `PATH` and the repository must be cloned locally (`git clone https://github.com/CYglume/PREPFIRE.git`).

The script performs the following steps automatically:

| Step | Action |
|------|--------|
| 1 | Creates a clean `.venv_test` virtual environment |
| 2 | Upgrades `pip` and installs the `build` backend |
| 3 | Builds the wheel (`python -m build`) and prints the output filenames |
| 4 | Installs the built `.whl` into the test environment |
| 5 | Imports `prepfire` and all sub-modules from outside the source tree, printing the installed version |
| 6 | Calls `setup_project_structure()` in a temporary directory to verify the project scaffold |
| 7 | Removes `.venv_test` and the temporary directory |

A passing run ends with `=== BUILD AND INSTALL TEST PASSED ===`. Any import error or missing dependency is surfaced at step 5.

**Cleanup:** Testing generates cache files that are safe to delete:

```bash
# Remove pytest and Python caches (auto-regenerated on next run)
rm -rf .pytest_cache
find . -type d -name "__pycache__" -exec rm -rf {} +
```

## Acknowledgments

- Copernicus Climate Data Store for weather data
- Contributors and maintainers

## Funding and supporting projects
This work was financed by the projects FireCycle (CNS2023-144228) funded by the Spanish Ministry of Science and Innovation (MCIN/AEI/10.13039/501100011033) and project “Understanding Wildfire Risk: A Local-Scale Assessment Framework in Chile”, financed by the AXA Research Fund. The work has been also supported by project FLARE (PID2023-148568OB-I00).
