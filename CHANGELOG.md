# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- [CITATION.cff](CITATION.cff): maintain the Zenodo citation format everytime new releases are made and linked to Zenodo.

### Changed
- `clustering.py` — scenario frequency output reorganised for consistency across both output pathways:
  - `_cluster_freqs()` extracted as a dedicated internal helper returning `freq_cluster` (count-based) and `freq_cluster_area` (area-weighted) per cluster
  - Wind direction frequencies now split into `freq_wdir` (count-based) and `freq_wdir_area` (burnt-area-weighted) in `weatherSceneFreq()` for both the `int` and `list/tuple` percentile paths
  - Joint scenario frequencies `freq_scenario` and `freq_scenario_area` now computed as the product of the respective cluster and wind direction frequencies in both `addWindDir()` (single-percentile path) and the extensive percentile group path, ensuring symmetric output columns across all output tables

## [0.1.2] - 2026-05-15
### Added
- `PrepFirePipeline` — `done_lcp` parameter: when `True` (or when `lcp_{region}.tif` already exists), `process_landscape()` skips all raster-reproject operations; consistent design with `done_cds_download`
- `generate_weather_types` — `scenario_tag` parameter: optional string appended to all output CSV filenames (e.g. `scenario_tag="v2"` → `p95_extreme_weather_types_v2.csv`); replaces the previous meaningless `-1.csv` / `-2.csv` suffix loop
- Output directory `Processed_data/<region>/Fires/` for processed fire records
- Output directory `Processed_data/<region>/Weather/FMS/` pre-created by directory structure setup

### Changed
- `download_weather_data`: date column coerced via `pd.to_datetime()` before `.strftime()` — fixes `AttributeError` when reading fire records from ESRI Shapefile (which stores dates as strings)
- `generate_ignition_points`: passes `self.bound_extent.geometry.iloc[0]` (Shapely object) instead of the GeoDataFrame — fixes `Unknown geometry type: 'featurecollection'` error
- `process_raster`: integer source dtypes (e.g. `uint8` fuel codes) are now preserved as-is; float dtypes normalised to `float32`; `src_nodata`/`dst_nodata` passed through to `rasterio.warp.reproject()`
- `extract_fire_weather`: output CSV renamed from `single_fire_weather.csv` to `fire_weather_records.csv`
- LCP output filename changed from `lcp_.tif` to `lcp_{region}.tif`
- FMS output directory capitalised from `fms/` to `FMS/` for consistency with sibling folders
- `output_weather_types`: removed stale-file suffix loop; default behaviour is now to overwrite on re-runs

### Fixed
- `fires_region.gpkg` saved to `Fires/` instead of `Ignition/` (semantically correct location)
- Removed unused `Single/` folder from directory structure setup

### Docs
- README project structure tree updated: removed `Single/`, added `Fires/` and `Weather/FMS/`, corrected output filenames and `lcp_{region}.tif`
- README `PrepFirePipeline` example updated with `done_lcp` and `scenario_tag` parameters
- README Pipeline Methods section rewritten with accurate per-method summaries and `scenario_tag` usage example
- README Fire Weather section updated to document `fire_weather_records.csv` and scenario output table
- README Testing section expanded with explicit commands for Windows and Linux/macOS local build test scripts

## [0.1.1] - 2026-05-08

### Changed
- Switched GitHub Actions publish workflow from GitHub Release asset upload to PyPI OIDC trusted publishing (`pypa/gh-action-pypi-publish`)
- Version bump to 0.1.1 for first PyPI release

## [0.1.0] - 2026-03-06

### Added
- PyPI-ready packaging: replaced `setup.py` with `pyproject.toml` (PEP 621, setuptools.build_meta backend)
- GitHub Actions workflows: `publish.yml` for release-triggered PyPI publishing and `tests.yml` for CI across Python 3.10–3.12
- Comprehensive smoke test suite (`tests/test_smoke.py`, 23 test cases) covering imports, clustering, helpers, and pipeline validation
- Pytest infrastructure: `conftest.py` fixtures and synthetic CSV fixture (`tests/fixtures/fire_weather_synthetic.csv`)
- Local build test scripts for Linux/macOS (`scripts/local_build_test.sh`) and Windows (`scripts/local_build_test.bat`)
- Funding and acknowledgments section in README

### Changed
- Package renamed from `scenfire` to `prepfire`; all module paths updated accordingly
- Pipeline efficiency improvements in `pipeline.py` and core modules
- `examples/basic_usage.py` updated to reflect renamed package and new API

### Removed
- `setup.py` (superseded by `pyproject.toml`)
- `MANIFEST.in` (superseded by `pyproject.toml` package discovery)
- `meta.yaml` conda recipe
- `examples/advanced_usage.py` (consolidated into `basic_usage.py`)

## [0.0.3] - 2026-01-30

### Added
- Manual input support for climate variables (e.g. live plant moisture) directly via pipeline parameters

### Changed
- Clustering module refactored to support configurable manual inputs alongside ERA5-derived values
- README expanded with manual input usage examples

## [0.0.2] - 2025-12-25

### Added
- Percentile-group-based scenario selection: fire weather scenarios are now defined by user-specified percentile thresholds rather than fixed cluster counts
- Mean value aggregation per percentile group in clustering output
- Dead Fuel Moisture Content (DFMC) calculation added to weather processing (`weather.py`)

### Fixed
- DFMC was missing from ERA5 weather extraction pipeline; now computed from relative humidity and temperature

## [0.0.1] - 2025-10-28

### Added
- Polygon-based bounding box support: `get_bound_extent` now accepts a GeoDataFrame in addition to explicit coordinates
- Ignition point generation constrained to polygon boundary (points no longer generated outside the study area)
- GPL-3.0 full license text

### Fixed
- `get_bound_extent` logic error causing incorrect spatial extents for non-square bounding boxes
- Off-by-one in fire point generation that placed sample ignition points outside the polygon
- Live plant moisture manual input wiring in `raster.py` and `pipeline.py`

## [0.0.0] - 2025-04-22

### Added
- Initial commit: core package structure (`scenfire/`) with `pipeline.py`, `core/` (clustering, raster, weather), and `utils/helpers.py`
- ERA5-Land weather data download and processing
- K-means clustering for fire weather type classification
- Landscape file (LCP) construction and raster cropping utilities
- Fuel Moisture Scenario (.fms) file generation
- KDE-based ignition probability map generation
- Project directory structure setup utility
- Conda recipe (`meta.yaml`)
