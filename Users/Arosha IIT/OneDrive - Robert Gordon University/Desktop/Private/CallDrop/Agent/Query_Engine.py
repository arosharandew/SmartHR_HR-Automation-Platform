import pandas as pd
import numpy as np
import joblib
from .Config import ENGINEERED_CSV_PATH, MODEL_PATH, FEATURE_COLUMNS

class QueryEngine:
    def __init__(self):
        self.df = pd.read_csv(ENGINEERED_CSV_PATH)
        # Create datetime column
        if 'datetime' not in self.df.columns:
            if 'date' in self.df.columns and 'time' in self.df.columns:
                self.df['datetime'] = pd.to_datetime(self.df['date'].astype(str) + ' ' + self.df['time'].astype(str))
            elif 'start_timestamp' in self.df.columns:
                self.df['datetime'] = pd.to_datetime(self.df['start_timestamp'], unit='s')
            else:
                # Fallback: use call_id order (not great, but better than nothing)
                self.df['datetime'] = pd.to_datetime(self.df['call_id'], origin='unix', unit='s')
        self.df = self.df.sort_values('datetime').reset_index(drop=True)

        # Load model
        try:
            self.model = joblib.load(MODEL_PATH)
        except:
            self.model = None

    # ---------- Basic info ----------
    def get_total_calls(self):
        return len(self.df)

    def get_drop_count(self):
        return self.df['is_drop'].sum()

    def get_drop_rate(self):
        return self.df['is_drop'].mean() * 100

    # ---------- First/Last calls ----------
    def get_first_call(self):
        return self.df.iloc[0].to_dict()

    def get_last_call(self):
        return self.df.iloc[-1].to_dict()

    def get_first_n_calls(self, n):
        return self.df.head(n)[['call_id', 'datetime', 'is_drop']].to_dict('records')

    def get_last_n_calls(self, n):
        return self.df.tail(n)[['call_id', 'datetime', 'is_drop']].to_dict('records')

    # ---------- Specific call by ID ----------
    def get_call_by_id(self, call_id):
        row = self.df[self.df['call_id'] == call_id]
        if row.empty:
            return None
        return row.iloc[0].to_dict()

    # ---------- Date filter ----------
    def get_calls_on_date(self, date_str):
        target = pd.to_datetime(date_str).date()
        mask = self.df['datetime'].dt.date == target
        return self.df[mask][['call_id', 'datetime', 'is_drop']].to_dict('records')

    # ---------- Aggregations (full dataset) ----------
    def get_avg_rsrp_min_dropped(self):
        return self.df[self.df['is_drop'] == 1]['rsrp_min'].mean()

    def get_avg_rsrp_min_normal(self):
        return self.df[self.df['is_drop'] == 0]['rsrp_min'].mean()

    def get_stats(self):
        return {
            'total': len(self.df),
            'drops': self.df['is_drop'].sum(),
            'drop_rate': self.df['is_drop'].mean() * 100,
            'avg_rsrp_drop': self.df[self.df['is_drop']==1]['rsrp_min'].mean(),
            'avg_rsrp_normal': self.df[self.df['is_drop']==0]['rsrp_min'].mean(),
            'avg_slope_drop': self.df[self.df['is_drop']==1]['rsrp_slope_last5'].mean(),
            'avg_slope_normal': self.df[self.df['is_drop']==0]['rsrp_slope_last5'].mean(),
        }

    # ---------- Filter by condition (simple) ----------
    def filter_calls(self, column, operator, value):
        if operator == '<':
            filtered = self.df[self.df[column] < value]
        elif operator == '>':
            filtered = self.df[self.df[column] > value]
        elif operator == '==':
            filtered = self.df[self.df[column] == value]
        else:
            return pd.DataFrame()
        return filtered[['call_id', 'datetime', 'is_drop', column]]

    # ---------- Predict drop for a given call ID ----------
    def predict_call_id(self, call_id):
        row = self.df[self.df['call_id'] == call_id]
        if row.empty:
            return None
        features = row[FEATURE_COLUMNS].iloc[0].to_dict()
        if self.model is None:
            return "Model not loaded."
        X = pd.DataFrame([features])[FEATURE_COLUMNS]
        prob = self.model.predict_proba(X)[0][1]
        pred = self.model.predict(X)[0]
        return {'prediction': int(pred), 'probability': float(prob)}

    def predict_from_features(self, feature_values):
        """feature_values: list of numbers in the exact order of FEATURE_COLUMNS"""
        if self.model is None:
            return None
        # Ensure we have exactly the right number of features
        if len(feature_values) != len(FEATURE_COLUMNS):
            raise ValueError(f"Expected {len(FEATURE_COLUMNS)} features, got {len(feature_values)}")
        X = pd.DataFrame([feature_values], columns=FEATURE_COLUMNS)
        prob = self.model.predict_proba(X)[0][1]
        pred = self.model.predict(X)[0]
        return {'prediction': int(pred), 'probability': float(prob)}