import logging
import os

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import rasterio.warp
from scipy.stats import gaussian_kde

logger = logging.getLogger(__name__)

# Public functions

def process_raster(input_raster_path, output_raster_path, gdf_bbox, new_crs='EPSG:3035', resolution=100):
    """
    Crops a raster to the extent of a GeoDataFrame bounding box, reprojects it to a new CRS,
    and resamples it to a given resolution.
    
    Parameters
    ----------
    input_raster_path : str
        Path to input raster file
    output_raster_path : str
        Path where the processed raster will be saved
    gdf_bbox : GeoDataFrame
        GeoDataFrame containing the bounding box geometry
    new_crs : str, optional (default='EPSG:3035')
        Target coordinate reference system
    resolution : float, optional (default=100)
        Target resolution in meters
        
    Returns
    -------
    None
        Saves the processed raster to the specified output path
        
    Notes
    -----
    This function performs three operations in sequence:
    1. Crops the raster to the extent of the bounding box
    2. Reprojects the cropped raster to the specified CRS
    3. Resamples the reprojected raster to the specified resolution
    """
    with rasterio.open(input_raster_path) as src:
        # Ensure bbox is in source CRS
        if gdf_bbox.crs != src.crs:
            gdf_bbox = gdf_bbox.to_crs(src.crs)
        
        # Extract bbox coordinates
        minx, miny, maxx, maxy = gdf_bbox.total_bounds  # Use total_bounds for safety
        
        # Create a reading window for the raster with the bbox
        window = rasterio.windows.from_bounds(minx, miny, maxx, maxy, transform=src.transform)
        

        # Read the cropped data
        data = src.read(1, window=window)

        # Get transform for the window
        window_transform = src.window_transform(window)

        # Reproject the cropped bounds to the new CRS
        dst_bounds = rasterio.warp.transform_bounds(src.crs, new_crs, minx, miny, maxx, maxy)

        # Calculate new transform and shape based on resolution
        dst_transform = rasterio.transform.from_origin(
            west=dst_bounds[0], north=dst_bounds[3], xsize=resolution, ysize=resolution
        )
        dst_width = int((dst_bounds[2] - dst_bounds[0]) / resolution)
        dst_height = int((dst_bounds[3] - dst_bounds[1]) / resolution)

        # Prepare metadata
        kwargs = src.meta.copy()
        kwargs.update({
            'crs': new_crs,
            'transform': dst_transform,
            'width': dst_width,
            'height': dst_height,
            'dtype': 'float32',  # Adjust if needed
        })

        # Reproject the cropped data
        destination = np.empty((dst_height, dst_width), dtype='float32')
        rasterio.warp.reproject(
            source=data,
            destination=destination,
            src_transform=window_transform,
            src_crs=src.crs,
            dst_transform=dst_transform,
            dst_crs=new_crs,
            resampling=rasterio.warp.Resampling.nearest
        )

        # Write to output raster
        with rasterio.open(output_raster_path, 'w', **kwargs) as dst:
            dst.write(destination, 1)
    
    logger.info("Raster has been processed and saved to: %s", output_raster_path)

def crop_raster_to_bbox(input_raster_path, output_raster_path, gdf_bbox):
    """
    Crops a raster to the extent of a bounding box defined by a GeoDataFrame.
    
    Parameters
    ----------
    input_raster_path : str
        Path to input raster file
    output_raster_path : str
        Path where the cropped raster will be saved
    gdf_bbox : GeoDataFrame
        GeoDataFrame containing the bounding box geometry
        
    Returns
    -------
    None
        Saves the cropped raster to the specified output path
        
    Notes
    -----
    This function only crops the raster to the extent of the bounding box.
    This ensure the correct extent of the raster is used for the simulation.
    It does not reproject or resample the raster. For those operations,
    use process_raster() instead.
    """
    with rasterio.open(input_raster_path) as src:
        # Ensure the raster CRS matches gdf_bbox CRS, reproject if necessary
        if src.crs != gdf_bbox.crs:
            gdf_bbox = gdf_bbox.to_crs(src.crs)

        # Get bbox limits in raster CRS coordinates
        minx, miny, maxx, maxy = gdf_bbox.geometry.bounds.iloc[0]
        
        # Create a reading window for the raster with the bbox
        window = rasterio.windows.from_bounds(minx, miny, maxx, maxy, transform=src.transform)

        # Read the data from the selected window
        data = src.read(1, window=window)  # Read the first band of the raster

        # Define the transformation and metadata for the new raster
        new_transform = rasterio.windows.transform(window, src.transform)
        kwargs = src.meta.copy()
        kwargs.update({
            'crs': src.crs,
            'transform': new_transform,
            'width': window.width,
            'height': window.height,
        })

        # Save the cropped raster to output file
        with rasterio.open(output_raster_path, 'w', **kwargs) as dst:
            dst.write(data, 1)

    logger.info("Raster has been cropped and saved to: %s", output_raster_path)

