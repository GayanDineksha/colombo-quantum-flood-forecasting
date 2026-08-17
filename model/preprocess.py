import pandas as pd
import numpy as np

RAW_NASA_PATH = "data/raw/Colombo_Climate_Data_NASA.csv"
RAW_RECENT_PATH = "data/raw/Colombo_Climate_Data_2025_2026.csv"
OUTPUT_PATH = "data/processed_data.npz"
LOOKBACK_DAYS = 14   
FEATURES = [
    "Rainfall_mm", "Humidity_pct", "Temperature_C",
    "Soil_Moisture", "Wind_Speed_ms", "Atmospheric_Pressure_kPa",
]


RISK_WEIGHTS = {
    "rainfall_3day": 0.45,
    "soil_moisture": 0.25,
    "humidity": 0.15,
    "pressure_inv": 0.10,
    "wind": 0.05,
}


def load_and_merge():
    df1 = pd.read_csv(RAW_NASA_PATH)
    df2 = pd.read_csv(RAW_RECENT_PATH)
    df = pd.concat([df1, df2], ignore_index=True)
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date").reset_index(drop=True)

    full_range = pd.date_range(df["Date"].min(), df["Date"].max(), freq="D")
    missing = full_range.difference(df["Date"])
    assert len(missing) == 0, f"Found {len(missing)} missing dates - fill before proceeding"
    assert df["Date"].duplicated().sum() == 0, "Found duplicate dates"

    return df


def _minmax(series):
    return (series - series.min()) / (series.max() - series.min())


def engineer_flood_risk_index(df):
    """
    Builds the composite Flood Risk Index (%) - the training target.
    This is a documented heuristic proxy label, since no verified
    historical flood-event ground truth exists for Colombo at daily
    resolution. Stated explicitly as a methodological limitation.
    """
    df = df.copy()
    df["Rainfall_3day"] = df["Rainfall_mm"].rolling(window=3, min_periods=1).sum()

    r_rain = _minmax(df["Rainfall_3day"])
    r_soil = _minmax(df["Soil_Moisture"])
    r_humid = _minmax(df["Humidity_pct"])
    r_pressure_inv = _minmax(-df["Atmospheric_Pressure_kPa"])  # low pressure -> higher risk
    r_wind = _minmax(df["Wind_Speed_ms"])

    composite = (
        RISK_WEIGHTS["rainfall_3day"] * r_rain
        + RISK_WEIGHTS["soil_moisture"] * r_soil
        + RISK_WEIGHTS["humidity"] * r_humid
        + RISK_WEIGHTS["pressure_inv"] * r_pressure_inv
        + RISK_WEIGHTS["wind"] * r_wind
    )

    df["Flood_Risk_Index"] = (composite * 99.9).round(2)
    return df


def build_sequences(df, lookback=LOOKBACK_DAYS):
    """
    Builds sliding-window sequences: X = past `lookback` days of the 6
    raw features (MinMax scaled), y = next day's Flood_Risk_Index.
    """
    feature_data = df[FEATURES].copy()
    scalers = {}
    scaled = pd.DataFrame(index=feature_data.index)
    for col in FEATURES:
        min_val, max_val = feature_data[col].min(), feature_data[col].max()
        scaled[col] = (feature_data[col] - min_val) / (max_val - min_val)
        scalers[col] = {"min": float(min_val), "max": float(max_val)}

    target = df["Flood_Risk_Index"].values
    scaled_arr = scaled.values

    X, y, dates = [], [], []
    for i in range(lookback, len(df)):
        X.append(scaled_arr[i - lookback:i])
        y.append(target[i])
        dates.append(df["Date"].iloc[i])

    return np.array(X), np.array(y), np.array(dates), scalers


def chronological_split(X, y, dates, train_frac=0.75, val_frac=0.10):
    """
    Time-based split - NOT shuffled. Shuffling time-series data leaks
    future information into training and invalidates the evaluation.
    """
    n = len(X)
    train_end = int(n * train_frac)
    val_end = int(n * (train_frac + val_frac))

    return {
        "X_train": X[:train_end], "y_train": y[:train_end], "dates_train": dates[:train_end],
        "X_val": X[train_end:val_end], "y_val": y[train_end:val_end], "dates_val": dates[train_end:val_end],
        "X_test": X[val_end:], "y_test": y[val_end:], "dates_test": dates[val_end:],
    }


def main():
    print("Loading and merging datasets...")
    df = load_and_merge()
    print(f"  {len(df)} continuous daily rows, {df['Date'].min().date()} to {df['Date'].max().date()}")

    print("Engineering Flood Risk Index target...")
    df = engineer_flood_risk_index(df)
    print(f"  Risk Index range: {df['Flood_Risk_Index'].min():.1f}% to {df['Flood_Risk_Index'].max():.1f}%")
    print(f"  Risk Index mean: {df['Flood_Risk_Index'].mean():.1f}%")

    print(f"Building sliding-window sequences (lookback={LOOKBACK_DAYS} days)...")
    X, y, dates, scalers = build_sequences(df)
    print(f"  {len(X)} sequences, shape {X.shape}")

    print("Performing chronological train/val/test split...")
    split = chronological_split(X, y, dates)
    print(f"  Train: {len(split['X_train'])} ({split['dates_train'][0]} to {split['dates_train'][-1]})")
    print(f"  Val:   {len(split['X_val'])} ({split['dates_val'][0]} to {split['dates_val'][-1]})")
    print(f"  Test:  {len(split['X_test'])} ({split['dates_test'][0]} to {split['dates_test'][-1]})")

    np.savez(
        OUTPUT_PATH,
        X_train=split["X_train"], y_train=split["y_train"],
        X_val=split["X_val"], y_val=split["y_val"],
        X_test=split["X_test"], y_test=split["y_test"],
        feature_names=np.array(FEATURES),
        lookback=LOOKBACK_DAYS,
    )
    print(f"\nSaved processed data to {OUTPUT_PATH}")

    # Also save the full engineered dataframe for reference / thesis figures
    df.to_csv("data/engineered_dataset.csv", index=False)
    print("Saved full engineered dataset to engineered_dataset.csv")


if __name__ == "__main__":
    main()