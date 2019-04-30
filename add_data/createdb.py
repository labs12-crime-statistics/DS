"""Create DB tables and input rows for tables."""

from sqlalchemy import create_engine, func, text
from sqlalchemy.orm import sessionmaker
from decouple import config
from shapely import wkb, wkt
import pandas as pd
from models import *
import json
import datetime


# Connect to DB
DB_URI  = config('DB_URI')
ENGINE  = create_engine(DB_URI)
Session = sessionmaker(bind=ENGINE)
SESSION = Session()

# Bas serverity values
SEVERITY_HIGH = 1.0
SEVERITY_MEDIUM = 0.5
SEVERITY_LOW  = 0.2

block_dict = {}
loctype_dict = {}
crimetype_dict = {}


def str_contains_any_substr(string, substrings):
    """Tests to see if any subtrings are contained within string.

    Args:
        string (str): string to search
        substrings (list(str)): list of substrings to search for in string
    Returns:
        (bool) if a substring is contained within string
    """
    for subs in substrings:
        if subs in string:
            return True
    return False


def crime_severity(x):
    """Turns description of crime into numerical crime severity.

    Args:
        x (list(str)): list of [primary type of crime, description of crime]
    Returns:
        (float) crime severity
    """
    primary_type = x[0]
    description  = x[1]
    if (primary_type == 'THEFT'):
        if (description == 'PURSE-SNATCHING') or \
            (description == 'POCKET-PICKING') or \
            (description == 'FROM_BUILDING'):
            return SEVERITY_MEDIUM
        else:
            return SEVERITY_LOW
        
    if (primary_type == 'BATTERY'):
        if 'AGG' in description and \
            'DOMESTIC' not in description:
            return SEVERITY_HIGH
        else:
            return SEVERITY_MEDIUM
        
    if (primary_type == 'NARCOTICS'):
        if 'DEL' in description or \
            'CONSPIRACY' in description:
            return SEVERITY_HIGH
        else:
            return SEVERITY_MEDIUM
        
    if (primary_type == 'OTHER OFFENSE'):
        if str_contains_any_substr(
            description, ['GUN', 'SEX', 'VOILENT', 'PAROLE', 'ARSON']):
            return SEVERITY_HIGH
        else:
            return SEVERITY_LOW
        
    if (primary_type == 'ASSAULT'):
        if str_contains_any_substr(
            description, ['AGG']):
            return SEVERITY_HIGH
        else:
            return SEVERITY_MEDIUM
        
    if (primary_type == 'ROBBERY'):
        if str_contains_any_substr(
            description, ['AGG', 'ARMED']):
            return SEVERITY_HIGH
        else:
            return SEVERITY_MEDIUM
        
    if (primary_type == 'BURGLARY'):
        if str_contains_any_substr(
            description, ['INVASION']):
            return SEVERITY_HIGH
        else:
            return SEVERITY_MEDIUM
        
    if (primary_type == 'CRIMINAL TRESPASS'):
        if str_contains_any_substr(
            description, ['RESIDENCE']):
            return SEVERITY_HIGH
        else:
            return SEVERITY_MEDIUM
        
    if (primary_type == 'MOTOR VEHICLE THEFT'):
        if str_contains_any_substr(
            description, ['AUTO']):
            return SEVERITY_HIGH
        else:
            return SEVERITY_LOW
        
    if (primary_type == 'WEAPONS VIOLATION'):
        if str_contains_any_substr(
            description, ['USE', 'SALE']):
            return SEVERITY_HIGH
        else:
            return SEVERITY_MEDIUM
        
    if (primary_type == 'CONCEALED CARRY LICENSE VIOLATION'):
        if str_contains_any_substr(
            description, ['INFLUENCE']):
            return SEVERITY_HIGH
        else:
            return SEVERITY_MEDIUM
        
    if (primary_type == 'PUBLIC PEACE VIOLATION'):
        if str_contains_any_substr(
            description, ['RECKLESS', 'MOB', 'ARSON', 'BOMB']):
            return SEVERITY_HIGH
        else:
            return SEVERITY_MEDIUM
        
    if (primary_type == 'INTERFERENCE WITH PUBLIC OFFICER'):
        if str_contains_any_substr(
            description, ['OBSTRUCT']):
            return SEVERITY_HIGH
        else:
            return SEVERITY_LOW
        
    if (primary_type == 'STALKING'):
        if str_contains_any_substr(
            description, ['AGG']):
            return SEVERITY_HIGH
        else:
            return SEVERITY_LOW
        
    if (primary_type == 'SEX OFFENSE'):
        if str_contains_any_substr(
            description, ['CRIM', 'CHILD', 'INDECEN']):
            return SEVERITY_HIGH
        else:
            return SEVERITY_LOW
        
    if (primary_type == 'LIQUOR LAW VIOLATION'):
        if str_contains_any_substr(
            description, ['MINOR']):
            return SEVERITY_HIGH
        else:
            return SEVERITY_LOW
    
    if (primary_type == 'HOMICIDE') or \
        (primary_type == 'CRIM SEXUAL ASSAULT') or \
        (primary_type == 'ARSON') or \
        (primary_type == 'OFFENSE INVOLVING CHILDREN') or \
        (primary_type == 'PROSTITUTION') or \
        (primary_type == 'KIDNAPPING') or \
        (primary_type == 'HUMAN TRAFFICKING') or \
        (primary_type == 'NON-CRIMINAL (SUBJECT SPECIFIED)'):
        return SEVERITY_HIGH

    if (primary_type == 'INTIMIDATION') or \
        (primary_type == 'OTHER NARCOTIC VIOLATION') or \
        (primary_type == 'OBSCENITY') or \
        (primary_type == 'PUBLIC INDECENCY'):
        return SEVERITY_MEDIUM

    if (primary_type == 'DECEPTIVE PRACTICE') or \
        (primary_type == 'CRIMINAL DAMAGE') or \
        (primary_type == 'NON-CRIMINAL') or \
        (primary_type == 'GAMBLING'):
        return SEVERITY_LOW

    return None


