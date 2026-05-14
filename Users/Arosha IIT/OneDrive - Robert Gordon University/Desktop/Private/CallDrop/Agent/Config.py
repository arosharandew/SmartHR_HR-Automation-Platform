import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SIM_DATA_DIR = os.path.join(PROJECT_ROOT, "Simulation", "Data")
ENGINEERED_CSV_PATH = os.path.join(SIM_DATA_DIR, "Engineered.csv")
MODEL_PATH = os.path.join(PROJECT_ROOT, "Models", "tuned_xgb.pkl")
VECTOR_STORE_DIR = os.path.join(PROJECT_ROOT, "VectorStore")

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