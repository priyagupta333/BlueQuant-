"""
train_and_predict_credits.py

- Train a regression model to predict AGBM (t/ha) from features.
- Predict for new rows or images and compute carbon & credits given an area (ha).
"""

import os
import pandas as pd
import numpy as np
import joblib
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
from PIL import Image

MODEL_PATH = "agbm_model.joblib"

# -------------------------
# Utility: robust column name resolver
# -------------------------
def _find_feature_cols(df):
    """Return standardized feature column names present in df.
       Looks for variants like mean_red, mean_r, mean_red_channel, etc."""
    col_lower = {c.lower(): c for c in df.columns}
    mapping = {}
    # expected keys: red, green, blue, vegetation_index (ndvi)
    candidates = {
        "red": ["mean_red", "mean_r", "mean_red_channel", "meanred", "red_mean"],
        "green": ["mean_green", "mean_g", "mean_green_channel", "meangreen", "green_mean"],
        "blue": ["mean_blue", "mean_b", "mean_blue_channel", "meanblue", "blue_mean"],
        "vi": ["vegetation_index", "ndvi", "vi", "vegetationindex", "veg_index"]
    }
    for key, names in candidates.items():
        for n in names:
            if n in col_lower:
                mapping[key] = col_lower[n]
                break
    return mapping

# -------------------------
# Feature extraction from RGB image (simple)
# -------------------------
def extract_simple_features_from_image(image_path):
    """
    Returns a dict: mean_red, mean_green, mean_blue, vegetation_index (simple)
    vegetation_index here is an approximate index computed from RGB:
       VI = (G - R) / (G + R + 1e-6)  -> range roughly (-1, 1)
    This is a quick proxy for NDVI when only RGB is available.
    """
    img = Image.open(image_path).convert("RGB")
    arr = np.array(img).astype(np.float32)
    mean_r = float(arr[:, :, 0].mean())
    mean_g = float(arr[:, :, 1].mean())
    mean_b = float(arr[:, :, 2].mean())
    vi = float((mean_g - mean_r) / (mean_g + mean_r + 1e-6))
    return {
        "mean_red": mean_r,
        "mean_green": mean_g,
        "mean_blue": mean_b,
        "vegetation_index": vi
    }

# -------------------------
# Train model using CSVs
# -------------------------
def train_model(features_csv="features_metadata.csv", labels_csv="train_agbm_metadata.csv", model_path=MODEL_PATH):
    print("Loading CSVs...")
    feat = pd.read_csv(features_csv)
    lab = pd.read_csv(labels_csv)

    print("Discovering feature columns...")
    mapping = _find_feature_cols(feat)
    print("Found mapping:", mapping)
    required = ["red", "green", "blue"]
    for r in required:
        if r not in mapping:
            raise ValueError(f"Feature column for '{r}' not found in {features_csv}. Found columns: {feat.columns.tolist()}")

    # Merge on chip_id (robust)
    if "chip_id" not in feat.columns or "chip_id" not in lab.columns:
        # fallback: try 'id' or 'filename'
        raise ValueError("Both CSVs must contain 'chip_id' column to merge on. Rename appropriately.")
    df = pd.merge(feat, lab, on="chip_id", how="inner")
    print(f"Merged dataset rows: {len(df)}")

    # Prepare X, y using discovered columns
    X = pd.DataFrame({
        "red": df[mapping["red"]],
        "green": df[mapping["green"]],
        "blue": df[mapping["blue"]],
    })
    # add vegetation_index if present
    if "vi" in mapping:
        X["vi"] = df[mapping["vi"]]
    else:
        # compute simple VI from mean green & red
        X["vi"] = (X["green"] - X["red"]) / (X["green"] + X["red"] + 1e-6)

    y = df["agbm"].astype(float)  # target: tons per hectare

    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    print("Training RandomForestRegressor on features:", X.columns.tolist())
    model = RandomForestRegressor(n_estimators=200, random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)

    # Evaluate
    y_pred = model.predict(X_test)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    print(f"Model trained. Test RMSE (t/ha): {rmse:.3f}")

    # Save model and the feature column order
    joblib.dump({"model": model, "feature_cols": X.columns.tolist()}, model_path)
    print("Saved model to", model_path)
    return model, X.columns.tolist()

