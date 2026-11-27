
import sys
from pathlib import Path
import pandas as pd

# Ajouter la racine du projet au chemin Python
PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.database import get_connection


# Lire les données depuis PostgreSQL
def read_query(query, params=None):
    conn = get_connection()

    try:
        with conn.cursor() as cursor:
            cursor.execute(query, params or [])
            rows = cursor.fetchall()

            columns = [
                description.name
                for description in cursor.description
            ]

            return pd.DataFrame(rows, columns=columns)

    finally:
        conn.close()


# Exécuter INSERT, UPDATE et DELETE
def execute_query(query, params=None):
    conn = get_connection()

    try:
        with conn.cursor() as cursor:
            cursor.execute(query, params or [])

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


# Récupérer les prévisions de ventes Chronos-2
def get_sales_forecasts():
    return read_query("""
        SELECT
            item_id,
            forecast_date,
            predicted_quantity,
            model_name
        FROM sales_forecasts
        ORDER BY forecast_date, item_id;
    """)
