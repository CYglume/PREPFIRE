import pandas as pd
import numpy as np
import geopandas as gpd
from shapely.geometry import Point
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

def output_weather_types(fire_weather, weather_dir, km, n_max, col_fire_size, extreme_percentile):
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
    n_max : int
        Maximum number of clusters
    col_fire_size : str
        Column name for fire size
    extreme_percentile : int
        Percentile for extreme weather types (e.g., 95 for 95th percentile)

    Returns
    -------
    None
        Saves two CSV files to the specified directory:
        - extreme_weather_types.csv: Contains extreme weather conditions for each cluster
        - mean_weather_types.csv: Contains average weather conditions for each cluster
        
    Notes
    -----
    This function:
    1. Assigns cluster labels to each fire weather record
    2. Calculates extreme weather conditions for each cluster using the specified percentile
    3. Calculates average weather conditions for each cluster
    4. Analyzes wind direction patterns within each cluster
    5. Calculates frequency of each weather type based on cluster size and wind direction
    6. Exports the results to CSV files
    
    For extreme weather types, wind speed is increased by 10 units and uses the specified percentile,
    while relative humidity uses the complementary percentile (100-extreme_percentile).
    """
    # ------------------------- Extreme weather types -------------------------
    weather_types = fire_weather.copy()
    weather_types["Cluster"] = (km.labels_+1)
    
    # Calculate cluster summary
    cluster_summary = (
        weather_types.groupby("Cluster").agg(
            WS=("WS", lambda x: np.percentile(x, extreme_percentile) + 10),
            RH=("RH", lambda x: np.percentile(x, 100-extreme_percentile)),
            T=("T", lambda x: np.percentile(x, extreme_percentile)),
            n=("Cluster", "size"),
        ).reset_index()
    )

    cluster_summary["freq_cluster"] = cluster_summary["n"] / cluster_summary["n"].sum()
    cluster_summary.drop("n", axis=1, inplace=True)

    # Evaluate the wind direction
    wdirs = weather_types[["Cluster", "WD", col_fire_size]].copy()
    wdirs["dir"] = np.select(
        [
            (wdirs["WD"] >= 0) & (wdirs["WD"] <= 22.5),
            (wdirs["WD"] > 22.5) & (wdirs["WD"] <= 67.5),
            (wdirs["WD"] > 67.5) & (wdirs["WD"] <= 112.5),
            (wdirs["WD"] > 112.5) & (wdirs["WD"] <= 157.5),
            (wdirs["WD"] > 157.5) & (wdirs["WD"] <= 202.5),
            (wdirs["WD"] > 202.5) & (wdirs["WD"] <= 247.5),
            (wdirs["WD"] > 247.5) & (wdirs["WD"] <= 292.5),
            (wdirs["WD"] > 292.5) & (wdirs["WD"] <= 337.5),
        ],
        [0, 45, 90, 135, 180, 225, 270, 315],
        default=0,
    )

    # Wind dir frequency in each cluster
    wdirs_freqs = (
        wdirs.groupby(["Cluster", "dir"])["dir"]
        .count()
        .reset_index(name="n")
        .groupby("Cluster")
        .apply(lambda x: x.assign(freq_wd=x["n"] / x["n"].sum()))
        .drop("n", axis=1)
    )

    wdirs_ba = (
        wdirs.groupby(["Cluster","dir"])[col_fire_size].sum()
    )

    # Attributing the WD value
    for nc in range(1, n_max + 1):
        for d in [0, 45, 90, 135, 180, 225, 270, 315]:
            if not ((wdirs_freqs["Cluster"] == nc) & (wdirs_freqs["dir"] == d)).any():
                new_row = pd.DataFrame({"Cluster": [nc], "dir": [d], "freq_wd": [0.0]})
                wdirs_freqs = pd.concat([wdirs_freqs, new_row])

    wdirs_freqs.reset_index(inplace=True, drop=True)
    wdirs_freqs = pd.concat([wdirs_freqs, wdirs_ba.reset_index(drop=True)], axis=1)

    weather_wd = pd.merge(cluster_summary, wdirs_freqs, on="Cluster")
    weather_wd["freq"] = weather_wd["freq_cluster"] * weather_wd["freq_wd"]
    weather_wd.to_csv(os.path.join(weather_dir, "extreme_weather_types.csv"), 
                      index=False, sep=';', decimal=',')

    print("Extreme weather types done")

    # ------------------------- Average weather types -------------------------
    mean_weather_types = (
        weather_types.groupby("Cluster")
        .agg(
            WS=("WS", lambda x: np.mean(x) + 10),
            RH=("RH", "mean"),
            T=("T", "mean"),
            n=("Cluster", "size"),
        )
        .reset_index()
    )

    mean_weather_types["freq_cluster"] = mean_weather_types["n"] / mean_weather_types["n"].sum()
    mean_weather_types.drop("n", axis=1, inplace=True)

    mean_weather_wd = pd.merge(mean_weather_types, wdirs_freqs, on="Cluster")
    mean_weather_wd["freq"] = mean_weather_wd["freq_cluster"] * mean_weather_wd["freq_wd"]
    mean_weather_wd.to_csv(os.path.join(weather_dir, "mean_weather_types.csv"), 
                           index=False, sep=';', decimal=',')

    print("Mean weather types done")
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