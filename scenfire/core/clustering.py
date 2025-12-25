import pandas as pd
import numpy as np
import geopandas as gpd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
import os

def cluster_fire_weather(fire_weather, min_n=4, max_n=10):
    """
    Performs K-means clustering on fire weather data to identify distinct weather patterns.
    
    Parameters
    ----------
    fire_weather : pandas.DataFrame
        DataFrame containing fire weather data with columns 'WS', 'RH', and 'T'
    min_n : int, optional (default=4)
        Minimum number of clusters to use if optimal number is lower
    max_n : int, optional (default=10)
        Maximum number of clusters to test when finding optimal number
        
    Returns
    -------
    sklearn.cluster.KMeans
        Fitted KMeans clustering model using the optimal number of clusters
        
    Notes
    -----
    This function:
    1. Scales the weather data (wind speed, relative humidity, temperature)
    2. Finds the optimal number of clusters using silhouette score analysis
    3. Performs K-means clustering with the optimal number of clusters
    4. Returns the fitted KMeans model
    
    The optimal number of clusters is determined by finding the maximum silhouette score
    among possible cluster numbers. If the optimal number is less than min_n, min_n is used instead.
    """
    print("Clustering...")
    clust_data = fire_weather[["WS", "RH", "T"]]
    scaled_data = (clust_data - clust_data.mean()) / clust_data.std()

    # Find optimal number of clusters using silhouette score
    silhouette_scores = []
    possible_n = range(2, max_n)

    os.environ["OMP_NUM_THREADS"] = '3'
    for n in possible_n:
        km = KMeans(n_clusters=n, n_init=25, random_state=0)
        labels = km.fit_predict(scaled_data)
        silhouette_scores.append(silhouette_score(scaled_data, labels))

    # Find the index of the maximum silhouette score
    n_max = possible_n[np.argmax(silhouette_scores)]
    if n_max < min_n:
        print("Optimal number of clusters is lower than min_n:", min_n)
        print("Using minimum number of clusters.")
        n_max = min_n

    print("Silhouette Scores:", silhouette_scores)
    print("Optimal Number of Clusters:", n_max)

    # Perform KMeans clustering with the optimal number of clusters
    km = KMeans(n_clusters=n_max, n_init=25, random_state=0)
    km.fit(scaled_data)

    return km

