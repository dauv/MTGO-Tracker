import json
import os
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

import db
import importer
import sidebar

st.set_page_config(page_title="Import — MTGO Tracker", page_icon="📥", layout="wide")

filters = sidebar.render_sidebar()
st.title("📥 Import Match Logs")

if filters is None:
    st.stop()

conn = filters["conn"]
hero = filters["hero"]

st.markdown(
    """
    Point to the folder containing your `Match_GameLog_*.dat` files.
    The default MTGO log location is usually:

    `C:\\Users\\<you>\\AppData\\Local\\Wizards of the Coast\\Magic Online\\Logs`

    Already-imported files are skipped automatically.
    """
)

# ---------------------------------------------------------------------------
# Folder selection
# ---------------------------------------------------------------------------

log_folder = st.text_input(
    "Log folder path",
    value=st.session_state.config.get("log_folder", ""),
    help="The folder MTGO writes its Match_GameLog_*.dat files into.",
)

if st.button("Scan for new logs"):
    if not log_folder or not os.path.exists(log_folder):
        st.error("Folder not found. Check the path.")
    else:
        all_files = [
            f for f in os.listdir(log_folder)
            if f.startswith("Match_GameLog_") and f.endswith(".dat")
        ]
        parsed = db.get_parsed_files(conn)
        new_files = [f for f in all_files if f not in parsed]

        st.session_state["pending_files"] = new_files
        st.session_state["pending_folder"] = log_folder

        # Persist the folder
        st.session_state.config["log_folder"] = log_folder
        CONFIG_FILE = Path(__file__).parent.parent / "mtgo_config.json"
        CONFIG_FILE.write_text(json.dumps(st.session_state.config, indent=2))

        if new_files:
            st.success(f"Found **{len(new_files)}** new files out of {len(all_files)} total.")
        else:
            st.info(f"All {len(all_files)} files are already imported. Nothing to do.")

# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

pending = st.session_state.get("pending_files", [])

if pending:
    folder = st.session_state.get("pending_folder", log_folder)
    st.subheader(f"{len(pending)} files ready to import")

    with st.expander("Preview file list"):
        for f in pending[:50]:
            st.text(f)
        if len(pending) > 50:
            st.caption(f"… and {len(pending) - 50} more")

    if st.button("Import all", type="primary"):
        progress_bar = st.progress(0.0)
        status_text = st.empty()

        successes, skipped, errors = 0, 0, []

        for i, filename in enumerate(pending):
            filepath = os.path.join(folder, filename)
            progress_bar.progress((i + 1) / len(pending))
            status_text.text(f"Importing {i+1}/{len(pending)}: {filename}")

            ok, msg = importer.import_log_file(conn, filepath, hero)
            if ok:
                successes += 1
            elif msg == "Already imported":
                skipped += 1
            else:
                errors.append(f"{filename}: {msg}")

        progress_bar.empty()
        status_text.empty()

        st.success(f"Done! Imported **{successes}** new matches. {skipped} already in DB.")

        if errors:
            with st.expander(f"⚠️ {len(errors)} files could not be parsed"):
                for e in errors:
                    st.text(e)

        st.session_state["pending_files"] = []
        st.rerun()

# ---------------------------------------------------------------------------
# DB summary
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Database summary")

try:
    import pandas as pd

    total_matches = pd.read_sql_query(
        "SELECT COUNT(*) as cnt FROM Matches WHERE P1=?", conn, params=[hero]
    ).iloc[0]["cnt"]
    total_parsed = pd.read_sql_query(
        "SELECT COUNT(*) as cnt FROM Parsed_Files", conn
    ).iloc[0]["cnt"]

    c1, c2 = st.columns(2)
    c1.metric("Your matches in DB", int(total_matches))
    c2.metric("Log files imported", int(total_parsed))
except Exception:
    st.info("Run a scan to see stats.")
