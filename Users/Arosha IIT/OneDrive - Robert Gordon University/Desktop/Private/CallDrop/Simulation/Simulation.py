import pandas as pd
import numpy as np
import os
from datetime import datetime


# ------------------------------------------------------------
# 1. Generator for one call (full implementation)
# ------------------------------------------------------------
def generate_one_call(call_id, is_drop, start_unix_ts, drop_type=None):
    """
    Generate one call's second‑by‑second data.
    """
    np.random.seed(int(start_unix_ts) % 1000000)

    # Determine drop characteristics
    if is_drop:
        if drop_type is None:
            r = np.random.random()
            if r < 0.6:
                drop_type = 'rf'
            elif r < 0.8:
                drop_type = 'network'
            else:
                drop_type = 'handover'
    else:
        drop_type = None

    # Call duration
    if not is_drop:
        duration = np.random.randint(30, 240)
    else:
        if drop_type == 'network':
            duration = np.random.randint(20, 120)
        else:
            duration = np.random.randint(10, 90)

    # Starting RSRP
    if drop_type == 'rf':
        start_rsrp = np.random.randint(-95, -70)
    else:
        start_rsrp = np.random.randint(-85, -65)

    # Signal evolution
    steps = np.random.randn(duration).cumsum() * 0.8
    if drop_type == 'rf':
        trend = np.linspace(0, -25, duration)
    elif drop_type in ('network', 'handover'):
        trend = np.linspace(0, -5, duration)
    else:
        trend = np.linspace(0, -5, duration)
    rsrp_vals = start_rsrp + trend + steps
    rsrp_vals = np.clip(rsrp_vals, -130, -44)

    # RF crash
    if drop_type == 'rf':
        crash_start = int(duration * 0.7)
        for t in range(crash_start, duration):
            rsrp_vals[t] = np.minimum(rsrp_vals[t], -110 - (t - crash_start))
        rsrp_vals[-5:] = np.linspace(rsrp_vals[-5], -125, 5)

    # Handover oscillation
    if drop_type == 'handover':
        ho_start = duration - 10
        for t in range(max(0, ho_start), duration):
            if (t - ho_start) % 3 == 0:
                rsrp_vals[t] -= 15
            elif (t - ho_start) % 3 == 1:
                rsrp_vals[t] += 10
            else:
                rsrp_vals[t] -= 20
        rsrp_vals = np.clip(rsrp_vals, -130, -44)

    # Ambiguous normal (weak signal hangup)
    if not is_drop and np.random.random() < 0.15:
        rsrp_vals[-8:] = np.random.randint(-115, -100, size=8)

    # RSRQ & SINR
    base_rsrq = -10 + (rsrp_vals + 90) / 10
    noise_rsrq = np.random.randn(duration) * 3
    rsrq_vals = np.clip(base_rsrq + noise_rsrq, -20, -3)

    base_sinr = 15 + (rsrp_vals + 90) / 8
    noise_sinr = np.random.randn(duration) * 4
    sinr_vals = np.clip(base_sinr + noise_sinr, -5, 30)

    # Rain intensity
    rain = np.random.exponential(scale=1.5) if np.random.random() < 0.3 else 0
    if is_drop and drop_type == 'rf' and rain > 5:
        rsrp_vals[-10:] -= 3

    # Tower load
    def get_tower_load(hour, is_drop, network_failure):
        if (7 <= hour <= 9) or (17 <= hour <= 19):
            base = np.random.randint(70, 95)
        else:
            base = np.random.randint(30, 70)
        if network_failure:
            base = np.random.randint(20, 60)
        extra = np.random.randint(-10, 30) if is_drop else np.random.randint(-20, 10)
        return np.clip(base + extra, 0, 100)

    start_hour = datetime.fromtimestamp(start_unix_ts).hour
    network_failure = (drop_type == 'network')
    tower_load = get_tower_load(start_hour, is_drop, network_failure)

    # Speed scenario
    if is_drop:
        scenario = np.random.choice(['stationary', 'walking', 'driving'], p=[0.3, 0.2, 0.5])
    else:
        scenario = np.random.choice(['stationary', 'walking', 'driving'], p=[0.5, 0.3, 0.2])
    if scenario == 'stationary':
        speed = np.random.uniform(0, 5)
    elif scenario == 'walking':
        speed = np.random.uniform(5, 10)
    else:
        speed = np.random.uniform(30, 120)

    # Band
    if is_drop and drop_type == 'rf':
        band_weights = [0.5, 0.3, 0.2]
    else:
        band_weights = [0.33, 0.33, 0.34]
    band = np.random.choice(['LTE_B3', 'LTE_B20', '5G_n78'], p=band_weights)

    # Build rows
    rows = []
    for t in range(duration):
        rows.append({
            'timestamp': int(start_unix_ts + t),
            'rsrp': round(rsrp_vals[t], 1),
            'rsrq': round(rsrq_vals[t], 1),
            'sinr': round(sinr_vals[t], 1),
            'rain_intensity': round(rain, 1),
            'call_id': call_id,
            'band': band,
            'tower_load': tower_load,
            'speed_kmph': round(speed, 1)
        })
    return pd.DataFrame(rows)


# ------------------------------------------------------------
# 2. Simulation function – adds one call using real current time
# ------------------------------------------------------------
def simulate_and_save_one_call(drop_probability=0.08, data_dir="Data"):
    main_csv = os.path.join(data_dir, "telecom_call_drop.csv")
    drop_csv = os.path.join(data_dir, "Drop.csv")

    os.makedirs(data_dir, exist_ok=True)

    # Determine next call_id
    if os.path.exists(main_csv):
        df_main = pd.read_csv(main_csv)
        next_call_id = df_main['call_id'].max() + 1
    else:
        next_call_id = 0

    # Use current real time as start timestamp
    start_ts = int(datetime.now().timestamp())

    is_drop = np.random.random() < drop_probability

    df_new = generate_one_call(
        call_id=next_call_id,
        is_drop=is_drop,
        start_unix_ts=start_ts,
        drop_type=None
    )

    df_new.to_csv(main_csv, mode='a', header=not os.path.exists(main_csv), index=False)
    print(f"✅ Appended {len(df_new)} rows for call_id={next_call_id} to {main_csv} (start timestamp = {start_ts})")

    drop_record = pd.DataFrame([[next_call_id, int(is_drop)]], columns=['call_id', 'is_drop'])
    drop_record.to_csv(drop_csv, mode='a', header=not os.path.exists(drop_csv), index=False)
    print(f"📝 Recorded call_id={next_call_id}, is_drop={is_drop} in {drop_csv}")

    return next_call_id, is_drop


# ------------------------------------------------------------
# 3. Run one simulation
# ------------------------------------------------------------
if __name__ == "__main__":
    call_id, dropped = simulate_and_save_one_call(drop_probability=0.08)
    print(f"\n🎉 Simulation completed for call #{call_id} (dropped = {dropped})")