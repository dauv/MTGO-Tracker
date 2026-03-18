"""
Shared sidebar component for all pages.
Handles auto-connect, global date/format filters, and returns a filter context dict.
"""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import streamlit as st

import db

CONFIG_FILE = Path(__file__).parent / "mtgo_config.json"


def load_config():
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:
            pass
    return {"db_path": "", "hero": "", "log_folder": ""}


def _try_connect(cfg):
    """Attempt DB connection using config. Stores result in session_state."""
    db_path = cfg.get("db_path", "")
    if db_path and os.path.exists(db_path):
        try:
            conn = db.get_connection(db_path)
            db.init_db(conn)
            st.session_state.conn = conn
            return True
        except Exception:
            pass
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

        start_date = st.date_input(
            "From",
            value=datetime.now().date() - timedelta(days=365),
            key="filter_start",
        )
        end_date = st.date_input(
            "To",
            value=datetime.now().date(),
            key="filter_end",
        )

        formats = db.get_formats(conn, hero)
        selected_formats = (
            st.multiselect("Format", options=formats, key="filter_formats")
            if formats
            else []
        )

        match_types = db.get_match_types(conn, hero)
        selected_match_types = (
            st.multiselect("Match Type", options=match_types, key="filter_match_types")
            if match_types
            else []
        )

        return {
            "hero": hero,
            "conn": conn,
            "start_date": start_date,
            "end_date": end_date,
            "formats": selected_formats or None,
            "match_types": selected_match_types or None,
        }
