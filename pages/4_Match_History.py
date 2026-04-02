import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode

import db
import sidebar

CONFIG_FILE = Path(__file__).parent.parent / "mtgo_config.json"

COMMON_FORMATS = ["Premodern", "Legacy", "Vintage", "Modern", "Standard",
                  "Pauper", "Pioneer", "Commander", "Draft", "Sealed"]
RESULT_OPTIONS = ["Win", "Loss", "Unknown"]
WINNER_MAP     = {"Win": "P1", "Loss": "P2", "Unknown": "NA"}

st.set_page_config(page_title="Match History — MTGO Tracker", page_icon="📜", layout="wide")

filters = sidebar.render_sidebar()
st.title("📜 Match History")

if filters is None:
    st.stop()

conn = filters["conn"]
hero = filters["hero"]
cfg  = st.session_state.config

# ---------------------------------------------------------------------------
# Deck & format options
# ---------------------------------------------------------------------------

saved_decks     = cfg.get("saved_decks",     [])
saved_opp_decks = cfg.get("saved_opp_decks", [])
known_decks     = db.get_known_decks(conn, hero)
known_opp_decks = db.get_known_opp_decks(conn, hero)
my_deck_options  = sorted(set(known_decks     + saved_decks))
opp_deck_options = sorted(set(known_opp_decks + saved_opp_decks))
deck_options     = sorted(set(my_deck_options + opp_deck_options))  # for default deck picker

known_formats  = db.get_formats(conn, hero)
format_options = sorted(set(COMMON_FORMATS + known_formats))

default_format = cfg.get("default_format", "")
default_deck   = cfg.get("default_deck", "")

# ---------------------------------------------------------------------------
# Settings expander
# ---------------------------------------------------------------------------

with st.expander("⚙️ Defaults & deck management", expanded=(not default_format and not default_deck)):
    s1, s2, s3 = st.columns(3)

    with s1:
        st.markdown("**Default format**")
        sel_fmt = st.selectbox(
            "Auto-fill format for unset matches",
            options=["(none)"] + format_options,
            index=(format_options.index(default_format) + 1) if default_format in format_options else 0,
            key="def_fmt_sel", label_visibility="collapsed",
        )
        if st.button("Save format default"):
            cfg["default_format"] = "" if sel_fmt == "(none)" else sel_fmt
            st.session_state.config = cfg
            CONFIG_FILE.write_text(json.dumps(cfg, indent=2))
            st.rerun()

    with s2:
        st.markdown("**Default deck (yours)**")
        sel_deck = st.selectbox(
            "Auto-fill your deck for unset matches",
            options=["(none)"] + deck_options,
            index=(deck_options.index(default_deck) + 1) if default_deck in deck_options else 0,
            key="def_deck_sel", label_visibility="collapsed",
        )
        if st.button("Save deck default"):
            cfg["default_deck"] = "" if sel_deck == "(none)" else sel_deck
            st.session_state.config = cfg
            CONFIG_FILE.write_text(json.dumps(cfg, indent=2))
            st.rerun()

    with s3:
        st.markdown("**Add / remove saved decks**")
        new_deck = st.text_input("New deck name", key="new_deck_input", label_visibility="collapsed",
                                 placeholder="New deck name…")
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Add", key="add_deck_btn") and new_deck.strip():
                cfg["saved_decks"] = sorted(set(saved_decks + [new_deck.strip()]))
                st.session_state.config = cfg
                CONFIG_FILE.write_text(json.dumps(cfg, indent=2))
                st.rerun()
        with col_b:
            if saved_decks:
                to_del = st.selectbox("Remove", saved_decks, key="del_deck_sel",
                                      label_visibility="collapsed")
                if st.button("Remove", key="del_deck_btn"):
                    cfg["saved_decks"] = [d for d in saved_decks if d != to_del]
                    st.session_state.config = cfg
                    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))
                    st.rerun()

# ---------------------------------------------------------------------------
# Load & filter matches
# ---------------------------------------------------------------------------

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

# Filter bar
fc1, fc2, fc3, fc4 = st.columns([3, 1, 1, 1])
with fc1:
    search = st.text_input("Search", placeholder="opponent, deck, format…", label_visibility="collapsed")
with fc3:
    result_filter = st.radio("", ["All", "Wins", "Losses"], horizontal=True)
with fc4:
    na_filter = st.radio("Decks", ["All", "Unset"], horizontal=True, label_visibility="collapsed")

if search:
    mask = (
        df["P2"].str.contains(search, case=False, na=False)
        | df["P1_Subarch"].str.contains(search, case=False, na=False)
        | df["P2_Subarch"].str.contains(search, case=False, na=False)
    )
    df = df[mask]
if result_filter == "Wins":
    df = df[df["Result"] == "Win"]
elif result_filter == "Losses":
    df = df[df["Result"] == "Loss"]
