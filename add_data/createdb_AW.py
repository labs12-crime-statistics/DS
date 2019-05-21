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
import pandas as pd
from models import *
import json
import datetime


# Connect to DB
DB_URI  = config('DB_URI')
ENGINE  = create_engine(DB_URI)
Session = sessionmaker(bind=ENGINE)
SESSION = Session()

block_dict = {}
loctype_dict = {}
crimetype_dict = {}
locgroup_dict = {}
crimeppo_dict = {}
crimevio_dict = {}


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
    SESSION.execute(text("CREATE INDEX crimetype_category_idx ON crimetype (category);"))
    SESSION.execute(text("CREATE INDEX locdesc_description1_idx ON locdesctype (key1);"))
    SESSION.execute(text("CREATE INDEX locdesc_description2_idx ON locdesctype (key1, key2);"))
    SESSION.execute(text("CREATE INDEX locdesc_description3_idx ON locdesctype (key1, key2, key3);"))
    SESSION.execute(text("CREATE INDEX zipcodegeom_zipcode_idx ON zipcodegeom (zipcode);"))
    SESSION.execute(text("CREATE INDEX city_city_idx ON city (city);"))
    SESSION.execute(text("CREATE INDEX city_state_idx ON city (state);"))
    SESSION.execute(text("CREATE INDEX city_country_idx ON city (country);"))
    SESSION.execute(text("CREATE INDEX loc_group_idx ON locdestype (locgroup);"))
    SESSION.execute(text("CREATE INDEX crime_ppo_idx ON crimetype (ppo);"))
    SESSION.execute(text("CREATE INDEX crime_viol_idx ON crimetype (violence);"))
    SESSION.commit()

def add_formatted_data(csv_file_path, table_type):
    tables = {
        "city": ["city", "state", "country", "location"],
        "block": ["cityid", "shape", "population"],
        "zipcodegeom": ["cityid", "zipcode", "shape"],
        "incident": ["crimetypeid", "locdescid", "cityid", "blockid", "location", "datetime", "hour", "dow", "month", "year", "locgroup", "ppo", "violence"],
        "crimetype": ["category", "ppo", "violence"],
        "locdesctype": ["key1", "key2", "key3", "locgroup"]
    }
    with open(csv_file_path, 'r') as f:
        RAW_CONN = create_engine(DB_URI).raw_connection()
        cursor = RAW_CONN.cursor()
        cmd = """COPY {}({}) FROM STDIN DELIMITER ',' CSV HEADER;"""
        cmd = cmd.format(table_type, ",".join(tables[table_type]))
        cursor.copy_expert(cmd, f)
        RAW_CONN.commit()

def find_crimetypeid(x):
    return crimetype_dict.get(tuple(CRIMETYPE_DICT.get(x, ("OTHER OFFENSE"))))

def find_loctypeid(x):
    return loctype_dict.get(tuple(LOCATION_DICT.get(x, ("OTHER", "OTHER", "OTHER"))))

def find_blockid(x):
    geom = wkt.loads(x)
    for k in block_dict:
        if block_dict[k].contains(geom):
            return k
    return None

location_cat = [
    ["INDOOR", "RESIDENTIAL", "APARTMENT"],
    ["INDOOR", "RESIDENTIAL", "HOUSE"],
    ["INDOOR", "RESIDENTIAL", "OTHER"],
    ["INDOOR", "COMMERCIAL", "HOTEL/MOTEL"],
    ["INDOOR", "COMMERCIAL", "STORE"],
    ["INDOOR", "COMMERCIAL", "RESTAURANT"],
    ["INDOOR", "COMMERCIAL", "INDUSTRIAL"],
    ["INDOOR", "OTHER", "OTHER"],
    ["OUTDOOR", "PUBLIC", "ROAD"],
    ["OUTDOOR", "PUBLIC", "STREET"],
    ["OUTDOOR", "PUBLIC", "PARK"],
    ["OUTDOOR", "PUBLIC", "TRANSIT"],
    ["OUTDOOR", "PUBLIC", "RELIGIOUS"],
    ["OUTDOOR", "PUBLIC", "OTHER"],
    ["OUTDOOR", "PRIVATE", "NONCOMMERCIAL"],
    ["OUTDOOR", "PRIVATE", "COMMERCIAL"],
    ["OTHER", "OTHER", "OTHER"]
]

