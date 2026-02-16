import streamlit as st
import pandas as pd
import os, json
from fpdf import FPDF
from streamlit_gsheets import GSheetsConnection

# --- 1. KONFIGURACE A HESLO (MUSÍ BÝT PRVNÍ) ---
st.set_page_config(page_title="Pétanque Pro", layout="wide")

def over_heslo():
    if "autentizovan" not in st.session_state:
        st.session_state.autentizovan = False
    
    if not st.session_state.autentizovan:
        # Načtení hesla ze Secrets (nebo nouzové admin123)
        try:
            master_heslo = str(st.secrets["access_password"]).strip()
        except:
            master_heslo = "admin123"
        
        st.title("🔒 Přístup omezen")
        vstup = st.text_input("Zadejte heslo turnaje:", type="password")
        
        if st.button("Vstoupit"):
            if vstup.strip() == master_heslo:
                st.session_state.autentizovan = True
                st.rerun()
            else:
                st.error("Nesprávné heslo!")
        st.stop()

# Spuštění kontroly hesla
over_heslo()

# --- 2. PŘIPOJENÍ GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def uloz_do_google():
    stav = {
        "nazev_akce": st.session_state.nazev_akce,
        "datum_akce": st.session_state.get("datum_akce", ""),
        "kolo": st.session_state.kolo,
        "max_kol": st.session_state.max_kol,
        "system": st.session_state.system,
        "tymy": st.session_state.tymy.to_dict(orient="records"),
        "historie": st.session_state.historie
    }
    df_save = pd.DataFrame([{"stav_json": json.dumps(stav, ensure_ascii=False)}])
    conn.update(worksheet="Stav", data=df_save)

def nacti_z_google():
    try:
        df = conn.read(worksheet="Stav", ttl=0)
        if not df.empty and "stav_json" in df.columns:
            r = df.iloc[0]["stav_json"]
            if r and r != "{}" and not pd.isna(r):
                return json.loads(r)
    except: pass
    return None

# --- 3. INICIALIZACE DAT ---
if "kolo" not in st.session_state:
    data = nacti_z_google()
    if data:
        st.session_state.nazev_akce = data.get("nazev_akce", "Pétanque Turnaj")
        st.session_state.datum_akce = data.get("datum_akce", "")
        st.session_state.kolo = data.get("kolo", 0)
        st.session_state.max_kol = data.get("max_kol", 3)
        st.session_state.system = data.get("system", "Švýcar")
        st.session_state.tymy = pd.DataFrame(data["tymy"])
        st.session_state.historie = data.get("historie", [])
        
        # Pojistka pro stará data: přidá chybějící sloupce
        for col in ["Výhry", "Skóre +", "Skóre -", "Rozdíl", "Buchholz", "Zápasy"]:
            if col not in st.session_state.tymy.columns:
                st.session_state.tymy[col] = 0
    else:
        st.session_state.nazev_akce = "Pétanque Turnaj"
        st.session_state.datum_akce = ""
        st.session_state.kolo = 0
        st.session_state.max_kol = 3
        st.session_state.system = "Švýcar"
        st.session_state.tymy = None
        st.session_state.historie = []

# --- 4. LOGIKA PÁROVÁNÍ (ŠVÝCAR BEZ OPAKOVÁNÍ) ---
def generuj_parovani_svycar(tymy_list, historie):
    hraci = tymy_list.copy()
    odehrane = set()
    for h in historie:
        odehrane.add(tuple(sorted((h["Hráč/Tým 1"], h["Hráč/Tým 2"]))))

    parovani = []
    p_hraci = hraci.copy()
    while len(p_hraci) > 1:
        h1 = p_hraci[0]
        nasel = False
        for i in range(1, len(p_hraci)):
            h2 = p_hraci[i]
            if tuple(sorted((h1, h2))) not in odehrane:
                parovani.append((h1, h2))
                p_hraci.pop(i)
                p_hraci.pop(0)
                nasel = True
                break
        if not nasel:
            h2 = p_hraci[1]
            parovani.append((h1, h2))
            p_hraci.pop(1)
            p_hraci.pop(0)
    return parovani

