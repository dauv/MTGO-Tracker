import sqlite3
import pandas as pd


def get_connection(db_path):
    return sqlite3.connect(db_path, check_same_thread=False)


def init_db(conn):
    """Create tables if they don't exist. Safe to call on an existing DB."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS Matches (
            Match_ID TEXT PRIMARY KEY,
            Draft_ID TEXT,
            P1 TEXT, P1_Arch TEXT, P1_Subarch TEXT,
            P2 TEXT, P2_Arch TEXT, P2_Subarch TEXT,
            P1_Roll INTEGER, P2_Roll INTEGER, Roll_Winner TEXT,
            P1_Wins INTEGER, P2_Wins INTEGER, Match_Winner TEXT,
            Format TEXT, Limited_Format TEXT, Match_Type TEXT, Date TEXT
        );
        CREATE TABLE IF NOT EXISTS Games (
            Match_ID TEXT, P1 TEXT, P2 TEXT, Game_Num INTEGER,
            PD_Selector TEXT, PD_Choice TEXT, On_Play TEXT, On_Draw TEXT,
            P1_Mulls INTEGER, P2_Mulls INTEGER, Turns INTEGER, Game_Winner TEXT
        );
        CREATE TABLE IF NOT EXISTS Plays (
            Match_ID TEXT, Game_Num INTEGER, Play_Num INTEGER, Turn_Num INTEGER,
            Casting_Player TEXT, Action TEXT, Primary_Card TEXT,
            Target1 TEXT, Target2 TEXT, Target3 TEXT,
            Opp_Target INTEGER, Self_Target INTEGER,
            Cards_Drawn INTEGER, Attackers INTEGER,
            Active_Player TEXT, Nonactive_Player TEXT
        );
        CREATE TABLE IF NOT EXISTS Parsed_Files (
            filename TEXT PRIMARY KEY,
            parsed_at TEXT
        );
    """)
    conn.commit()


def get_matches(conn, hero, start_date=None, end_date=None, formats=None, match_types=None):
    """Return matches from the hero's perspective (WHERE P1 = hero)."""
    query = "SELECT * FROM Matches WHERE P1 = ?"
    params = [hero]

    if start_date:
        query += " AND Date >= ?"
        params.append(start_date.strftime("%Y-%m-%d") + "-00:00")
    if end_date:
        query += " AND Date <= ?"
        params.append(end_date.strftime("%Y-%m-%d") + "-23:59")
    if formats:
        query += f" AND Format IN ({','.join('?'*len(formats))})"
        params.extend(formats)
    if match_types:
        query += f" AND Match_Type IN ({','.join('?'*len(match_types))})"
        params.extend(match_types)

    query += " ORDER BY Date DESC"

    df = pd.read_sql_query(query, conn, params=params)
    if not df.empty:
        df["ParsedDate"] = pd.to_datetime(df["Date"], format="%Y-%m-%d-%H:%M", errors="coerce")
        df["Won"] = (df["Match_Winner"] == "P1").astype(int)
        df["Result"] = df["Won"].map({1: "Win", 0: "Loss"})
    return df


def get_formats(conn, hero):
    try:
        df = pd.read_sql_query(
            "SELECT DISTINCT Format FROM Matches WHERE P1=? AND Format NOT IN ('NA','') ORDER BY Format",
            conn, params=[hero],
        )
        return df["Format"].tolist()
    except Exception:
        return []


def get_match_types(conn, hero):
    try:
        df = pd.read_sql_query(
            "SELECT DISTINCT Match_Type FROM Matches WHERE P1=? AND Match_Type NOT IN ('NA','') ORDER BY Match_Type",
            conn, params=[hero],
        )
        return df["Match_Type"].tolist()
    except Exception:
        return []


def get_parsed_files(conn):
    try:
        df = pd.read_sql_query("SELECT filename FROM Parsed_Files", conn)
        return set(df["filename"].tolist())
    except Exception:
        return set()
