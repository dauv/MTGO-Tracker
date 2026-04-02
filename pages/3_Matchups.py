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
    st.info("No matches found.")
    st.stop()

gdf = db.get_games(
    conn, hero,
    start_date=filters["start_date"],
    end_date=filters["end_date"],
    formats=filters["formats"],
    match_types=filters["match_types"],
    decks=filters["decks"],
)

known_decks = db.get_known_decks(conn, hero)

fc1, fc2 = st.columns([2, 1])
with fc1:
    deck_options = ["All my decks"] + known_decks
    selected_deck = st.selectbox("Your deck", deck_options, key="matchup_deck")
with fc2:
    min_matches = st.slider("Min. matches", 1, 20, 2, key="matchup_min")

# Apply deck filter to both match and game data
if selected_deck != "All my decks":
    df  = df[df["P1_Subarch"] == selected_deck]
    if not gdf.empty:
        gdf = gdf[gdf["P1_Subarch"] == selected_deck]

if df.empty:
    st.info(f"No matches found for deck **{selected_deck}**.")
    st.stop()


def _game_stats_by(gdf, group_col):
    """Return GW%, Pre GW%, Post GW% grouped by group_col."""
    if gdf.empty or group_col not in gdf.columns:
        return None
    has_col = gdf[group_col].notna() & ~gdf[group_col].isin(["NA", ""])
    decided = gdf[gdf["Decided"] & has_col]
    if decided.empty:
        return None

    def _pct(subset, label):
        s = (
            subset.groupby(group_col)
            .agg(W=("GameWon", "sum"), T=("GameWon", "count"))
            .reset_index()
        )
        s[label] = s["W"] / s["T"] * 100
        return s[[group_col, label]]

    stats = _pct(decided, "GW%")
    stats = stats.merge(_pct(decided[decided["Preboard"]],  "Pre GW%"),  on=group_col, how="left")
    stats = stats.merge(_pct(decided[~decided["Preboard"]], "Post GW%"), on=group_col, how="left")
    return stats


def _fmt_pct(v):
    return f"{v:.1f}%" if v == v else "—"  # NaN-safe


def opp_winrate_chart(match_data, game_data, opp_col, title, rename):
    g = (
        match_data.groupby(opp_col)
        .agg(Matches=("Won", "count"), Wins=("Won", "sum"))
        .reset_index()
    )
    g["Losses"] = g["Matches"] - g["Wins"]
    g["MW%"] = g["Wins"] / g["Matches"] * 100
    g = g[g["Matches"] >= min_matches].sort_values("MW%", ascending=True)

    if g.empty:
        st.info(f"No entries with {min_matches}+ matches.")
        return

    # Chart
    label_col = g.apply(
        lambda r: f"{r['MW%']:.0f}%  ({int(r['Wins'])}W–{int(r['Losses'])}L)", axis=1
    )
    fig = px.bar(
        g,
        y=opp_col,
        x="MW%",
        orientation="h",
        color="MW%",
        color_continuous_scale=["#e74c3c", "#f39c12", "#2ecc71"],
        range_color=[30, 70],
        text=label_col,
        title=title,
        labels={opp_col: "", "MW%": "Match Win %"},
    )
    fig.add_vline(x=50, line_dash="dash", line_color="gray", opacity=0.4)
    fig.update_traces(textposition="outside")
    fig.update_layout(
        xaxis=dict(range=[0, 115], ticksuffix="%"),
        coloraxis_showscale=False,
        height=max(300, len(g) * 40 + 100),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Table — merge in game stats
    display = g[[opp_col, "Matches", "Wins", "Losses", "MW%"]].rename(columns={opp_col: rename})
    gstats = _game_stats_by(game_data, opp_col)
    if gstats is not None:
        display = display.merge(
            gstats.rename(columns={opp_col: rename}), on=rename, how="left"
        )

    for col in ["MW%", "GW%", "Pre GW%", "Post GW%"]:
        if col in display.columns:
            display[col] = display[col].apply(_fmt_pct)

    st.dataframe(
        display.sort_values("MW%", ascending=False),
        hide_index=True, use_container_width=True,
    )


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab_deck, tab_h2h = st.tabs(["vs Deck", "Head-to-Head"])

with tab_deck:
    st.subheader("Win Rate vs Opponent Deck")
    has_data = df["P2_Subarch"].notna() & (df["P2_Subarch"] != "NA") & (df["P2_Subarch"] != "")
    if not has_data.any():
        st.warning("No opponent deck data. Assign opponent deck names in Match History.")
    else:
        opp_winrate_chart(df[has_data], gdf, "P2_Subarch", "Win Rate vs Opponent Deck", "Opp. Deck")

with tab_h2h:
    st.subheader("Head-to-Head vs Opponent")

    opponents = sorted(df["P2"].dropna().unique().tolist())
    if not opponents:
        st.info("No opponents found.")
    else:
        selected = st.selectbox("Select opponent", options=opponents)
        opp_df  = df[df["P2"] == selected]
        opp_gdf = gdf[gdf["P2_Subarch"].notna()] if not gdf.empty else gdf  # keep all games for this opponent
        # Filter games to this opponent via Match_ID
        if not gdf.empty:
            opp_match_ids = set(opp_df["Match_ID"])
            opp_gdf = gdf[gdf["Match_ID"].isin(opp_match_ids)]
        else:
            opp_gdf = gdf

        total  = len(opp_df)
        wins   = int(opp_df["Won"].sum())
        losses = total - wins
        mwr    = wins / total * 100 if total > 0 else 0.0

        # Game win stats
        decided = opp_gdf[opp_gdf["Decided"]] if not opp_gdf.empty else opp_gdf
        g_total = len(decided)
        g_wins  = int(decided["GameWon"].sum()) if g_total else 0
        gwr     = g_wins / g_total * 100 if g_total else None

        pre  = decided[decided["Preboard"]]  if not decided.empty else decided
        post = decided[~decided["Preboard"]] if not decided.empty else decided
        pre_wr  = int(pre["GameWon"].sum())  / len(pre)  * 100 if len(pre)  else None
        post_wr = int(post["GameWon"].sum()) / len(post) * 100 if len(post) else None

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Matches",      total)
        c2.metric("Record",       f"{wins}W – {losses}L")
        c3.metric("Match Win %",  f"{mwr:.1f}%")
        c4.metric("Game Win %",   f"{gwr:.1f}%" if gwr is not None else "—")
        c5.metric("Pre / Post GW%",
                  f"{pre_wr:.1f}% / {post_wr:.1f}%"
                  if pre_wr is not None and post_wr is not None else "—")

        st.divider()

        cols = ["Date", "P1_Subarch", "P2_Subarch", "P1_Wins", "P2_Wins", "Result", "Format"]
        rename_map = {
            "P1_Subarch": "Your Deck", "P2_Subarch": "Their Deck",
            "P1_Wins": "Your W",      "P2_Wins":    "Their W",
        }
        display = opp_df[cols].rename(columns=rename_map).copy()
        display["Date"] = opp_df["Date"].str[:10].values
        st.dataframe(display, hide_index=True, use_container_width=True)
