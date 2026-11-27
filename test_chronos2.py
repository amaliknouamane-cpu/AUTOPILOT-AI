import pandas as pd
from chronos import Chronos2Pipeline
from backend.database import get_connection

print("Loading sales history from PostgreSQL...")

conn = get_connection()

try:
    historique = pd.read_sql_query(
        """
        SELECT item_id, timestamp, target
        FROM sales_history
        ORDER BY item_id, timestamp;
        """,
        conn
    )
finally:
    conn.close()

historique["timestamp"] = pd.to_datetime(historique["timestamp"])

# Complete daily history for all products
series_completes = []

date_debut = historique["timestamp"].min()
date_fin = historique["timestamp"].max()

dates = pd.date_range(
    start=date_debut,
    end=date_fin,
    freq="D"
)

for item, groupe in historique.groupby("item_id"):

    groupe = groupe.set_index("timestamp").sort_index()

    groupe = groupe.reindex(dates)

    groupe["item_id"] = item
    groupe["target"] = groupe["target"].fillna(0)

    groupe.index.name = "timestamp"

    series_completes.append(groupe.reset_index())

historique = pd.concat(series_completes, ignore_index=True)

historique["target"] = historique["target"].astype(int)

historique = historique.sort_values(
    ["item_id", "timestamp"]
).reset_index(drop=True)

print("\nComplete daily sales history:")
print(historique)

# Verify that all products have the same last historical date
print("\nLast historical date by product:")

print(
    historique.groupby("item_id")["timestamp"].max()
)
print("\nHistorical data:")
print(historique)

print("\nLoading Chronos-2...")
pipeline = Chronos2Pipeline.from_pretrained(
    "amazon/chronos-2",
    device_map="cpu"
)

print("\nGenerating forecasts...")

prediction = pipeline.predict_df(
    historique,
    prediction_length=5,
    id_column="item_id",
    timestamp_column="timestamp",
    target="target"
)
# Keep only forecasts after the last historical date of each product
last_dates = historique.groupby("item_id")["timestamp"].max()

prediction = prediction[
    prediction.apply(
        lambda row: row["timestamp"] > last_dates[row["item_id"]],
        axis=1
    )
].copy()

# Clean sales predictions
prediction["predictions"] = (
    prediction["predictions"]
    .clip(lower=0)
    .astype(float)
    .round(2)
)

# Chronos can legitimately return zero for intermittent products when the
# available history is sparse. Keep those products forecastable with a
# transparent mean-daily-sales fallback instead of plotting only 1-2 series.
daily_mean_by_item = historique.groupby("item_id")["target"].mean()
prediction["model_name"] = "amazon/chronos-2"
zero_forecast = prediction["predictions"] <= 0
prediction.loc[zero_forecast, "predictions"] = (
    prediction.loc[zero_forecast, "item_id"]
    .map(daily_mean_by_item)
    .astype(float)
    .round(2)
)
prediction.loc[zero_forecast, "model_name"] = "historical-mean-fallback"
# Save forecasts into PostgreSQL
conn = get_connection()

try:
    with conn.cursor() as cursor:

        # Remove previous future forecasts
        cursor.execute("""
            DELETE FROM sales_forecasts
            WHERE forecast_date >= CURRENT_DATE;
        """)

        # Insert new forecasts
        for _, row in prediction.iterrows():
            cursor.execute("""
                INSERT INTO sales_forecasts
                (item_id, forecast_date, predicted_quantity, model_name)
                VALUES (%s, %s, %s, %s);
            """, (
                row["item_id"],
                row["timestamp"],
                round(float(row["predictions"]), 2),
                row["model_name"]
            ))

    conn.commit()
    print("Forecasts saved successfully!")

except Exception:
    conn.rollback()
    raise

finally:
    conn.close()

print("\nSALES FORECAST:")
print(prediction.to_string(index=False))