if na_filter == "Unset":
    df = df[
        df["P1_Subarch"].isin(["NA", "", None]) |
        df["P2_Subarch"].isin(["NA", "", None]) |
        df["P1_Subarch"].isna() |
        df["P2_Subarch"].isna()
    ]

df = df.reset_index(drop=True)

# ---------------------------------------------------------------------------
# Build display dataframe
# ---------------------------------------------------------------------------

display_df = df[[
    "Date", "P1_Subarch", "P2", "P2_Subarch",
    "P1_Wins", "P2_Wins", "Result", "Format",
]].copy()
display_df["Date"]  = df["Date"].str[:10].values
display_df["Notes"] = df["Notes"].apply(
    lambda v: "📝" if isinstance(v, str) and v.strip() else ""
)
display_df = display_df.rename(columns={
    "P1_Subarch": "Your Deck",
    "P2":         "Opponent",
    "P2_Subarch": "Opp. Deck",
    "P1_Wins":    "Your W",
    "P2_Wins":    "Opp. W",
})
display_df = display_df[[
    "Date", "Your Deck", "Opponent", "Opp. Deck",
    "Your W", "Opp. W", "Result", "Notes",
]]

# ---------------------------------------------------------------------------
# Two-column layout: AgGrid left, edit panel right
# ---------------------------------------------------------------------------

col_table, col_edit = st.columns([3, 2])

with col_table:
    st.caption(f"{len(df)} matches — click a row to edit")

    # Row colour based on Result column
    row_style = JsCode("""
    function(params) {
        if (params.data.Result === 'Win') {
            return { 'color': '#2ecc71', 'fontWeight': '600' };
        } else if (params.data.Result === 'Loss') {
            return { 'color': '#e74c3c', 'fontWeight': '600' };
        }
        return { 'color': '#888888' };
    }
    """)

    gb = GridOptionsBuilder.from_dataframe(display_df)
    gb.configure_default_column(resizable=True, sortable=True, filter=False)
    gb.configure_selection(selection_mode="single", use_checkbox=False)
    gb.configure_column("Date",      width=100)
    gb.configure_column("Your Deck", width=130)
    gb.configure_column("Opponent",  width=120)
    gb.configure_column("Opp. Deck", width=130)
    gb.configure_column("Your W",    width=75,  headerName="Your W")
    gb.configure_column("Opp. W",    width=75,  headerName="Opp. W")
    gb.configure_column("Result",    width=80)
    gb.configure_column("Notes",     width=60,  headerName="📝")
    gb.configure_grid_options(
        getRowStyle=row_style,
        wrapHeaderText=True,
        autoHeaderHeight=True,
    )

    dark_css = {
        ".ag-root-wrapper":                     {"background-color": "#0e1117 !important", "border-color": "#2d3147 !important"},
        ".ag-header":                           {"background-color": "#1a1d27 !important", "border-color": "#2d3147 !important"},
        ".ag-header-cell":                      {"background-color": "#1a1d27 !important", "color": "#fafafa !important"},
        ".ag-header-cell-label":                {"color": "#fafafa !important"},
        ".ag-row":                              {"background-color": "#0e1117 !important", "border-color": "#2d3147 !important"},
        ".ag-row-hover":                        {"background-color": "#1e2130 !important"},
        ".ag-row-selected":                     {"background-color": "#2a3f6f !important"},
        ".ag-cell":                             {"border-color": "#2d3147 !important"},
        ".ag-paging-panel":                     {"background-color": "#0e1117 !important", "color": "#fafafa !important"},
    }

    grid_response = AgGrid(
        display_df,
        gridOptions=gb.build(),
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        allow_unsafe_jscode=True,
        use_container_width=True,
        height=560,
        theme="alpine",
        custom_css=dark_css,
    )

    selected = grid_response.get("selected_rows")
    # selected_rows can be a DataFrame or list depending on aggrid version
    import pandas as pd
    if isinstance(selected, pd.DataFrame):
        has_selection = not selected.empty
    else:
        has_selection = bool(selected)

