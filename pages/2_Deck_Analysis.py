import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import plotly.express as px
import streamlit as st

import db
import sidebar

st.set_page_config(page_title="Deck Analysis — MTGO Tracker", page_icon="🃏", layout="wide")

filters = sidebar.render_sidebar()
st.title("🃏 Deck Analysis")

if filters is None:
    st.stop()

conn = filters["conn"]
hero = filters["hero"]

df = db.get_matches(
    conn, hero,
    start_date=filters["start_date"],
    end_date=filters["end_date"],
    formats=filters["formats"],
    match_types=filters["match_types"],
    decks=filters["decks"],
)

if df.empty:
    st.info("No matches found. Import some logs or widen the date range.")
    st.stop()

gdf = db.get_games(
    conn, hero,
    start_date=filters["start_date"],
    end_date=filters["end_date"],
    formats=filters["formats"],
    match_types=filters["match_types"],
    decks=filters["decks"],
)

min_matches = st.slider("Minimum matches to show", 1, 20, 2)

has_deck_data = df["P1_Subarch"].notna() & ~df["P1_Subarch"].isin(["NA", ""])

if not has_deck_data.any():
    st.warning("No deck names set yet. Assign them in **Match History** by clicking on a row.")
    st.stop()

# ---------------------------------------------------------------------------
# Match win stats per deck
# ---------------------------------------------------------------------------

g = (
    df[has_deck_data]
    .groupby("P1_Subarch")
    .agg(Matches=("Won", "count"), Wins=("Won", "sum"))
    .reset_index()
)
g["Losses"] = g["Matches"] - g["Wins"]
g["MW%"] = g["Wins"] / g["Matches"] * 100
g = g[g["Matches"] >= min_matches]
g = g.rename(columns={"P1_Subarch": "Deck"})

if g.empty:
    st.info(f"No decks with {min_matches}+ matches.")
    st.stop()

# ---------------------------------------------------------------------------
# Game win stats per deck (from Games table)
# ---------------------------------------------------------------------------

if not gdf.empty:
    has_game_deck = gdf["P1_Subarch"].notna() & ~gdf["P1_Subarch"].isin(["NA", ""])
    decided = gdf[gdf["Decided"] & has_game_deck]

    def _game_stats(subset, win_col, total_col, pct_col):
        s = (
            subset.groupby("P1_Subarch")
            .agg(**{win_col: ("GameWon", "sum"), total_col: ("GameWon", "count")})
            .reset_index()
        )
        s[pct_col] = s[win_col] / s[total_col] * 100
        return s[["P1_Subarch", pct_col]]

    gw  = _game_stats(decided,                        "GW",   "GT",  "GW%")
    pre = _game_stats(decided[decided["Preboard"]],   "PreW", "PreT","Pre GW%")
    post= _game_stats(decided[~decided["Preboard"]], "PostW","PostT","Post GW%")

    for stats_df, col in [(gw, "GW%"), (pre, "Pre GW%"), (post, "Post GW%")]:
        g = g.merge(
            stats_df.rename(columns={"P1_Subarch": "Deck"}),
            on="Deck", how="left",
        )

g = g.sort_values("MW%", ascending=False)

# ---------------------------------------------------------------------------
# Chart — match win %
# ---------------------------------------------------------------------------

label_col = g.apply(
    lambda r: f"{r['MW%']:.0f}%  ({int(r['Wins'])}W–{int(r['Losses'])}L)", axis=1
)

fig = px.bar(
    g,
    x="Deck",
    y="MW%",
    color="MW%",
    color_continuous_scale=["#e74c3c", "#f39c12", "#2ecc71"],
    range_color=[30, 70],
    text=label_col,
    labels={"MW%": "Match Win %"},
)
fig.add_hline(y=50, line_dash="dash", line_color="gray", opacity=0.4)
fig.update_traces(textposition="outside")
fig.update_layout(
    yaxis=dict(range=[0, 110], ticksuffix="%"),
    coloraxis_showscale=False,
    xaxis_title="",
)
st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Summary table
# ---------------------------------------------------------------------------

display = g[["Deck", "Matches", "Wins", "Losses", "MW%"]].copy()

for col in ["GW%", "Pre GW%", "Post GW%"]:
    if col in g.columns:
        display[col] = g[col]

# Format percentage columns
for col in ["MW%", "GW%", "Pre GW%", "Post GW%"]:
    if col in display.columns:
        display[col] = display[col].apply(
            lambda v: f"{v:.1f}%" if v == v else "—"  # NaN check
        )

st.dataframe(display, hide_index=True, use_container_width=True)
