# PREPFIRE

PREPFIRE (PREParation for FIRE simulation) is a Python package for preparing materials for fire simulation and analysis, providing tools for processing fire data, weather conditions, and landscape characteristics. The package implements a complete pipeline for fire risk assessment and simulation.

The output files are intended for the fire spread simulation in FlamMap algorithm.

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

### From GitHub (recommended)

Install directly from the repository:

```bash
pip install git+https://github.com/CYglume/PREPFIRE.git
```

To install a specific release version:

```bash
pip install git+https://github.com/CYglume/PREPFIRE.git@v0.1.0
```

### From GitHub Release

Download the `.whl` file from the [Releases page](https://github.com/CYglume/PREPFIRE/releases) and install it:

```bash
pip install prepfire-0.1.0-py3-none-any.whl
```

Or install directly from the release URL:

```bash
pip install https://github.com/CYglume/PREPFIRE/releases/download/v0.1.0/prepfire-0.1.0-py3-none-any.whl
```

<!-- ### From PyPI (not yet available)
```bash
pip install prepfire
``` -->

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
│       ├── fires.shp               # (Required) Vector map for historical fire ignition points
│       ├── cropping_polygon/       # Optional bounding box for defining the processing area
│       └── lcp_Fuel/
│           ├── elevation.tif       # (Required) File names must match the corresponding string
│           ├── slope.tif           # (Required) File names must match the corresponding string
│           ├── aspect.tif          # (Required) File names must match the corresponding string
│           ├── fuel.tif            # (Required) File names must match the corresponding string
│           ├── canopyCover.tif     # (Required) File names must match the corresponding string
│           ├── canopyHeight.tif    # (Required) File names must match the corresponding string
│           ├── cbh.tif             # (Required) File names must match the corresponding string
│           └── cbd.tif             # (Required) File names must match the corresponding string
└── Processed_data/
    └── region/
        ├── Single/
        ├── Landscape/
        ├── Ignition/
        ├── Weather/
        │   └── CDS/
        ├── Final/
        └── Sim/
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
    extreme_percentile=95,          # Optional: Threshold for extreme weather (0-100). can be multiple values, e.g. [30, 60] for average conditions between percentiles
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
    done_cds_download=False,        # Optional: Whether to skip CDS download procedures
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
1. `process_fire_data()`: Load and process fire data from shapefiles
2. `process_weather_data()`: Process weather data for the region
3. `generate_weather_types()`: Process and generate weather types from processed data
4. `generate_ignition_points()`: Generate sample ignition points
5. `process_landscape()`: Process landscape data for the region
6. `generate_fmd_and_simpoints()`: Generate FMS and KDE point density files
- `prepare_simulation()`: Run the complete fire simulation pipeline from 1. to 6.
- ~~`run_fire_simulations()`: Run fire simulations based on the prepared data (pending implementation)~~

See function description within each object function to get further information.

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
        Use the whole extent from input data `fire.shp` for the process

### Fire Weather
The algorithm collects and compiles fire weather information through the Copernicus Climate Data Store (CDS). If the user has self produced climatic information for weather scenario clustering, fire weather table (.csv) can be provided to the variable `fire_weather` when construcing the `PrepFirePipeline` object.

The CSV table (file path: `path/to/fire_weather.csv`) should at least contains the following data structure:
| Date | Fire_size_in_ha | Temperature | RH | Wind_speed | ...

Corresponding column names should be assigned to the object correctly
```Python
prepfire.PrepFirePipeline(
    col_fire_size    = "Fire_size_in_ha",
    col_fire_date    = "Date",
    weather_variable = ['Temperature', 'RH', 'Wind_speed'],
    fire_weather     = "path/to/fire_weather.csv"
)
```

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

**Local build test:** To verify the full build-and-install cycle locally, see the scripts in [`scripts/`](scripts/) (`local_build_test.sh` for Linux/macOS/Git Bash, `local_build_test.bat` for Windows).

**Cleanup:** Testing generates cache files that are safe to delete:

```bash
# Remove pytest and Python caches (auto-regenerated on next run)
rm -rf .pytest_cache
find . -type d -name "__pycache__" -exec rm -rf {} +
```

## Acknowledgments

- Copernicus Climate Data Store for weather data
- Contributors and maintainers