def build_lcp_file(input_folder, output_file, lcp_comp = ['elevation', 'slope', 'aspect', 'fuel', 'canopyCover', 'canopyHeight', 'cbh', 'cbd']):
    """
    Build a multi-band LCP (Landscape) file by stacking individual raster layers. 
    The landscape file is built based on the requirements of FconstMTT (FlameMap) as default.
    
    Parameters
    ----------
    input_folder : str
        Path to folder containing individual raster files
    output_file : str 
        Path where the output LCP file will be saved
    lcp_comp : list, optional (default=['elevation', 'slope', 'aspect', 'fuel', 'canopyCover', 'canopyHeight', 'cbh', 'cbd'])
        List of landscape components to include in the LCP file. Default includes:
        elevation, slope, aspect, fuel, canopy cover, canopy height, canopy base height,
        and canopy bulk density
        
    Returns
    -------
    None
        Creates a multi-band GeoTIFF file at the specified output path
        
    Notes
    -----
    The LCP file is a multi-band GeoTIFF file where each band represents a different
    landscape component. The bands are ordered according to the lcp_comp list.
    Each band is tagged with a descriptive name in the file metadata.
    """
                             

    # Get list of raster files, excluding temporary files
    raster_files = [os.path.join(input_folder, f) for f in os.listdir(input_folder) if os.path.isfile(os.path.join(input_folder, f))]
    raster_files = [f for f in raster_files if "temp" not in f]

    # Map component names to their corresponding files
    raster_files_sorted = {l:f for l in lcp_comp for f in raster_files if l in f}
    
    # Define descriptive layer names for metadata
    layer_names = {'elevation'     : 'Elevation',
                   'slope'         : 'Slope',
                   'aspect'        : 'Aspect',                
                   'fuel'          : 'Fuel models',
                   'canopyCover'   : 'Canopy cover',
                   'canopyHeight'  : 'Canopy height',
                   'cbh'           : 'Canopy base height',
                   'cbd'           : 'Canopy bulk density'
                }

    # Read all raster layers into memory
    layers = {}
    for fp in raster_files_sorted:
        with rasterio.open(raster_files_sorted[fp]) as src:
            layers[fp] = src.read(1)

    # Get metadata from first raster to use as template
    with rasterio.open(list(raster_files_sorted.values())[0]) as src0:
        meta = src0.meta

    # Update metadata for multi-band output
    meta.update({
        "driver": "GTiff",
        "count": len(raster_files_sorted)  # Number of layers
    })

    # Write stacked raster with layer descriptions
    with rasterio.open(output_file, "w", **meta) as dest:
        for idx in range(len(lcp_comp)):
            dest.write(layers[lcp_comp[idx]], idx + 1)
            dest.update_tags(idx + 1, DESCRIPTION=layer_names[lcp_comp[idx]])

    logger.info("LCP file built: %s", output_file)

def produce_fms(fuel_raster_path, weather_dir, fms_out_dir, liveHerb=60, liveWood=90, extreme_percentile=95):
    """
    Produce fuel moisture scenario (FMS) files based on weather type data.

    Parameters
    ----------
    fuel_raster_path : str
        Path to fuel type raster file
    weather_dir : str
        Directory containing weather type CSV files
    fms_out_dir : str
        Directory to write output FMS files to
    liveHerb : int, optional (default = 60)
        Moisture condition for live herbaceous plants
    liveWood : int, optional (default = 90)
        Moisture condition for live woody plants
    extreme_percentile : int | float | list | tuple, optional (default = 95)
        Must match the value used in output_weather_types() so the correct
        output CSV filenames are resolved. Int/float → extreme + mean CSVs;
        list/tuple → extensive percentile group CSV.

    Returns
    -------
    None
        Creates FMS files for the weather scenarios found in weather_dir.

    Notes
    -----
    This function:
    1. Extracts unique fuel types from the fuel raster
    2. Resolves the correct weather type CSV filenames based on extreme_percentile type
    3. Uses write_fms() to generate the actual FMS files
    """
    # Open template raster and read first band
    with rasterio.open(fuel_raster_path) as src:
        band = src.read(1)
        nodata_value = src.nodata

    # Get unique fuel type values, excluding nodata
    fuels = np.unique(band.astype(int))
    if nodata_value is not None:
        fuels = fuels[fuels != int(nodata_value)]

    os.makedirs(fms_out_dir, exist_ok=True)

    # Resolve the correct CSV filenames based on what output_weather_types() produced
    if isinstance(extreme_percentile, (list, tuple, np.ndarray)):
        weather_files = [
            (os.path.join(weather_dir, "Extensive_percentile_group_weather_scenarios.csv"), "extensive"),
        ]
    else:
        p = int(extreme_percentile)
        weather_files = [
            (os.path.join(weather_dir, f"p{p}_extreme_weather_types.csv"), "extreme"),
            (os.path.join(weather_dir, "all_mean_weather_types.csv"), "mean"),
        ]

    for weather_type_path, wtype in weather_files:
        if not os.path.exists(weather_type_path):
            logger.warning("Weather type file not found, skipping: %s", weather_type_path)
            continue
        logger.info("Using weather type file: %s", weather_type_path)
        write_fms(weather_type_path, fms_out_dir, fuels, liveHerb, liveWood, wtype)

