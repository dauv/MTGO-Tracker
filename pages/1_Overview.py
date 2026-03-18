import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

import db
import sidebar

st.set_page_config(page_title="Overview — MTGO Tracker", page_icon="📊", layout="wide")

filters = sidebar.render_sidebar()
st.title("📊 Overview")

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
    st.info("No matches found for the current filters. Try importing logs or widening the date range.")
    st.stop()

# ---------------------------------------------------------------------------
# Key metrics
# ---------------------------------------------------------------------------

total = len(df)
wins = int(df["Won"].sum())
losses = total - wins
winrate = wins / total * 100

col1, col2, col3, col4 = st.columns(4)
col1.metric("Matches", total)
col2.metric("Wins", wins)
col3.metric("Losses", losses)
col4.metric("Win Rate", f"{winrate:.1f}%")

st.divider()

# ---------------------------------------------------------------------------
# Recent form — last 20 matches as colour-coded W/L badges
# ---------------------------------------------------------------------------

st.subheader("Recent Form")
recent = df.head(20)
badges = []
for _, row in recent.iterrows():
    color = "#2ecc71" if row["Won"] else "#e74c3c"
    label = "W" if row["Won"] else "L"
    deck = row.get("P1_Subarch") or "?"
    opp_deck = row.get("P2_Subarch") or "?"
    opp = row.get("P2") or "?"
    tip = f"{deck} vs {opp} ({opp_deck})"
    badges.append(
        f'<span title="{tip}" style="background:{color};color:white;'
        f'padding:4px 9px;border-radius:5px;font-weight:bold;'
        f'margin:2px;display:inline-block;cursor:default">{label}</span>'
    )
st.markdown(" ".join(badges), unsafe_allow_html=True)

st.divider()

# ---------------------------------------------------------------------------
# Winrate over time (monthly rolling)
# ---------------------------------------------------------------------------

st.subheader("Win Rate Over Time")

df_time = df.dropna(subset=["ParsedDate"]).copy()
if not df_time.empty:
    df_time["Month"] = df_time["ParsedDate"].dt.to_period("M").dt.to_timestamp()
    monthly = (
        df_time.groupby("Month")
        .agg(Wins=("Won", "sum"), Matches=("Won", "count"))
        .reset_index()
    )
    monthly["Winrate"] = monthly["Wins"] / monthly["Matches"] * 100
    monthly["Label"] = monthly.apply(
        lambda r: f"{r['Winrate']:.0f}%  ({int(r['Wins'])}W–{int(r['Matches']-r['Wins'])}L)", axis=1
    )

    fig = px.line(
        monthly,
        x="Month",
        y="Winrate",
        markers=True,
        text="Label",
        labels={"Winrate": "Win Rate %", "Month": ""},
    )
    fig.update_traces(
        textposition="top center",
        hovertemplate="%{x|%b %Y}<br>Win Rate: %{y:.1f}%<extra></extra>",
        line=dict(color="#3498db", width=2),
        marker=dict(size=8),
    )
    fig.add_hline(y=50, line_dash="dash", line_color="gray", opacity=0.4, annotation_text="50%")
    fig.update_layout(
        yaxis=dict(range=[0, 105], ticksuffix="%"),
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# Cumulative wins & losses over time
# ---------------------------------------------------------------------------

st.subheader("Cumulative Record")

df_sorted = df_time.sort_values("ParsedDate").copy()
df_sorted["CumWins"] = df_sorted["Won"].cumsum()
df_sorted["CumLosses"] = (1 - df_sorted["Won"]).cumsum()

fig2 = go.Figure()
fig2.add_trace(
    go.Scatter(
        x=df_sorted["ParsedDate"],
        y=df_sorted["CumWins"],
        name="Wins",
        line=dict(color="#2ecc71", width=2),
        hovertemplate="%{x|%Y-%m-%d}<br>Wins: %{y}<extra></extra>",
    )
)
fig2.add_trace(
    go.Scatter(
        x=df_sorted["ParsedDate"],
        y=df_sorted["CumLosses"],
        name="Losses",
        line=dict(color="#e74c3c", width=2),
        hovertemplate="%{x|%Y-%m-%d}<br>Losses: %{y}<extra></extra>",
    )
)
fig2.update_layout(
    yaxis_title="Matches",
    xaxis_title="",
    hovermode="x unified",
    legend=dict(orientation="h", y=1.02, x=1, xanchor="right"),
)
st.plotly_chart(fig2, use_container_width=True)
