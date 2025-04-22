# SCENFIRE

SCENFIRE is a Python package for preparing materials for fire simulation and analysis, providing tools for processing fire data, weather conditions, and landscape characteristics. The package implements a complete pipeline for fire risk assessment and simulation.

The output files are intended for the fire ignition simulation in FlamMap algorithm.

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

The package is available through conda-forge:

```bash
conda install -c conda-forge scenfire
```

## Project Structure

```
scenfire_project/
├── input_data/
│   └── region/
│       ├── fires.shp
│       └── lcp_Fuel/
│           ├── elevation.tif
│           ├── slope.tif
│           ├── aspect.tif
│           ├── fuel.tif
│           ├── canopyCover.tif
│           ├── canopyHeight.tif
│           ├── cbh.tif
│           └── cbd.tif
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
from scenfire.pipeline import ScenFirePipeline, setup_project_structure, run_prepare

# Set up initial project folder if data is not prepared as desired folder structure
setup_project_structure(
    region,                      # Required: Name of the region folder
    root_dir="path/to/project",  # Optional: Project root directory (defaults to current directory)
)

# Initialize the pipeline
pipeline = ScenFirePipeline(
    region="your_region",        # Required: Name of the region folder
    root_dir="path/to/project",  # Optional: Project root directory (defaults to current directory)
    bound_coords=None,           # Optional: Bounding box coordinates [xmin, ymin, xmax, ymax]
    output_crs="EPSG:3035",     # Optional: Output coordinate system
    col_fire_size="Area_ha",    # Optional: Column name for fire size in hectares
    col_fire_date="Date",       # Optional: Column name for fire dates
    extreme_percentile=95,      # Optional: Threshold for extreme weather (0-100)
    lcp_components=[            # Optional: Landscape components for LCP file
        'elevation', 'slope', 'aspect', 'fuel',
        'canopyCover', 'canopyHeight', 'cbh', 'cbd'
    ],
    cds_api_key="your_key",     # Optional: API key for weather data
    time_of_day=["12:00"],      # Optional: Times for weather data download
    buffer_size=20000,          # Optional: Buffer size in meters for weather data
    min_clusters=4,             # Optional: Minimum number of weather clusters
    max_clusters=10,            # Optional: Maximum number of weather clusters
    log_level="INFO",           # Optional: Logging level
    fire_months=[5,6,7,8,9,10], # Optional: Months to consider for fire season
    lcp_resolution=100,         # Optional: Resolution in meters for LCP raster
    done_cds_download=False     # Optional: Whether to skip CDS download step
)

# Run the pipeline
pipeline.prepare_simulation()

# Or use the quick run function
results = run_prepare(
    region="your_region",        # Required: Name of the region folder
    root_dir="path/to/project",  # Optional: Project root directory
    **kwargs                     # Optional: Additional keyword arguments for ScenFirePipeline
)
```

### Pipeline Methods

The `ScenFirePipeline` class provides the following methods:

- `process_fire_data(plot_fires=False)`: Load and process fire data from shapefiles
- `process_weather_data()`: Process weather data for the region
- `generate_weather_types()`: Process and generate weather types from processed data
- `generate_ignition_points()`: Generate sample ignition points
- `process_landscape()`: Process landscape data for the region
- `generate_output_files()`: Generate FMS and KDE point density files
- `run_fire_simulations()`: Run fire simulations based on the prepared data (pending implementation)
- `prepare_simulation()`: Run the complete fire simulation pipeline

### CDS API Key

The Copernicus Climate Data Store (CDS) API key can be provided in three ways:

1. Directly in the pipeline initialization:
```python
pipeline = ScenFirePipeline(region="your_region", cds_api_key="your_api_key")
```

2. Environment variable:
```python
import os
os.environ["CDS_API_KEY"] = "your_api_key"
pipeline = ScenFirePipeline(region="your_region")
```

3. Interactive prompt:
If no API key is provided, the program will prompt you to enter it interactively.

## Development

### Quick Start for Development

```bash
# Create and activate environment
conda create -n scenfire-dev python=3.10
conda activate scenfire-dev

# Install critical dependencies from conda-forge
conda install -c conda-forge netcdf4 geopandas rasterio xarray

# Install other dependencies
conda install -c conda-forge numpy pandas cdsapi scikit-learn shapely matplotlib pyproj zarr cftime h5netcdf pytest

# Build and install package
conda build .
conda install --use-local scenfire

# Run tests
# Add tests as needed
pytest tests/
```

### Key Dependencies

- shapely and netCDF4 must be installed from conda-forge
- numpy >= 1.26 and Python >= 3.10 are required

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Acknowledgments

- Copernicus Climate Data Store for weather data
- Contributors and maintainers