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
    # Migrations: add columns that didn't exist in older versions
    for migration in [
        "ALTER TABLE Matches ADD COLUMN Notes TEXT DEFAULT ''",
    ]:
        try:
            conn.execute(migration)
            conn.commit()
        except Exception:
            pass  # column already exists


def get_games(conn, hero, start_date=None, end_date=None, formats=None, match_types=None, decks=None):
    """Return games joined to matches, filtered the same way as get_matches."""
    query = """
        SELECT g.Match_ID, g.Game_Num, g.Game_Winner, g.On_Play, g.On_Draw,
               g.P1_Mulls, g.P2_Mulls, g.Turns,
               m.Format, m.Match_Type, m.Date, m.P1_Subarch, m.P2_Subarch
        FROM Games g
        JOIN Matches m ON g.Match_ID = m.Match_ID
        WHERE m.P1 = ?
    """
    params = [hero]
    if start_date:
        query += " AND m.Date >= ?"
        params.append(start_date.strftime("%Y-%m-%d") + "-00:00")
    if end_date:
        query += " AND m.Date <= ?"
        params.append(end_date.strftime("%Y-%m-%d") + "-23:59")
    if formats:
        query += f" AND m.Format IN ({','.join('?'*len(formats))})"
        params.extend(formats)
    if match_types:
        query += f" AND m.Match_Type IN ({','.join('?'*len(match_types))})"
        params.extend(match_types)
    if decks:
        query += f" AND m.P1_Subarch IN ({','.join('?'*len(decks))})"
        params.extend(decks)

    df = pd.read_sql_query(query, conn, params=params)
    if not df.empty:
        # Exclude NA results (timeouts/DCs) from win calculations
        df["Decided"] = df["Game_Winner"].isin(["P1", "P2"])
        df["GameWon"] = (df["Game_Winner"] == "P1").astype(int)
        df["Preboard"] = (df["Game_Num"] == 1)
    return df


def get_matches(conn, hero, start_date=None, end_date=None, formats=None, match_types=None, decks=None):
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
    if decks:
        query += f" AND P1_Subarch IN ({','.join('?'*len(decks))})"
        params.extend(decks)

    query += " ORDER BY Date DESC"

    df = pd.read_sql_query(query, conn, params=params)
    if not df.empty:
        df["ParsedDate"] = pd.to_datetime(df["Date"], format="%Y-%m-%d-%H:%M", errors="coerce")
        df["Won"] = (df["Match_Winner"] == "P1").astype(int)
        df["Result"] = df["Match_Winner"].map({"P1": "Win", "P2": "Loss"}).fillna("Unknown")
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


def update_match(conn, match_id, fields: dict):
    """Update editable fields on a single match row."""
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    vals = list(fields.values()) + [match_id]
    conn.execute(f"UPDATE Matches SET {set_clause} WHERE Match_ID = ?", vals)
    conn.commit()


def get_known_decks(conn, hero):
    """Return sorted list of distinct deck names already in DB for the hero."""
    try:
        df = pd.read_sql_query(
            "SELECT DISTINCT P1_Subarch FROM Matches WHERE P1=? AND P1_Subarch NOT IN ('NA','') ORDER BY P1_Subarch",
            conn, params=[hero],
        )
        return df["P1_Subarch"].tolist()
    except Exception:
        return []


def get_known_opp_decks(conn, hero):
    """Return sorted list of distinct opponent deck names already in DB."""
    try:
        df = pd.read_sql_query(
            "SELECT DISTINCT P2_Subarch FROM Matches WHERE P1=? AND P2_Subarch NOT IN ('NA','') ORDER BY P2_Subarch",
            conn, params=[hero],
        )
        return df["P2_Subarch"].tolist()
    except Exception:
        return []


def get_match_plays(conn, match_id):
    """Return all plays for a single match, ordered by game then play number."""
    try:
        return pd.read_sql_query(
            """SELECT Game_Num, Turn_Num, Casting_Player, Action, Primary_Card
               FROM Plays
               WHERE Match_ID = ?
               ORDER BY Game_Num, Play_Num""",
            conn, params=[match_id],
        )
    except Exception:
        return pd.DataFrame()


def get_match_games(conn, match_id):
    """Return all games for a single match, ordered by game number."""
    try:
        df = pd.read_sql_query(
            "SELECT * FROM Games WHERE Match_ID = ? ORDER BY Game_Num",
            conn, params=[match_id],
        )
        return df
    except Exception:
        return pd.DataFrame()


def get_parsed_files(conn):
    try:
        df = pd.read_sql_query("SELECT filename FROM Parsed_Files", conn)
        return set(df["filename"].tolist())
    except Exception:
        return set()
