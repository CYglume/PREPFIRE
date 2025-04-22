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


def generate_sample_ignition_points(bound_extent, bound_crs, sampletxt_output_filename, out_crs = None, num_points = 500000):
    """
    Generates random ignition points within a bounding box and exports them to a CSV file.
    
    Parameters
    ----------
    bound_extent : shapely.geometry
        Geometry defining the bounding box extent
    bound_crs : str
        Coordinate reference system of the bounding box
    sampletxt_output_filename : str
        Path to output CSV file
    out_crs : str, optional (default=None)
        Output coordinate reference system. If None, uses bound_crs
    num_points : int, optional (default=500000)
        Number of random points to generate
        
    Returns
    -------
    None
        Exports points to CSV file with FIRE_NUM, XStart, YStart columns
        
    Notes
    -----
    This function:
    1. Creates a GeoDataFrame with the bounding box geometry
    2. Generates random points within the bounding box
    3. Optionally reprojects the points to a different coordinate system (output CRS)
    4. Assigns a unique identifier to each point
    5. Exports the points to a CSV file
    
    The output CSV file contains three columns:
    - FIRE_NUM: Unique identifier for each ignition point
    - XStart: X-coordinate of the ignition point
    - YStart: Y-coordinate of the ignition point
    
    If the output file already exists, the function will not overwrite it.
    """
    # Create layer with boundaries
    gdf_bbox = gpd.GeoDataFrame(geometry=[bound_extent], crs=bound_crs)

    # Extract bbox limits from GeoDataFrame
    minx, miny, maxx, maxy = gdf_bbox.total_bounds  # returns (minx, miny, maxx, maxy)

    if not os.path.exists(sampletxt_output_filename):
        # Generate random points within bbox
        x_coords = np.random.uniform(minx, maxx, num_points)
        y_coords = np.random.uniform(miny, maxy, num_points)
        points = [Point(x, y) for x, y in zip(x_coords, y_coords)]

        # Create GeoDataFrame with points
        gdf_points = gpd.GeoDataFrame(geometry=points, crs=bound_crs)
        if out_crs is not None:
            gdf_points = gdf_points.to_crs(crs=out_crs)

        # Create FIRE_NUM, XStart and YStart columns
        gdf_points['FIRE_NUM'] = range(1, len(gdf_points) + 1)
        gdf_points['XStart'] = gdf_points.geometry.x
        gdf_points['YStart'] = gdf_points.geometry.y

        # Export to CSV file
        gdf_points[['FIRE_NUM', 'XStart', 'YStart']].to_csv(sampletxt_output_filename, index=False)
    print("Sampled csv file exported")
    print("--> Fire ignition points done")