rev_location_dict = {
    ("INDOOR", "RESIDENTIAL", "APARTMENT") : ["APARTMENT/CONDO COMMON LAUNDRY ROOM", "PROJECT/TENEMENT/PUBLIC HOUSING", "MULTI-UNIT DWELLING (APARTMENT, DUPLEX, ETC)", "CHA PLAY LOT", "CHA LOBBY", "CHA BREEZEWAY", "CHA ELEVATOR", "CHA PARKING LOT", "CHA STAIRWELL", "APARTMENT", "CHA APARTMENT", "CHA HALLWAY/STAIRWELL/ELEVATOR", "CHA GROUNDS", "CHA HALLWAY"],
    ("INDOOR", "RESIDENTIAL", "HOUSE") : ["SINGLE RESIDENCE OCCUPANCY (SRO'S) LOCATIONS", "CONDOMINIUM/TOWNHOUSE", "SINGLE FAMILY DWELLING", "HOUSE"],
    ("INDOOR", "RESIDENTIAL", "OTHER") : ["ELEVATOR", "DRIVEWAY", "TRANSIENT ENCAMPMENT", "STAIRWELL*", "TOOL SHED*", "FRAT HOUSE/SORORITY/DORMITORY", "MOBILE HOME/TRAILERS/CONSTRUCTION TRAILERS/RV'S/MOTORHOME", "GROUP HOME", "PATIO*", "MAIL BOX", "YARD (RESIDENTIAL/BUSINESS)", "PORCH, RESIDENTIAL", "BALCONY*", "OTHER RESIDENCE", "TRAILER", "VESTIBULE", "GARAGE", "BASEMENT", "STAIRWELL", "HALLWAY", "PORCH", "YARD", "DRIVEWAY - RESIDENTIAL", "RESIDENCE", "RESIDENCE PORCH/HALLWAY", "RESIDENTIAL YARD (FRONT/BACK)"],
    ("INDOOR", "COMMERCIAL", "HOTEL/MOTEL") : ["MOTEL", "HOTEL", "SHORT-TERM VACATION RENTAL", "HOTEL/MOTEL"],
    ("INDOOR", "COMMERCIAL", "STORE") : ["LIQUOR STORE", "CREDIT UNION", "DRUG STORE", "DEPARTMENT STORE", "BANK", "BOOK STORE", "ELECTRONICS STORE (IE:RADIO SHACK, ETC.)", "FURNITURE STORE", "BANK DROP BOX/MONEY DROP-OUTSIDE OF BANK*", "DRIVE THRU BANKING (WINDOW)*", "OPTICAL OFFICE INSIDE STORE OR SUPERMARKET*", "BANKING INSIDE MARKET-STORE *", "DRIVE THRU*", "EQUIPMENT RENTAL", "RECORD-CD MUSIC/COMPUTER GAME STORE", "METHADONE CLINIC", "SEX ORIENTED/BOOK STORE", "COMPUTER SERVICES/REPAIRS/SALES", "VIDEO RENTAL STORE", "DIY CENTER (LOWE'S,HOME DEPOT,OSH,CONTRACTORS WAREHOUSE)", "TATTOO PARLOR*", "BEAUTY SUPPLY STORE", "MEMBERSHIP STORE (COSTCO,SAMS CLUB)*", "VISION CARE FACILITY*", "MEDICAL MARIJUANA FACILITIES/BUSINESSES", "NURSERY/FLOWER SHOP", "AUTO SUPPLY STORE*", "CLEANER/LAUNDROMAT", "GUN/SPORTING GOODS", "LAUNDROMAT", "PET STORE", "THEATRE/MOVIE", "TOBACCO SHOP", "NAIL SALON", "AUTO REPAIR SHOP", "HARDWARE/BUILDING SUPPLY", "BEAUTY/BARBER SHOP", "JEWELRY STORE", "CELL PHONE STORE", "CLOTHING STORE", "MINI-MART", "OTHER STORE", "LAUNDRY ROOM", "CLEANERS/LAUNDROMAT", "BARBER SHOP/BEAUTY SALON", "LIVERY STAND OFFICE", "GARAGE/AUTO REPAIR", "RETAIL STORE", "NEWSSTAND", "BARBERSHOP", "SAVINGS AND LOAN", "APPLIANCE STORE", "CLEANING STORE", "TAVERN/LIQUOR STORE", "SMALL RETAIL STORE", "GROCERY FOOD STORE", "PAWN SHOP", "SURPLUS SURVIVAL STORE", "CONVENIENCE STORE", "SAVINGS & LOAN"],
    ("INDOOR", "COMMERCIAL", "RESTAURANT") : ["COFFEE SHOP (STARBUCKS, COFFEE BEAN, PEET'S, ETC.)", "ENTERTAINMENT/COMEDY CLUB (OTHER)", "BAR/SPORTS BAR (OPEN DAY & NIGHT)", "BAR/COCKTAIL/NIGHTCLUB", "NIGHT CLUB (OPEN EVENINGS ONLY)", "RESTAURANT/FAST FOOD", "CLUB", "TAVERN", "RESTAURANT", "BAR OR TAVERN"],
    ("INDOOR", "COMMERCIAL", "INDUSTRIAL") : ["FACTORY", "WAREHOUSE", "CONSTRUCTION SITE", "ENERGY PLANT/FACILITY", "CHEMICAL STORAGE/MANUFACTURING PLANT", "OIL REFINERY", "GARMENT MANUFACTURER", "MANUFACTURING COMPANY", "FACTORY/MANUFACTURING BUILDING", "LOADING DOCK", "NUCLEAR FACILITY", "WATER FACILITY", "DEPT OF DEFENSE FACILITY"],
    ("INDOOR", "COMMERCIAL", "OFFICE") : ["HIGH-RISE BUILDING", "TELECOMMUNICATION FACILITY/LOCATION", "FINANCE COMPANY", "POST OFFICE", "MEDICAL/DENTAL OFFICES", "OFFICE BUILDING/OFFICE", "OFFICE", "COMMERCIAL / BUSINESS OFFICE"],
    ("INDOOR", "OTHER", "OTHER") : ["HOSPITAL", "PARKING LOT",  "FIRE STATION",  "CAR WASH", "GAS STATION", "LIBRARY", "HANDBALL COURTS",  "VETERINARIAN/ANIMAL HOSPITAL", "TRANSITIONAL HOUSING/HALFWAY HOUSE", "SEX ORIENTED/BOOK STORE/STRIP CLUB/GENTLEMAN'S CLUB", "STUDIO (FILM/PHOTOGRAPHIC/MUSIC)", "VEHICLE STORAGE LOT (CARS, TRUCKS, RV'S, BOATS, TRAILERS, ETC.)",  "AUTO DEALERSHIP (CHEVY, FORD, BMW, MERCEDES, ETC.)", "ABORTION CLINIC/ABORTION FACILITY*", "ABATEMENT LOCATION", "SEWAGE FACILITY/PIPE", "HOCKEY RINK/ICE HOCKEY",  "FOSTER HOME BOYS OR GIRLS*", "MORTUARY", "HOSPICE", "DAY CARE/CHILDREN*", "ABANDONED BUILDING ABANDONED HOUSE", "BOWLING ALLEY*", "TRANSPORTATION FACILITY (AIRPORT)", "ARCADE,GAME ROOM/VIDEO GAMES (EXAMPLE CHUCKIE CHEESE)*", "DAY CARE/ADULTS*", "TRADE SCHOOL (MEDICAL-TECHNICAL-BUSINESS)*", "CONVENTION CENTER", "SKATING RINK*", "AUTO SALES LOT", "OTHER PREMISE", "GARAGE/CARPORT", "POLICE FACILITY", "PRIVATE SCHOOL/PRESCHOOL", "STORAGE SHED", "BUS, SCHOOL, CHURCH", "MUSEUM", "POOL-PUBLIC/OUTDOOR OR INDOOR*", "DETENTION/JAIL FACILITY", "RECYCLING CENTER", "SHOPPING MALL (COMMON AREA)", "PUBLIC STORAGE", "JUNIOR HIGH SCHOOL", "COLISEUM", "ELEMENTARY SCHOOL", "TOW YARD*", "NURSING/CONVALESCENT/RETIREMENT HOME", "SPECIALTY SCHOOL/OTHER", "GOVERNMENT FACILITY (FEDERAL,STATE, COUNTY & CITY)", "MASSAGE PARLOR", "COLLEGE/JUNIOR COLLEGE/UNIVERSITY", "HIGH SCHOOL", "HEALTH SPA/GYM", "PARKING UNDERGROUND/BUILDING", "PHARMACY INSIDE STORE OR SUPERMARKET*", "OTHER BUSINESS", "MARKET", "BANQUET HALL", "ROOMING HOUSE", "POOLROOM", "GOVERNMENT BUILDING", "PUBLIC HIGH SCHOOL", "NURSING HOME", "GAS STATION DRIVE/PROP.", "FUNERAL PARLOR", "SCHOOL YARD", "JUNK YARD/GARBAGE DUMP", "PUBLIC GRAMMAR SCHOOL", "YMCA", "HORSE STABLE", "FARM", "KENNEL", "COACH HOUSE", "COUNTY JAIL", "GANGWAY", "DUMPSTER", "AIRPORT TERMINAL MEZZANINE - NON-SECURE AREA", "AIRPORT TRANSPORTATION SYSTEM (ATS)", "BOWLING ALLEY", "AIRPORT PARKING LOT", "AIRPORT TERMINAL LOWER LEVEL - SECURE AREA", "AIRPORT EXTERIOR - SECURE AREA", "MOVIE HOUSE/THEATER", "COLLEGE/UNIVERSITY RESIDENCE HALL", "FEDERAL BUILDING", "SCHOOL, PRIVATE, GROUNDS", "CTA GARAGE / OTHER PROPERTY", "COLLEGE/UNIVERSITY GROUNDS", "AIRPORT EXTERIOR - NON-SECURE AREA", "JAIL / LOCK-UP FACILITY", "ABANDONED BUILDING", "SCHOOL, PUBLIC, GROUNDS", "AIRPORT TERMINAL UPPER LEVEL - SECURE AREA", "CHA PARKING LOT/GROUNDS", "OTHER RAILROAD PROP / TRAIN DEPOT", "NURSING HOME/RETIREMENT HOME", "SCHOOL, PRIVATE, BUILDING", "AIRPORT VENDING ESTABLISHMENT", "SPORTS ARENA/STADIUM", "AIRPORT TERMINAL UPPER LEVEL - NON-SECURE AREA", "CURRENCY EXCHANGE", "ANIMAL HOSPITAL", "AIRPORT/AIRCRAFT", "ATHLETIC CLUB", "MEDICAL/DENTAL OFFICE", "POLICE FACILITY/VEH PARKING LOT", "PARKING LOT/GARAGE(NON.RESID.)", "RESIDENCE-GARAGE", "HOSPITAL BUILDING/GROUNDS", "DAY CARE CENTER", "SCHOOL, PUBLIC, BUILDING", "AIRPORT BUILDING NON-TERMINAL - SECURE AREA", "AIRPORT TERMINAL LOWER LEVEL - NON-SECURE AREA", "GOVERNMENT BUILDING/PROPERTY", "AUTO / BOAT / RV DEALERSHIP", "VACANT LOT/LAND", "POOL ROOM"],
    ("OUTDOOR", "PUBLIC", "ROAD") : ["UNDERPASS/BRIDGE*", "FREEWAY", "EXPRESSWAY EMBANKMENT", "BRIDGE", "HIGHWAY/EXPRESSWAY"],
    ("OUTDOOR", "PUBLIC", "STREET") : ["STREET", "ALLEY", "SIDEWALK", "TUNNEL", "SEWER", "PEDESTRIAN OVERCROSSING"],
    ("OUTDOOR", "PUBLIC", "PARK") : ["MUSCLE BEACH", "DAM/RESERVOIR", "CULTURAL SIGNIFICANCE/MONUMENT", "CEMETARY*", "RIVER BED*", "BEACH", "SLIPS/DOCK/MARINA/BOAT", "OTHER/OUTSIDE", "LAGOON", "LAKE", "RIVER BANK", "RIVER", "PRAIRIE", "FOREST PRESERVE", "CEMETARY", "PARK PROPERTY", "LAKEFRONT/WATERFRONT/RIVERBANK", "WOODED AREA"],
    ("OUTDOOR", "PUBLIC", "TRANSIT") : ["MTA - BLUE LINE - GRAND/LATTC", "MTA - PURPLE LINE - WESTLAKE/MACARTHUR PARK", "MTA - GOLD LINE - SOUTHWEST MUSEUM", "MTA - SILVER LINE - ROSECRANS", "MTA - ORANGE LINE - SHERMAN WAY", "MTA - SILVER LINE - 37TH ST/USC", "MTA - GOLD LINE - LINCOLN/CYPRESS", "MTA - SILVER LINE - PACIFIC COAST HWY", "MTA - PURPLE LINE - WILSHIRE/NORMANDIE", "MTA - ORANGE LINE - VAN NUYS", "MTA - ORANGE LINE - LAUREL CANYON", "MTA - ORANGE LINE - DE SOTO", "MTA - PURPLE LINE - 7TH AND METRO CENTER", "MTA - SILVER LINE - CAL STATE LA", "MTA - ORANGE LINE - ROSCOE", "MTA - ORANGE LINE - NORDHOFF", "MTA - ORANGE LINE - WOODMAN", "MTA - SILVER LINE - SLAUSON", "MTA - SILVER LINE - DOWNTOWN STREET STOPS", "MTA - SILVER LINE - MANCHESTER", "MTA - ORANGE LINE - WOODLEY", "MTA - ORANGE LINE - PIERCE COLLEGE", "HARBOR FRWY STATION (NOT LINE SPECIFIC)", "MTA - SILVER LINE - SAN PEDRO STREET STOPS", "MTA - RED LINE - NORTH HOLLYWOOD", "TRAIN, OTHER THAN MTA (ALSO QUERY 809/810/811)", "MTA - ORANGE LINE - CANOGA", "MTA - EXPO LINE - LATTC/ORTHO INSTITUTE", "MTA - PURPLE LINE - WILSHIRE/VERMONT", "MTA - BLUE LINE - VERNON", "MTA - EXPO LINE - JEFFERSON/USC", "MTA - BLUE LINE - WASHINGTON", "MTA - GOLD LINE - MARIACHI PLAZA", "MTA - RED LINE - HOLLYWOOD/WESTERN", "MTA - EXPO LINE - EXPO/BUNDY", "MTA - EXPO LINE - WESTWOOD/RANCHO PARK", "MTA - ORANGE LINE - SEPULVEDA", "MTA - ORANGE LINE - TAMPA", "MTA - GOLD LINE - HIGHLAND PARK", "MTA - ORANGE LINE - CHATSWORTH", "MTA - GREEN LINE - HARBOR FWY", "MTA - SILVER LINE - HARBOR FWY", "MTA - BLUE LINE - SAN PEDRO", "MTA - RED LINE - UNIVERSAL CITY/STUDIO CITY", "MTA - EXPO LINE - LA CIENEGA/JEFFERSON", "MTA - SILVER LINE - HARBOR GATEWAY TRANSIT CTR", "MTA - SILVER LINE - UNION STATION", "MTA - EXPO LINE - PICO", "MTA - GOLD LINE - LITTLE TOKYO/ARTS DISTRICT", "MTA - RED LINE - CIVIC CENTER/GRAND PARK", "MTA - GOLD LINE - CHINATOWN", "MTA - PURPLE LINE - CIVIC CENTER/GRAND PARK", "MTA - GOLD LINE - UNION STATION", "MTA - EXPO LINE - EXPO/LA BREA", "MTA - EXPO LINE - PALMS", "MTA - RED LINE - VERMONT/SUNSET", "MTA - GREEN LINE - AVALON", "LA UNION STATION (NOT LINE SPECIFIC)", "MTA - RED LINE - UNION STATION", "MTA - EXPO LINE - EXPO/VERMONT", "BUS-CHARTER/PRIVATE", "MTA - ORANGE LINE - RESEDA", "BUS DEPOT/TERMINAL, OTHER THAN MTA", "MTA - PURPLE LINE - WILSHIRE/WESTERN", "MTA - RED LINE - WESTLAKE/MACARTHUR PARK", "MTA - BLUE LINE - PICO", "MTA - BLUE LINE - 7TH AND METRO CENTER", "MTA - PURPLE LINE - PERSHING SQUARE", "MTA - RED LINE - PERSHING SQUARE", "MTA - PURPLE LINE - UNION STATION", "MTA - EXPO LINE - 7TH AND METRO CENTER", "MTA - EXPO LINE - EXPO PARK/USC", "MTA - RED LINE - HOLLYWOOD/HIGHLAND", "MTA - BLUE LINE - 103RD/WATTS TOWERS", "MTA - RED LINE - WILSHIRE/VERMONT", "MTA - EXPO LINE - EXPO/WESTERN", "MTA - GOLD LINE - INDIANA", "MTA - RED LINE - HOLLYWOOD/VINE", "MTA - GOLD LINE - HERITAGE SQ", "MTA - EXPO LINE - EXPO/CRENSHAW", "TERMINAL, OTHER THAN MTA", "MTA - RED LINE - VERMONT/SANTA MONICA", "MTA - GOLD LINE - SOTO", "MTA - ORANGE LINE - BALBOA", "MTA - ORANGE LINE - NORTH HOLLYWOOD", "MTA - EXPO LINE - FARMDALE", "MTA - EXPO LINE - EXPO/SEPULVEDA", "7TH AND METRO CENTER (NOT LINE SPECIFIC)", "MTA - RED LINE - 7TH AND METRO CENTER", "MTA - RED LINE - VERMONT/BEVERLY", "MTA - GOLD LINE - PICO/ALISO", "TRAIN DEPOT/TERMINAL, OTHER THAN MTA", "GREEN LINE (I-105 FWY LEVEL TRAIN)", "TRAM/STREETCAR(BOXLIKE WAG ON RAILS)*", "ORANGE LINE PARKING LOT", "OTHER INTERSTATE, CHARTER BUS", "TRAIN TRACKS", "BLUE LINE (ABOVE GROUND SURFACE TRAIN)", "AMTRAK TRAIN", "BUS STOP/LAYOVER (ALSO QUERY 124)", "REDLINE SUBWAY TUNNEL", "GREYHOUND OR INTERSTATE BUS", "REDLINE SUBWAY RAIL CAR (INSIDE TRAIN)", "REDLINE SUBWAY MEZZANINE", "REDLINE ENTRANCE/EXIT", "REDLINE SUBWAY PLATFORM", "REDLINE (SUBWAY TRAIN)", "TRAIN", "MTA PROPERTY OR PARKING LOT", "CHARTER BUS AND PRIVATELY OWNED BUS", "BUS STOP OR LAYOVER", "BUS DEPOT", "MUNICIPAL BUS LINE INCLUDES LADOT/DASH", "OTHER RR TRAIN (UNION PAC, SANTE FE ETC", "TRAIN DEPOT", "TERMINAL", "TAXI", "MTA - GREEN LINE - AVIATION/LAX", "MTA BUS", "METROLINK TRAIN", "BUS STOP", "CTA PROPERTY", "CTA \"L\" TRAIN", "TAXI CAB", "CTA \"L\" PLATFORM", "RAILROAD PROPERTY", "CTA BUS STOP", "CTA TRAIN", "CTA PLATFORM", "CTA BUS", "CTA STATION", "TAXICAB", "VEHICLE - OTHER RIDE SERVICE", "VEHICLE - OTHER RIDE SHARE SERVICE (E.G., UBER, LYFT)"],
    ("OUTDOOR", "PUBLIC", "RELIGIOUS") : ["MOSQUE*", "OTHER PLACE OF WORSHIP", "SYNAGOGUE/TEMPLE", "CHURCH/CHAPEL (CHANGED 03-03 FROM CHURCH/TEMPLE)", "MISSIONS/SHELTERS", "CHURCH", "CHURCH PROPERTY", "CHURCH/SYNAGOGUE/PLACE OF WORSHIP"],
    ("OUTDOOR", "PUBLIC", "OTHER") : ["PAY PHONE", "PUBLIC RESTROOM(INDOORS-INSIDE)", "PUBLIC RESTROOM/OUTSIDE*", "AUTOMATED TELLER MACHINE (ATM)", "COIN OPERATED MACHINE", "BASKETBALL COURTS",  "SKATEBOARD FACILITY/SKATEBOARD PARK*", "ATM (AUTOMATIC TELLER MACHINE)", "AMUSEMENT PARK*", "GOLF COURSE*"],
    ("OUTDOOR", "PRIVATE", "NONCOMMERCIAL") : ["VEHICLE, PASSENGER/TRUCK", "LIVERY AUTO", "VEHICLE NON-COMMERCIAL", "BOAT/WATERCRAFT", "AUTO"],
    ("OUTDOOR", "PRIVATE", "COMMERCIAL") : ["TRUCK, COMMERICAL", "DELIVERY SERVICE (FED EX, UPS, COURIERS,COURIER SERVICE)*", "TRUCKING TERMINAL", "TRUCK", "DELIVERY TRUCK", "OTHER COMMERCIAL TRANSPORTATION", "VEHICLE-COMMERCIAL", "VEHICLE - DELIVERY TRUCK", "CTA TRACKS - RIGHT OF WAY", "VEHICLE-COMMERCIAL - TROLLEY BUS", "VEHICLE-COMMERCIAL - ENTERTAINMENT/PARTY BUS"],
    ("OTHER", "OTHER", "OTHER") : ["VACANT LOT", "AIRCRAFT", "THE BEVERLY CONNECTION", "THE BEVERLY CENTER", "TACTICAL SIGNIFICANCE", "ESCALATOR*", "RETIRED (DUPLICATE) DO NOT USE THIS CODE", "TRASH CAN/TRASH DUMPSTER", "HORSE RACING/SANTA ANITA PARK*", "SPORTS VENUE, OTHER", "VALET", "MASS GATHERING LOCATION", "WEBSITE", "SPORTS ARENA", "STAPLES CENTER *", "CHECK CASHING*", "TV/RADIO/APPLIANCE", "DODGER STADIUM", "THE GROVE", "SWAP MEET", "CYBERSPACE", "OTHER", None]
}


