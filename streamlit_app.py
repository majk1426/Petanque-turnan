import streamlit as st
import pandas as pd
import os, json
from fpdf import FPDF
from streamlit_gsheets import GSheetsConnection

# --- KONFIGURACE ---
st.set_page_config(page_title="Organizátor pétanque", layout="wide")

# --- PŘIPOJENÍ GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def uloz_do_google():
    stav = {
        "nazev_akce": st.session_state.nazev_akce,
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

# --- INICIALIZACE ---
if "kolo" not in st.session_state:
    data = nacti_z_google()
    if data:
        st.session_state.nazev_akce = data["nazev_akce"]
        st.session_state.kolo = data["kolo"]
        st.session_state.max_kol = data["max_kol"]
        st.session_state.system = data["system"]
        st.session_state.tymy = pd.DataFrame(data["tymy"])
        st.session_state.historie = data["historie"]
    else:
        st.session_state.nazev_akce = "Pétanque Turnaj"
        st.session_state.kolo = 0
        st.session_state.max_kol = 3
        st.session_state.system = "Švýcar"
        st.session_state.tymy = None
        st.session_state.historie = []

def prepocitej_buchholz():
    tymy_df = st.session_state.tymy
    historie = st.session_state.historie
    nove_buchholzy = []
    for _, tym in tymy_df.iterrows():
        jmeno = tym["Hráč/Tým"]
        souperi = [h["Hráč/Tým 2"] if h["Hráč/Tým 1"] == jmeno else h["Hráč/Tým 1"] 
                   for h in historie if h["Hráč/Tým 1"] == jmeno or h["Hráč/Tým 2"] == jmeno]
        b_skore = sum(tymy_df[tymy_df["Hráč/Tým"] == s]["Výhry"].iloc[0] for s in souperi if s != "VOLNÝ LOS")
        nove_buchholzy.append(b_skore)
    st.session_state.tymy["Buchholz"] = nove_buchholzy

# --- OPRAVENÝ PDF EXPORT (TABULKA + HISTORIE) ---
def export_pdf():
    pdf = FPDF()
    pdf.add_page()
    # Kvůli českým znakům v latin-1 používáme náhrady, pro plnou češtinu by byl třeba .ttf font
    pdf.set_font("Arial", "B", 16)
    pdf.cell(190, 10, f"Vysledky: {st.session_state.nazev_akce}", ln=True, align="C")
    
    # Konečné pořadí
    pdf.set_font("Arial", "B", 12)
    pdf.ln(5)
    pdf.cell(190, 10, "Konecne poradi:", ln=True)
    pdf.set_font("Arial", "", 10)
    
    df_v = st.session_state.tymy.sort_values(by=["Výhry", "Buchholz", "Rozdíl"], ascending=False)
    for i, (_, r) in enumerate(df_v.iterrows(), 1):
        line = f"{i}. {r['Hráč/Tým']} - Vyhry: {r['Výhry']}, Buchholz: {r['Buchholz']}, Rozdil: {r['Skóre +']-r['Skóre -']}"
        pdf.cell(190, 7, line.encode('latin-1', 'replace').decode('latin-1'), ln=True)
    
    # Historie zápasů
    pdf.ln(10)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(190, 10, "Prehled zapasu (historie):", ln=True)
    pdf.set_font("Arial", "", 9)
    
    for h in st.session_state.historie:
        line = f"Kolo {h['Kolo']}: {h['Hráč/Tým 1']} {h['S1']} : {h['S2']} {h['Hráč/Tým 2']}"
        pdf.cell(190, 6, line.encode('latin-1', 'replace').decode('latin-1'), ln=True)
        
    return pdf.output(dest="S").encode("latin-1", errors="replace")

# --- HLAVNÍ LOGIKA ---
st.title("🏆 Organizátor pétanque")

if st.session_state.kolo == 0:
    st.session_state.nazev_akce = st.text_input("Název turnaje:", st.session_state.nazev_akce)
    st.session_state.system = st.radio("Systém:", ["Švýcar", "Každý s každým"])
    v = st.text_area("Hráči (každý na nový řádek):")
    h_list = [i.strip() for i in v.split('\n') if i.strip()]
    
    if st.session_state.system == "Každý s každým":
        vypocet_kol = len(h_list) - 1 if len(h_list) % 2 == 0 else len(h_list)
        st.session_state.max_kol = vypocet_kol
        st.info(f"Počet kol nastaven automaticky na: {vypocet_kol}")
    else:
        st.session_state.max_kol = st.number_input("Počet kol:", 1, 15, 3)

    if st.button("Zahájit turnaj"):
        if len(h_list) >= 2:
            h = h_list.copy()
            if len(h) % 2 != 0: h.append("VOLNÝ LOS")
            st.session_state.tymy = pd.DataFrame([{"Hráč/Tým": x, "Výhry": 0, "Skóre +": 0, "Skóre -": 0, "Rozdíl": 0, "Buchholz": 0} for x in h])
            st.session_state.kolo = 1
            st.session_state.historie = []
            uloz_do_google()
            st.rerun()

elif st.session_state.kolo <= st.session_state.max_kol:
    st.subheader(f"🏟️ {st.session_state.kolo}. kolo z {st.session_state.max_kol}")
    
    # Generování zápasů
    df_t = st.session_state.tymy
    if st.session_state.system == "Švýcar":
        df_s = df_t.sort_values(by=["Výhry", "Buchholz", "Rozdíl"], ascending=False)
        h = df_s["Hráč/Tým"].tolist()
    else:
        h_orig = df_t["Hráč/Tým"].tolist()
        n = len(h_orig)
        s = (st.session_state.kolo - 1) % (n - 1)
        res = h_orig[1:]
        rotated = res[-s:] + res[:-s] if s > 0 else res
        h = [h_orig[0]] + rotated
    
    zapasy = [(h[i], h[len(h)-1-i]) for i in range(len(h)//2)]
    
    aktualni_vysledky = []
    for i, (t1, t2) in enumerate(zapasy):
        c1, c2, c3, c4 = st.columns([3,1,1,3])
        with c1: st.write(t1)
        # KLÍČOVÁ OPRAVA: key obsahuje číslo kola, takže se po uložení widgety resetují
        with c2: s1 = st.number_input("S1", 0, 13, 0, key=f"k{st.session_state.kolo}_s1_{i}")
        with c3: s2 = st.number_input("S2", 0, 13, 0, key=f"k{st.session_state.kolo}_s2_{i}")
        with c4: st.write(t2)
        aktualni_vysledky.append((t1, s1, t2, s2))

    if st.button("Uložit výsledky kola"):
        for t1, s1, t2, s2 in aktualni_vysledky:
            # Update statistik
            for t, s_plus, s_minus in [(t1, s1, s2), (t2, s2, s1)]:
                idx = st.session_state.tymy[st.session_state.tymy["Hráč/Tým"] == t].index[0]
                st.session_state.tymy.at[idx, "Skóre +"] += s_plus
                st.session_state.tymy.at[idx, "Skóre -"] += s_minus
                if s_plus > s_minus: st.session_state.tymy.at[idx, "Výhry"] += 1
            st.session_state.historie.append({"Kolo": st.session_state.kolo, "Hráč/Tým 1": t1, "S1": s1, "S2": s2, "Hráč/Tým 2": t2})
        
        prepocitej_buchholz()
        st.session_state.kolo += 1
        uloz_do_google()
        st.rerun()

else:
    st.header("🏁 Turnaj ukončen")
    df_f = st.session_state.tymy.sort_values(by=["Výhry", "Buchholz", "Rozdíl"], ascending=False).reset_index(drop=True)
    df_f.index += 1
    st.table(df_f)
    
    st.download_button("📥 Stáhnout PDF s historií", data=export_pdf(), file_name="konecne_vysledky.pdf")
    
    if st.button("Restartovat turnaj"):
        st.session_state.kolo = 0
        uloz_do_google()
        st.rerun()
