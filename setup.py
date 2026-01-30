from setuptools import setup, find_packages

setup(
    name="prepfire",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "numpy",
        "pandas",
        "geopandas",
        "rasterio",
        "xarray",
        "netCDF4",
        "cdsapi",
        "scikit-learn",
        "shapely",
        "matplotlib",
        "wheel",
        "setuptools",
        "pyproj",
        "zarr",
        "cftime",
        "h5netcdf"
    ],
    python_requires=">=3.10",
) 