def output_weather_types(fire_weather, weather_dir, km, extreme_percentile, col_fire_size = "Area_ha", weather_variable = ['T', 'RH', 'WS', 'DFMC']):
    """
    Generate extreme and average weather type summaries from clustered fire weather data.
    
    Parameters
    ----------
    fire_weather : pandas.DataFrame
        DataFrame containing fire weather data with columns 'WS', 'RH', 'T', 'WD', and fire size (col_fire_size)
    weather_dir : str
        Directory to save the output files
    km : sklearn.cluster.KMeans
        Fitted KMeans clustering model
    extreme_percentile : int | tuple | list
        int: Percentile for extreme weather types (e.g., 95 for 95th percentile) \\
        tuple | list: List of percentiles to generate mean weather types within each percentile interval
    col_fire_size : str (default="Area_ha")
        Column name for fire size \\
        "Area_ha" is the default value for ERA5 weather data from ECMWF
    weather_variable: list (default=['T', 'RH', 'WS', 'DFMC'])


    Returns
    -------
    None
        Saves two CSV files based on extreme_percentile:\\
        extreme_percentile: int
        - pXX_extreme_weather_types.csv: Contains extreme weather conditions (by percentile XX) for each cluster
        - all_mean_weather_types.csv: Contains average weather conditions for each cluster
        
        extreme_percentile: list | tuple
        - tables of all mean values in each percentile groups
        
    Notes
    -----
    This function:
    1. Assigns cluster labels to each fire weather record
    2. Calculates extreme weather conditions for each cluster using the specified percentile
    3. Calculates frequency of each weather type based on cluster size and wind direction
    
    For extreme weather types, wind speed (WS) is increased by 10 units and uses the specified percentile,
    while relative humidity (RH) uses the complementary percentile (100-extreme_percentile).
    """
    
    weather_types = fire_weather.copy()
    weather_types["Cluster"] = (km.labels_+1)
    wdirs_freqs = weatherSceneFreq(weather_types, col_fire_size, extreme_percentile)
    output_table_dict = {}

    # Calculate cluster summary
    if isinstance(extreme_percentile, tuple | list | np.ndarray):
        # ------------------------- Extensive percentile groups -------------------------
        # add p0 and p100 for full coverage
        extreme_percentile.extend([0,100])
        extreme_percentile = sorted(set(extreme_percentile)) # remove duplicated values
        
        for i in range(len(extreme_percentile)-1):
            ext_pt = extreme_percentile[i:i+2] # get every two values in list
            cluster_summary = weatherAggregate(weather_types, ext_pt).drop(columns=['freq_cluster'])
            cluster_summary[[wvar+'_pt' for wvar in weather_variable]] = i
            if 'output_pd' not in locals():
                output_pd = cluster_summary 
            else:
                output_pd = pd.concat([output_pd, cluster_summary], ignore_index=True)

        intervals = pd.IntervalIndex.from_breaks(
            extreme_percentile,
            closed="right"    # matches your (a,b]
        )

        lookup = (
            pd.DataFrame({
                "pt_index": range(len(intervals)),     # 0,1,2,3
                "pt_interval": intervals.astype(str)   # '(0, 30]', ...
            })
        )

        for var in weather_variable:
            wdirs_freqs = wdirs_freqs.merge(
                output_pd[[f"{var}_pt", "Cluster", var]],
                on=[f"{var}_pt", "Cluster"],
                how="left"
            )
            wdirs_freqs[f"{var}_pt_interval"] = wdirs_freqs[f"{var}_pt"].map(
                lookup.set_index("pt_index")["pt_interval"]
            )

        output_table_dict['Extensive_percentile_group_weather_scenarios'] = wdirs_freqs

    elif isinstance(extreme_percentile, int | float | np.int64):
        # ------------------------- Extreme weather types -------------------------
        cluster_summary = weatherAggregate(weather_types, extreme_percentile)
        output_table_dict[f'p{extreme_percentile}_extreme_weather_types'] = addWindDir(cluster_summary, wdirs_freqs)

        # ------------------------- Average weather types -------------------------
        mean_weather_types = weatherAggregate(weather_types, "mean")
        output_table_dict['all_mean_weather_types'] = addWindDir(mean_weather_types, wdirs_freqs)
        
        
    else:
        raise ValueError(f"Unknown value type for extreme_percentile: {type(extreme_percentile)}")
    
    # Output Datasets into CSV
    for fname, table in output_table_dict.items():
        table.to_csv(os.path.join(weather_dir, f"{fname}.csv"), 
                     index=False) # Check if we need these options: sep=';', decimal=','
        
    print("\n--> Weather data done")

