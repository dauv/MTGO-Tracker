import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

import db
import sidebar

st.set_page_config(page_title="Match History — MTGO Tracker", page_icon="📜", layout="wide")

filters = sidebar.render_sidebar()
st.title("📜 Match History")

if filters is None:
    st.stop()

df = db.get_matches(
    filters["conn"],
    filters["hero"],
    start_date=filters["start_date"],
    end_date=filters["end_date"],
    formats=filters["formats"],
    match_types=filters["match_types"],
)

if df.empty:
    st.info("No matches found.")
    st.stop()

# ---------------------------------------------------------------------------
# Search / filter
# ---------------------------------------------------------------------------

search = st.text_input("Search (opponent name, deck, format…)", placeholder="e.g. Burn, Legacy, PlayerName")

if search:
    mask = (
        df["P2"].str.contains(search, case=False, na=False)
        | df["P1_Subarch"].str.contains(search, case=False, na=False)
        | df["P2_Subarch"].str.contains(search, case=False, na=False)
        | df["P2_Arch"].str.contains(search, case=False, na=False)
        | df["Format"].str.contains(search, case=False, na=False)
        | df["Match_Type"].str.contains(search, case=False, na=False)
    )
    df = df[mask]

# ---------------------------------------------------------------------------
# Result filter
# ---------------------------------------------------------------------------

result_filter = st.radio("Show", ["All", "Wins only", "Losses only"], horizontal=True)
if result_filter == "Wins only":
    df = df[df["Won"] == 1]
elif result_filter == "Losses only":
    df = df[df["Won"] == 0]

st.caption(f"{len(df)} matches")

# ---------------------------------------------------------------------------
# Display table
# ---------------------------------------------------------------------------

display_cols = {
    "Date": "Date",
    "P1_Subarch": "Your Deck",
    "P1_Arch": "Your Arch.",
    "P2": "Opponent",
    "P2_Subarch": "Opp. Deck",
    "P2_Arch": "Opp. Arch.",
    "P1_Wins": "Your W",
    "P2_Wins": "Opp. W",
    "Result": "Result",
    "Format": "Format",
    "Match_Type": "Type",
}

display = df[list(display_cols.keys())].rename(columns=display_cols).copy()
# Format date to readable form (strip time)
display["Date"] = df["Date"].str[:10].values


def _row_style(row):
    if row["Result"] == "Win":
        return ["color: #2ecc71"] * len(row)
    elif row["Result"] == "Loss":
        return ["color: #e74c3c"] * len(row)
    return [""] * len(row)


styled = display.style.apply(_row_style, axis=1)
st.dataframe(styled, hide_index=True, use_container_width=True)