# -------------------------
# Prediction + Credit computation
# -------------------------
def predict_agbm_from_features_row(model_obj, feature_cols, feature_row):
    """feature_row: dict with keys matching feature_cols or at least red/green/blue/vi"""
    # create array in correct order
    x = np.array([feature_row.get(c, 0.0) for c in feature_cols], dtype=float).reshape(1, -1)
    pred = model_obj.predict(x)[0]
    return float(pred)  # t/ha

def compute_carbon_and_credits(biomass_t_per_ha, area_ha):
    """Given biomass (t/ha) and area (ha), compute totals and credits.
       Returns dict with biomass_total (t), carbon_t, co2e_t, credits (t CO2e)."""
    biomass_total = biomass_t_per_ha * area_ha              # t biomass
    carbon_t = biomass_total * 0.5                         # t C (assume 50% carbon fraction)
    co2e_t = carbon_t * 44.0 / 12.0                        # convert C to CO2e => * (44/12) ≈ 3.6667
    credits = co2e_t                                       # 1 credit = 1 t CO2e
    return {
        "biomass_t_per_ha": float(biomass_t_per_ha),
        "area_ha": float(area_ha),
        "biomass_total_t": float(biomass_total),
        "carbon_t": float(carbon_t),
        "co2e_t": float(co2e_t),
        "credits": float(credits)
    }

# -------------------------
# Utility: predict from image path + area
# -------------------------
def predict_from_image_and_area(image_path, area_ha, model_path=MODEL_PATH):
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model not found at {model_path}. Run training first.")
    payload = joblib.load(model_path)
    model = payload["model"]
    feature_cols = payload["feature_cols"]

    feats = extract_simple_features_from_image(image_path)
    # align keys -> use feature_cols order
    # some feature cols may be named 'red','green','blue','vi'
    mapping_keys = {
        "red": ["mean_red", "mean_r", "red"],
        "green": ["mean_green", "mean_g", "green"],
        "blue": ["mean_blue", "mean_b", "blue"],
        "vi": ["vegetation_index", "ndvi", "vi"]
    }
    # build feature_row dict with possible keys
    feature_row = {}
    # fill with our extracted feats where possible
    feature_row["red"] = feats["mean_red"]
    feature_row["green"] = feats["mean_green"]
    feature_row["blue"] = feats["mean_blue"]
    feature_row["vi"] = feats["vegetation_index"]

    # reorder into model feature_cols
    ordered_row = {c: feature_row.get(c, 0.0) for c in feature_cols}

    agbm_pred = predict_agbm_from_features_row(model, feature_cols, ordered_row)
    results = compute_carbon_and_credits(agbm_pred, area_ha)
    return results

# -------------------------
# Example CLI usage
# -------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Train model or predict credits from image/features.")
    parser.add_argument("--train", action="store_true", help="Train model from features_metadata.csv + train_agbm_metadata.csv")
    parser.add_argument("--predict-image", type=str, help="Path to image to predict (requires trained model)")
    parser.add_argument("--area", type=float, default=1.0, help="Area in hectares for credit calculation (default=1.0 ha)")
    parser.add_argument("--model-path", type=str, default=MODEL_PATH, help="Where to save/load model")

    args = parser.parse_args()

    if args.train:
        train_model("features_metadata.csv", "train_agbm_metadata.csv", model_path=args.model_path)
    elif args.predict_image:
        res = predict_from_image_and_area(args.predict_image, args.area, model_path=args.model_path)
        print("\n=== Prediction & Credit Summary ===")
        print(f"Predicted biomass (t/ha): {res['biomass_t_per_ha']:.3f}")
        print(f"Area (ha): {res['area_ha']:.3f}")
        print(f"Total biomass (t): {res['biomass_total_t']:.3f}")
        print(f"Carbon (t C): {res['carbon_t']:.3f}")
        print(f"CO2e (t CO2): {res['co2e_t']:.3f}")
        print(f"Credits (t CO2e): {res['credits']:.3f}")
    else:
        parser.print_help()