def generate_sample_ignition_points(bound_geometry, bound_crs, sampletxt_output_filename, out_crs = None, num_points = 500000):
    """
    Generates random ignition points strictly within the *actual geometry* of a boundary layer
    (Polygon or MultiPolygon) and exports them to a CSV file.

    Parameters
    ----------
    bound_geometry : shapely.geometry.Polygon or shapely.geometry.MultiPolygon
        Geometry defining the boundary within which to generate points (e.g., a country, park).
        It must be a Shapely Polygon or MultiPolygon object.
    bound_crs : str
        Coordinate reference system (CRS) of the `bound_geometry` (e.g., "EPSG:4326", "EPSG:32630").
    sampletxt_output_filename : str
        Path to the output CSV file where the ignition points will be saved.
    out_crs : str, optional
        Output coordinate reference system (CRS) for the points in the CSV file.
        If `None` (default), the points will retain the `bound_crs`.
    num_points : int, optional
        The total number of random points to generate *within the actual boundary*.
        Defaults to 500,000.

    Returns
    -------
    None
        This function does not return any value. It exports the generated points
        to the specified CSV file.

    Notes
    -----
    This function:
    1. Validates that `bound_geometry` is a Polygon or MultiPolygon.
    2. Creates a GeoDataFrame representing the precise boundary using `bound_geometry` and `bound_crs`.
    3. Checks if the `sampletxt_output_filename` already exists. If it does, the function
       will print a message and exit without overwriting the file.
    4. Leverages `geopandas.GeoSeries.sample_points(num_points)` to efficiently generate
       random points that are uniformly distributed *within the area* of the `bound_geometry`.
       This method handles the underlying point-in-polygon tests, ensuring points are truly inside.
    5. The resulting MultiPoint geometries from `sample_points()` are then 'exploded'
       into individual Point geometries, creating a GeoDataFrame where each row represents
       a single ignition point.
    6. If the requested `num_points` is very large relative to the geometry's size,
       or if the geometry is invalid/empty, `sample_points()` might generate fewer
       points than requested. A warning is printed in such cases.
    7. Optionally reprojects the generated points to the `out_crs` if specified
       and if it differs from `bound_crs`.
    8. Assigns a unique identifier (`FIRE_NUM`) to each point.
    9. Extracts the X and Y coordinates of each point into `XStart` and `YStart` columns.
    10. Exports the points to the CSV file, containing only the 'FIRE_NUM', 'XStart',
        and 'YStart' columns, without the GeoDataFrame index.

    The output CSV file contains three columns:
    - FIRE_NUM: Unique sequential identifier for each ignition point (integer).
    - XStart: X-coordinate of the ignition point (float).
    - YStart: Y-coordinate of the ignition point (float).
    """
    # 3. Check if output file already exists to prevent accidental overwrites
    if os.path.exists(sampletxt_output_filename):
        print(f"Output file '{sampletxt_output_filename}' already exists. Skipping generation.")
        print("--> Fire ignition points done")
        return

    # 4. Generate random points within the polygon using sample_points()
    try:
        # sample_points() returns a GeoSeries where each entry is a MultiPoint containing 'n' points
        # for the corresponding input geometry.
        # sampled_points_multipoint_series = bound_geometry.geometry.sample_points(num_points)
        gdf_boundary = gpd.GeoDataFrame(geometry=[bound_geometry], crs=bound_crs)
        foo_multipoint_series = gdf_boundary.geometry.sample_points(500000)

    except Exception as e:
        print(f"Error generating points with sample_points(): {e}")
        print("This might happen if the geometry is invalid or too small to generate the requested number of points.")
        print("--> Fire ignition points failed")
        return


    # Create GeoDataFrame with points
    gdf_points = gpd.GeoDataFrame(
        geometry=foo_multipoint_series.explode(ignore_index=True),
        crs=bound_crs
    )

    # Check if fewer points than requested were generated
    if len(gdf_points) < num_points:
        print(f"Warning: Only {len(gdf_points)} points were generated by sample_points(), instead of the requested {num_points}.")

    # 6. Reproject to output CRS if specified
    if out_crs is not None and gdf_points.crs != out_crs:
        print(f"Reprojecting points from {gdf_points.crs.to_string()} to {out_crs}...")
        gdf_points = gdf_points.to_crs(crs=out_crs)

    # 7. Create FIRE_NUM, XStart, and YStart columns (maintaining exact output format)
    gdf_points['FIRE_NUM'] = range(1, len(gdf_points) + 1)
    gdf_points['XStart'] = gdf_points.geometry.x
    gdf_points['YStart'] = gdf_points.geometry.y

    # 8. Export to CSV file with the required columns
    gdf_points[['FIRE_NUM', 'XStart', 'YStart']].to_csv(sampletxt_output_filename, index=False)
    
    print("Sampled CSV file exported.")
    print("--> Fire ignition points done.")

# Internal function
def weatherAggregate(weather_tp, ext_percentile, weather_variables = ['T', 'RH', 'WS', 'DFMC']):
    """
    (internal function) process and aggregate weather types into designed groups
    """
    if isinstance(ext_percentile, tuple | list | np.ndarray):
        if len(ext_percentile) != 2:
            raise ValueError(f"ext_percentile: {ext_percentile} should get exactly 2 values for cluster average!")
        
        agg_dict = {
            var: (var, lambda x: mean_between_percentiles(x, *ext_percentile))
            for var in weather_variables
        }

        agg_dict["n"] = ("Cluster", "size")

        cluster_sum = weather_tp.groupby("Cluster").agg(**agg_dict).reset_index()
        
    elif isinstance(ext_percentile, int | float | np.int64):
        wvar_pt_colnames = []  
        cluster_sum = weather_tp.groupby(["Cluster", *wvar_pt_colnames]).agg(
            WS=("WS", lambda x: np.percentile(x, ext_percentile) + 10),
            RH=("RH", lambda x: np.percentile(x, 100-ext_percentile)),
            T=("T", lambda x: np.percentile(x, ext_percentile)),
            n=("Cluster", "size"),
        ).reset_index()

    elif ext_percentile == "mean":
        cluster_sum = weather_tp.groupby("Cluster").agg(
            WS=("WS", lambda x: np.mean(x) + 10),
            RH=("RH", "mean"),
            T=("T", "mean"),
            n=("Cluster", "size"),
        ).reset_index()

    cluster_sum["freq_cluster"] = cluster_sum["n"] / cluster_sum["n"].sum()
    cluster_sum.drop("n", axis=1, inplace=True)

    return(cluster_sum)

