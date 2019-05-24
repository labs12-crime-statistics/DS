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
import os

# Read/write DB URI
DB_URI  = config('DB_URI')
ENGINE  = create_engine(DB_URI)
Session = sessionmaker(bind=ENGINE)
SESSION = Session()

# Get currnt date and range of months/years to look at for predicting future
date = datetime.datetime.today()
start_year = date.year - 1
start_month = date.month - 2
end_year = date.year
end_month = date.month - 1
print(start_year, end_year, start_month, end_month)

# SQL query string for sleecting dates
dates = "AND ("+" OR ".join(["(incident.year = {} AND incident.month > {})".format(year, start_month) if start_year == year else "(incident.year = {} AND incident.month < {})".format(year, end_month) if end_year == year else "incident.year = {}".format(year) for year in range(start_year, end_year+1)])+")\n"

# SQL query
query = f"""
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
    incident.hour;
"""

df = pd.read_sql_query(query, DB_URI, coerce_float=False)

# Get number of blockids and relative location
block_ids = {}
for ind, blockid in enumerate(df["blockid"].unique()):
    block_ids[blockid] = ind
X = np.zeros((len(block_ids), 12*7*24))

# Create prediction
for i in df.index.values:
    X[block_ids[df.loc[i,"blockid"]], ((12 * (df.loc[i,"year"] - start_year) + df.loc[i,"month"] - start_month - 1) * 7 + (df.loc[i,"dow"])) * 24 + df.loc[i,"hour"]] = float(df.loc[i,"severity"])

# Put predictions into pandas DataFrame with corresponding block id
predictions = pd.DataFrame([[x] for x in list(block_ids)], columns=["id"])
predictions.loc[:, "prediction"] = predictions["id"].apply(lambda x: X[block_ids[x],:].astype(np.float64).tobytes().hex())
predictions.loc[:, "month"] = end_month
predictions.loc[:, "year"] = end_year
predictions.to_csv("predictions.csv", index=False)

# Query SQL
query_commit_predictions = """
CREATE TEMPORARY TABLE temp_predictions (
    id SERIAL PRIMARY KEY,
    prediction TEXT,
    month INTEGER,
    year INTEGER
);

COPY temp_predictions (id, prediction, month, year) FROM STDIN DELIMITER ',' CSV HEADER;

UPDATE block
SET 
    prediction = DECODE(temp_predictions.prediction, 'hex'),
    month = temp_predictions.month,
    year = temp_predictions.year 
FROM temp_predictions
WHERE block.id = temp_predictions.id;

DROP TABLE temp_predictions;
"""

# Open saved predictions and send to database using above query
with open("predictions.csv", "r") as f:
    print("SENDING TO DB")
    RAW_CONN = create_engine(DB_URI).raw_connection()
    cursor = RAW_CONN.cursor()
    cursor.copy_expert(query_commit_predictions, f)
    RAW_CONN.commit()
    RAW_CONN.close()
os.remove("predictions.csv")

for r in SESSION.execute("SELECT ENCODE(prediction::BYTEA, 'hex'), id FROM block WHERE prediction IS NOT NULL LIMIT 5;").fetchall():
    print(np.frombuffer(bytes.fromhex(r[0]), dtype=np.float64).reshape((12,7,24)).shape)