LOCATION_DICT = {}
for k in rev_location_dict:
    for i in rev_location_dict[k]:
        LOCATION_DICT[i] = list(k)


location_group = [
    ["RESIDENTIAL"],
    ["COMMERCIAL"],
    ["STREET"],
    ["PERSONAL_VEHICLE"],
    ["OTHER"]
]

rev_location_group_dict = {
    ("RESIDENTIAL") : [["INDOOR", "RESIDENTIAL", "APARTMENT"], ["INDOOR", "RESIDENTIAL", "HOUSE"],["INDOOR", "RESIDENTIAL", "OTHER"]],
    ("COMMERCIAL") : [["INDOOR", "COMMERCIAL", "HOTEL/MOTEL"], ["INDOOR", "COMMERCIAL", "STORE"], ["INDOOR", "COMMERCIAL", "RESTAURANT"], ["INDOOR", "COMMERCIAL", "INDUSTRIAL"]],
    ("STREET") : [["OUTDOOR", "PUBLIC", "STREET"]],
    ("PERSONAL_VEHICLE") : [["OUTDOOR", "PRIVATE", "NONCOMMERCIAL"]],
    ("OTHER") : [["INDOOR", "OTHER", "OTHER"], ["OUTDOOR", "PUBLIC", "ROAD"], ["OUTDOOR", "PUBLIC", "PARK"], ["OUTDOOR", "PUBLIC", "TRANSIT"], ["OUTDOOR", "PUBLIC", "RELIGIOUS"], ["OUTDOOR", "PUBLIC", "OTHER"], ["OUTDOOR", "PRIVATE", "COMMERCIAL"], ["OTHER", "OTHER", "OTHER"]]
}

