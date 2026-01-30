"""
Basic Usage Example for PREPFIRE Package

This example demonstrates how to use the PREPFIRE package to:
1. Set up a project structure
2. Process fire data
3. Download and process weather data
4. Generate weather types
5. Process landscape data
6. Generate output files for simulation

The example assumes you have the following data structure:
input_data/
└── region_name/
    ├── fires.shp          # Fire ignition points shapefile
    └── lcp_Fuel/          # Landscape component rasters
        ├── elevation.tif
        ├── slope.tif
        ├── aspect.tif
        ├── fuel.tif
        ├── canopyCover.tif
        ├── canopyHeight.tif
        ├── cbh.tif
        └── cbd.tif
"""

import os
from pathlib import Path

from prepfire.pipeline import PrepFirePipeline, setup_project_structure

# Set up initial project folder if data is not prepared as desired folder structure
setup_project_structure(
    region="your_region",
    root_dir="path/to/project"
)

# Use case 1 (Basic): Run the complete pipeline
# Initialize the pipeline
pipeline = PrepFirePipeline(
    region="your_region",        # Required: Name of the region folder
    root_dir="path/to/project",  # Optional: Project root directory (defaults to current directory)
    cds_api_key="your_api_key", # Optional: CDS API key (can also be set via environment variable)
    time_of_day=["12:00"],      # Optional: List of times to download weather data for
    min_clusters=4,             # Optional: Minimum number of clusters for weather type clustering
    max_clusters=10,            # Optional: Maximum number of clusters for weather type clustering
    fire_months=[5,6,7,8,9,10] # Optional: List of months to consider for fire season
)

results = pipeline.prepare_simulation()

# Use case 2: If weather information has been provided
# Initialize the pipeline
pipeline = PrepFirePipeline(
    region="your_region",                                       # Required: Name of the region folder
    fire_weather= "path/to/fire_weather.csv"                    # Required: path to the self provided fire weather csv
    root_dir="path/to/project",                                 # Optional: Project root directory (defaults to current directory)
    min_clusters=4,                                             # Optional: Minimum number of clusters for weather type clustering
    max_clusters=10,                                            # Optional: Maximum number of clusters for weather type clustering
    col_fire_size    = "Fire_size_in_ha",                       # Optional: Column name in `fire_weather` for fire size
    col_fire_date    = "Date",                                  # Optional: Column name in `fire_weather` for fire starting date
    weather_variable = ['Temperature', 'RH', 'Wind_speed'],     # Optional: Column name in `fire_weather` for weather variables
)

results = {pipeline.process_fire_data()
                   .generate_weather_types()
                   .generate_ignition_points()
                   .process_landscape()
                   .generate_fmd_and_simpoints()
}


# Access the results
print("\nPipeline completed successfully!")
print("\nGenerated files:")
print(f"- Processed fire data: {results['fires_gdf'].shape[0]} fires processed")
print(f"- Weather types: {len(results['fire_weather'])} weather records")
print(f"- Number of clusters: {results['km_model'].n_clusters}")
print(f"- LCP file: {results['lcp_file']}")
print(f"- FMS directory: {results['fms_dir']}")
print(f"- Ignition probability raster: {results['kde_file']}")
