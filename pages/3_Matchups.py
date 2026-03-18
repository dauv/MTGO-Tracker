import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import plotly.express as px
import streamlit as st

import db
import sidebar

st.set_page_config(page_title="Matchups — MTGO Tracker", page_icon="⚔️", layout="wide")

filters = sidebar.render_sidebar()
st.title("⚔️ Matchups")

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

min_matches = st.slider("Minimum matches to show", 1, 20, 2, key="matchup_min")


def opp_winrate_chart(data, opp_col, title, rename):
    g = (
        data.groupby(opp_col)
        .agg(Matches=("Won", "count"), Wins=("Won", "sum"))
        .reset_index()
    )
    g["Losses"] = g["Matches"] - g["Wins"]
    g["Win Rate"] = g["Wins"] / g["Matches"] * 100
    g = g[g["Matches"] >= min_matches].sort_values("Win Rate", ascending=True)

    if g.empty:
        st.info(f"No entries with {min_matches}+ matches.")
        return

    label_col = g.apply(
        lambda r: f"{r['Win Rate']:.0f}%  ({int(r['Wins'])}W–{int(r['Losses'])}L)", axis=1
    )
    fig = px.bar(
        g,
        y=opp_col,
        x="Win Rate",
        orientation="h",
        color="Win Rate",
        color_continuous_scale=["#e74c3c", "#f39c12", "#2ecc71"],
        range_color=[30, 70],
        text=label_col,
        title=title,
        labels={opp_col: "", "Win Rate": "Win Rate %"},
    )
    fig.add_vline(x=50, line_dash="dash", line_color="gray", opacity=0.4)
    fig.update_traces(textposition="outside")
    fig.update_layout(
        xaxis=dict(range=[0, 115], ticksuffix="%"),
        coloraxis_showscale=False,
        height=max(300, len(g) * 40 + 100),
    )
    st.plotly_chart(fig, use_container_width=True)

    display = g[[opp_col, "Matches", "Wins", "Losses", "Win Rate"]].rename(
        columns={opp_col: rename}
    )
    display["Win Rate"] = display["Win Rate"].round(1).astype(str) + "%"
    st.dataframe(display.sort_values("Win Rate", ascending=False), hide_index=True, use_container_width=True)


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab_arch, tab_deck, tab_h2h = st.tabs(["vs Archetype", "vs Deck", "Head-to-Head"])

with tab_arch:
    st.subheader("Win Rate vs Opponent Archetype")
    has_data = df["P2_Arch"].notna() & (df["P2_Arch"] != "NA") & (df["P2_Arch"] != "")
    if not has_data.any():
        st.warning("No opponent archetype data. Assign opponent archetypes via the original tracker.")
    else:
        opp_winrate_chart(df[has_data], "P2_Arch", "Win Rate vs Opponent Archetype", "Opp. Archetype")

with tab_deck:
    st.subheader("Win Rate vs Opponent Deck")
    has_data = df["P2_Subarch"].notna() & (df["P2_Subarch"] != "NA") & (df["P2_Subarch"] != "")
    if not has_data.any():
        st.warning("No opponent deck data. Assign opponent deck names via the original tracker.")
    else:
        opp_winrate_chart(df[has_data], "P2_Subarch", "Win Rate vs Opponent Deck", "Opp. Deck")

with tab_h2h:
    st.subheader("Head-to-Head vs Opponent")

    opponents = sorted(df["P2"].dropna().unique().tolist())
    if not opponents:
        st.info("No opponents found.")
    else:
        selected = st.selectbox("Select opponent", options=opponents)
        opp_df = df[df["P2"] == selected]

        total = len(opp_df)
        wins = int(opp_df["Won"].sum())
        losses = total - wins
        wr = wins / total * 100 if total > 0 else 0.0

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Matches", total)
        c2.metric("Record", f"{wins}W – {losses}L")
        c3.metric("Win Rate", f"{wr:.1f}%")

        st.divider()

        # Match history vs this opponent
        cols = ["Date", "P1_Subarch", "P2_Subarch", "P1_Wins", "P2_Wins", "Result", "Format", "Match_Type"]
        rename_map = {
            "P1_Subarch": "Your Deck",
            "P2_Subarch": "Their Deck",
            "P1_Wins": "Your W",
            "P2_Wins": "Their W",
        }
        display = opp_df[cols].rename(columns=rename_map).copy()
        display["Date"] = opp_df["Date"].str[:10].values
        st.dataframe(display, hide_index=True, use_container_width=True)
