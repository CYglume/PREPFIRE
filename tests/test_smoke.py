"""Smoke tests for prepfire public API.

These tests verify that the core functions can be imported and produce
correct outputs on synthetic data, without requiring real ERA5 downloads
or large raster files.
"""
import os
import tempfile

import numpy as np
import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Import tests
# ---------------------------------------------------------------------------

def test_import_prepfire():
    import prepfire
    assert hasattr(prepfire, "__version__")
    assert isinstance(prepfire.__version__, str)


def test_import_pipeline():
    from prepfire.pipeline import PrepFirePipeline, setup_project_structure, run_prepare
    assert callable(PrepFirePipeline)
    assert callable(setup_project_structure)
    assert callable(run_prepare)


def test_import_core_modules():
    from prepfire.core import clustering, raster, weather
    assert hasattr(clustering, "cluster_fire_weather")
    assert hasattr(clustering, "output_weather_types")
    assert hasattr(raster, "produce_fms")
    assert hasattr(weather, "get_bound_extent")


def test_import_helpers():
    from prepfire.utils.helpers import rh_calc, vpd_calc, dfmc_calc, dfmc_vpd_calc
    assert callable(rh_calc)


# ---------------------------------------------------------------------------
# Clustering tests
# ---------------------------------------------------------------------------

class TestClustering:
    def test_cluster_fire_weather_returns_kmeans(self, fire_weather_df):
        from prepfire.core.clustering import cluster_fire_weather

        km = cluster_fire_weather(fire_weather_df, min_n=2, max_n=5)
        assert hasattr(km, "labels_")
        assert hasattr(km, "n_clusters")
        assert 2 <= km.n_clusters <= 5

    def test_cluster_fire_weather_respects_min_n(self, fire_weather_df):
        from prepfire.core.clustering import cluster_fire_weather

        km = cluster_fire_weather(fire_weather_df, min_n=4, max_n=5)
        assert km.n_clusters >= 4

    def test_cluster_labels_count(self, fire_weather_df):
        from prepfire.core.clustering import cluster_fire_weather

        km = cluster_fire_weather(fire_weather_df, min_n=2, max_n=4)
        assert len(km.labels_) == len(fire_weather_df)

    def test_output_weather_types_int_percentile(self, fire_weather_df, tmp_path):
        from prepfire.core.clustering import cluster_fire_weather, output_weather_types

        km = cluster_fire_weather(fire_weather_df, min_n=2, max_n=4)
        output_weather_types(fire_weather_df, str(tmp_path), km, extreme_percentile=95)

        assert (tmp_path / "p95_extreme_weather_types.csv").exists()
        assert (tmp_path / "all_mean_weather_types.csv").exists()

        extreme = pd.read_csv(tmp_path / "p95_extreme_weather_types.csv")
        assert "T" in extreme.columns
        assert "RH" in extreme.columns
        assert len(extreme) > 0

    def test_output_weather_types_list_percentile(self, fire_weather_df, tmp_path):
        from prepfire.core.clustering import cluster_fire_weather, output_weather_types

        km = cluster_fire_weather(fire_weather_df, min_n=2, max_n=4)
        output_weather_types(fire_weather_df, str(tmp_path), km, extreme_percentile=[30, 60, 90])

        assert (tmp_path / "Extensive_percentile_group_weather_scenarios.csv").exists()

    def test_list_percentile_not_mutated(self, fire_weather_df, tmp_path):
        """Verify fix for C2: input list should not be mutated."""
        from prepfire.core.clustering import cluster_fire_weather, output_weather_types

        km = cluster_fire_weather(fire_weather_df, min_n=2, max_n=4)
        percentiles = [30, 60, 90]
        original = percentiles.copy()
        output_weather_types(fire_weather_df, str(tmp_path), km, extreme_percentile=percentiles)
        assert percentiles == original


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_rh_calc(self):
        from prepfire.utils.helpers import rh_calc
        rh = rh_calc(td=10.0, t=20.0)
        assert 0 < rh < 100

    def test_vpd_calc(self):
        from prepfire.utils.helpers import vpd_calc
        vpd = vpd_calc(t=25.0, rh=50.0)
        assert vpd > 0

    def test_dfmc_calc(self):
        from prepfire.utils.helpers import dfmc_calc
        dfmc = dfmc_calc(t=25.0, rh=50.0)
        assert isinstance(float(dfmc), float)

    def test_dfmc_vpd_calc(self):
        from prepfire.utils.helpers import dfmc_vpd_calc
        import xarray as xr
        vpd = xr.DataArray([0.5, 1.0, 2.0])
        result = dfmc_vpd_calc(vpd)
        assert len(result) == 3
        assert all(result > 0)


# ---------------------------------------------------------------------------
# Pipeline initialization tests
# ---------------------------------------------------------------------------

class TestPipelineInit:
    def test_setup_project_structure(self, tmp_path):
        from prepfire.pipeline import setup_project_structure
        setup_project_structure("test_region", root_dir=str(tmp_path))

        assert (tmp_path / "input_data" / "test_region").is_dir()
        assert (tmp_path / "input_data" / "test_region" / "lcp_Fuel").is_dir()
        assert (tmp_path / "Processed_data").is_dir()

    def test_pipeline_init_validates_region(self):
        from prepfire.pipeline import PrepFirePipeline
        with pytest.raises(ValueError, match="Region name"):
            PrepFirePipeline(region="", root_dir=tempfile.mkdtemp())

    def test_pipeline_init_validates_percentile(self):
        from prepfire.pipeline import PrepFirePipeline
        with pytest.raises(ValueError, match="percentile"):
            PrepFirePipeline(region="test", root_dir=tempfile.mkdtemp(), extreme_percentile=150)

    def test_pipeline_init_validates_clusters(self):
        from prepfire.pipeline import PrepFirePipeline
        with pytest.raises(ValueError, match="Minimum"):
            PrepFirePipeline(region="test", root_dir=tempfile.mkdtemp(), min_clusters=1)

    def test_pipeline_creates_directories(self, tmp_path):
        from prepfire.pipeline import PrepFirePipeline
        pipeline = PrepFirePipeline(region="test_region", root_dir=str(tmp_path))

        assert (tmp_path / "Processed_data" / "test_region" / "Weather").is_dir()
        assert (tmp_path / "Processed_data" / "test_region" / "Landscape").is_dir()
        assert (tmp_path / "Processed_data" / "test_region" / "Ignition").is_dir()


# ---------------------------------------------------------------------------
# Weather bound extent tests
# ---------------------------------------------------------------------------

class TestBoundExtent:
    def test_get_bound_extent_from_coords(self):
        import geopandas as gpd
        from shapely.geometry import Point
        from prepfire.core.weather import get_bound_extent

        gdf = gpd.GeoDataFrame(
            geometry=[Point(14, 57), Point(15, 58)],
            crs="EPSG:4326"
        )
        extent = get_bound_extent([13, 56, 16, 59], gdf, "EPSG:3035", buffer_size=10000)
        assert extent is not None
        assert extent.area > 0

    def test_get_bound_extent_from_gdf(self):
        import geopandas as gpd
        from shapely.geometry import Point
        from prepfire.core.weather import get_bound_extent

        gdf = gpd.GeoDataFrame(
            geometry=[Point(14, 57), Point(15, 58)],
            crs="EPSG:4326"
        )
        # Pass None to derive extent from gdf itself
        extent = get_bound_extent(None, gdf, "EPSG:3035", buffer_size=5000)
        assert extent is not None
        assert extent.area > 0
