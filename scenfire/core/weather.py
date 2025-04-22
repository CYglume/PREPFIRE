import os
import cdsapi
import pandas as pd
import xarray as xr
import numpy as np
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import box, Polygon
import math
import logging
from ..utils.helpers import rh_calc, vpd_calc, dfmc_calc, dfmc_vpd_calc

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_bound_extent(bound_coords: list[float] | tuple[float, float, float, float],
                     gdf: gpd.GeoDataFrame, 
                     buffer_size: float = 20000) -> Polygon:
    """
    Creates a buffered bounding box around a GeoDataFrame's geometries. 
    Uses predefined coordinates or calculates from the GeoDataFrame's geometries.
    If the GeoDataFrame's CRS is geographic (latitude/longitude), the buffer is in degrees.
    If the GeoDataFrame's CRS is projected (meters), the buffer is in meters.
    
    Parameters
    ----------
    bound_coords : list[float] | tuple[float, float, float, float]
        Coordinates in degrees of the bounding box (xmin, ymin, xmax, ymax).
        Default crs is EPSG:4326.
        If not provided, the bounding box will be calculated from the GeoDataFrame's geometries.
    gdf : GeoDataFrame
        Input GeoDataFrame containing geometries
    buffer_size : float, optional (default=20000)
        Size of the buffer in meters
        
    Returns
    -------
    Polygon
        A rectangular polygon representing the buffered extent
        
    Raises
    ------
    TypeError
        If input is not a GeoDataFrame
    ValueError
        If GeoDataFrame is empty or has no CRS defined
    """
    
    # Verify input is a GeoDataFrame
    if not isinstance(gdf, gpd.GeoDataFrame):
        raise TypeError("Input must be a GeoDataFrame")
    # Check if GeoDataFrame is empty or has no CRS
    if gdf.empty:
        raise ValueError("Input GeoDataFrame is empty")
    if not gdf.crs:
        raise ValueError("Input GeoDataFrame must have a CRS defined")
    
    # Create bounding box
    if bound_coords:
        # Verify provided coordinates are valid
        if len(bound_coords) != 4:
            raise ValueError("Provided coordinates must be a tuple of 4 floats (xmin, ymin, xmax, ymax)")
        # Check correct order of coordinates
        if bound_coords[0] > bound_coords[2] or bound_coords[1] > bound_coords[3]:
            raise ValueError("Provided coordinates are not in the correct order (xmin, ymin, xmax, ymax)")
        # Calculate buffer depending on the CRS
        if gdf.crs.is_geographic:
            # Calculate buffer size in degrees based on latitude
            center_lat = (bound_coords[1] + bound_coords[3]) / 2
            # Length of 1 degree of longitude at this latitude
            lon_degree_length = math.cos(math.radians(center_lat)) * 111320
            # Convert buffer from meters to degrees
            buffer_size_x = buffer_size / lon_degree_length  # longitude buffer
            buffer_size_y = buffer_size / 111320  # latitude buffer (1 degree = ~111.32km)
        else:
            buffer_size_x = buffer_size
            buffer_size_y = buffer_size
        
        # Create bounding box from provided coordinates
        bound_extent = box(bound_coords[0] - buffer_size_x,
                           bound_coords[1] - buffer_size_y,
                           bound_coords[2] + buffer_size_x,
                           bound_coords[3] + buffer_size_y)
    elif gdf.crs.is_geographic:
        # Get the bounding box
        xmin, ymin, xmax, ymax = gdf.total_bounds
        
        # Calculate buffer size in degrees based on latitude
        # At the center latitude of our area
        center_lat = (ymin + ymax) / 2
        # Length of 1 degree of longitude at this latitude
        lon_degree_length = math.cos(math.radians(center_lat)) * 111320
        # Convert buffer from meters to degrees
        buffer_size_x = buffer_size / lon_degree_length  # longitude buffer
        buffer_size_y = buffer_size / 111320  # latitude buffer (1 degree = ~111.32km)
        
        # Apply buffer with different scales for x and y
        bound_extent = box(
            xmin - buffer_size_x,  # min_x - buffer
            ymin - buffer_size_y,  # min_y - buffer
            xmax + buffer_size_x,  # max_x + buffer
            ymax + buffer_size_y   # max_y + buffer
        )
    else:
        # Get the bounding box (minx, miny, maxx, maxy)
        xmin, ymin, xmax, ymax = gdf.total_bounds
        # Apply buffer in projected units (meters)
        xmin -= buffer_size
        ymin -= buffer_size
        xmax += buffer_size
        ymax += buffer_size

        bound_extent = box(xmin, ymin, xmax, ymax)

    return bound_extent

