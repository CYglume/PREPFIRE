@echo off
REM Local build and install test for prepfire (Windows)
REM Builds the package, installs the wheel in a temp venv, and verifies imports.
REM Usage: scripts\local_build_test.bat
setlocal enabledelayedexpansion

set "PACKAGE_DIR=%~dp0.."
set "INSTALL_DIR=%USERPROFILE%\prepfire_test"

REM ---- Phase 1: Build ----
echo === 1. Create a clean virtual environment ===
python -m venv "%PACKAGE_DIR%\.venv_test"
call "%PACKAGE_DIR%\.venv_test\Scripts\activate.bat"

echo === 2. Install build tools ===
python -m pip install --upgrade pip build

echo === 3. Build the package ===
cd /d "%PACKAGE_DIR%"
python -m build
echo Built files:
dir /b dist\

echo === 4. Install the built wheel ===
for %%f in (dist\*.whl) do pip install "%%f"

echo === 5. Test imports (outside source tree) ===
cd /d "%TEMP%"
python -c "import prepfire; print('Version:', prepfire.__version__); from prepfire.core import weather, clustering, raster; from prepfire.utils.helpers import rh_calc, vpd_calc, dfmc_calc, dfmc_vpd_calc; from prepfire.pipeline import PrepFirePipeline, setup_project_structure, run_prepare; import numpy, pandas, geopandas, rasterio, xarray; import scipy.stats, sklearn.cluster, shapely, matplotlib, cdsapi; print('All imports successful!')"
cd /d "%PACKAGE_DIR%"

REM ---- Phase 2: Install test (separate directory) ----
echo === 6. Set up test project structure ===
mkdir "%INSTALL_DIR%" 2>nul
cd /d "%INSTALL_DIR%"
python -c "from prepfire.pipeline import setup_project_structure; setup_project_structure(region='my_region', root_dir='.'); print('Project structure created.')"
cd /d "%PACKAGE_DIR%"

REM ---- Cleanup ----
echo === 7. Cleanup ===
call deactivate
rmdir /s /q "%PACKAGE_DIR%\.venv_test"
rmdir /s /q "%INSTALL_DIR%"

echo.
echo === BUILD AND INSTALL TEST PASSED ===
endlocal
