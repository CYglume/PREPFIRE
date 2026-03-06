"""
PREPFIRE Pipeline Module

This module provides a class-based implementation for the PREPFIRE package
for fire simulation input preparation and analysis.
"""

import os
import warnings
import logging
from pathlib import Path
from typing import Optional, List
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
from shapely.geometry import box
from datetime import datetime
import cdsapi
import rasterio
from rasterio.mask import mask
from rasterio.warp import transform_bounds
from rasterio.crs import CRS
from rasterio.enums import Resampling

from .core.weather import (
    get_bound_extent,
    download_weather_data,
    weather_data_processing,
    extract_fire_weather
)

from .core.clustering import (
    cluster_fire_weather,
    output_weather_types,
    generate_sample_ignition_points
)

from .core.raster import (
    process_raster,
    crop_raster_to_bbox,
    build_lcp_file,
    produce_fms,
    produce_ignition_prob_KDE
)

from .core import clustering, raster, weather
from .utils import helpers

logger = logging.getLogger(__name__)

class PrepFirePipeline:
    """
    A class to manage the PREPFIRE pipeline for fire simulation input preparation.

    This class provides a structured way to execute the complete PREPFIRE pipeline,
    including data loading, weather processing, clustering, and file generation.
    
    The pipeline can use either a specified root directory or the current working directory
    as the anchor point for all paths. The expected directory structure is:
    
    ```
    root_directory/
    ├── input_data/
    │   └── region/
    │       ├── fires.shp
    │       ├── lcp_Fuel/
    │       └── cropping_polygon/ (optional bounding box)
    └── Processed_data/
        └── region/
    ```
    """
    
    def __init__(
        self,
        region: str,
        root_dir: Optional[str] = None,
        bound_coords: Optional[list[float]] = None,
        output_crs: str = "EPSG:3035",
        col_fire_size: str = 'Area_ha',
        col_fire_date: str = 'Date',
        extreme_percentile: int | float | list | tuple = 95,
        lcp_components: Optional[List[str]] = ['elevation', 'slope', 'aspect', 'fuel', 'canopyCover', 'canopyHeight', 'cbh', 'cbd'],
        cds_api_key: Optional[str] = None,
        time_of_day: List[str] = ['12:00'],
        buffer_size: int = 20000,
        min_clusters: int = 4,
        max_clusters: int = 10,
        fire_months: Optional[List[int]] = [5,6,7,8,9,10],
        lcp_resolution: int = 100,
        done_cds_download: bool = False,
        livePlantMoist = [60, 90],
        weather_variable: Optional[List[str]] = ['T', 'RH', 'WS', 'DFMC'],
        fire_weather: Optional[str] = None,
        log_level: str = 'INFO',
    ):
        """
        Initialize the PREPFIRE pipeline.
        
        Parameters
        ----------
        region : str
            Name of the region being processed. This should match the folder name
            under input_data/ where the fire data is located.
        root_dir : str, optional
            Root directory for the project. If not provided, the current working
            directory will be used.
        bound_coords : list of float, optional
            Coordinates of the bounding box [xmin, ymin, xmax, ymax] in the output CRS.
            If not provided, will be calculated from input cropping polygon or fire data (the least option).
        output_crs : str, optional
            Coordinate reference system for the output data. Default is "EPSG:3035"
            (ETRS89 / LAEA Europe).
        col_fire_size : str, optional
            Column name for fire size data in hectares. Default is 'Area_ha'.
        col_fire_date : str, optional
            Column name for fire date data. Default is 'Date'.
        extreme_percentile : int | tuple | list (Default = 95)
            int: Percentile for extreme weather types (e.g., 95 for 95th percentile) \\
            tuple | list: List of percentiles to generate mean weather types within each percentile interval (from p0 to p100)
        lcp_components : list of str, optional
            List of landscape components for LCP building. Default includes:
            ['elevation', 'slope', 'aspect', 'fuel', 'canopyCover', 'canopyHeight', 'cbh', 'cbd']
        cds_api_key : str, optional
            API key for Copernicus Climate Data Store. Can also be set via CDS_API_KEY
            environment variable.
        time_of_day : list of str, optional
            List of times of day for CDS weather data download in 24h format (HH:MM).
            Default is ['12:00'].
        buffer_size : int, optional
            Buffer size in meters for weather data extraction. Must be positive.
            Default is 20000 (20km).
        min_clusters : int, optional
            Minimum number of clusters for weather type clustering. Must be at least 2.
            Default is 4.
        max_clusters : int, optional
            Maximum number of clusters for weather type clustering. Must be greater than
            min_clusters. Default is 10.
        log_level : str, optional
            Logging level. Must be one of: 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'.
            Default is 'INFO'.
        fire_months : list of int, optional
            List of months (1-12) to consider for fire season. Default is [5,6,7,8,9,10]
            (May to October).
        lcp_resolution : int, optional
            Resolution of output LCP raster in meters. Must be positive.
            Default is 100.
        done_cds_download : bool, optional
            Whether to skip the CDS download step. Default is False.
        weather_variable: List of str, optional
            Weather variables to be used for weather scenario clustering.
        livePlantMoist: list of int, optional
            Two int of moisture of live herbaceous (first int) and live woody plants (second int).
            Only accepted exactly two values.
        fire_weather: path to csv file for fire weather input, optional
            Table should contain fire size information (column name: col_fire_size) and fire weather extraction at starting date.
            Weather column should contain variables stated in `weather_variable`

        Raises
        ------
        ValueError
            If required parameters are missing or invalid.
        """
        print(f"------ Initialization of PREPFIRE pipeline for region: {region} ------")
        # Initialize attributes
        self.region             = region
        self.bound_coords       = bound_coords
        self.output_crs         = output_crs
        self.col_fire_size      = col_fire_size
        self.col_fire_date      = col_fire_date
        self.extreme_percentile = extreme_percentile
        self.time_of_day        = time_of_day
        self.buffer_size        = buffer_size
        self.min_clusters       = min_clusters
        self.max_clusters       = max_clusters
        self.log_level          = log_level
        self.fire_months        = fire_months
        self.lcp_resolution     = lcp_resolution
        self.lcp_components     = lcp_components
        self.done_cds_download  = done_cds_download
        self.weather_variable   = weather_variable
        self.fire_weather       = fire_weather
        self.livePlantMoist     = livePlantMoist
        
        # Set root directory
        self.root_dir = root_dir if root_dir else os.getcwd()
        
        # Get CDS API key from parameters or environment
        if not self.done_cds_download:
            self.cds_api_key = cds_api_key or os.getenv('CDS_API_KEY', '')
        
        # Validate region
        if not self.region:
            raise ValueError("Region name must be provided")
            
        # Validate other parameters
        if isinstance(self.extreme_percentile, int | float):
            if self.extreme_percentile < 0 or self.extreme_percentile > 100:
                raise ValueError("Extreme percentile must be between 0 and 100")
        if isinstance(self.extreme_percentile, list | tuple):
            if any(pp < 0 or pp > 100 for pp in self.extreme_percentile):
                raise ValueError("Extreme percentile must be between 0 and 100")
        if self.buffer_size <= 0:
            raise ValueError("Buffer size must be positive")
        if self.min_clusters < 2:
            raise ValueError("Minimum number of clusters must be at least 2")
        if self.max_clusters < self.min_clusters:
            raise ValueError("Maximum number of clusters must be greater than minimum")
        if not all(1 <= m <= 12 for m in self.fire_months):
            raise ValueError("Fire months must be between 1 and 12")
        if self.lcp_resolution <= 0:
            raise ValueError("LCP resolution must be positive")
        
        # Set paths
        self.input_data_path = os.path.join(self.root_dir, "input_data", self.region)
        self.processed_data_path = os.path.join(self.root_dir, "Processed_data", self.region)
        self.weather_dir = os.path.join(self.processed_data_path, "Weather")
        
        # Store intermediate results
        self.fires_gdf = None
        self.fires_gdf_WGS84 = None
        self.bound_extent = None
        self.buffered_bound_extent = None
        self.km_model = None
        self.ignition_file = None
        self.lcp_file = None
        self.output_files = {}
        
        # Configure logging (sets root logger level; only effective if no handlers exist yet)
        logging.basicConfig(
            level=getattr(logging, self.log_level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            force=True,  # override any earlier basicConfig call
        )
        
        # Check directory structure
        self._validate_directory_structure()
        self._create_processed_directories()
        
        logger.info(f"Initialized PREPFIRE pipeline for region: {self.region}")
        
    def _validate_directory_structure(self):
        """
        Validate the required directory structure exists.
        
        This method checks if the required input directories exist and creates them if they don't.
        It also logs warnings if directories need to be created.
        
        Returns
        -------
        None
        """            
        if not os.path.exists(os.path.join(self.input_data_path, "lcp_Fuel")):
            os.makedirs(os.path.join(self.input_data_path, "lcp_Fuel"), exist_ok=True)
            logger.warning(f"Created LCP fuel directory: {os.path.join(self.input_data_path, 'lcp_Fuel')}")
            logger.warning("..Please add input data files before running the pipeline")

        if not os.path.exists(os.path.join(self.input_data_path, "cropping_polygon")):
            os.makedirs(os.path.join(self.input_data_path, "cropping_polygon"), exist_ok=True)
            logger.warning(f"Created LCP fuel directory: {os.path.join(self.input_data_path, 'cropping_polygon')}")
            logger.warning("..Cropping_polygon is optional for cropping the processing area by extra input file.")
    
    def _create_processed_directories(self):
        """
        Create the processed data directory structure.
        
        This method creates the directory structure needed for storing processed data,
        including directories for single fire processing, landscape data, ignition points,
        weather data, and simulation results.
        
        Returns
        -------
        None
        """
        # Create main processed data directory
        os.makedirs(self.processed_data_path, exist_ok=True)
        
        # Create subdirectories for different processing stages
        subdirs = [
            "Single",          # For single fire processing
            "Landscape",       # For landscape data
            "Ignition",        # For ignition points
            "Weather",         # For weather data
            os.path.join("Weather", "CDS"),  # For raw CDS data
            "Final",          # For final output files
            "Sim"             # For simulation results
        ]
        
        for subdir in subdirs:
            os.makedirs(os.path.join(self.processed_data_path, subdir), exist_ok=True)
        logger.info("Created processed data directory structure")
    
    def process_fire_data(self, plot_fires: bool = False):
        """
        Load and process fire data from shapefiles.
        
        This method loads fire data from shapefiles in the input directory,
        filters fires within the bounding box, reprojects to the output CRS,
        and saves the processed data to a GeoPackage file.
        
        Parameters
        ----------
        plot_fires : bool, optional (default=False)
            Whether to plot the fire locations after processing
            
        Returns
        -------
        self : PrepFirePipeline
            For method chaining
            
        Raises
        ------
        FileNotFoundError
            If no shapefile is found in the input directory
        ValueError
            If required columns are missing from the fire data
        """
        print(f"------ Processing fire ignition data ------")
        # Check input fire historical data (vector file)
        fire_files = [f for f in os.listdir(self.input_data_path) if f.endswith(('.shp', '.gpkg'))]
        if not fire_files:
            raise FileNotFoundError(f"No shapefile found in {self.input_data_path}")
        if len(fire_files) > 1:
            logger.warning(f"Multiple shapefiles found in {self.input_data_path}. Using the first one: {fire_files[0]}")
        
        fires_f = os.path.join(self.input_data_path, fire_files[0])
        self.fires_gdf = gpd.read_file(fires_f)
        self.fires_gdf = self.fires_gdf.to_crs(crs=self.output_crs)
        logger.info(f"Loaded fire data from: {fires_f}")
        
        # Verify required columns exist
        required_columns = [self.col_fire_size, self.col_fire_date]
        missing_columns = [col for col in required_columns if col not in self.fires_gdf.columns]
        if missing_columns:
            raise ValueError(f"Required columns not found in fire data: {', '.join(missing_columns)}")
        
        ###
        # Check extra input cropping polygon
        # bound_coord (gpd, list, tuple, None) will be used to generate buffered_bound
        # bound_extent (should be geoDataFrame) will be used to generate new ignition points
        if self.bound_coords is None:
            # Only search for cropping polygon when no bounding coordinates input
            bound_ply_files = [f for f in os.listdir(os.path.join(self.input_data_path, "cropping_polygon")) if f.endswith(('.shp', '.gpkg'))]
            if bound_ply_files: 
                # Case 1: using extra bound file
                if len(bound_ply_files) > 1:
                    raise ValueError(f"Found {len(bound_ply_files)} polygon file, which should be 1 only.")
                else:
                    # if detect cropping polygon file
                    # Replace null bound_coords with the input polygon
                    bound_ply_f = os.path.join(self.input_data_path, "cropping_polygon", bound_ply_files[0])
                    self.bound_coords = gpd.read_file(bound_ply_f)
                    self.bound_extent = self.bound_coords
                    logger.info(f"Loaded bounding extent data from: {bound_ply_f}")
            else: 
                # Case 2: using boundary from fire historical vector
                self.bound_extent = gpd.GeoDataFrame({'geometry': [box(*self.fires_gdf.total_bounds)]}, crs=self.fires_gdf.crs).to_crs(crs=self.output_crs)
        else:
            # Case 3: using manually input boundary
            self.bound_extent = gpd.GeoDataFrame({'geometry': [box(*self.bound_coords)]}, crs="EPSG:4326").to_crs(crs=self.output_crs)

        ###
        # Process fire data
        self.buffered_bound_extent = get_bound_extent(self.bound_coords, self.fires_gdf, self.output_crs, self.buffer_size)
        self.fires_gdf    = self.fires_gdf[self.fires_gdf.intersects(self.buffered_bound_extent)]
        # Drop fid column if it exists for export to gpkg
        if 'fid' in self.fires_gdf.columns:
            self.fires_gdf = self.fires_gdf.drop(columns='fid')
        
        # Save processed fire data
        output_path = os.path.join(self.processed_data_path, "Ignition", "fires_region.gpkg")
        self.fires_gdf.to_file(output_path, index=False)
        logger.info(f"Processed {len(self.fires_gdf)} fires")
        
        if plot_fires:
            fig, ax = plt.subplots(figsize=(10, 10))
            self.fires_gdf.to_crs(epsg=4326).plot(ax=ax, color='red', markersize=10)
            ax.set_xlabel('Longitude')
            ax.set_ylabel('Latitude')
            plt.show()
        return self
    
    def process_weather_data(self):
        """
        Process weather data for the region.
        
        This method downloads weather data from the Copernicus Climate Data Store (CDS),
        processes the downloaded data, and extracts weather conditions for fire events.
        
        Returns
        -------
        self : PrepFirePipeline
            For method chaining
            
        Raises
        ------
        ValueError
            If fire data has not been processed or if no weather data was extracted
        """
        print(f"------ Processing Weather Data ------")
        if self.fires_gdf is None or self.buffered_bound_extent is None:
            raise ValueError("Fire data not processed. Call process_fire_data() first.")
        self.fires_gdf_WGS84 = self.fires_gdf.to_crs(epsg=4326)
        logger.info("CRS for fire gdf changed to EPSG:4326! (matching CDS)")

        try:           
            downloaded_nc = ["era5_2m_temperature.nc", "era5_2m_dewpoint_temperature.nc", "era5_10m_u_component_of_wind.nc", "era5_10m_v_component_of_wind.nc"]
            # Get API key interactively if not provided
            if self.done_cds_download:
                if any([f not in os.listdir(self.weather_dir) for f in downloaded_nc]):
                    logger.info("Weather data not complete in folder!")
                    self.done_cds_download = False

            if not self.done_cds_download:
                if not self.cds_api_key:
                    self.cds_api_key = input("Please enter your Copernicus Climate Data Store API key: ").strip()
                    if not self.cds_api_key:
                        raise ValueError("CDS API key is required for weather data processing")
            
            # Download weather data
            if not self.done_cds_download:
                self.done_cds_download = download_weather_data(
                    gdf=self.fires_gdf_WGS84,
                    date_column=self.col_fire_date,
                    processed_path=self.processed_data_path,
                    bound_extent_ply=self.buffered_bound_extent,
                    bound_crs=self.output_crs,
                    cdsAPI_KEY=self.cds_api_key,
                    fetch=True,
                    time_of_day=self.time_of_day,
                    fire_months=self.fire_months
                )
            
            # Process weather data
            weather_data_processing(
                weather_dir=self.weather_dir,
                in_cds_time="valid_time",
                in_cds_x="longitude",
                in_cds_y="latitude"
            )
 
            # Extract fire weather
            self.fire_weather = extract_fire_weather(
                fires_gdf_wgs=self.fires_gdf_WGS84,
                weather_dir=self.weather_dir,
                date_column=self.col_fire_date,
                dfmc_type='rh'
            )
            
            if self.fire_weather is None or self.fire_weather.empty:
                raise ValueError("No weather data was extracted")
            
            logger.info("Weather data processing completed successfully")
            
        except Exception as e:
            logger.error(f"Error processing weather data: {str(e)}")
            raise
            
        return self
    
    def generate_weather_types(self):
        """
        Process and generate weather types from processed data.
        
        This method performs clustering on the fire weather data to identify distinct
        weather patterns, and generates extreme and mean weather type summaries.
        
        Returns
        -------
        self : PrepFirePipeline
            For method chaining
            
        Raises
        ------
        ValueError
            If weather data has not been processed or if clustering parameters are invalid
        FileNotFoundError
            If required output files are not created
        """
        print(f"------ Generating Scenario types from weather ------")
        if self.fire_weather is None:
            raise ValueError("Weather data not processed. Call process_weather_data() first.")
        

        
        try:
            # Validate input data
            if self.fire_weather.empty:
                raise ValueError("Weather data is empty")
            
            # Validate clustering parameters
            if self.min_clusters < 2:
                raise ValueError("Minimum number of clusters must be at least 2")
            if self.max_clusters < self.min_clusters:
                raise ValueError("Maximum number of clusters must be greater than minimum")
            if self.max_clusters > len(self.fire_weather):
                raise ValueError("Maximum number of clusters cannot exceed number of samples")
            
            logger.info(f"Performing clustering analysis with {self.min_clusters}-{self.max_clusters} clusters...")
            
            # Perform clustering
            self.km_model = cluster_fire_weather(
                fire_weather=self.fire_weather,
                min_n=self.min_clusters,
                max_n=self.max_clusters,
                weather_variable=self.weather_variable
            )
            
            if self.km_model is None:
                raise ValueError("Clustering analysis failed to find optimal clusters")
            
            # Generate weather types
            logger.info("Generating weather types...")
            output_weather_types(
                fire_weather=self.fire_weather,
                weather_dir=self.weather_dir,
                km=self.km_model,
                extreme_percentile=self.extreme_percentile,
                col_fire_size=self.col_fire_size,
                weather_variable=self.weather_variable
            )
            
            logger.info(f"Weather type generation completed successfully with {self.km_model.n_clusters} clusters")
            
        except Exception as e:
            logger.error(f"Error generating weather types: {str(e)}")
            raise
            
        return self
    
    def generate_ignition_points(self):
        """
        Generate sample ignition points.
        
        This method directly calling the `generate_sample_ignition_points()` function generates random ignition points within the bounding box
        and saves them to a text file for use in fire simulations.
        
        Returns
        -------
        self : PrepFirePipeline
            For method chaining
            
        Raises
        ------
        ValueError
            If bound extent is not defined
        FileNotFoundError
            If the output file is not created
        """
        print(f"------ Generating random ignition points for simulation ------")
        if self.bound_extent is None:
            raise ValueError("Bound extent not defined. Call process_fire_data() first.")
        
        # Define output file path
        self.output_ig_point_list = os.path.join(self.processed_data_path, "Ignition", "Sample_ig_pts.txt")
        
        # Generate the sample points
        generate_sample_ignition_points(
            bound_geometry=self.bound_extent,
            bound_crs=self.output_crs, 
            sampletxt_output_filename=self.output_ig_point_list
        )
        
        # Validate output file was created
        if not os.path.exists(self.output_ig_point_list):
            raise FileNotFoundError("Sample points file was not created")
            
        logger.info("Sample points generated")
        return self
    
    def process_landscape(self):
        """
        Process landscape data for the region.
        
        This method processes each landscape component raster, reprojects and resamples
        them to the specified CRS and resolution, and builds a multi-band LCP file.
        
        Returns
        -------
        self : PrepFirePipeline
            For method chaining
            
        Raises
        ------
        ValueError
            If bound extent is not defined
        FileNotFoundError
            If required raster files are not found or if the LCP file is not created
        """
        print(f"------ Processing landscape data ------")
        if self.buffered_bound_extent is None:
            raise ValueError("Bound extent not defined. Call process_fire_data() first.")
        
        try:
            # Validate input raster files exist
            required_files = [
                os.path.join(self.input_data_path, "lcp_Fuel", f"{comp}.tif")
                for comp in self.lcp_components
            ]
            in_folder_raster = [f for f in os.listdir(os.path.join(self.input_data_path, "lcp_Fuel")) if f.endswith('.tif')]
            
            missing_files = [f for f in required_files if not os.path.exists(f)]
            if missing_files:
                raise FileNotFoundError(
                    f"Required raster files not found: {', '.join(missing_files)} \n Found raster files: {', '.join(in_folder_raster)}"
                )
            
            # Create GeoDataFrame with bounding box
            gdf_bbox = gpd.GeoDataFrame(
                geometry=[self.buffered_bound_extent],
                crs=self.output_crs
            )
            
            # Process each landscape component
            for comp in self.lcp_components:
                logger.info(f"Processing landscape component: {comp}")
                input_file = os.path.join(self.input_data_path, "lcp_Fuel", f"{comp}.tif")
                temp_file = os.path.join(self.processed_data_path, "Landscape", f"{comp}_temp.tif")
                output_file = os.path.join(self.processed_data_path, "Landscape", f"{comp}.tif")
                
                # First process the raster
                process_raster(
                    input_raster_path=input_file,
                    output_raster_path=temp_file,
                    gdf_bbox=gdf_bbox,
                    new_crs=self.output_crs,
                    resolution=self.lcp_resolution
                )
                
                # Then crop the processed raster to the bounding box
                crop_raster_to_bbox(
                    input_raster_path=temp_file,
                    output_raster_path=output_file,
                    gdf_bbox=gdf_bbox,
                )
            
            # Build LCP file
            self.lcp_file = os.path.join(self.processed_data_path, "Final", "lcp_.tif")
            build_lcp_file(
                input_folder=os.path.join(self.processed_data_path, "Landscape"),
                output_file=self.lcp_file,
                lcp_comp=self.lcp_components
            )
            
            # Validate LCP file creation
            if not os.path.exists(self.lcp_file):
                raise FileNotFoundError("LCP file was not created successfully")
            
            logger.info("Landscape processing completed successfully")
            
        except Exception as e:
            logger.error(f"Error processing landscape data: {str(e)}")
            raise
        finally:
            # Clean up temporary files
            for temp_file in [os.path.join(self.processed_data_path, "Landscape", f"{comp}_temp.tif") for comp in self.lcp_components]:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    
        return self
    
    def generate_fmd_and_simpoints(self):
        """
        Generate FMS and KDE point density files.
        
        This method generates fuel moisture scenario (FMS) files based on weather types
        and produces an ignition probability raster using kernel density estimation.
        
        Returns
        -------
        self : PrepFirePipeline
            For method chaining
        """
        # Create output directories
        print(f"------ Generating .fms and ignition points KDE ------")
        os.makedirs(os.path.join(self.weather_dir, "fms"), exist_ok=True)
        
        # Produce FMS files
        fuel_raster = os.path.join(self.processed_data_path, "Landscape", "fuel.tif")
        fms_dir = os.path.join(self.weather_dir, "fms")
        
        produce_fms(
            fuel_raster_path=fuel_raster,
            weather_dir=self.weather_dir,
            fms_out_dir=fms_dir,
            liveHerb=self.livePlantMoist[0],
            liveWood=self.livePlantMoist[1],
            extreme_percentile=self.extreme_percentile,
        )
        
        # Produce ignition probability raster
        fire_files = [f for f in os.listdir(self.input_data_path) if f.endswith(('.shp', '.gpkg'))]
        fires_f = os.path.join(self.input_data_path, fire_files[0])
        
        kde_file = os.path.join(self.processed_data_path, "Ignition", "ig_kde.tif")
        produce_ignition_prob_KDE(
            fires_f=fires_f,
            template_raster_path=fuel_raster,
            output_raster=kde_file
        )
        
        # Store output file paths
        self.output_files = {
            'fms_dir': fms_dir,
            'kde_file': kde_file
        }
        
        logger.info("Output files generated")
        return self
    
    def run_fire_simulations(self):
        """
        (Pending function)
        (Will be updated)
        Run fire simulations based on the prepared data.
        
        Returns:
        --------
        self : PrepFirePipeline
            For method chaining
        """
        # This function needs to be implemented to run actual fire simulations
        # Use the code from mtt_simulations.py
        print(f"------ Prepare simulation settings for: {self.region} ------")
        return self
    

    
    def prepare_simulation(self):
        """
        Run the complete fire simulation pipeline.
        
        This method runs all pipeline stages in sequence:
        1. Setup directories
        2. Load fire data
        3. Process weather data
        4. Generate weather types
        5. Generate sample points
        6. Process landscape and build LCP file
        7. Generate output files (FMS, Ig_points_KDE)
        8. Run fire simulations (pending)
        
        Returns
        -------
        dict
            Dictionary containing all results and file paths
            
        Raises
        ------
        Exception
            If any stage of the pipeline fails
        """
        try:
            # Execute pipeline stages
            (self
                .process_fire_data()
                .process_weather_data()
                .generate_weather_types()
                .generate_ignition_points()
                .process_landscape()
                .generate_fmd_and_simpoints()
            )
            
            logger.info("Pipeline completed successfully")
            
            # Return results dictionary
            return {
                'fires_gdf': self.fires_gdf,
                'fires_gdf_WGS84': self.fires_gdf_WGS84,
                'bound_extent': self.bound_extent,
                'fire_weather': self.fire_weather,
                'km_model': self.km_model,
                'ignition_file': self.ignition_file,
                'lcp_file': self.lcp_file,
                **self.output_files
            }
            
        except Exception as e:
            logger.error(f"Pipeline failed: {str(e)}")
            raise

def setup_project_structure(region, root_dir=None):
    """
    Set up the initial project directory structure for input data.
    
    Creates the following directory structure:
    ```
    root_dir/
    ├── input_data/
    │   └── region/
    │       └── lcp_Fuel/
    │       └── cropping_polygon/ (optional bounding box)
    └── Processed_data/
    ```
    
    Parameters
    ----------
    region : str
        Region name for the project
    root_dir : str, optional
        Root directory for the project. If not provided, the current working
        directory will be used.
        
    Returns
    -------
    None
    """
    if root_dir is None:
        root_dir = os.getcwd()
    else:
        root_dir = os.path.abspath(root_dir)

    # Create directory structure for input data
    dirs = [
        os.path.join(root_dir, "input_data"),
        os.path.join(root_dir, "Processed_data"),
        os.path.join(root_dir, "input_data", region),
        os.path.join(root_dir, "input_data", region, "lcp_Fuel"),
        os.path.join(root_dir, "input_data", region, "cropping_polygon")
    ]
    
    for dir_path in dirs:
        os.makedirs(dir_path, exist_ok=True)
        logger.info(f"Created directory: {dir_path}")

def run_prepare(region, root_dir=None, **kwargs):
    """
    Run the complete fire simulation pipeline.
    
    This function sets up the project structure and runs the complete PREPFIRE pipeline
    for the specified region.
    
    Parameters
    ----------
    region : str
        Region name for the project
    root_dir : str, optional
        Root directory for the project. If not provided, the current working
        directory will be used.
    **kwargs : dict, optional
        Additional keyword arguments to pass to the PrepFirePipeline constructor.
        See PrepFirePipeline.__init__ for more details.
        
    Returns
    -------
    dict
        Results and paths to output files
    """
    print(f"--->> Run all in module processes for {region} ------")
    setup_project_structure(region, root_dir=root_dir)
    pipeline = PrepFirePipeline(region=region, **kwargs)
    return pipeline.prepare_simulation() 