LOCATION_GROUP_DICT = {}
for k in rev_location_group_dict:
    for i in rev_location_group_dict[k]:
        LOCATION_GROUP_DICT[i] = list(k)


crimetype_cat = [
    ["ARSON"],
    ["ASSAULT"],
    ["BATTERY"],
    ["BURGLARY"],
    ["CONCEALED CARRY LICENSE VIOLATION"],
    ["CRIMINAL SEXUAL ASSAULT"],
    ["CRIMINAL DAMAGE"],
    ["CRIMINAL TRESPASS"],
    ["DECEPTIVE PRACTICE"],
    ["DOMESTIC VIOLENCE"],
    ["GAMBLING"],
    ["HOMICIDE"],
    ["HUMAN TRAFFICKING"],
    ["INTERFERENCE WITH PUBLIC OFFICER"],
    ["INTIMIDATION"],
    ["KIDNAPPING"],
    ["LIQUOR LAW VIOLATION"],
    ["MOTOR VEHICLE THEFT"],
    ["NARCOTICS"],
    ["NON-CRIMINAL"],
    ["OBSCENITY"],
    ["OFFENSE INVOLVING CHILDREN"],
    ["OTHER NARCOTIC VIOLATION"],
    ["OTHER OFFENSE"],
    ["PROSTITUTION"],
    ["PUBLIC INDECENCY"],
    ["PUBLIC PEACE VIOLATION"],
    ["RITUALISM"],
    ["ROBBERY"],
    ["SEX OFFENSE"],
    ["STALKING"],
    ["THEFT"],
    ["WEAPONS VIOLATION"]
]

