"""
Advanced Usage Example for SCENFIRE Package

This example demonstrates how to use individual components of the SCENFIRE package
for more fine-grained control over the fire simulation process.
"""

import os
from pathlib import Path
import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt

from scenfire.core.weather import (
    get_bound_extent,
    download_weather_data,
    weather_data_processing,
    extract_fire_weather
)

from scenfire.core.clustering import (
    cluster_fire_weather,
    output_weather_types,
    generate_sample_ignition_points
)

from scenfire.core.raster import (
    process_raster,
    crop_raster_to_bbox,
    build_lcp_file,
    produce_fms,
    produce_ignition_prob_KDE
)

def process_fire_data_example():
    """Example of processing fire data manually"""
    # Load fire data
    fires_path = "input_data/example_region/fires.shp"
    fires_gdf = gpd.read_file(fires_path)
    
    # Get bounding extent with 20km buffer
    bound_extent = get_bound_extent(None, fires_gdf, buffer_size=20000)
    
    # Plot the fires and bounding box
    fig, ax = plt.subplots(figsize=(10, 10))
    fires_gdf.plot(ax=ax, color='red', markersize=10)
    bound_extent.boundary.plot(ax=ax, color='blue', linewidth=2)
    plt.title("Fire Ignition Points and Bounding Box")
    plt.show()
    
    return fires_gdf, bound_extent

def process_weather_data_example(fires_gdf, bound_extent):
    """Example of processing weather data manually"""
    # Download weather data from CDS
    cds_api_key = os.getenv('CDS_API_KEY')
    if not cds_api_key:
        raise ValueError("Please set CDS_API_KEY environment variable")
    
    # Download weather data
    download_weather_data(
        fires_gdf,
        col_fire_date='Date',
        processed_data_path="Processed_data/example_region",
        bound_extent=bound_extent,
        output_crs="EPSG:3035",
        cds_api_key=cds_api_key,
        fetch=True,
        time_of_day=['12:00'],
        fire_months=[5,6,7,8,9,10]
    )
    
    # Process weather data
    weather_data_processing(
        "Processed_data/example_region/Weather",
        "valid_time",
        "longitude",
        "latitude"
    )
    
    # Extract fire weather
    fire_weather = extract_fire_weather(
        fires_gdf,
        "Processed_data/example_region/Weather",
        col_fire_date='Date'
    )
    
    return fire_weather

def cluster_weather_example(fire_weather):
    """Example of clustering weather data manually"""
    # Perform clustering
    km_model = cluster_fire_weather(
        fire_weather,
        min_n=4,
        max_n=10
    )
    
    # Generate weather types
    output_weather_types(
        fire_weather,
        "Processed_data/example_region/Weather",
        km_model,
        n_max=10,
        col_fire_size='Area_ha',
        extreme_percentile=95
    )
    
    return km_model

def process_landscape_example(bound_extent):
    """Example of processing landscape data manually"""
    # Create GeoDataFrame with bounding box
    gdf_bbox = gpd.GeoDataFrame(
        geometry=[bound_extent],
        crs="EPSG:3035"
    )
    
    # Process each landscape component
    components = ['elevation', 'slope', 'aspect', 'fuel',
                 'canopyCover', 'canopyHeight', 'cbh', 'cbd']
    
    for comp in components:
        input_file = f"input_data/example_region/lcp_Fuel/{comp}.tif"
        output_file = f"Processed_data/example_region/Landscape/{comp}.tif"
        
        # Process and crop raster
        process_raster(
            input_file,
            output_file,
            gdf_bbox,
            new_crs="EPSG:3035",
            resolution=100
        )
    
    # Build LCP file
    build_lcp_file(
        "Processed_data/example_region/Landscape",
        "Processed_data/example_region/Final/lcp_.tif",
        components
    )

def generate_output_files_example():
    """Example of generating output files manually"""
    # Generate FMS files
    produce_fms(
        "Processed_data/example_region/Landscape/fuel.tif",
        "Processed_data/example_region/Weather",
        "Processed_data/example_region/Weather/fms"
    )
    
    # Generate ignition probability raster
    produce_ignition_prob_KDE(
        "input_data/example_region/fires.shp",
        "Processed_data/example_region/Landscape/fuel.tif",
        "Processed_data/example_region/Ignition/ig_kde.tif"
    )

def main():
    """Run all examples"""
    print("Processing fire data...")
    fires_gdf, bound_extent = process_fire_data_example()
    
    print("\nProcessing weather data...")
    fire_weather = process_weather_data_example(fires_gdf, bound_extent)
    
    print("\nClustering weather data...")
    km_model = cluster_weather_example(fire_weather)
    
    print("\nProcessing landscape data...")
    process_landscape_example(bound_extent)
    
    print("\nGenerating output files...")
    generate_output_files_example()
    
    print("\nAll processing completed successfully!")

if __name__ == "__main__":
    main() 