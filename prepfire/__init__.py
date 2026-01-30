"""
PREPFIRE: A Python package for fire simulation input preparation.

PREPFIRE (PREParation for FIRE simulation) provides tools for processing fire data,
weather conditions, and landscape characteristics. The package implements a complete
pipeline for fire risk assessment and simulation input preparation.

Key features include:
- Fire data processing and analysis
- Landscape file (lcp) component processing
- Weather data integration with ERA5-Land dataset
- Weather type clustering and analysis
- Interactive API key management for weather data
- Ignition probability map generation
- Fuel Moistures File (.fms) generation
- Project structure setup utility

The output files are intended for fire ignition simulation in FlamMap algorithm.
"""

__version__ = '0.1.0'
__author__ = 'Cheng-Ying Yang, Marcos Rodrigues Mimbrero'
__authors__ = ['Cheng-Ying Yang', 'Marcos Rodrigues Mimbrero']
__email__ = 'rmarcos@unizar.es'

from .pipeline import PrepFirePipeline, setup_project_structure, run_prepare
from .core import raster, weather, clustering

# Backward compatibility alias
PrepFirePipeline = PrepFirePipeline

__all__ = [
    'PrepFirePipeline',
    'PrepFirePipeline',  # Backward compatibility
    'setup_project_structure',
    'run_prepare',
    'raster',
    'weather',
    'clustering'
] 