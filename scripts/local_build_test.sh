#!/usr/bin/env bash
# Local build and install test for prepfire
# Builds the package, installs the wheel in a temp venv, and verifies imports.
# Usage: bash scripts/local_build_test.sh
set -e

PACKAGE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
INSTALL_DIR="$HOME/prepfire_test"

# ---- Phase 1: Build ----
echo "=== 1. Create a clean virtual environment ==="
python -m venv "$PACKAGE_DIR/.venv_test"
source "$PACKAGE_DIR/.venv_test/Scripts/activate" 2>/dev/null || source "$PACKAGE_DIR/.venv_test/bin/activate"

echo "=== 2. Install build tools ==="
python -m pip install --upgrade pip build

echo "=== 3. Build the package ==="
cd "$PACKAGE_DIR"
python -m build
echo "Built files:"
ls dist/

echo "=== 4. Install the built wheel ==="
pip install dist/*.whl

echo "=== 5. Test imports (outside source tree) ==="
cd "$TEMP" 2>/dev/null || cd /tmp
python -c "
import prepfire
print('Version:', prepfire.__version__)

from prepfire.core import weather, clustering, raster
from prepfire.utils.helpers import rh_calc, vpd_calc, dfmc_calc, dfmc_vpd_calc
from prepfire.pipeline import PrepFirePipeline, setup_project_structure, run_prepare

import numpy, pandas, geopandas, rasterio, xarray
import scipy.stats, sklearn.cluster, shapely, matplotlib, cdsapi

print('All imports successful!')
"
cd "$PACKAGE_DIR"

# ---- Phase 2: Install test (separate directory) ----
echo "=== 6. Set up test project structure ==="
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"
python -c "
from prepfire.pipeline import setup_project_structure
setup_project_structure(region='my_region', root_dir='.')
print('Project structure created at: $INSTALL_DIR')
"
cd "$PACKAGE_DIR"

# ---- Cleanup ----
echo "=== 7. Cleanup ==="
deactivate
rm -rf "$PACKAGE_DIR/.venv_test"
rm -rf "$INSTALL_DIR"

echo ""
echo "=== BUILD AND INSTALL TEST PASSED ==="