def reset_tables():
    """Reset DB tables."""
    BASE.metadata.drop_all(bind=ENGINE)
    BASE.metadata.create_all(bind=ENGINE)

def create_indexes():
    SESSION.execute(text("CREATE INDEX incident_block_idx ON incident (blockid);"))
    SESSION.execute(text("CREATE INDEX incident_city_idx ON incident (cityid);"))
    SESSION.execute(text("CREATE INDEX incident_cityblock_idx ON incident (cityid, blockid);"))
    SESSION.execute(text("CREATE INDEX incident_date_idx ON incident (month, year);"))
    SESSION.execute(text("CREATE INDEX incident_dow_idx ON incident (dow);"))
    SESSION.execute(text("CREATE INDEX incident_time_idx ON incident (hour);"))
    SESSION.execute(text("CREATE INDEX incident_crimetype_idx ON incident (crimetypeid);"))
    SESSION.execute(text("CREATE INDEX incident_locdesc_idx ON incident (locdescid);"))
    SESSION.execute(text("CREATE INDEX crimetype_primary_idx ON crimetype (primarytype);"))
    SESSION.execute(text("CREATE INDEX crimetype_description_idx ON crimetype (description);"))
    SESSION.execute(text("CREATE INDEX crimetype_category_idx ON crimetype (category);"))
    SESSION.execute(text("CREATE INDEX locdesc_description_idx ON locdesctype (description);"))
    SESSION.execute(text("CREATE INDEX zipcodegeom_zipcode_idx ON zipcodegeom (zipcode);"))
    SESSION.execute(text("CREATE INDEX city_city_idx ON city (city);"))
    SESSION.execute(text("CREATE INDEX city_state_idx ON city (state);"))
    SESSION.execute(text("CREATE INDEX city_country_idx ON city (country);"))
    SESSION.commit()