def get_fire_weather(x, fires, raster, col_fire_date: str, in_cds_time="valid_time", in_x = 'longitude',in_y = 'latitude'):
    """
    Extract weather data from raster at the date/location of the fire at index x in the dataset 'fires'.
    
    Parameters
    ----------
    x : int
        Index of the fire in the fires dataset
    fires : pandas.DataFrame or geopandas.GeoDataFrame
        Dataset containing fire information with geometry and date
    raster : xarray.Dataset
        Weather data raster to extract from
    col_fire_date : str
        Column name in fires dataset containing the fire date
    in_cds_time : str, optional (default="valid_time")
        Name of the time dimension in the raster
    in_x : str, optional (default="longitude")
        Name of the x-coordinate dimension in the raster
    in_y : str, optional (default="latitude")
        Name of the y-coordinate dimension in the raster
        
    Returns
    -------
    xarray.DataArray
        Weather data extracted at the fire location and date
    """
    fire = fires.iloc[x]
    date = pd.to_datetime(fire[col_fire_date])
    return raster.sel(**{in_cds_time: date}, method='nearest').sel(**{in_x:fire.geometry.x, in_y:fire.geometry.y}, method="nearest").squeeze()

def download_weather_data(gdf, date_column, processed_path, bound_extent, bound_crs, cdsAPI_KEY, fetch=True,
                           time_of_day = ['12:00'], fire_months=[5,6,7,8,9,10]):
    """
    Downloads ERA5-Land weather data from the Copernicus Climate Data Store (CDS) API.
    
    Parameters
    ----------
    gdf : geopandas.GeoDataFrame
        GeoDataFrame containing fire data with dates
    date_column : str
        Column name in gdf containing the fire dates
    processed_path : str
        Path to save the downloaded weather data
    bound_extent : shapely.geometry.Polygon
        Bounding box polygon for the area of interest
    bound_crs : str or pyproj.CRS
        Coordinate reference system of the bound_extent
    cdsAPI_KEY : str
        API key for the Copernicus Climate Data Store
    fetch : bool, optional (default=True)
        Whether to fetch data from CDS API or just prepare the request for testing
    time_of_day : list, optional (default=['12:00'])
        List of times of day to download data for
    fire_months : list, optional (default=[5,6,7,8,9,10])
        List of months to download data for
        
    Returns
    -------
    bool
        True if data was successfully downloaded, False otherwise
        
    Raises
    ------
    ValueError
        If CDS API key is not provided
    """
    # Get API key interactively if not provided
    if not cdsAPI_KEY:
        cdsAPI_KEY = input("Please enter your Copernicus Climate Data Store API key: ").strip()
        if not cdsAPI_KEY:
            raise ValueError("CDS API key is required for weather data download")

    print("\nDownloading weather data...")
    t = gdf[date_column].tolist()
    date_range = [min(t).strftime("%Y-%m-%d"), max(t).strftime("%Y-%m-%d")]

    bounds_wgs = gpd.GeoDataFrame({'geometry': [bound_extent]}, crs=bound_crs)
    bounds_wgs = bounds_wgs.to_crs(epsg=4326).total_bounds
    # Reorder to CDS format [ymax, xmin, ymin, xmax]
    area_extract_cds = [bounds_wgs[3], bounds_wgs[0], bounds_wgs[1], bounds_wgs[2]]
    print(bounds_wgs)
    print(area_extract_cds)

    dates_by_month = dict()
    days_fire = pd.date_range(start=date_range[0], end=date_range[1], freq='D')
    days_fire = days_fire[days_fire.month.isin(fire_months)]

    for y in sorted(set(days_fire.strftime("%Y"))):
        y_days_fire = days_fire[days_fire.year.isin([int(y)])]
        for m in sorted(set(y_days_fire.strftime("%m"))):
            key = (y, m)
            month_days = y_days_fire.day[y_days_fire.month.isin([int(m)])]
            dates_by_month[key] = [min(month_days), max(month_days) + 1]

    var_weather = ["2m_temperature","2m_dewpoint_temperature","10m_u_component_of_wind","10m_v_component_of_wind"]
    for var in var_weather:
        os.makedirs(os.path.join(processed_path, "Weather", "CDS", var),
                    exist_ok=True)

    if fetch:
        c = cdsapi.Client(key=cdsAPI_KEY,
                        url='https://cds.climate.copernicus.eu/api', quiet=False, sleep_max=5, timeout=7200)

        firstRun = True
        for var in var_weather:
            print(f"\n...Downloading {var}...")
            if os.path.exists(os.path.join(processed_path,"Weather", f"era5_{var}.nc")):
                print("Exists: ", os.path.join(processed_path,"Weather", f"era5_{var}.nc"))
                continue

            downloaded_files = []
            print(f"Requesting......")
            for (year, month), dayRange in dates_by_month.items():
                print(f"{year}-{month}", end=" ")
                output_file = os.path.join(processed_path, "Weather", "CDS", var,
                                            f"era5_land_{year}_{month}_{dayRange[0]}-{dayRange[1]-1}_12UTC.nc")
                if os.path.exists(output_file):
                    continue

                c.retrieve(
                    'reanalysis-era5-land',
                    {
                        "variable": [var],
                        'year': year,
                        'month': month,
                        'day': [f"{i:02}" for i in range(*dayRange)],
                        'time': time_of_day,
                        "area": area_extract_cds,
                        "data_format": "netcdf",
                        "download_format": "unarchived",
                    },
                    output_file
                )

                if firstRun:
                    c = cdsapi.Client(key=cdsAPI_KEY, 
                            url='https://cds.climate.copernicus.eu/api', quiet=True, sleep_max=5, timeout=7200, progress=False)
                    firstRun = False

                downloaded_files.append(output_file)

            print("\nMerging NetCDF files...")
            merged_file = os.path.join(processed_path, "Weather", f"era5_{var}.nc")
            if os.path.exists(merged_file):
                print(f"File already exists: {merged_file}")
                continue

            datasets = [xr.open_dataset(f, engine='netcdf4') for f in downloaded_files]
            merged = xr.concat(datasets, dim='valid_time')
            merged.to_netcdf(merged_file)
            print(f"Saved merged NetCDF as {merged_file}\n")

        print("Extraction from CDS API finished")
        return True
    else:
        print("Weather data not fetched")
        return False

