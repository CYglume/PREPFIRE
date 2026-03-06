"""Generate synthetic fire history fixture data for tests."""
import numpy as np
import pandas as pd

np.random.seed(42)
N = 200

# Southern Sweden bounding box (approx lat/lon)
lon = np.random.uniform(13.0, 16.0, N)
lat = np.random.uniform(56.0, 59.0, N)

# Fire dates spread across fire seasons 2010-2020
years = np.random.choice(range(2010, 2021), N)
months = np.random.choice([5, 6, 7, 8], N)
days = np.random.randint(1, 28, N)
dates = [f"{y}-{m:02d}-{d:02d}" for y, m, d in zip(years, months, days)]

# Fire sizes (ha) — lognormal distribution
area = np.round(np.random.lognormal(mean=2, sigma=1.5, size=N), 2)

# Synthetic weather at fire location/date
T = np.round(np.random.uniform(15, 35, N), 1)        # Temperature (°C)
RH = np.round(np.random.uniform(15, 80, N), 1)       # Relative humidity (%)
WS = np.round(np.random.uniform(2, 30, N), 1)        # Wind speed (km/h)
WD = np.round(np.random.uniform(0, 360, N), 1)       # Wind direction (°)
DFMC = np.round(4.37 + 0.161 * RH - 0.1 * T - 0.027 * RH, 2)  # Dead fuel moisture

df = pd.DataFrame({
    "longitude": lon,
    "latitude": lat,
    "Date": dates,
    "Year": years,
    "Area_ha": area,
    "T": T,
    "RH": RH,
    "WS": WS,
    "WD": WD,
    "DFMC": DFMC,
})

df.to_csv("tests/fixtures/fire_weather_synthetic.csv", index=False)
print(f"Generated {N} synthetic fire records -> tests/fixtures/fire_weather_synthetic.csv")