def add_formatted_data(csv_file_path, table_type):
    tables = {
        "city": ["city", "state", "country", "location"],
        "block": ["cityid", "shape", "population"],
        "zipcodegeom": ["cityid", "zipcode", "shape"],
        "incident": ["crimetypeid", "locdescid", "cityid", "blockid", "location", "datetime", "hour", "dow", "month", "year"],
        "crimetype": ["category", "primarytype", "description", "severity"],
        "locdesctype": ["description"]
    }
    with open(csv_file_path, 'r') as f:
        RAW_CONN = create_engine(DB_URI).raw_connection()
        cursor = RAW_CONN.cursor()
        cmd = """COPY {}({}) FROM STDIN DELIMITER ',' CSV HEADER;"""
        cmd = cmd.format(table_type, ",".join(tables[table_type]))
        cursor.copy_expert(cmd, f)
        RAW_CONN.commit()

def find_crimetypeid(x):
    for k in crimetype_dict:
        if crimetype_dict[k] == x:
            return k
    return None

def find_loctypeid(x):
    for k in loctype_dict:
        if loctype_dict[k] == x:
            return k
    return None

def find_blockid(x):
    geom = wkt.loads(x)
    for k in block_dict:
        if block_dict[k].contains(geom):
            return k
    return None


reset_tables()
create_indexes()


pd.DataFrame([["CHICAGO", "ILLINOIS", "UNITED STATES OF AMERICA", "POINT(41.8781 -87.6298)"]], columns=["city", "state", "country", "location"]).to_csv("cities.csv", index=False)
add_formatted_data("cities.csv", "city")
print("city")


cityid = SESSION.query(City).filter(City.location == "POINT(41.8781 -87.6298)").one().id


with open("boundaries.json", "r") as fp:
    boundaries = json.load(fp)["features"]
with open("boundaries_tracts.json", "r") as fp:
    boundaries_tracts = json.load(fp)["features"]
pops = pd.read_csv("populations.csv")
popu = {}
for shape in boundaries:
    if shape["properties"]["tractce10"] not in popu:
        popu[shape["properties"]["tractce10"]] = 0
    try:
        popu[shape["properties"]["tractce10"]] += int(pops.loc[pops["CENSUS BLOCK FULL"]==int(shape["properties"]["geoid10"]),"TOTAL POPULATION"].values[0])
    except:
        pass
shapes = []
for shape in boundaries_tracts:
    str_poly = "MULTIPOLYGON("
    for ind1, i0 in enumerate(shape["geometry"]["coordinates"]):
        if ind1 > 0:
            str_poly += ","
        str_poly += "("
        for ind, i1 in enumerate(i0):
            if ind > 0:
                str_poly += ","    
            str_poly += "("+",".join(["{} {}".format(j[0], j[1]) for j in i1])+")"
        str_poly += ")"
    str_poly += ")"
    shapes.append([cityid, str_poly, popu[shape["properties"]["tractce10"]]])
pd.DataFrame(shapes, columns=["cityid", "shape", "population"]).to_csv("blocks.csv", index=False)
add_formatted_data("blocks.csv", "block")
print("blocks")


with open("zipcodes.json", "r") as fp:
    zipcodes = json.load(fp)["features"]
rows = []
for i, zc in enumerate(zipcodes):
    if type(zc["geometry"]["coordinates"][0][0][0]) == list:
        str_poly = "MULTIPOLYGON("
        for ind1, i0 in enumerate(zc["geometry"]["coordinates"]):
            if ind1 > 0:
                str_poly += ","
            str_poly += "("
            for ind, i1 in enumerate(i0):
                if ind > 0:
                    str_poly += ","
                str_poly += "("+",".join(["{} {}".format(j[0], j[1]) for j in i1])+")"
            str_poly += ")"
        str_poly += ")"
        rows.append([cityid, zc["properties"]["ZCTA5CE10"], str_poly])
    else:
        str_poly = "MULTIPOLYGON("
        for ind, i0 in enumerate(zc["geometry"]["coordinates"]):
            if ind > 0:
                str_poly += ","
            str_poly += "("    
            str_poly += "("+",".join(["{} {}".format(j[0], j[1]) for j in i0])+")"
            str_poly += ")"
        str_poly += ")"
        rows.append([cityid, zc["properties"]["ZCTA5CE10"], str_poly])
