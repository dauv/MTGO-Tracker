"""
Shared sidebar component for all pages.
Handles auto-connect, global date filters, and returns a filter context dict.
"""
import json
from datetime import datetime, timedelta
from pathlib import Path

import streamlit as st

import db

CONFIG_FILE = Path(__file__).parent / "mtgo_config.json"
DEFAULT_DB_PATH = str(Path(__file__).parent / "all_data.db")


def load_config():
    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text())
            if not cfg.get("db_path"):
                cfg["db_path"] = DEFAULT_DB_PATH
            return cfg
        except Exception:
            pass
    return {"db_path": DEFAULT_DB_PATH, "hero": "", "log_folder": ""}


def _try_connect(cfg):
    """Attempt DB connection using config. Stores result in session_state."""
    db_path = cfg.get("db_path") or DEFAULT_DB_PATH
    try:
        conn = db.get_connection(db_path)
        db.init_db(conn)
        st.session_state.conn = conn
        cfg["db_path"] = db_path
        return True
    except Exception:
        return False


def _ensure_state():
    if "config" not in st.session_state:
        st.session_state.config = load_config()
    if "conn" not in st.session_state:
        st.session_state.conn = None
        _try_connect(st.session_state.config)




def render_sidebar():
    """
    Render the sidebar with status + global filters.
    Returns a filter dict if connected, or None if not.
    """
    _ensure_state()

    with st.sidebar:
        st.title("MTGO Tracker")

        conn = st.session_state.conn
        hero = st.session_state.config.get("hero", "")

        if conn is None or not hero:
            st.warning("Not connected. Go to **Settings** first.")
            st.page_link("app.py", label="Go to Settings", icon="⚙️")
            return None

        st.caption(f"Playing as **{hero}**")
        st.divider()

        # --- Filters ---
        st.subheader("Filters")

        PERIOD_OPTIONS = ["2 weeks", "1 month", "3 months", "6 months", "All time"]
        cfg = st.session_state.config
        saved_period = cfg.get("filter_period", "All time")
        if saved_period not in PERIOD_OPTIONS:
            saved_period = "All time"

        selected_period = st.radio(
            "Period", PERIOD_OPTIONS,
            index=PERIOD_OPTIONS.index(saved_period),
            key="filter_period_radio",
        )

        if selected_period != saved_period:
            cfg["filter_period"] = selected_period
            CONFIG_FILE.write_text(json.dumps(cfg, indent=2))

        today = datetime.now().date()
        period_map = {
            "2 weeks":  today - timedelta(weeks=2),
            "1 month":  today - timedelta(days=30),
            "3 months": today - timedelta(days=90),
            "6 months": today - timedelta(days=180),
            "All time": None,
        }
        start_date = period_map[selected_period]
        end_date   = today


        match_types = db.get_match_types(conn, hero)
        selected_match_types = (
            st.multiselect("Match Type", options=match_types, key="filter_match_types")
            if match_types
            else []
        )

        return {
            "hero":        hero,
            "conn":        conn,
            "start_date":  start_date,
            "end_date":    end_date,
            "decks":       None,
            "formats":     None,
            "match_types": selected_match_types or None,
        }
