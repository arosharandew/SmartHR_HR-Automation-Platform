"""
Feature engineering for telecom call drop prediction.
- All original aggregation and feature generation methods are unchanged.
- Missing values (NaNs) are kept; no rows or columns are dropped.
- Invalid signal values (-999) are replaced with realistic floors.
"""

import pandas as pd
import numpy as np

# ==============================
# 1. Load raw data
# ==============================
raw_df = pd.read_csv("Data/telecom_call_drop.csv")
print("Raw data shape:", raw_df.shape)
print(raw_df.head())
print(raw_df['call_id'].nunique(), "unique calls")

# ==============================
# 2. Ensure correct order within each call
# ==============================
raw_df = raw_df.sort_values(['call_id', 'timestamp']).reset_index(drop=True)
print("Data sorted.")


# ==============================
# 3. Helper functions for aggregation
# ==============================
def last_n_slope(series, n=5):
    """
    Slope of the last `n` values (linear regression).
    Positive slope = signal improving, negative = degrading.
    """
    if len(series) < 2:
        return 0.0
    y = series.iloc[-n:].values if len(series) >= n else series.values
    x = np.arange(len(y))
    slope = np.polyfit(x, y, 1)[0]
    return slope


def time_below_threshold(series, threshold):
    """Number of seconds where series < threshold."""
    return (series < threshold).sum()


def compute_duration(ts_series):
    """Call duration in seconds (max timestamp - min timestamp)."""
    return ts_series.max() - ts_series.min()


# ==============================
# 4. Replace impossible signal values (-999) with realistic floors
# ==============================
raw_df['rsrp'] = raw_df['rsrp'].replace(-999, -130)
raw_df['rsrq'] = raw_df['rsrq'].replace(-999, -20)
raw_df['sinr'] = raw_df['sinr'].replace(-999, -5)
raw_df['rain_intensity'] = raw_df['rain_intensity'].replace(-999, 0)
print("Invalid signal values replaced with realistic floors.")

# ==============================
# 5. Aggregation per call_id
# ==============================
grouped = raw_df.groupby('call_id')

agg_funcs = {
    # RSRP features
    'rsrp_min': ('rsrp', 'min'),
    'rsrp_max': ('rsrp', 'max'),
    'rsrp_mean': ('rsrp', 'mean'),
    'rsrp_std': ('rsrp', 'std'),
    'rsrp_last': ('rsrp', 'last'),
    'rsrp_slope_last5': ('rsrp', lambda x: last_n_slope(x, 5)),
    'rsrp_slope_all': ('rsrp', lambda x: last_n_slope(x, len(x))),
    'rsrp_time_below_minus110': ('rsrp', lambda x: time_below_threshold(x, -110)),

    # RSRQ features
    'rsrq_min': ('rsrq', 'min'),
    'rsrq_mean': ('rsrq', 'mean'),
    'rsrq_std': ('rsrq', 'std'),
    'rsrq_slope_last5': ('rsrq', lambda x: last_n_slope(x, 5)),

    # SINR features
    'sinr_min': ('sinr', 'min'),
    'sinr_mean': ('sinr', 'mean'),
    'sinr_time_below_0': ('sinr', lambda x: time_below_threshold(x, 0)),

    # Rain intensity
    'rain_mean': ('rain_intensity', 'mean'),
    'rain_max': ('rain_intensity', 'max'),

    # Tower load
    'tower_load_mean': ('tower_load', 'mean'),
    'tower_load_max': ('tower_load', 'max'),
    'tower_load_high': ('tower_load', lambda x: (x > 80).sum()),

    # Speed (km/h)
    'speed_kmph_mean': ('speed_kmph', 'mean'),
    'speed_kmph_max': ('speed_kmph', 'max'),

    # Temporal features
    'call_duration_sec': ('timestamp', compute_duration),
    'start_timestamp': ('timestamp', 'min'),
}

features = grouped.agg(**agg_funcs).reset_index()  # call_id becomes a column

# ==============================
# 6. Extract hour of day from start_timestamp, plus date and time
# ==============================
# Convert start_timestamp to datetime
start_dt = pd.to_datetime(features['start_timestamp'], unit='s')
features['start_hour'] = start_dt.dt.hour
features['date'] = start_dt.dt.date          # new column: date (YYYY-MM-DD)
features['time'] = start_dt.dt.time          # new column: time (HH:MM:SS)
features.drop('start_timestamp', axis=1, inplace=True)

# ==============================
# 7. Convert band to dummy variables (0/1 integers)
# ==============================
band_info = raw_df[['call_id', 'band']].drop_duplicates('call_id')
band_dummies = pd.get_dummies(band_info['band'], prefix='band', dtype=int)
band_dummies['call_id'] = band_info['call_id']
features = features.merge(band_dummies, on='call_id', how='left')

# ==============================
# 8. Attach target (is_drop) – one value per call
# ==============================
target_df = raw_df[['call_id', 'is_drop']].drop_duplicates('call_id')
features = features.merge(target_df, on='call_id', how='left')

# ==============================
# 9. NO FILTERING – keep all rows (including calls with missing values)
# ==============================
print(f"Total calls before any filtering: {features.shape[0]}")
print(f"Drops in dataset: {features['is_drop'].sum()}")

# ==============================
# 10. Convert to numeric, but DO NOT drop any columns or rows
# ==============================
# For columns that are not numeric (date, time), we keep them as object
# We convert only numeric columns to float64 (non-numeric stay as-is)
for col in features.select_dtypes(include=['number']).columns:
    features[col] = pd.to_numeric(features[col], errors='coerce')

print("All numeric columns converted. Non-numeric columns (date, time) preserved.")

# ==============================
# 11. Save engineered dataset (including missing values and new date/time columns)
# ==============================
features.to_csv("Data/Engineered.csv", index=False)
print(f"Saved engineered data with {features.shape[0]} rows (calls) and {features.shape[1]} columns.")
print("Sample of first 2 rows:\n", features.head(2))

# ==============================
# 12. Final verification
# ==============================
print("\nData types after conversion:")
print(features.dtypes.value_counts())

print("\nClass distribution after processing:")
print(features['is_drop'].value_counts(dropna=False))
print("\nPercentages (including NaNs):")
print(features['is_drop'].value_counts(dropna=False, normalize=True) * 100)