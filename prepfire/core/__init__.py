"""
PREPFIRE Core Module

This module contains the core functionality for fire simulation and analysis,
including weather data processing, clustering, and raster operations.
"""

from .weather import (
    get_bound_extent,
    download_weather_data,
    weather_data_processing,
    extract_fire_weather
)

from .clustering import (
    cluster_fire_weather,
    output_weather_types,
    generate_sample_ignition_points,
)

from .raster import (
    process_raster,
    crop_raster_to_bbox,
    build_lcp_file,
    produce_fms,
    produce_ignition_prob_KDE
)

__all__ = [
    # Weather functions
    'get_bound_extent',
    'download_weather_data',
    'weather_data_processing',
    'extract_fire_weather',
    
    # Clustering functions
    'cluster_fire_weather',
    'output_weather_types',
    'generate_sample_ignition_points',
    
    # Raster functions
    'process_raster',
    'crop_raster_to_bbox',
    'build_lcp_file',
    'produce_fms',
    'produce_ignition_prob_KDE'
] 