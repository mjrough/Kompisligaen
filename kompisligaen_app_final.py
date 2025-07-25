
import streamlit as st
import pandas as pd
import requests
from pulp import LpProblem, LpVariable, LpMaximize, lpSum, LpBinary
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image

from PIL import Image

with st.sidebar:
    st.image("A_logo_design_for_Kompisligaen.png", width=200)
    st.markdown("## Kompisligaen")
    st.markdown("Bygg, del og vinn med laget ditt 💥")


st.set_page_config(page_title="FPL Optimizer Pro", layout="wide")
st.title("⚽ FPL Optimizer Pro")
st.caption("Optimaliser laget ditt med form, xG, kamper og chips!")

# === HENT FPL DATA ===
@st.cache_data(ttl=3600)
def get_fpl_data():
    url = "https://fantasy.premierleague.com/api/bootstrap-static/"
    r = requests.get(url)
    if r.status_code == 200:
        data = r.json()
        elements = pd.DataFrame(data['elements'])
        teams = pd.DataFrame(data['teams'])
        elements['team'] = elements['team'].map(teams.set_index('id')['name'])
        elements['now_cost'] = elements['now_cost'] / 10
        return elements, teams
    else:
        st.error("Kunne ikke hente data.")
        return pd.DataFrame(), pd.DataFrame()

players_df, teams_df = get_fpl_data()

# === TESTPANEL ===
with st.expander("🧪 Testpanel"):
    if st.button("Test API"):
        st.success(f"Hentet {len(players_df)} spillere fra FPL.")

# === HENT LAG MED ID ===
with st.expander("👤 Mitt FPL-lag"):
    fpl_id = st.text_input("FPL-lag-ID:")
    if fpl_id:
        r = requests.get(f"https://fantasy.premierleague.com/api/entry/{fpl_id}/event/1/picks/")
        if r.status_code == 200:
            st.success("Lag hentet!")
            st.json(r.json())
        else:
            st.warning("Fant ikke laget.")

# === OPTIMALISERING ===
with st.expander("⚙️ Optimaliser lag"):
    budget = st.slider("Budsjett", 80.0, 105.0, 100.0, 0.5)
    num_players = 15
    df = players_df[players_df["minutes"] > 0].nlargest(60, "total_points")

    model = LpProblem("FPL_Optimization", LpMaximize)
    choices = LpVariable.dicts("Player", df.index, cat=LpBinary)
    model += lpSum(choices[i]*df.loc[i, "total_points"] for i in df.index)
    model += lpSum(choices[i]*df.loc[i, "now_cost"] for i in df.index) <= budget
    model += lpSum(choices[i] for i in df.index) == num_players
    model.solve()
    selected = [i for i in df.index if choices[i].value() == 1]
    result_df = df.loc[selected][["web_name", "team", "now_cost", "total_points"]]
    result_df = result_df.rename(columns={"web_name": "Spiller", "team": "Lag", "now_cost": "Pris", "total_points": "Poeng"})
    st.dataframe(result_df.reset_index(drop=True))

# === SAMMENLIGNING ===
with st.expander("📊 Sammenlign lag"):
    if 'saved_teams' not in st.session_state:
        st.session_state['saved_teams'] = []
    if st.button("💾 Lagre dette laget"):
        st.session_state['saved_teams'].append(result_df)
    for idx, df in enumerate(st.session_state['saved_teams']):
        st.markdown(f"**Lag {idx+1}**")
        st.dataframe(df.reset_index(drop=True))
        st.write(f"Sum pris: £{df['Pris'].sum():.1f} — Poeng: {df['Poeng'].sum():.0f}")

# === CHIPS OG FORVENTEDE POENG ===
@st.cache_data(ttl=3600)
def simulate_future_points(df, weeks=5):
    np.random.seed(42)
    for i in range(1, weeks+1):
        df[f"GW{i}_pts"] = df["total_points"] / 38 + np.random.normal(0, 1, size=len(df))
        df[f"GW{i}_pts"] = df[f"GW{i}_pts"].clip(lower=0)
    return df

with st.expander("🔮 Chips og fremtidige poeng"):
    chips = st.multiselect("Velg chips", ["Bench Boost", "Triple Captain", "Free Hit"])
    if 'result_df' in locals():
        sim_df = simulate_future_points(result_df.copy())
        st.dataframe(sim_df[["Spiller", "Poeng", "Pris"] + [f"GW{i}_pts" for i in range(1, 6)]])
        if "Triple Captain" in chips:
            tc_bonus = sim_df.iloc[0][[f"GW{i}_pts" for i in range(1, 6)]].sum()
            st.success(f"Triple Captain gir ca. {tc_bonus:.1f} ekstra poeng")
        if "Bench Boost" in chips:
            bench_pts = sim_df.tail(4)[[f"GW{i}_pts" for i in range(1, 6)]].sum().sum()
            st.success(f"Bench Boost gir ca. {bench_pts:.1f} poeng")

# === FIXTURE + xG/xA ===
@st.cache_data(ttl=3600)
def get_fixture_data():
    r = requests.get("https://fantasy.premierleague.com/api/fixtures/")
    return pd.DataFrame(r.json()) if r.status_code == 200 else pd.DataFrame()

@st.cache_data(ttl=3600)
def add_xg_form(df):
    np.random.seed(0)
    df["xG_form"] = np.round(np.random.uniform(0.1, 0.6, len(df)), 2)
    df["xA_form"] = np.round(np.random.uniform(0.05, 0.4, len(df)), 2)
    return df

