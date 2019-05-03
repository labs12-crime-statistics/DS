from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from decouple import config
from geomet import wkb, wkt
import pandas as pd

import json
import datetime
import math
import io

# Connect to DB and create session with DB
DB_URI  = config('DB_URI')

config_dict = {}
config_dict["cityid"] = "1"
config_dict["sdt"] = "04/01/2019"
config_dict["edt"] = "01/01/2100"
config_dict["stime"] = "0"
config_dict["etime"] = "24"
dotw = ""
crimetypes = ""
locdesc1 = "".split(",")
locdesc2 = "".split(",")
locdesc3 = "".split(",")

query_base    = " FROM incident "
query_city    = "incident.cityid = {cityid}"
query_date    = "incident.datetime >= TO_DATE('{sdt}', 'MM/DD/YYYY') AND datetime <= TO_DATE('{edt}', 'MM/DD/YYYY')"
query_time    = "incident.hour >= {stime} AND hour <= {etime}"
query_dotw    = "incident.dow = ANY({dotw})"
query_crmtyp  = "crimetype.category = ANY({crimetypes})"
query_locdesc = "(locdesctype.key1, locdesctype.key2, locdesctype.key3) = ANY({lockeys})"
query_join    = "INNER JOIN crimetype ON incident.crimetypeid = crimetype.id INNER JOIN locdesctype ON incident.locdescid = locdesctype.id INNER JOIN city ON incident.cityid = city.id AND "

base_list = [query_city, query_date, query_time]
outputs   = ", ".join(["city.city", "city.state", "city.country", "incident.datetime", "incident.location", "crimetype.category", "locdesctype.key1 AS location_key1", "locdesctype.key2 AS location_key2", "locdesctype.key3 AS location_key3"])
if dotw != "":
    config_dict["dotw"] = dotw.split(",")
    base_list.append(query_dotw)
if crimetypes != "":
    config_dict["crimetypes"] = ["'{}'".format(x) for x in crimetypes.split(",")]
    config_dict["crimetypes"] = "ARRAY[{}]".format(", ".join(config_dict["crimetypes"]))
    base_list.append(query_crmtyp)
if locdesc1 != [""] and locdesc2 != [""] and locdesc3 != [""] and len(locdesc1) == len(locdesc2) and len(locdesc2) == len(locdesc3):
    config_dict["lockeys"] = []
    for i in range(len(locdesc1)):
        config_dict["lockeys"].append("('{}', '{}', '{}')".format(locdesc1[i], locdesc2[i], locdesc3[i]))
    config_dict["lockeys"] = "ARRAY[{}]".format(", ".join(config_dict["lockeys"]))
    base_list.append(query_locdesc)

query = "COPY (SELECT " + outputs + query_base + query_join + (" AND ".join(base_list)).format(**config_dict) +") TO STDOUT WITH DELIMITER ',' CSV HEADER;"
with io.StringIO() as f:
    RAW_CONN = create_engine(DB_URI).raw_connection()
    cursor = RAW_CONN.cursor()
    cursor.copy_expert(query, f)
    cursor.close()
    RAW_CONN.close()
    f.seek(0)
    data = pd.read_csv(f, sep=",")
    data.loc[:,"location"] = data.loc[:,"location"].apply(lambda x: [float(y) for y in wkt.dumps(wkb.loads(bytes.fromhex(x))).replace("(", "").replace(")", "").split(" ")[1:]])
    data.loc[:,"latitude"] = data.loc[:,"location"].apply(lambda x: x[0])
    data.loc[:,"longitude"] = data.loc[:,"location"].apply(lambda x: x[1])
    data = data.drop(columns=["location"])
with io.StringIO() as f:
    data.to_csv(f, index=False)
    print(f.getvalue())