rev_crimetype_dict = {
    ("ARSON"): ["ARSON"],
    ("ASSAULT"): ["OTHER ASSAULT", "DRUNK ROLL", "DRUNK ROLL - ATTEMPT", "ASSAULT WITH DEADLY WEAPON ON POLICE OFFICER", "ASSAULT WITH DEADLY WEAPON, AGGRAVATED ASSAULT", "ASSAULT"],
    ("BATTERY"): ["BATTERY - SIMPLE ASSAULT", "BATTERY ON A FIREFIGHTER", "BATTERY POLICE (SIMPLE)", "BATTERY WITH SEXUAL CONTACT", "BATTERY"],
    ("BURGLARY"): ["BURGLARY", "BURGLARY FROM VEHICLE", "BURGLARY FROM VEHICLE, ATTEMPTED", "BURGLARY, ATTEMPTED", "BURGLARY"],
    ("CRIMINAL SEXUAL ASSAULT"): ["RAPE, ATTEMPTED", "RAPE, FORCIBLE", "CHILD PORNOGRAPHY", "CRIM SEXUAL ASSAULT", "INTIMATE PARTNER - AGGRAVATED ASSAULT"],
    ("CRIMINAL DAMAGE"): ["VANDALISM - FELONY ($400 & OVER, ALL CHURCH VANDALISMS)", "VANDALISM - FELONY ($400 & OVER, ALL CHURCH VANDALISMS) 0114", "VANDALISM - MISDEAMEANOR ($399 OR UNDER)", "TRAIN WRECKING", "THROWING OBJECT AT MOVING VEHICLE", "TELEPHONE PROPERTY - DAMAGE", "RECKLESS DRIVING", "CRIMINAL DAMAGE"],
    ("CRIMINAL TRESPASS"): ["TRESPASSING", "UNAUTHORIZED COMPUTER ACCESS", "DRIVING WITHOUT OWNER CONSENT (DWOC)", "CREDIT CARDS, FRAUD USE ($950 & UNDER", "CREDIT CARDS, FRAUD USE ($950.01 & OVER)", "CRIMINAL TRESPASS"],
    ("DECEPTIVE PRACTICE"): ["EMBEZZLEMENT, GRAND THEFT ($950.01 & OVER)", "EMBEZZLEMENT, PETTY THEFT ($950 & UNDER)", "DOCUMENT FORGERY / STOLEN FELONY", "DOCUMENT WORTHLESS ($200 & UNDER)", "DOCUMENT WORTHLESS ($200.01 & OVER)", "DEFRAUDING INNKEEPER/THEFT OF SERVICES, $400 & UNDER", "DEFRAUDING INNKEEPER/THEFT OF SERVICES, OVER $400", "DECEPTIVE PRACTICE"],
    ("DOMESTIC VIOLENCE"): ["DOMESTIC VIOLENCE"],
    ("GAMBLING"): ["GAMBLING"],
    ("HOMICIDE"): ["MANSLAUGHTER, NEGLIGENT", "LYNCHING", "LYNCHING - ATTEMPTED", "CRIMINAL HOMICIDE", "HOMICIDE"],
    ("HUMAN TRAFFICKING"): ["HUMAN TRAFFICKING - COMMERCIAL SEX ACTS", "HUMAN TRAFFICKING - INVOLUNTARY SERVITUDE", "HUMAN TRAFFICKING"],
    ("INTERFERENCE WITH PUBLIC OFFICER"): ["RESISTING ARREST", "FALSE POLICE REPORT", "FAILURE TO DISPERSE", "FAILURE TO YIELD", "INTERFERENCE WITH PUBLIC OFFICER"],
    ("INTIMIDATION"): ["THREATENING PHONE CALLS/LETTERS", "EXTORTION", "DISRUPT SCHOOL", "CRIMINAL THREATS - NO WEAPON DISPLAYED", "CONTRIBUTING", "COUNTERFEIT", "CONSPIRACY", "BRIBERY", "BRANDISH WEAPON", "BOMB SCARE", "INTIMIDATION"],
    ("KIDNAPPING"): ["KIDNAPPING", "KIDNAPPING - GRAND ATTEMPT", "FALSE IMPRISONMENT", "CHILD STEALING", "KIDNAPPING"],
    ("LIQUOR LAW VIOLATION"): ["LIQUOR LAW VIOLATION"],
    ("MOTOR VEHICLE THEFT"): ["MOTOR VEHICLE THEFT"],
    ("NARCOTICS"): ["DRUGS, TO A MINOR", "NARCOTICS"],
    ("NON-CRIMINAL"): ["NON-CRIMINAL (SUBJECT SPECIFIED)", "NON - CRIMINAL", "NON-CRIMINAL"],
    ("OBSCENITY"): ["OBSCENITY"],
    ("OFFENSE INVOLVING CHILDREN"): ["CRM AGNST CHLD (13 OR UNDER) (14-15 & SUSP 10 YRS OLDER)", "CRM AGNST CHLD (13 OR UNDER) (14-15 & SUSP 10 YRS OLDER)0060", "CHILD ABANDONMENT", "CHILD ABUSE (PHYSICAL) - AGGRAVATED ASSAULT", "CHILD ABUSE (PHYSICAL) - SIMPLE ASSAULT", "CHILD ANNOYING (17YRS & UNDER)", "CHILD NEGLECT (SEE 300 W.I.C.)", "OFFENSE INVOLVING CHILDREN"],
    ("OTHER NARCOTIC VIOLATION"): ["OTHER NARCOTIC VIOLATION"],
    ("OTHER OFFENSE"): [None, "VIOLATION OF COURT ORDER", "VIOLATION OF RESTRAINING ORDER", "VIOLATION OF TEMPORARY RESTRAINING ORDER", "PROWLER", "PANDERING", "PEEPING TOM", "OTHER MISCELLANEOUS CRIME", "ILLEGAL DUMPING", "CRUELTY TO ANIMALS", "CONTEMPT OF COURT", "ABORTION/ILLEGAL", "OTHER OFFENSE"],
    ("PROSTITUTION"): ["PIMPING", "PROSTITUTION"],
    ("PUBLIC INDECENCY"): ["INDECENT EXPOSURE", "PUBLIC INDECENCY"],
    ("PUBLIC PEACE VIOLATION"): ["INCITING A RIOT", "DISTURBING THE PEACE", "BLOCKING DOOR INDUCTION CENTER", "PUBLIC PEACE VIOLATION"],
    ("RITUALISM"): ["RITUALISM"],
    ("ROBBERY"): ["ATTEMPTED ROBBERY", "ROBBERY"],
    ("SEX OFFENSE"): ["SEX, UNLAWFUL", "SEX,UNLAWFUL(INC MUTUAL CONSENT, PENETRATION W/ FRGN OBJ", "SEX,UNLAWFUL(INC MUTUAL CONSENT, PENETRATION W/ FRGN OBJ0059", "SEXUAL PENETRATION W/FOREIGN OBJECT", "SEXUAL PENTRATION WITH A FOREIGN OBJECT", "ORAL COPULATION", "LETTERS, LEWD", "LETTERS, LEWD  -  TELEPHONE CALLS, LEWD", "LEWD CONDUCT", "LEWD/LASCIVIOUS ACTS WITH CHILD", "INTIMATE PARTNER - SIMPLE ASSAULT", "INCEST (SEXUAL ACTS BETWEEN BLOOD RELATIVES)", "BEASTIALITY, CRIME AGAINST NATURE SEXUAL ASSLT WITH ANIM", "BEASTIALITY, CRIME AGAINST NATURE SEXUAL ASSLT WITH ANIM0065", "BIGAMY", "SEX OFFENSE"],
    ("STALKING"): ["STALKING"],
    ("THEFT"): ["VEHICLE - ATTEMPT STOLEN", "VEHICLE - STOLEN", "TILL TAP - ATTEMPT", "TILL TAP - GRAND THEFT ($950.01 & OVER)", "TILL TAP - PETTY ($950 & UNDER)", "THEFT FROM MOTOR VEHICLE - ATTEMPT", "THEFT FROM MOTOR VEHICLE - GRAND ($400 AND OVER)", "THEFT FROM MOTOR VEHICLE - PETTY ($950 & UNDER)", "THEFT FROM PERSON - ATTEMPT", "THEFT OF IDENTITY", "THEFT PLAIN - ATTEMPT", "THEFT PLAIN - PETTY ($950 & UNDER)", "THEFT, COIN MACHINE - ATTEMPT", "THEFT, COIN MACHINE - GRAND ($950.01 & OVER)", "THEFT, COIN MACHINE - PETTY ($950 & UNDER)", "THEFT, PERSON", "THEFT-GRAND ($950.01 & OVER)EXCPT,GUNS,FOWL,LIVESTK,PROD", "THEFT-GRAND ($950.01 & OVER)EXCPT,GUNS,FOWL,LIVESTK,PROD0036", "STALKING", "SODOMY/SEXUAL CONTACT B/W PENIS OF ONE PERS TO ANUS OTH", "SODOMY/SEXUAL CONTACT B/W PENIS OF ONE PERS TO ANUS OTH 0007=02", "SHOPLIFTING - ATTEMPT", "SHOPLIFTING - PETTY THEFT ($950 & UNDER)", "SHOPLIFTING-GRAND THEFT ($950.01 & OVER)", "PURSE SNATCHING", "PURSE SNATCHING - ATTEMPT", "PICKPOCKET", "PICKPOCKET, ATTEMPT", "PETTY THEFT - AUTO REPAIR", "GRAND THEFT / AUTO REPAIR", "GRAND THEFT / INSURANCE FRAUD", "DISHONEST EMPLOYEE - GRAND THEFT", "DISHONEST EMPLOYEE - PETTY THEFT", "DISHONEST EMPLOYEE ATTEMPTED THEFT", "BUNCO, ATTEMPT", "BUNCO, GRAND THEFT", "BUNCO, PETTY THEFT", "BOAT - STOLEN", "BIKE - ATTEMPTED STOLEN", "BIKE - STOLEN", "THEFT"],
    ("WEAPONS VIOLATION"): ["WEAPONS POSSESSION/BOMBING", "SHOTS FIRED AT INHABITED DWELLING", "SHOTS FIRED AT MOVING VEHICLE, TRAIN OR AIRCRAFT", "REPLICA FIREARMS(SALE,DISPLAY,MANUFACTURE OR DISTRIBUTE)", "REPLICA FIREARMS(SALE,DISPLAY,MANUFACTURE OR DISTRIBUTE)0132", "FIREARMS RESTRAINING ORDER (FIREARMS RO)", "DISCHARGE FIREARMS/SHOTS FIRED", "CONCEALED CARRY LICENSE VIOLATION", "WEAPONS VIOLATION"]
}

