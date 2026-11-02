from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from src.ml.features import to_model_input
from src.ml.train import MODEL_PATH


def load_artifact(path: Path = MODEL_PATH) -> dict | None:
    return joblib.load(path) if path.exists() else None


# Chance of each ticket being resolved within the horizon
def predict_chance(artifact: dict, features: pd.DataFrame) -> np.ndarray:
    model_input = to_model_input(features, artifact["categories"])
    return artifact["model"].predict_proba(model_input)[:, 1]


# Features of a ticket that would be opened on `day`, with the demand seen in the most recent
# days of the data and a rain value chosen by the user
def simulated_features(
    tickets: pd.DataFrame, service: str, neighborhood: str, day: pd.Timestamp, rain_3d_mm: float
) -> pd.DataFrame:
    last_day = tickets["opened_on"].max()
    recent_7 = tickets["opened_on"] > last_day - pd.Timedelta(days=7)
    recent_30 = tickets["opened_on"] > last_day - pd.Timedelta(days=30)
    service_rows = tickets[tickets["service_name"] == service]
    place = tickets[tickets["neighborhood_name"] == neighborhood]
    return pd.DataFrame(
        [
            {
                "service_name": service,
                "group_name": service_rows["group_name"].iloc[0],
                "neighborhood_name": neighborhood,
                "rpa": place["rpa"].iloc[0] if len(place) else None,
                "month": day.month,
                "day_of_week": day.day_of_week + 1,
                "is_weekend": int(day.day_of_week >= 5),
                "rain_3d_mm": rain_3d_mm,
                "service_demand_7d": int(recent_7[service_rows.index].sum()),
                "neighborhood_demand_30d": int(recent_30[place.index].sum()),
            }
        ]
    )
