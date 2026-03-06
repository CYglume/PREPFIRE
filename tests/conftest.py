import os
import pytest
import pandas as pd

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def fire_weather_df():
    """Load the synthetic fire weather fixture as a DataFrame."""
    return pd.read_csv(os.path.join(FIXTURES_DIR, "fire_weather_synthetic.csv"))