CRIMETYPE_DICT = {}
for k in rev_crimetype_dict:
    for i in rev_crimetype_dict[k]:
        CRIMETYPE_DICT[i] = list(k)

crime_personal_property = [
    ["PERSONAL"],
    ["PROPERTY"],
    ["OTHER"]
]

rev_crime_personal_property_dict = {
    ("PERSONAL") : [["ASSAULT"], ["BATTERY"],["CRIMINAL SEXUAL ASSAULT"], ["DOMESTIC VIOLENCE"], ["HOMICIDE"], ["HUMAN TRAFFICKING"], ["INTIMIDATION"], ["KIDNAPPING"], ["OBSCENITY"], ["OFFENSE INVOLVING CHILDREN"], ["SEX OFFENSE"], ["STALKING"]],
    ("PROPERTY") : [["ARSON"], ["BURGLARY"],["CRIMINAL DAMAGE"], ["CRIMINAL TRESPASS"], ["MOTOR VEHICLE THEFT"], ["ROBBERY"], ["THEFT"]],
    ("OTHER") : [["CONCEALED CARRY LICENSE VIOLATION"], ["DECEPTIVE PRACTICE"], ["GAMBLING"], ["INTERFERENCE WITH PUBLIC OFFICER"], ["LIQUOR LAW VIOLATION"], ["NARCOTICS"], ["NON-CRIMINAL"], ["OTHER NARCOTIC VIOLATION"], ["OTHER OFFENSE"], ["PROSTITUTION"], ["PUBLIC INDECENCY"], ["PUBLIC PEACE VIOLATION"], ["RITUALISM"], ["WEAPONS VIOLATION"]],
}

CRIME_PERSONAL_PROPERTY_DICT = {}
for k in rev_crime_personal_property_dict:
    for i in rev_crime_personal_property_dict[k]:
        CRIME_PERSONAL_PROPERTY_DICT[i] = list(k)

crime_violence = [
    ["VIOLENT"],
    ["NON_VIOLENT"]
]

