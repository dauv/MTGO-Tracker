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
DEFAULT_DB_PATH = str(Path(__file__).parent / "all_data.db")


def load_config():
    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text())
            # Migrate old configs that have no db_path or an empty one
            if not cfg.get("db_path"):
                cfg["db_path"] = DEFAULT_DB_PATH
            return cfg
        except Exception:
            pass
    return {"db_path": DEFAULT_DB_PATH, "hero": "", "log_folder": ""}


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
    db_path = cfg.get("db_path") or DEFAULT_DB_PATH
    try:
        conn = db.get_connection(db_path)
        db.init_db(conn)
        st.session_state.conn = conn
        cfg["db_path"] = db_path
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
st.markdown("Enter your MTGO username and log folder, then use the navigation on the left.")

st.divider()

cfg = st.session_state.config

col1, col2 = st.columns(2)

with col1:
    st.subheader("Your profile")
    hero = st.text_input(
        "MTGO username",
        value=cfg.get("hero", ""),
        help="Your in-game name — used to identify which side of each match is yours.",
    )

    if st.button("Save", type="primary"):
        if not hero:
            st.error("Enter your MTGO username.")
        else:
            cfg["hero"] = hero
            st.session_state.config = cfg
            save_config(cfg)
            st.success(f"Saved. Tracking matches as **{hero}**.")
            st.rerun()

with col2:
    st.subheader("Log folder")
    log_folder = st.text_input(
        "MTGO log folder path",
        value=cfg.get("log_folder", ""),
        placeholder=r"C:\Users\[User]\AppData\Local\Apps\2.0",
        help=(
            "Folder containing Match_GameLog_*.dat files. "
            r"Usually in AppData\Local\Apps\2.0 or Documents."
        ),
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
    db_path = st.session_state.config.get("db_path", DEFAULT_DB_PATH)
    if hero_name:
        try:
            row = pd.read_sql_query(
                "SELECT COUNT(*) as cnt FROM Matches WHERE P1=?",
                st.session_state.conn,
                params=[hero_name],
            ).iloc[0]
            total = int(row["cnt"])
            st.info(
                f"Database: `{db_path}`  \n"
                f"Found **{total}** matches as **{hero_name}**."
            )
        except Exception:
            st.info(f"Database: `{db_path}` (empty or new).")
    else:
        st.info(f"Database ready at `{db_path}`. Enter your username above to get started.")