def produce_ignition_prob_KDE(fires_f, template_raster_path, output_raster, KDE_bw = 0.1):
    """
    Produce an ignition probability raster using Kernel Density Estimation.
    
    Parameters
    ----------
    fires_f : str
        Path to historical fire ignition locations shapefile
    template_raster_path : str
        Path to template raster file
    output_raster : str
        Path to output raster file
    KDE_bw : float, optional (default=0.1)
        Band-width for smoothing band width in Gaussain KDE (smaller for more sensitive)

    Returns
    -------
    None
        Saves the ignition probability raster to the specified output path
        
    Notes
    -----
    This function:
    1. Loads historical fire ignition locations from a shapefile
    2. Creates a coordinate grid based on the template raster
    3. Applies Kernel Density Estimation to the historical fire ignition locations
    4. Normalizes the probability values to the range [0, 1]
    5. Saves the result as a raster file
    
    The bandwidth for the KDE is set to 0.1, which can be adjusted as needed.
    """
    # Step 1: Load and prepare input data
    # Read historical fire ignition locations shapefile and template raster parameters
    gdf = gpd.read_file(fires_f)
    
    with rasterio.open(template_raster_path) as src:
        raster_crs = src.crs
        bounds = src.bounds
        res_x, res_y = src.res
        width, height = src.width, src.height

    # Reproject historical fire ignition locations if needed
    if gdf.crs != raster_crs:
        gdf = gdf.to_crs(raster_crs)

    # Step 2: Create coordinate grid for KDE
    x = np.arange(bounds.left, bounds.right, res_x)
    y = np.arange(bounds.bottom, bounds.top, res_y)
    X, Y = np.meshgrid(x, y)

    # Step 3: Extract point coordinates and validate
    if gdf.empty:
        raise ValueError("Input shapefile contains no points")

    xy = np.vstack([gdf.geometry.x, gdf.geometry.y])
    
    if xy.shape[1] < 2:
        raise ValueError("At least two points are required for KDE")

    # Step 4: Apply KDE and evaluate on grid
    kde = gaussian_kde(xy, bw_method=KDE_bw)  # Bandwidth can be adjusted as needed
    Z = kde(np.vstack([X.ravel(), Y.ravel()]))
    Z = Z.reshape(Y.shape)

    # Step 5: Normalize probabilities to 0-1 range
    Z_min, Z_max = Z.min(), Z.max()
    if Z_max > Z_min:
        Z = (Z - Z_min) / (Z_max - Z_min)
    else:
        Z = np.zeros_like(Z)

    # Step 6: Save output raster
    transform = rasterio.transform.from_bounds(*bounds, height=height, width=width)
    Z = np.flipud(Z)  # Flip array to match raster orientation
    
    with rasterio.open(
        output_raster, 'w',
        driver='GTiff',
        height=height, width=width,
        count=1, dtype=Z.dtype,
        crs=raster_crs, transform=transform
    ) as dst:
        dst.write(Z, 1)

    logger.info("KDE probability surface saved to: %s", output_raster)

# Internal functions

def write_fms(input_wt_fn, output_fms_dir, f_types, liveHerb = 60, liveWood = 90, type_weather="extreme"):
    """
    Write fuel moisture scenario (FMS) files based on weather type data.
    
    Parameters
    ----------
    input_wt_fn : str
        Path to input weather type CSV file
    output_fms_dir : str
        Directory to write FMS files to
    f_types : array-like
        List of fuel types to generate FMS for
    liveHerb : int, optional (default = 60)
        Moisture condition for live herbaceous plants
    liveWood : int, optional (default = 90)
        Moisture condition for live woody plants
    type_weather : str, optional (default="extreme")
        Type of weather scenario ("extreme" or "mean")
        
    Returns
    -------
    None
        Creates one .fms file per weather type cluster in the specified output directory
        
    Notes
    -----
    Creates one .fms file per weather type cluster containing fuel moisture values
    calculated from temperature and relative humidity using an empirical formula.
    The formula used is: q = int(round(4.37 + 0.161*RH - 0.1*T - 0.027*RH, 0))
    where RH is relative humidity and T is temperature.
    """
    # Read weather type data (saved by output_weather_types with default comma separator)
    wt = pd.read_csv(input_wt_fn)
    
    # Generate FMS file for each weather type cluster
    for i in range(len(wt)):
        fms_file = os.path.join(output_fms_dir, f"{type_weather}_wt_fms{i}.fms")
        
        # Calculate base moisture value using empirical formula
        q = int(round(4.37 + 0.161*wt.RH[i] - 0.1*wt["T"][i] - 0.027*wt.RH[i], 0))
        
        # Write moisture values for each fuel type
        with open(fms_file, "w", encoding="utf-8") as f:
            for fuel_type in f_types:
                f.write(f"{fuel_type} {q} {q+1} {q+2} {liveHerb} {liveWood}\n") 