rev_crime_violence_dict = {
    ("VIOLENT") : [["ARSON"], ["ASSAULT"], ["BATTERY"],["CRIMINAL SEXUAL ASSAULT"], ["DOMESTIC VIOLENCE"], ["HOMICIDE"], ["HUMAN TRAFFICKING"], ["KIDNAPPING"], ["OFFENSE INVOLVING CHILDREN"], ["ROBBERY"], ["SEX OFFENSE"]],
    ("NON_VIOLENT") : [["BURGLARY"],["CRIMINAL DAMAGE"], ["CONCEALED CARRY LICENSE VIOLATION"], ["CRIMINAL TRESPASS"], ["DECEPTIVE PRACTICE"], ["GAMBLING"], ["INTERFERENCE WITH PUBLIC OFFICER"], ["INTIMIDATION"], ["LIQUOR LAW VIOLATION"], ["MOTOR VEHICLE THEFT"], ["NARCOTICS"], ["NON-CRIMINAL"], ["OTHER NARCOTIC VIOLATION"], ["OTHER OFFENSE"], ["PROSTITUTION"], ["PUBLIC INDECENCY"], ["PUBLIC PEACE VIOLATION"], ["RITUALISM"], ["ROBBERY"], ["STALKING"], ["THEFT"], ["WEAPONS VIOLATION"]],
}

CRIME_VIOLENCE_DICT = {}
for k in rev_crime_violence_dict:
    for i in rev_crime_violence_dict[k]:
        CRIME_VIOLENCE_DICT[i] = list(k)


reset_tables()
create_indexes()
print("reset")


pd.DataFrame(location_cat, columns=["key1", "key2", "key3"]).to_csv("ALL_DATA/locations.csv", index=False)
add_formatted_data("ALL_DATA/locations.csv", "locdesctype")
print("locdesc")


pd.DataFrame(crimetype_cat, columns=["category"]).to_csv("ALL_DATA/crimetypes.csv", index=False)
add_formatted_data("ALL_DATA/crimetypes.csv", "crimetype")
print("crimetype")


pd.DataFrame([["CHICAGO", "ILLINOIS", "UNITED STATES OF AMERICA", "POINT(41.8781 -87.6298)"]], columns=["city", "state", "country", "location"]).to_csv("Chicago_Data/cities.csv", index=False)
add_formatted_data("Chicago_Data/cities.csv", "city")
print("city")

pd.DataFrame(location_group, columns=["grouping"]).to_csv("ALL_DATA/locationgroups.csv", index=False)
add_formatted_data("ALL_DATA/locationgroups.csv", "loc_group")
print("locgroup")

pd.DataFrame(crime_personal_property, columns=["type"]).to_csv("ALL_DATA/crimeppo.csv", index=False)
add_formatted_data("ALL_DATA/crimeppo.csv", "ppo")
print("crimeppo")

pd.DataFrame(crime_violence, columns=["violence"]).to_csv("ALL_DATA/crimeviolence.csv", index=False)
add_formatted_data("ALL_DATA/crimeviolence.csv", "violence")
print("crimeviolence")

cityid = SESSION.query(City).filter(City.location == "POINT(41.8781 -87.6298)").one().id


with open("Chicago_Data/boundaries.json", "r") as fp:
    boundaries = json.load(fp)["features"]
with open("Chicago_Data/boundaries_tracts.json", "r") as fp:
    boundaries_tracts = json.load(fp)["features"]
pops = pd.read_csv("Chicago_Data/populations.csv")
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
pd.DataFrame(shapes, columns=["cityid", "shape", "population"]).to_csv("Chicago_Data/blocks.csv", index=False)
add_formatted_data("Chicago_Data/blocks.csv", "block")
print("blocks")


zipcodes_list = [60007, 60018, 60068, 60106, 60131, 60176, 60601, 60602, 60603, 60604, 60605, 60606, 60607, 60608, 60609, 60610, 60611, 60612, 60613, 60614, 60615, 60616, 60617, 60618, 60619, 60620, 60621, 60622, 60623, 60624, 60625, 60626, 60628, 60629, 60630, 60631, 60632, 60633, 60634, 60636, 60637, 60638, 60639, 60640, 60641, 60642, 60643, 60644, 60645, 60646, 60647, 60649, 60651, 60652, 60653, 60654, 60655, 60656, 60657, 60659, 60660, 60661, 60706, 60707, 60714, 60804, 60827]
zipcodes_list = [str(x) for x in zipcodes_list]
with open("Chicago_Data/zipcodes.json", "r") as fp:
    zipcodes = json.load(fp)["features"]
rows = []
for i, zc in enumerate(zipcodes):
    if zc["properties"]["ZCTA5CE10"] in zipcodes_list:
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
pd.DataFrame(rows, columns=["cityid", "zipcode", "shape"]).to_csv("Chicago_Data/zipcodes.csv", index=False)
add_formatted_data("Chicago_Data/zipcodes.csv", "zipcodegeom")
print("zipcodes")

incidents = pd.read_csv("Chicago_Data/crimes.csv")
incidents.loc[:,"location"] = incidents[["Longitude", "Latitude"]].apply(lambda x: "POINT({})".format(" ".join([str(y) for y in x])), axis=1)
crimetypes = SESSION.query(CrimeType).all()
crimetype_dict = {}
for c in crimetypes:
    crimetype_dict[(c.category)] = c.id
incidents.loc[:,"crimetypeid"] = incidents["Primary Type"].apply(find_crimetypeid)
loctypes = SESSION.query(LocationDescriptionType).all()
loctype_dict = {}
for c in loctypes:
    loctype_dict[(c.key1, c.key2, c.key3)] = c.id
incidents.loc[:,"locdescid"] = incidents["Location Description"].apply(find_loctypeid)
locationgroupings = SESSION.query(LocGroup).all()
locgroup_dict = {}
for c in locationgroups:
    locgroup_dict[(c.grouping)] = c.id
crimeppo = SESSION.query(CrimePPO).all()
crimeppo_dict = {}
for c in crimeppo:
    crimeppo_dict[(c.type)] = c.id
crimevio = SESSION.query(CrimeVIO).all()
crimevio_dict = {}
for c in crimevio:
    crimevio_dict[(c.violence)] = c.id
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
incidents.loc[:, "locgroup"] = incidents.loc[:,"locgroup"].astype(str)
incidents.loc[:, "ppo"] = incidents.loc[:,"ppo"].astype(str)
incidents.loc[:, "violence"] = incidents.loc[:,"violence"].astype(str)
incidents = incidents.loc[:,["crimetypeid", "locdescid", "cityid", "blockid", "location", "datetime", "hour", "dow", "month", "year", "locgroup", "ppo", "violence"]]
incidents = incidents.dropna()
incidents.loc[:,"crimetypeid"] = incidents.loc[:,"crimetypeid"].astype(int)
incidents.loc[:,"locdescid"] = incidents.loc[:,"locdescid"].astype(int)
incidents.loc[:,"cityid"] = incidents.loc[:,"cityid"].astype(int)
incidents.loc[:,"blockid"] = incidents.loc[:,"blockid"].astype(int)
incidents.to_csv("Chicago_Data/incident.csv", index=False)
print("\tuploading incidents")
add_formatted_data("Chicago_Data/incident.csv", "incident")
print("incidents")


pd.DataFrame([["LOS ANGELES", "CALIFORNIA", "UNITED STATES OF AMERICA", "POINT(34.0522 -118.2437)"]], columns=["city", "state", "country", "location"]).to_csv("LA_data/cities.csv", index=False)
add_formatted_data("LA_data/cities.csv", "city")
print("city")


cityid = SESSION.query(City).filter(City.location == "POINT(34.0522 -118.2437)").one().id


