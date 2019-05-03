"""Create DB tables and input rows for tables."""

from sqlalchemy import create_engine, func, text
from sqlalchemy.orm import sessionmaker

from decouple import config
from functools import partial

from shapely import wkb, wkt
from shapely.geometry import shape
from shapely.geometry.multipolygon import MultiPolygon
from shapely.ops import transform

import shapefile
import pyproj

import numpy as np
import pandas as pd

from models import *

import json
import datetime
import io

# Read/write DB URI
DB_URI  = config('DB_URI')

# Get currnt date and range of months/years to look at for predicting future
date = datetime.datetime.today()
start_year = date.year - 2
start_month = date.month - 1
end_year = date.year
end_month = date.month

# SQL query string for sleecting dates
dates = "AND ("+" OR ".join(["(incident.year = {} AND incident.month > {})".format(year, start_month) if start_year == year else "(incident.year = {} AND incident.month < {})".format(year, end_month) if end_year == year else "incident.year = {}".format(year) for year in range(start_year, end_year+1)])+")\n"

# SQL query
query = f"""WITH
    max_severity AS (
        SELECT MAX(severity) AS severity
        FROM (
            SELECT SUM(crimetype.severity)/AVG(block.population) AS severity
            FROM incident
            INNER JOIN block ON incident.blockid = block.id
            INNER JOIN crimetype ON incident.crimetypeid = crimetype.id
                AND block.population > 0
            GROUP BY
                incident.blockid,
                incident.year,
                incident.month,
                incident.dow,
                incident.hour
        ) AS categories
    ),
    block_incidents AS (
        SELECT
            incident.blockid,
            incident.year,
            incident.month,
            incident.dow,
            incident.hour,
            SUM(crimetype.severity)/AVG(block.population) AS severity
        FROM incident
        INNER JOIN block ON incident.blockid = block.id
        INNER JOIN crimetype ON incident.crimetypeid = crimetype.id
            AND block.population > 0
            {dates}
        GROUP BY
            incident.blockid,
            incident.year,
            incident.month,
            incident.dow,
            incident.hour
    )
    SELECT
        block_incidents.blockid,
        block_incidents.year,
        block_incidents.month,
        block_incidents.dow,
        block_incidents.hour,
        block_incidents.severity / max_severity.severity AS severity
    FROM
        block_incidents, max_severity;
"""

df = pd.read_sql_query(query, DB_URI, coerce_float=False)

# Get number of blockids and relative location
block_ids = {}
for ind, blockid in enumerate(df["blockid"].unique()):
    block_ids[blockid] = ind
X = np.zeros((len(block_ids), 2*12, 7*24))

# Create prediction
for i in df.index.values:
    X[block_ids[df.loc[i,"blockid"]], 12 * (df.loc[i,"year"] - start_year) + df.loc[i,"month"] - start_month - 1, 24 * (df.loc[i,"dow"]) + df.loc[i,"hour"]] = df.loc[i,"severity"]


# MODEL PREDICTION HERE

# Put predictions into pandas DataFrame with corresponding block id
predictions = pd.DataFrame([[x] for x in list(block_ids)], columns=["id"])
predictions.loc[:, "prediction"] = predictions["id"].apply(lambda x: str(X[block_ids[x],:,:].tobytes())[2:-1])
predictions.to_csv("predictions.csv", index=False)

# Query SQL
query_commit_predictions = """
CREATE TEMPORARY TABLE temp_predictions (
    id SERIAL PRIMARY KEY,
    prediction TEXT
);
COPY temp_predictions (id, prediction) FROM STDIN DELIMITER ',' CSV HEADER;
UPDATE block SET prediction = temp_predictions.prediction::BYTEA FROM temp_predictions WHERE block.id = temp_predictions.id;
DROP TABLE temp_predictions;
"""

# Open saved predictions and send to database using above query
with open("predictions.csv", "r") as f:
    RAW_CONN = create_engine(DB_URI).raw_connection()
    cursor = RAW_CONN.cursor()
    cursor.copy_expert(query_commit_predictions, f)
    for r in cursor.execute("SELECT prediction FROM block LIMIT 5;").fetchall():
        print(r[0])
    cursor.close()
    # Test first before committing
    # RAW_CONN.commit()
    # RAW_CONN.close()
