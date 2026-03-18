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

df = db.get_matches(
    filters["conn"],
    filters["hero"],
    start_date=filters["start_date"],
    end_date=filters["end_date"],
    formats=filters["formats"],
    match_types=filters["match_types"],
)

if df.empty:
    st.info("No matches found. Import some logs or widen the date range.")
    st.stop()

min_matches = st.slider("Minimum matches to show", 1, 20, 2, key="deck_min")


def winrate_df(source_df, group_col, rename=None):
    """Group by a column and compute win rate stats."""
    g = (
        source_df.groupby(group_col)
        .agg(Matches=("Won", "count"), Wins=("Won", "sum"))
        .reset_index()
    )
    g["Losses"] = g["Matches"] - g["Wins"]
    g["Win Rate"] = g["Wins"] / g["Matches"] * 100
    g = g[g["Matches"] >= min_matches].sort_values("Win Rate", ascending=False)
    if rename:
        g = g.rename(columns={group_col: rename})
    return g


def winrate_bar(data, x_col, title):
    if data.empty:
        st.info(f"No data with {min_matches}+ matches.")
        return

    label_col = data.apply(
        lambda r: f"{r['Win Rate']:.0f}%  ({int(r['Wins'])}W–{int(r['Losses'])}L)", axis=1
    )
    fig = px.bar(
        data,
        x=x_col,
        y="Win Rate",
        color="Win Rate",
        color_continuous_scale=["#e74c3c", "#f39c12", "#2ecc71"],
        range_color=[30, 70],
        text=label_col,
        title=title,
        labels={"Win Rate": "Win Rate %"},
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
# Tabs: By Deck / By Archetype
# ---------------------------------------------------------------------------

tab_deck, tab_arch = st.tabs(["By Deck", "By Archetype"])

with tab_deck:
    st.subheader("Win Rate by Deck")

    has_deck_data = df["P1_Subarch"].notna() & (df["P1_Subarch"] != "NA") & (df["P1_Subarch"] != "")
    if not has_deck_data.any():
        st.warning(
            "No deck names set yet. "
            "Set **P1_Subarch** via the original tracker, or assign them in Match History."
        )
    else:
        data = winrate_df(df[has_deck_data], "P1_Subarch", rename="Deck")
        winrate_bar(data, "Deck", "Win Rate by Deck")

        # Table
        display = data[["Deck", "Matches", "Wins", "Losses", "Win Rate"]].copy()
        display["Win Rate"] = display["Win Rate"].round(1).astype(str) + "%"
        st.dataframe(display, hide_index=True, use_container_width=True)

with tab_arch:
    st.subheader("Win Rate by Archetype")

    has_arch_data = df["P1_Arch"].notna() & (df["P1_Arch"] != "NA") & (df["P1_Arch"] != "")
    if not has_arch_data.any():
        st.warning("No archetype data set. Assign archetypes (Aggro, Control, etc.) via the original tracker.")
    else:
        data = winrate_df(df[has_arch_data], "P1_Arch", rename="Archetype")
        winrate_bar(data, "Archetype", "Win Rate by Archetype")

        display = data[["Archetype", "Matches", "Wins", "Losses", "Win Rate"]].copy()
        display["Win Rate"] = display["Win Rate"].round(1).astype(str) + "%"
        st.dataframe(display, hide_index=True, use_container_width=True)
