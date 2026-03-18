"""
Import MTGO Match_GameLog_*.dat files into the SQLite database.
Wraps the existing modo.py parsing logic and ensures matches are always
stored from the hero's perspective (hero = P1).
"""
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import modo
import db


# ---------------------------------------------------------------------------
# Inversion helpers (mirror of modo.invert_join, but for single records)
# ---------------------------------------------------------------------------

def _invert_match(match_data):
    h = modo.header("Matches")
    m = list(match_data)

    def swap(a, b):
        ia, ib = h.index(a), h.index(b)
        m[ia], m[ib] = m[ib], m[ia]

    swap("P1", "P2")
    swap("P1_Arch", "P2_Arch")
    swap("P1_Subarch", "P2_Subarch")
    swap("P1_Roll", "P2_Roll")
    swap("P1_Wins", "P2_Wins")

    for col in ("Match_Winner", "Roll_Winner"):
        idx = h.index(col)
        if m[idx] == "P1":
            m[idx] = "P2"
        elif m[idx] == "P2":
            m[idx] = "P1"

    return m


def _invert_game(game_data):
    h = modo.header("Games")
    g = list(game_data)

    def swap(a, b):
        ia, ib = h.index(a), h.index(b)
        g[ia], g[ib] = g[ib], g[ia]

    swap("P1", "P2")
    swap("P1_Mulls", "P2_Mulls")
    swap("On_Play", "On_Draw")

    for col in ("PD_Selector", "Game_Winner"):
        idx = h.index(col)
        if g[idx] == "P1":
            g[idx] = "P2"
        elif g[idx] == "P2":
            g[idx] = "P1"

    return g


# ---------------------------------------------------------------------------
# Public import function
# ---------------------------------------------------------------------------

def import_log_file(conn, filepath, hero):
    """
    Parse a single Match_GameLog file and insert it into the DB.

    Returns (success: bool, message: str).
    """
    filename = os.path.basename(filepath)

    # Skip already-imported files
    if filename in db.get_parsed_files(conn):
        return False, "Already imported"

    # Read raw content
    try:
        with open(filepath, "r", encoding="latin1") as f:
            content = f.read()
    except Exception as exc:
        return False, f"Read error: {exc}"

    # Get file modification time in the format modo expects
    try:
        mtime = time.strftime("%a %b %d %H:%M:%S %Y", time.localtime(os.path.getmtime(filepath)))
    except Exception:
        mtime = time.strftime("%a %b %d %H:%M:%S %Y")

    # Parse with modo
    try:
        result = modo.get_all_data(content, mtime, filename)
    except Exception as exc:
        return False, f"Parse error: {exc}"

    if isinstance(result, str):
        return False, f"Parse error: {result}"

    match_data, game_data, play_data, _unresolved, _timeout = result

    # Ensure hero is always P1
    h_m = modo.header("Matches")
    p1_name = match_data[h_m.index("P1")]
    p2_name = match_data[h_m.index("P2")]

    if p1_name != hero and p2_name != hero:
        return False, f"Hero '{hero}' not in match ({p1_name} vs {p2_name})"

    if p2_name == hero:
        match_data = _invert_match(match_data)
        game_data = [_invert_game(g) for g in game_data]

    # Insert into DB
    try:
        cursor = conn.cursor()

        mh = modo.header("Matches")
        cursor.execute(
            f"INSERT OR IGNORE INTO Matches ({','.join(mh)}) VALUES ({','.join('?'*len(mh))})",
            match_data,
        )

        gh = modo.header("Games")
        for g in game_data:
            cursor.execute(
                f"INSERT INTO Games ({','.join(gh)}) VALUES ({','.join('?'*len(gh))})",
                g,
            )

        ph = modo.header("Plays")
        for p in play_data:
            cursor.execute(
                f"INSERT INTO Plays ({','.join(ph)}) VALUES ({','.join('?'*len(ph))})",
                p,
            )

        cursor.execute(
            "INSERT OR IGNORE INTO Parsed_Files (filename, parsed_at) VALUES (?, ?)",
            (filename, datetime.now().isoformat()),
        )

        conn.commit()
        return True, "Success"

    except Exception as exc:
        conn.rollback()
        return False, f"DB error: {exc}"