with col_edit:
    if not has_selection:
        st.caption("← Click a row to edit it")
    else:
        # Match the selected row back to original df by Date + Opponent
        if isinstance(selected, pd.DataFrame):
            sel = selected.iloc[0]
        else:
            sel = selected[0]

        # Find matching row in df using Date + Opponent (robust across filter changes)
        mask = (
            (df["Date"].str[:10] == sel["Date"]) &
            (df["P2"] == sel["Opponent"])
        )
        matches = df[mask]
        if matches.empty:
            st.caption("← Click a row to edit it")
            st.stop()

        match_row = matches.iloc[0]
        match_id  = match_row["Match_ID"]

        st.markdown(f"**{match_row['Date'][:10]}** · You vs **{match_row['P2']}**")

        cur_deck     = match_row.get("P1_Subarch", "") or "NA"
        cur_opp_deck = match_row.get("P2_Subarch", "") or "NA"
        cur_result   = match_row.get("Result", "Unknown")
        cur_notes    = match_row.get("Notes", "")    or ""

        my_opts  = ["NA"] + [d for d in my_deck_options  if d != "NA"]
        opp_opts = ["NA"] + [d for d in opp_deck_options if d != "NA"]

        if cur_deck     not in my_opts:  my_opts.insert(1,  cur_deck)
        if cur_opp_deck not in opp_opts: opp_opts.insert(1, cur_opp_deck)

        def _idx(lst, val, fallback=0):
            try:    return lst.index(val)
            except: return fallback

        with st.form("edit_form", border=True):
            new_deck     = st.selectbox("Your Deck",  my_opts,  index=_idx(my_opts,  cur_deck))
            new_deck_txt = st.text_input("… or type a new deck name (yours)", value="",
                                         placeholder="Leave blank to use selection above")

            new_opp_deck = st.selectbox("Opp. Deck",  opp_opts, index=_idx(opp_opts, cur_opp_deck))
            new_opp_txt  = st.text_input("… or type a new deck name (opp.)", value="",
                                         placeholder="Leave blank to use selection above")

            new_result   = st.selectbox("Result", RESULT_OPTIONS, index=_idx(RESULT_OPTIONS, cur_result))
            new_notes    = st.text_area("Notes", value=cur_notes, height=100,
                                        placeholder="Optional match notes…")

            if st.form_submit_button("💾 Save", type="primary", use_container_width=True):
                final_deck     = new_deck_txt.strip() or new_deck
                final_opp_deck = new_opp_txt.strip()  or new_opp_deck
                db.update_match(conn, match_id, {
                    "P1_Subarch":   final_deck,
                    "P2_Subarch":   final_opp_deck,
                    "Match_Winner": WINNER_MAP.get(new_result, "NA"),
                    "Notes":        new_notes,
                })
                if final_deck     and final_deck     != "NA" and final_deck     not in my_deck_options:
                    cfg["saved_decks"]     = sorted(set(saved_decks     + [final_deck]))
                if final_opp_deck and final_opp_deck != "NA" and final_opp_deck not in opp_deck_options:
                    cfg["saved_opp_decks"] = sorted(set(saved_opp_decks + [final_opp_deck]))
                if cfg.get("saved_decks") != saved_decks or cfg.get("saved_opp_decks") != saved_opp_decks:
                    st.session_state.config = cfg
                    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))
                st.success("Saved.")
                st.rerun()

# ---------------------------------------------------------------------------
# Match record / cards played (shown below when a match is selected)
# ---------------------------------------------------------------------------

if has_selection:
    import pandas as pd

    st.divider()
    st.subheader("🃏 Match Record")

    plays = db.get_match_plays(conn, match_id)
    games = db.get_match_games(conn, match_id)

    if plays.empty:
        st.caption("No play data found for this match.")
    else:
        hero_name = match_row["P1"]
        opp_name  = match_row["P2"]

        # Only show meaningful actions (skip Draws / Attacks)
        SHOW_ACTIONS = {"Casts", "Land Drop", "Activated Ability"}
        plays = plays[plays["Action"].isin(SHOW_ACTIONS)]
        plays = plays[plays["Primary_Card"].notna() & (plays["Primary_Card"] != "NA")]

        game_nums = sorted(plays["Game_Num"].unique())
        tabs = st.tabs([f"Game {g}" for g in game_nums])

        for tab, gnum in zip(tabs, game_nums):
            with tab:
                gplays = plays[plays["Game_Num"] == gnum]

                # Game result header
                if not games.empty:
                    grow = games[games["Game_Num"] == gnum]
                    if not grow.empty:
                        grow = grow.iloc[0]
                        if grow["Game_Winner"] == "P1":
                            st.markdown("**Result: 🟢 Win**")
                        elif grow["Game_Winner"] == "P2":
                            st.markdown("**Result: 🔴 Loss**")

                your_plays = gplays[gplays["Casting_Player"] == hero_name]
                opp_plays  = gplays[gplays["Casting_Player"] == opp_name]

                def _card_list(subset):
                    if subset.empty:
                        return pd.DataFrame(columns=["Card", "Times"])
                    return (
                        subset.groupby("Primary_Card", sort=False)
                        .agg(Times=("Primary_Card", "count"))
                        .reset_index()
                        .rename(columns={"Primary_Card": "Card"})
                    )

                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"**You ({hero_name})**")
                    st.dataframe(_card_list(your_plays), hide_index=True, use_container_width=True)
                with c2:
                    st.markdown(f"**Opponent ({opp_name})**")
                    st.dataframe(_card_list(opp_plays), hide_index=True, use_container_width=True)
