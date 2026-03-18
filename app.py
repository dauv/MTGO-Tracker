"""
MTGO Tracker — Settings / entry-point page.
Run with: streamlit run app.py
"""
import json
import os
from pathlib import Path

import streamlit as st

import db

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

CONFIG_FILE = Path(__file__).parent / "mtgo_config.json"


def load_config():
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:
            pass
    return {"db_path": "", "hero": "", "log_folder": ""}


def save_config(cfg):
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))


# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="MTGO Tracker",
    page_icon="🃏",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Bootstrap session state
if "config" not in st.session_state:
    st.session_state.config = load_config()
if "conn" not in st.session_state:
    st.session_state.conn = None
    cfg = st.session_state.config
    if cfg.get("db_path") and os.path.exists(cfg["db_path"]):
        try:
            conn = db.get_connection(cfg["db_path"])
            db.init_db(conn)
            st.session_state.conn = conn
        except Exception:
            pass

# ---------------------------------------------------------------------------
# Sidebar status (minimal on settings page)
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("MTGO Tracker")
    if st.session_state.conn is not None:
        hero = st.session_state.config.get("hero", "—")
        st.success(f"Connected as **{hero}**")
    else:
        st.warning("Not connected")

# ---------------------------------------------------------------------------
# Main content
# ---------------------------------------------------------------------------

st.title("⚙️ Settings")
st.markdown("Set your database path and MTGO username, then use the navigation on the left.")

st.divider()

cfg = st.session_state.config

col1, col2 = st.columns(2)

with col1:
    st.subheader("Database")
    db_path = st.text_input(
        "Path to database file",
        value=cfg.get("db_path", ""),
        placeholder=r"C:\Users\you\MTGO-Tracker\all_data.db",
        help="Point to your existing all_data.db, or enter a new path to create a fresh database.",
    )
    hero = st.text_input(
        "Your MTGO username",
        value=cfg.get("hero", ""),
        help="Your in-game name — used to identify which side of each match is yours.",
    )
    create_new = st.checkbox("Create a new database if the file doesn't exist", value=True)

    if st.button("Save & Connect", type="primary"):
        if not db_path:
            st.error("Enter a database path.")
        elif not hero:
            st.error("Enter your MTGO username.")
        elif not os.path.exists(db_path) and not create_new:
            st.error("File not found. Enable 'Create new' to make a fresh database.")
        else:
            try:
                conn = db.get_connection(db_path)
                db.init_db(conn)
                st.session_state.conn = conn
                cfg["db_path"] = db_path
                cfg["hero"] = hero
                st.session_state.config = cfg
                save_config(cfg)
                st.success(f"Connected! Tracking matches as **{hero}**.")
                st.rerun()
            except Exception as exc:
                st.error(f"Connection failed: {exc}")

with col2:
    st.subheader("Log folder")
    log_folder = st.text_input(
        "MTGO log folder path",
        value=cfg.get("log_folder", ""),
        placeholder=r"C:\Users\you\AppData\Local\Wizards of the Coast\Magic Online\Logs",
        help="Folder containing Match_GameLog_*.dat files. Used by the Import page.",
    )
    if st.button("Save log folder"):
        cfg["log_folder"] = log_folder
        st.session_state.config = cfg
        save_config(cfg)
        st.success("Saved.")

# ---------------------------------------------------------------------------
# Status summary
# ---------------------------------------------------------------------------

st.divider()

if st.session_state.conn is not None:
    import pandas as pd
    hero_name = st.session_state.config.get("hero", "")
    try:
        row = pd.read_sql_query(
            "SELECT COUNT(*) as cnt FROM Matches WHERE P1=?",
            st.session_state.conn,
            params=[hero_name],
        ).iloc[0]
        total = int(row["cnt"])
        st.info(
            f"Connected to **{st.session_state.config.get('db_path','')}**. "
            f"Found **{total}** matches as **{hero_name}**."
        )
    except Exception:
        st.info("Connected to database (empty or new).")
else:
    st.info("Not connected yet. Fill in the form above.")