def prepocitej_buchholz():
    t_df = st.session_state.tymy
    hist = st.session_state.historie
    for idx, r in t_df.iterrows():
        jm = r["Hráč/Tým"]
        souperi = [h["Hráč/Tým 2"] if h["Hráč/Tým 1"] == jm else h["Hráč/Tým 1"] 
                   for h in hist if h["Hráč/Tým 1"] == jm or h["Hráč/Tým 2"] == jm]
        b = sum(t_df[t_df["Hráč/Tým"] == s]["Výhry"].iloc[0] for s in souperi if s != "VOLNÝ LOS")
        st.session_state.tymy.at[idx, "Buchholz"] = int(b)
        st.session_state.tymy.at[idx, "Zápasy"] = len(souperi)
        st.session_state.tymy.at[idx, "Rozdíl"] = st.session_state.tymy.at[idx, "Skóre +"] - st.session_state.tymy.at[idx, "Skóre -"]

# --- 5. HLAVNÍ OBSAH ---
if st.session_state.kolo == 0:
    st.title("🏆 Nový turnaj")
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.nazev_akce = st.text_input("Název:", st.session_state.nazev_akce)
        st.session_state.system = st.radio("Systém:", ["Švýcar", "Každý s každým"])
        st.session_state.max_kol = st.number_input("Počet kol:", 1, 15, 3)
    with col2:
        v = st.text_area("Hráči (jeden na řádek):")
    
    if st.button("Zahájit", type="primary"):
        h_list = [i.strip() for i in v.split('\n') if i.strip()]
        if len(h_list) >= 2:
            if len(h_list) % 2 != 0: h_list.append("VOLNÝ LOS")
            st.session_state.tymy = pd.DataFrame([{"Hráč/Tým": x, "Výhry": 0, "Skóre +": 0, "Skóre -": 0, "Rozdíl": 0, "Buchholz": 0, "Zápasy": 0} for x in h_list])
            st.session_state.kolo = 1
            uloz_do_google()
            st.rerun()

elif st.session_state.kolo <= st.session_state.max_kol:
    st.header(f"🏟️ Kolo {st.session_state.kolo} / {st.session_state.max_kol}")
    
    if st.session_state.system == "Švýcar":
        df_s = st.session_state.tymy.sort_values(by=["Výhry", "Buchholz", "Rozdíl"], ascending=False)
        zapasy = generuj_parovani_svycar(df_s["Hráč/Tým"].tolist(), st.session_state.historie)
    else:
        h = st.session_state.tymy["Hráč/Tým"].tolist()
        n = len(h)
        s = (st.session_state.kolo - 1) % (n - 1)
        rot = [h[0]] + (h[1:][-s:] + h[1:][:-s] if s > 0 else h[1:])
        zapasy = [(rot[i], rot[n-1-i]) for i in range(n//2)]

    aktualni = []
    for i, (t1, t2) in enumerate(zapasy):
        c1, c2, c3, c4 = st.columns([3, 1, 1, 3])
        is_bye = (t1 == "VOLNÝ LOS" or t2 == "VOLNÝ LOS")
        with c1: st.write(f"**{t1}**")
        with c2: s1 = st.number_input("Body", 0, 13, 13 if t2 == "VOLNÝ LOS" else 0, key=f"s1_{i}")
        with c3: s2 = st.number_input("Body", 0, 13, 13 if t1 == "VOLNÝ LOS" else 0, key=f"s2_{i}")
        with c4: st.write(f"**{t2}**")
        aktualni.append((t1, s1, t2, s2))
    
    if st.button("Uložit kolo"):
        for t1, s1, t2, s2 in aktualni:
            for t, sp, sm in [(t1, s1, s2), (t2, s2, s1)]:
                idx = st.session_state.tymy[st.session_state.tymy["Hráč/Tým"] == t].index[0]
                st.session_state.tymy.at[idx, "Skóre +"] += sp
                st.session_state.tymy.at[idx, "Skóre -"] += sm
                if sp > sm: st.session_state.tymy.at[idx, "Výhry"] += 1
            st.session_state.historie.append({"Kolo": st.session_state.kolo, "Hráč/Tým 1": t1, "S1": s1, "S2": s2, "Hráč/Tým 2": t2})
        prep