pd.DataFrame(rows, columns=["cityid", "zipcode", "shape"]).to_csv("zipcodes.csv", index=False)
add_formatted_data("zipcodes.csv", "zipcodegeom")
print("zipcodes")
    

incidents = pd.read_csv("crimes.csv")
incidents.loc[:,"category"] = incidents[["Primary Type", "Description"]].apply(lambda x: " | ".join(x), axis=1)
incidents = incidents.drop_duplicates(subset="category")
incidents.loc[:,"primarytype"] = incidents["Primary Type"]
incidents.loc[:,"description"] = incidents["Description"]
incidents.loc[:,"severity"] = incidents["category"].apply(lambda x: crime_severity(x.split(" | ")))
incidents = incidents.loc[:,["category", "primarytype", "description", "severity"]]
incidents = incidents.dropna()
incidents.to_csv("crimetypes.csv", index=False)
add_formatted_data("crimetypes.csv", "crimetype")
print("crimetypes")


incidents = pd.read_csv("crimes.csv")
incidents.loc[:,"description"] = incidents["Location Description"]
incidents = incidents.drop_duplicates(subset="description")
incidents = incidents.loc[:,["description"]]
incidents = incidents.dropna()
incidents.to_csv("locdesc.csv", index=False)
add_formatted_data("locdesc.csv", "locdesctype")
print("locdesc")


incidents = pd.read_csv("crimes.csv")
incidents.loc[:,"location"] = incidents[["Longitude", "Latitude"]].apply(lambda x: "POINT({})".format(" ".join([str(y) for y in x])), axis=1)
incidents.loc[:,"crimefull"] = incidents[["Primary Type", "Description"]].apply(lambda x: " | ".join(x), axis=1)
crimetypes = SESSION.query(CrimeType).all()
crimetype_dict = {}
for c in crimetypes:
    crimetype_dict[c.id] = c.category
incidents.loc[:,"crimetypeid"] = incidents["crimefull"].apply(find_crimetypeid)
loctypes = SESSION.query(LocationDescriptionType).all()
loctype_dict = {}
for c in loctypes:
    loctype_dict[c.id] = c.description
incidents.loc[:,"locdescid"] = incidents["Location Description"].apply(find_loctypeid)
blocks = SESSION.query(Blocks).all()
block_dict = {}
for b in blocks:
    block_dict[b.id] = wkb.loads(b.shape.data.tobytes())
incidents.loc[:,"blockid"] = incidents["location"].apply(find_blockid)
incidents.loc[:, "datetime"] = pd.to_datetime(incidents["Date"])
incidents.loc[:, "hour"] = incidents["datetime"].apply(lambda x: x.hour)
incidents.loc[:, "dow"] = incidents["datetime"].apply(lambda x: x.weekday())
incidents.loc[:, "month"] = incidents["datetime"].apply(lambda x: x.month)
incidents.loc[:, "year"] = incidents["datetime"].apply(lambda x: x.year)
incidents.loc[:, "cityid"] = cityid
incidents = incidents.loc[:,["crimetypeid", "locdescid", "cityid", "blockid", "location", "datetime", "hour", "dow", "month", "year"]]
incidents = incidents.dropna()
incidents.loc[:,"crimetypeid"] = incidents.loc[:,"crimetypeid"].astype(int)
incidents.loc[:,"locdescid"] = incidents.loc[:,"locdescid"].astype(int)
incidents.loc[:,"cityid"] = incidents.loc[:,"cityid"].astype(int)
incidents.loc[:,"blockid"] = incidents.loc[:,"blockid"].astype(int)
incidents.to_csv("incident.csv", index=False)
print("\tuploading incidents")
add_formatted_data("incident.csv", "incident")
print("incidents")