def weather_data_processing(weather_dir, in_cds_time="valid_time", in_cds_x = 'longitude',in_cds_y = 'latitude', check_rh = False):
    """
    Process weather data from ERA5-Land variables to calculate derived weather indices.
    
    Parameters
    ----------
    weather_dir : str
        Directory containing the ERA5-Land NetCDF files
    in_cds_time : str, optional (default="valid_time")
        Name of the time dimension in the NetCDF files
    in_cds_x : str, optional (default="longitude")
        Name of the x-coordinate dimension in the NetCDF files
    in_cds_y : str, optional (default="latitude")
        Name of the y-coordinate dimension in the NetCDF files
    check_rh : bool, optional (default=False)
        Whether to plot a histogram of relative humidity values
        
    Returns
    -------
    dict
        Dictionary of saved file paths for each weather variable
    """
    print("Start calculating weather data...")
    # Load input variables
    temp = xr.open_dataset(os.path.join(weather_dir,"era5_2m_temperature.nc"), engine='netcdf4')
    tempd = xr.open_dataset(os.path.join(weather_dir,"era5_2m_dewpoint_temperature.nc"), engine='netcdf4')
    wind_u = xr.open_dataset(os.path.join(weather_dir,"era5_10m_u_component_of_wind.nc"), engine='netcdf4')
    wind_v = xr.open_dataset(os.path.join(weather_dir,"era5_10m_v_component_of_wind.nc"), engine='netcdf4')

    # Convert temperatures from K to °C
    temp = temp - 273
    tempd = tempd - 273

    # Calculate derived variables
    rh = rh_calc(tempd.d2m, temp.t2m)
    rh = rh.rename('rh')

    vpd = vpd_calc(temp.t2m, rh.values)
    vpd = vpd.rename('vpd')

    wspeed = 3.6 * np.sqrt(wind_u.u10**2 + wind_v.v10**2)
    wspeed = wspeed.rename('wspeed')

    wdir = 180 + (180/np.pi) * np.arctan2(wind_u.u10, wind_v.v10)
    wdir = wdir.rename('wdir')

    dfmc = dfmc_calc(temp.t2m, rh.values)
    dfmc = dfmc.rename('dfmc')

    dfmc_vpd = dfmc_vpd_calc(vpd)
    dfmc_vpd = dfmc_vpd.rename('dfmc')

    # Prepare metadata
    metadata = {
        'time': temp[in_cds_time],
        'lat': temp[in_cds_y],
        'lon': temp[in_cds_x],
        'crs': "EPSG:4326"
    }

    weather_data = {
        'rh': rh,
        'vpd': vpd,
        'wspeed': wspeed,
        'wdir': wdir,
        'dfmc': dfmc,
        'dfmc_vpd': dfmc_vpd,
        'metadata': metadata
    }

    if check_rh:
        # Abre el archivo NetCDF
        ds = rh
        # Muestra las variables disponibles en el archivo
        print(ds)
        # Selecciona la variable de interés (ajústala según el contenido del NetCDF)
        variable = "rh"  # Por ejemplo, temperatura a 2m (ajustar según el caso)
        datos = ds.values  # Extrae los valores como un array de NumPy

        # Aplanar los datos para obtener una lista de valores
        datos = datos.flatten()

        # Filtrar valores NaN (si los hay)
        datos = datos[~np.isnan(datos)]

        # Crear el histograma
        plt.figure(figsize=(8,6))
        plt.hist(datos, bins=50, color='royalblue', edgecolor='black', alpha=0.7)

        # Etiquetas y título
        plt.xlabel("Valor de la variable")
        plt.ylabel("Frecuencia")
        plt.title("Histograma de la variable " + variable)

        # Mostrar la gráfica
        plt.show()
    return save_weather_data(weather_data, weather_dir, in_cds_time)