def weatherSceneFreq(weather_tp, col_fire_size, ext_percentile, weather_variable = ['T', 'RH', 'WS', 'DFMC']):
    """
    (internal function) assigning independent wind directions to each cluster, including all possible wind directions
    """
    # Evaluate the wind direction
    wvars = weather_tp[["Cluster", col_fire_size, "WD",*weather_variable]].copy()
    wvars["dir"] = np.select(
            [
                (wvars["WD"] >= 0) & (wvars["WD"] <= 22.5),
                (wvars["WD"] > 22.5) & (wvars["WD"] <= 67.5),
                (wvars["WD"] > 67.5) & (wvars["WD"] <= 112.5),
                (wvars["WD"] > 112.5) & (wvars["WD"] <= 157.5),
                (wvars["WD"] > 157.5) & (wvars["WD"] <= 202.5),
                (wvars["WD"] > 202.5) & (wvars["WD"] <= 247.5),
                (wvars["WD"] > 247.5) & (wvars["WD"] <= 292.5),
                (wvars["WD"] > 292.5) & (wvars["WD"] <= 337.5),
            ],
            [0, 45, 90, 135, 180, 225, 270, 315],
            default=0, # assign WD > 337.5 to 0
    )

    wvar_pt_colnames = []
    if isinstance(ext_percentile, tuple | list | np.ndarray):
        for v in weather_variable:
            wvars[v+'_pt'] = weatherPercentileFreqList(wvars[v].to_numpy(), ext_percentile)
            wvar_pt_colnames.append(v+'_pt')

    # Wind dir frequency in each cluster
    wvars_freqs = (
        wvars.groupby(["Cluster", "dir", *wvar_pt_colnames])[col_fire_size]
            .count()
            .reset_index(name="n")
            .groupby("Cluster")
            .apply(lambda x: x.assign(freq_wvars=x["n"] / x["n"].sum()),
                    include_groups=False)
            .reset_index()
            .drop("n", axis=1)
    )
    
    wvars_ba = (
        wvars.groupby(["Cluster","dir", *wvar_pt_colnames])[col_fire_size]
        .sum()
        .reset_index(name="area")
        .groupby("Cluster")
        .apply(lambda x: x.assign(freq_area=x["area"] / x["area"].sum()),
                include_groups=False)
        .reset_index().drop('area', axis=1)
    )
    
    wvars_freqs = pd.concat([wvars_freqs, wvars_ba['freq_area']], axis=1)

    return(wvars_freqs)

def weatherPercentileFreqList(weather_array, percentiles):
    """
    Percentile list should not contain 0 for correct grouping
    """
    # 1. Sort percentiles
    sorted_percentiles = np.sort(percentiles)
    sorted_percentiles = sorted_percentiles[sorted_percentiles!=0] # remove 0 from list
    
    # 2. Calculate the actual data values for the percentile boundaries
    # np.percentile handles the 0th (min) and 100th (max) percentiles automatically
    bin_edges = np.percentile(weather_array, sorted_percentiles)
    
    # Ensure unique edges for cases with repeated values
    unique_bin_edges = np.unique(bin_edges)
    
    # 3. Use np.digitize to find which bin each data point belongs to
    # right=True means bins are (bin_edge[i-1], bin_edge[i]] (inclusive on the right)
    # The first bin is inclusive on the left for the min value.
    bin_indices = np.digitize(weather_array, unique_bin_edges, right=True)

    # # 4. Construct new pd dataframe for frequency calculation  
    # df_new = pd.DataFrame({
    #     'value': T_test,
    #     'pt'   : bin_indices
    # })
    
    return bin_indices

def addWindDir(cluster_summary, wdirs_freqs):
    """
    (internal function) merge generated wind frequencies into weather types DataFrame
    """
    weather_wd = pd.merge(cluster_summary, wdirs_freqs, on="Cluster")
    weather_wd["freq_Cls_dir_counts"] = weather_wd["freq_cluster"] * weather_wd["freq_wvars"]
    weather_wd["freq_Cls_dir_area"] = weather_wd["freq_cluster"] * weather_wd["freq_area"]

    return(weather_wd)

def mean_between_percentiles(x, p_low, p_high):
    low, high = np.percentile(x, [p_low, p_high])
    return x[(x >= low) & (x <= high)].mean()