src = shapefile.Reader('LA_data/tracts.shp')
project = partial(
    pyproj.transform,
    pyproj.Proj(init='ESRI:102645'), # source coordinate system
    pyproj.Proj(init='EPSG:4326')
)
pops = pd.read_csv("LA_data/population.csv")
records = src.records()
rows = []
for ind, rec in enumerate(src.shapeRecords()):
    rows.append([cityid, MultiPolygon([(transform(project, shape(json.loads(json.dumps(rec.shape.__geo_interface__)))))]).wkt, records[ind][0]])
blocks = pd.DataFrame(rows, columns=["cityid", "shape", "population"])
blocks.loc[:, "population"] = blocks["population"].apply(lambda x: pops.loc[pops["OBJECTID"] == x, "POP"].values[0] if x in pops["OBJECTID"].values else None)
blocks = blocks.dropna()
blocks.loc[:, "population"] = blocks.loc[:, "population"].astype(int)
blocks.to_csv("LA_data/blocks.csv", index=False)
add_formatted_data("LA_data/blocks.csv", "block")
print("blocks")


zipcodes_list = [90895,91001,91006,91007,91011,91010,91016,91020,91017,93510,91023,91024,91030,91040,91043,91042,91101,91103,91105,93534,91104,93532,91107,93536,91106,93535,91108,93543,93544,91123,93551,93550,93553,93552,91182,93563,93590,91189,91202,91201,93591,91204,91203,91206,91205,91208,91207,91210,91214,91302,91301,91304,91303,91306,91307,91310,92397,91311,91316,91321,91325,91324,91326,91331,91330,91335,91340,91343,91342,91345,91344,91350,91346,91352,91351,91354,91356,91355,91357,91361,91364,91367,91365,91381,91383,91384,91387,91390,91402,91401,91404,91403,91406,91405,91411,91423,91436,91495,91501,91502,91505,91504,91506,91602,91601,91604,91606,91605,91608,91607,91614,91706,91702,91711,91722,91724,91723,91732,91731,91733,91735,91740,91741,91745,91744,91747,91746,91748,90002,90001,91750,91755,90004,90003,91754,90006,90005,90008,91759,90007,90010,90012,91765,90011,90014,91767,91766,90013,90016,90015,91768,90018,91770,90017,90020,91773,91772,90019,90022,91776,90021,91775,91780,90024,91778,90023,90026,90025,90028,90027,91790,90029,91789,90032,91792,91791,90031,90034,91793,90033,90036,90035,90038,91801,90037,90040,91803,90039,90042,90041,90044,90043,90046,90045,90048,90047,90049,90052,90056,90058,90057,90060,90059,90062,90061,90064,90063,90066,90065,90068,90067,90069,90071,90074,90077,91008,90084,90089,90095,90094,90096,90201,90189,90211,90210,90212,90221,90220,90222,90230,90232,90241,90240,90245,90242,90248,90247,90250,90249,90254,90260,90255,90262,90264,90263,90266,90265,90270,90274,90272,90277,90275,90280,90278,90291,90290,90293,90292,90295,90301,90296,90303,90302,90305,90304,90402,90401,90404,90403,90406,93243,90405,90501,90503,90502,90505,90504,90508,90601,90603,90602,90605,90604,90606,90631,90639,90638,90650,90640,90660,90670,90702,90701,90704,90703,90706,90710,90713,90712,90715,90717,90716,90731,90723,90733,90732,90745,90744,90747,90746,90755,90803,90802,90805,90804,90807,90806,90808,90813,90810,90815,90814,90840]
zipcodes_list = [str(x) for x in zipcodes_list]
with open("LA_data/zipcodes.json", "r") as fp:
    zipcodes = json.load(fp)["features"]
rows = []
for i, zc in enumerate(zipcodes):
    if zc["properties"]["ZCTA5CE10"] in zipcodes_list:
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
pd.DataFrame(rows, columns=["cityid", "zipcode", "shape"]).to_csv("LA_data/zipcodes.csv", index=False)
add_formatted_data("LA_data/zipcodes.csv", "zipcodegeom")
print("zipcodes")


incidents = pd.read_csv("LA_data/crimes.csv")
incidents = incidents.dropna(subset=["Location "])
incidents.loc[:,"location"] = incidents["Location "].astype(str).apply(lambda x: x if x != "(0, 0)" else None)
incidents = incidents.dropna(subset=["location"])
incidents.loc[:,"location"] = incidents.loc[:,"location"].apply(lambda x: "POINT{}".format("".join(x.split(","))))
crimetypes = SESSION.query(CrimeType).all()
crimetype_dict = {}
for c in crimetypes:
    crimetype_dict[(c.category)] = c.id
incidents.loc[:,"crimetypeid"] = incidents["Crime Code Description"].apply(find_crimetypeid)
loctypes = SESSION.query(LocationDescriptionType).all()
loctype_dict = {}
for c in loctypes:
    loctype_dict[(c.key1, c.key2, c.key3)] = c.id
incidents.loc[:,"locdescid"] = incidents["Premise Description"].apply(find_loctypeid)
locationgroupings = SESSION.query(LocGroup).all()
locgroup_dict = {}
for c in locationgroups:
    locgroup_dict[(c.grouping)] = c.id
crimeppo = SESSION.query(CrimePPO).all()
crimeppo_dict = {}
for c in crimeppo:
    crimeppo_dict[(c.type)] = c.id
crimevio = SESSION.query(CrimeVIO).all()
crimevio_dict = {}
for c in crimevio:
    crimevio_dict[(c.violence)] = c.id
blocks = SESSION.query(Blocks).all()
block_dict = {}
for b in blocks:
    block_dict[b.id] = wkb.loads(b.shape.data.tobytes())
incidents.loc[:,"blockid"] = incidents["location"].apply(find_blockid)
incidents.loc[:, "datetime"] = pd.to_datetime(incidents["Date Occurred"])
incidents.loc[:, "hour"] = incidents["Time Occurred"].apply(lambda x: x)
incidents.loc[:, "dow"] = incidents["datetime"].apply(lambda x: x.weekday())
incidents.loc[:, "month"] = incidents["datetime"].apply(lambda x: x.month)
incidents.loc[:, "year"] = incidents["datetime"].apply(lambda x: x.year)
incidents.loc[:, "cityid"] = cityid
incidents.loc[:, "locgroup"] = incidents.loc[:,"locgroup"].astype(str)
incidents.loc[:, "ppo"] = incidents.loc[:,"ppo"].astype(str)
incidents.loc[:, "violence"] = incidents.loc[:,"violence"].astype(str)
incidents = incidents.loc[:,["crimetypeid", "locdescid", "cityid", "blockid", "location", "datetime", "hour", "dow", "month", "year", "locgroup", "ppo", "violence"]]
incidents = incidents.dropna()
incidents.loc[:,"crimetypeid"] = incidents.loc[:,"crimetypeid"].astype(int)
incidents.loc[:,"locdescid"] = incidents.loc[:,"locdescid"].astype(int)
incidents.loc[:,"cityid"] = incidents.loc[:,"cityid"].astype(int)
incidents.loc[:,"blockid"] = incidents.loc[:,"blockid"].astype(int)
incidents.to_csv("LA_data/incident.csv", index=False)
print("\tuploading incidents")
add_formatted_data("LA_data/incident.csv", "incident")
print("incidents")