with st.expander("📅 Fixtures og xG/xA"):
    fixtures = get_fixture_data()
    if not fixtures.empty:
        df_xg = add_xg_form(players_df.copy())
        st.subheader("Topp formspillere")
        st.dataframe(df_xg.sort_values(by=["xG_form", "xA_form"], ascending=False)[["web_name", "team", "xG_form", "xA_form"]].head(15))


# --- NESTE NIVÅ: CHIPS OG FORVENTEDE POENG OVER FLERE RUNDER ---

import numpy as np

# Dummy simulering av forventet poeng per spiller for neste 5 kamper
@st.cache_data(ttl=3600)
def simulate_future_points(df, weeks=5):
    np.random.seed(42)
    for i in range(1, weeks+1):
        df[f"GW{i}_pts"] = df["total_points"] / 38 + np.random.normal(0, 1, size=len(df))
        df[f"GW{i}_pts"] = df[f"GW{i}_pts"].clip(lower=0)
    return df

with st.expander("🔮 Chips og fremtidige poengsimuleringer"):
    selected_chips = st.multiselect("Velg chips som skal simuleres", ["Bench Boost", "Triple Captain", "Free Hit"])
    fpl_df_future = simulate_future_points(players_df.copy())

    if "result_df" in locals():
        result_df = simulate_future_points(result_df.copy())
        st.subheader("📅 Forventet poeng de neste 5 rundene (simulert)")
        st.dataframe(result_df[["Spiller", "Poeng", "Pris"] + [f"GW{i}_pts" for i in range(1, 6)]])
    else:
        st.info("⚠️ Kjør først en optimalisering for å vise fremtidspoeng.")

    if "Triple Captain" in selected_chips and "result_df" in locals():
        tc_bonus = result_df.iloc[0][[f"GW{i}_pts" for i in range(1, 6)]].sum()
        st.success(f"📈 Simulert Triple Captain-effekt: {tc_bonus:.1f} ekstra poeng")

    if "Bench Boost" in selected_chips and "result_df" in locals():
        bench_pts = result_df.tail(4)[[f"GW{i}_pts" for i in range(1, 6)]].sum().sum()
        st.success(f"📈 Simulert Bench Boost-poeng fra benken: {bench_pts:.1f}")


# --- NESTE NIVÅ: Fixtures + xG/xA-baserte vurderinger ---

@st.cache_data(ttl=3600)
def get_fixture_data():
    url = "https://fantasy.premierleague.com/api/fixtures/"
    r = requests.get(url)
    if r.status_code == 200:
        fixtures = pd.DataFrame(r.json())
        return fixtures
    else:
        st.error("Kunne ikke hente kampprogram.")
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def attach_fixture_difficulty(players, fixtures, teams_df):
    future = fixtures[(fixtures['event'].notnull()) & (fixtures['event'] >= 1)]
    difficulty = []

    for _, row in players.iterrows():
        player_team = row['team']
        team_fixtures = future[(future['team_h'] == player_team) | (future['team_a'] == player_team)]
        next5 = team_fixtures.head(5)
        avg_difficulty = next5['team_h_difficulty'].mean() if len(next5) > 0 else 3
        difficulty.append(avg_difficulty)

    players['fixture_difficulty'] = difficulty
    return players

@st.cache_data(ttl=3600)
def add_xg_factors(players_df):
    np.random.seed(0)
    players_df["xG_form"] = np.round(np.random.uniform(0.1, 0.6, len(players_df)), 2)
    players_df["xA_form"] = np.round(np.random.uniform(0.05, 0.4, len(players_df)), 2)
    return players_df

with st.expander("📅 Fixture-analyse og xG/xA"):
    fixture_data = get_fixture_data()
    if not fixture_data.empty:
        players_xg = add_xg_factors(players_df.copy())
        players_full = attach_fixture_difficulty(players_xg, fixture_data, players_df)

        top_form = players_full.sort_values(by=["xG_form", "xA_form"], ascending=False)
        st.subheader("🔥 Spillere med høyest xG/xA-form")
        st.dataframe(top_form[["web_name", "team", "xG_form", "xA_form", "fixture_difficulty"]].head(15))


import json

# === EKSPORT TIL JSON / E-POST ===
with st.expander("📤 Eksport og deling"):
    if 'result_df' in locals():
        json_data = result_df.to_dict(orient="records")
        json_str = json.dumps(json_data, indent=2)
        st.download_button("💾 Last ned som JSON", data=json_str, file_name="mitt_optimaliserte_lag.json")

        email_text = "\n".join([f"{r['Spiller']} ({r['Lag']}) - £{r['Pris']} - {r['Poeng']}p" for _, r in result_df.iterrows()])
        st.text_area("✉️ Del via e-post eller kopiér tekst", value=email_text, height=200)

# === VISUELL LAGOPPSTILLING ===
with st.expander("📐 Visuell lagoppstilling"):
    if 'result_df' in locals():
        st.subheader("⚽ 4-4-2 Formasjon (eksempelvis)")

        starters = result_df.head(11).reset_index(drop=True)
        bench = result_df.tail(4).reset_index(drop=True)

        def display_row(names):
            cols = st.columns(len(names))
            for i, name in enumerate(names):
                cols[i].markdown(f"🔹 **{name}**", unsafe_allow_html=True)

        gk = starters.iloc[0]["Spiller"]
        defnames = starters.iloc[1:5]["Spiller"].tolist()
        mid = starters.iloc[5:9]["Spiller"].tolist()
        fwd = starters.iloc[9:]["Spiller"].tolist()

        display_row([gk])
        display_row(defnames)
        display_row(mid)
        display_row(fwd)

        st.caption("Benk:")
        st.write(", ".join(bench["Spiller"].tolist()))
