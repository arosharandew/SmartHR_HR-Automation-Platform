import pandas as pd
import numpy as np
import os
import joblib

# ------------------------------------------------------------------
# Paths
# ------------------------------------------------------------------
MODEL_PATH = "../Models/tuned_xgb.pkl"
ENGINEERED_CSV = "Data/Engineered.csv"
RAW_CSV = "Data/telecom_call_drop.csv"

FEATURE_COLUMNS = [
    'rsrp_min', 'rsrp_max', 'rsrp_mean', 'rsrp_std', 'rsrp_last',
    'rsrp_slope_last5', 'rsrp_slope_all', 'rsrp_time_below_minus110',
    'rsrq_min', 'rsrq_mean', 'rsrq_std', 'rsrq_slope_last5',
    'sinr_min', 'sinr_mean', 'sinr_time_below_0',
    'rain_mean', 'rain_max',
    'tower_load_mean', 'tower_load_max', 'tower_load_high',
    'speed_kmph_mean', 'speed_kmph_max',
    'call_duration_sec', 'start_hour',
    'band_5G_n78', 'band_LTE_B20', 'band_LTE_B3'
]

# ------------------------------------------------------------------
# 1. Load model
# ------------------------------------------------------------------
if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(f"Model not found at {MODEL_PATH}")
model = joblib.load(MODEL_PATH)
print(f"Model loaded from {MODEL_PATH}")

# ------------------------------------------------------------------
# 2. Load Engineered.csv
# ------------------------------------------------------------------
if not os.path.exists(ENGINEERED_CSV):
    raise FileNotFoundError(f"Engineered data not found at {ENGINEERED_CSV}")
eng_df = pd.read_csv(ENGINEERED_CSV)
print(f"Engineered data shape: {eng_df.shape}")

# Identify the last call
last_call_id = eng_df['call_id'].max()
last_call_row = eng_df[eng_df['call_id'] == last_call_id].iloc[0]
print(f"Last call ID: {last_call_id}")

# Extract features and force to float (coerce errors to NaN)
X_last = last_call_row[FEATURE_COLUMNS].astype(float).values.reshape(1, -1)

# Check for NaN
if np.isnan(X_last).any():
    # Option: fill NaN with 0 (or use median, but here we use 0)
    print("Warning: NaN values found in feature vector. Filling with 0.")
    X_last = np.nan_to_num(X_last, nan=0.0)

# Predict
prediction = model.predict(X_last)[0]
probability = model.predict_proba(X_last)[0][1]
print(f"Prediction for call {last_call_id}: {prediction} (drop probability: {probability:.4f})")

# ------------------------------------------------------------------
# 3. Update engineered CSV
# ------------------------------------------------------------------
if 'is_drop' not in eng_df.columns:
    eng_df['is_drop'] = 0
eng_df.loc[eng_df['call_id'] == last_call_id, 'is_drop'] = prediction
eng_df.to_csv(ENGINEERED_CSV, index=False)
print(f"✅ Updated {ENGINEERED_CSV}: set is_drop = {prediction} for call_id = {last_call_id}")

# ------------------------------------------------------------------
# 4. Update raw CSV
# ------------------------------------------------------------------
if not os.path.exists(RAW_CSV):
    raise FileNotFoundError(f"Raw data not found at {RAW_CSV}")
raw_df = pd.read_csv(RAW_CSV)
print(f"Raw data shape: {raw_df.shape}")

if 'is_drop' not in raw_df.columns:
    raw_df['is_drop'] = 0
raw_df.loc[raw_df['call_id'] == last_call_id, 'is_drop'] = prediction
raw_df.to_csv(RAW_CSV, index=False)
print(f"✅ Updated {RAW_CSV}: set is_drop = {prediction} for all rows with call_id = {last_call_id}")