def save_weather_data(weather_data, weather_dir, in_cds_time="valid_time"):
    """
    Internal function to save processed weather data to NetCDF files.
    Save processed weather data to NetCDF files.
    
    Parameters
    ----------
    weather_data : dict
        Dictionary containing weather variables and metadata from weather_data_processing()
    weather_dir : str
        Directory to save the output files
    in_cds_time : str, optional (default="valid_time")
        Name of the time dimension in the NetCDF files
        
    Returns
    -------
    dict
        Dictionary of saved file paths for each weather variable
    """
    print("Saving weather data...")
    metadata = weather_data['metadata']
    saved_files = {}
    
    for var_name, data in weather_data.items():
        if var_name == 'metadata':
            continue
            
        ds = data
        output_file = os.path.join(weather_dir, f"{var_name}.nc")
        if os.path.exists(output_file):
            os.remove(output_file)  # Delete the file
        ds.to_netcdf(output_file)
        ds.close()
        saved_files[var_name] = output_file
    
    print("Weather data saved")
    print(saved_files)
    return saved_files

def extract_fire_weather(fires_gdf_wgs, weather_dir, date_column='Date', year_column = 'Year', **kwargs):
    """
    Extract weather data at fire locations and dates from NetCDF files.
    
    Parameters
    ----------
    fires_gdf_wgs : geopandas.GeoDataFrame
        GeoDataFrame containing fire data with dates and locations in WGS84 (EPSG:4326)
    weather_dir : str
        Directory containing the processed weather NetCDF files
    date_column : str, optional (default='Date')
        Column name in fires_gdf_wgs containing the fire dates
    year_column : str, optional (default='Year')
        Column name in fires_gdf_wgs containing the fire years. If not provided, the year will be extracted from the fire date_column.
    **kwargs : dict
        Additional keyword arguments passed to get_fire_weather()
        
    Returns
    -------
    pandas.DataFrame
        DataFrame containing fire data with extracted weather variables
    """
    # Fetch weather data
    temp = xr.open_dataset(os.path.join(weather_dir, "era5_2m_temperature.nc"), engine='netcdf4')
    tempd = xr.open_dataset(os.path.join(weather_dir, "era5_2m_dewpoint_temperature.nc"), engine='netcdf4')
    wspeed = xr.open_dataset(os.path.join(weather_dir, "wspeed.nc"), engine='netcdf4')
    wdir = xr.open_dataset(os.path.join(weather_dir, "wdir.nc"), engine='netcdf4')
    rh = xr.open_dataset(os.path.join(weather_dir, "rh.nc"), engine='netcdf4')
    
    # Convert temperatures from K to °C
    temp = temp - 273
    tempd = tempd - 273

    # Extract data at the location/date of each fire
    temp_ext = [get_fire_weather(x, fires_gdf_wgs, temp, date_column, **kwargs) for x in range(len(fires_gdf_wgs))]
    tempd_ext = [get_fire_weather(x, fires_gdf_wgs, tempd, date_column, **kwargs) for x in range(len(fires_gdf_wgs))]
    wind_ext = [get_fire_weather(x, fires_gdf_wgs, wspeed, date_column, **kwargs) for x in range(len(fires_gdf_wgs))]
    wind_dir = [get_fire_weather(x, fires_gdf_wgs, wdir, date_column, **kwargs) for x in range(len(fires_gdf_wgs))]
    rh_ext = [get_fire_weather(x, fires_gdf_wgs, rh, date_column, **kwargs) for x in range(len(fires_gdf_wgs))]

    # Combine datasets
    fire_weather = pd.DataFrame(fires_gdf_wgs)
    org_colNum = fire_weather.shape[1]
    fire_weather['T'] = [float(arr.t2m.values) for arr in temp_ext]
    fire_weather['TD'] = [float(arr.d2m.values) for arr in tempd_ext]
    fire_weather['WS'] = [float(arr.wspeed.values) for arr in wind_ext]
    fire_weather['WD'] = [float(arr.wdir.values) for arr in wind_dir]
    fire_weather['RH'] = [float(arr.rh.values) for arr in rh_ext]
    fire_weather = fire_weather.dropna(subset=fire_weather.columns[org_colNum:])


    # Calculate annual fire weather statistics
    if year_column not in fire_weather.columns:
        fire_weather[year_column] = pd.to_datetime(fire_weather['Date']).dt.year
    annual_fire_weather = fire_weather.groupby(fire_weather[year_column]).agg({
        'T': lambda x: np.percentile(x, 95),  # 95th percentile temperature
        'TD': lambda x: np.percentile(x, 95), # 95th percentile dewpoint
        'WS': lambda x: np.max(x)+10,         # Maximum wind speed + 10
        'WD': lambda x: x.value_counts().idxmax(), # Most common wind direction
        'RH': lambda x: np.percentile(x, 5)   # 5th percentile relative humidity
    }).reset_index()

    # Save results to CSV files
    annual_fire_weather.to_csv(os.path.join(weather_dir, "annual_fire_weather.csv"), 
                              sep=';', decimal=',', index=False)    
    fire_weather.to_csv(os.path.join(weather_dir, "single_fire_weather.csv"), 
                       sep=';', decimal=',', index=False)
    
    return fire_weather 