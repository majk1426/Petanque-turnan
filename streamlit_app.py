import streamlit as st
import pandas as pd
from fpdf import FPDF
import os
from streamlit_gsheets import GSheetsConnection
import json

# --- KONFIGURACE ---
KLUB_NAZEV = "Club přátel pétanque HK"
st.set_page_config(page_title=KLUB_NAZEV, layout="wide")

# Připojení na Google Tabulky
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    conn = None
    st.error(f"Chyba připojení ke Google Tabulkám. Zkontroluj Secrets. Detaily: {e}")

def zobraz_logo():
    if os.path.exists("logo.jpg"):
        st.image("logo.jpg", width=150)
    else:
        st.subheader(KLUB_NAZEV)

# --- FUNKCE PRO GOOGLE TABULKY ---
def uloz_do_google():
    if conn is None: return
    try:
        data_k_ulozeni = {
            "kolo": st.session_state.kolo,
            "historie": st.session_state.historie,
            "tymy": st.session_state.tymy.to_dict('records') if st.session_state.tymy is not None else None,
            "system": st.session_state.system,
            "nazev_akce": st.session_state.nazev_akce,
            "max_kol": st.session_state.max_kol
        }
        df_save = pd.DataFrame([{"stav_json": json.dumps(data_k_ulozeni)}])
        conn.update(worksheet="Stav", data=df_save)
    except:
        pass # Tiché selhání, aby to nerušilo turnaj

def nacti_z_google():
    if conn is None: return False
    try:
        df = conn.read(worksheet="Stav", ttl=0)
        if not df.empty and "stav_json" in df.columns:
            raw_data = df.iloc[0]["stav_json"]
            if raw_data == "{}" or not raw_data or pd.isna(raw_data): return False
            data = json.loads(raw_data)
            st.session_state.kolo = data["kolo"]
            st.session_state.historie = data["historie"]
            st.session_state.tymy = pd.DataFrame(data["tymy"]) if data["tymy"] else None
            st.session_state.system = data["system"]
            st.session_state.nazev_akce = data["nazev_akce"]
            st.session_state.max_kol = data["max_kol"]
            return True
    except:
        return False
    return False

# --- FUNKCE PRO PDF ---
def vytvor_pdf_bytes(df, nazev_akce):
    pdf = FPDF()
    pdf.add_page()
    
    font_path = "DejaVuSans.ttf"
    if os.path.exists(font_path):
        pdf.add_font('DejaVu', '', font_path, uni=True)
        pismo = 'DejaVu'
    else:
        pismo = 'Arial'
        
    pdf.set_font(pismo, '', 16)
    pdf.cell(0, 10, KLUB_NAZEV, ln=True)
    pdf.set_font(pismo, '', 12)
    pdf.cell(0, 10, f"VÝSLEDKY: {nazev_akce}", ln=True)
    pdf.ln(10)
    
    # Hlavička tabulky
    pdf.set_font(pismo, '', 10)
    pdf.cell(15, 10, "Poz.", border=1)
    pdf.cell(80, 10, "Tým", border=1)
    pdf.cell(20, 10, "V", border=1)
    pdf.cell(20, 10, "S+", border=1)
    pdf.cell(20, 10, "S-", border=1)
    pdf.cell(20, 10, "Diff", border=1)
    pdf.ln()
    
    # Data tabulky (bez volného losu)
    for i, (_, row) in enumerate(df.iterrows(), 1):
        if row['Tým'] != "VOLNÝ LOS":
            pdf.cell(15, 10, str(i), border=1)
            pdf.cell(80, 10, str(row['Tým']), border=1)
            pdf.cell(20, 10, str(row['Výhry']), border=1)
            pdf.cell(20, 10, str(row['Skóre +']), border=1)
            pdf.cell(20, 10, str(row['Skóre -']), border=1)
            pdf.cell(20, 10, str(row['Rozdíl']), border=1)
            pdf.ln()
            
    return pdf.output(dest='S').encode('latin-1', errors='replace')

# --- START APLIKACE ---
if 'kolo' not in st.session_state:
    if not nacti_z_google():
        st.session_state.update({'kolo': 0, 'historie': [], 'tymy': None, 'system': "Švýcar", 'nazev_akce': "Hradecká koule", 'max_kol': 3})

# --- 1. SETUP TURNAJE ---
if st.session_state.kolo == 0:
    zobraz_logo()
    st.title("🏆 Turnajový manažer")
    st.session_state.nazev_akce = st.text_input("Název turnaje:", st.session_state.nazev_akce)
    st.session_state.system = st.radio("Systém turnaje:", ["Švýcar", "Každý s každým"])
    st.session_state.max_kol = st.number_input("Počet kol:", 1, 10, st.session_state.max_kol)
    vstup = st.text_area("Seznam hráčů (každý na nový řádek):")
    
    if st.button("Zahájit turnaj", type="primary"):
        hraci = [h.strip() for h in vstup.split('\n') if h.strip()]
        if len(hraci) >= 2:
            if len(hraci) % 2 != 0: hraci.append("VOLNÝ LOS")
            st.session_state.tymy = pd.DataFrame([{"Tým": h, "Výhry": 0, "Skóre +": 0, "Skóre -": 0, "Rozdíl": 0, "Buchholz": 0} for h in hraci])
            st.session_state.kolo = 1
            uloz_do_google()
            st.rerun()

# --- 2. PRŮBĚH TURNAJE ---
elif st.session_state.kolo <= st.session_state.max_kol:
    zobraz_logo()
    st.header(f"🏟️ {st.session_state.nazev_akce} | Kolo {st.session_state.kolo}/{st.session_state.max_kol}")
    
    # Logika pro párování
    if st.session_state.system == "Švýcar":
        for i, r in st.session_state.tymy.iterrows():
            souperi = [h["Tým 2"] if h["Tým 1"] == r["Tým"] else h["Tým 1"] for h in st.session_state.historie if h["Tým 1"] == r["Tým"] or h["Tým 2"] == r["Tým"]]
            bhz = sum([st.session_state.tymy[st.session_state.tymy["Tým"] == s].iloc[0]["Výhry"] for s in souperi if not st.session_state.tymy[st.session_state.tymy["Tým"] == s].empty])
            st.session_state.tymy.at[i, "Buchholz"] = bhz
            st.session_state.tymy.at[i, "Rozdíl"] = r["Skóre +"] - r["Skóre -"]
        
        df_serazene = st.session_state.tymy.sort_values(by=["Výhry", "Buchholz", "Rozdíl"], ascending=False)
        serazene_list = df_serazene["Tým"].tolist()
        aktualni_rozpis = [(serazene_list[i], serazene_list[i+1]) for i in range(0, len(serazene_list), 2)]
    else:
        hraci = st.session_state.tymy["Tým"].tolist()
        aktualni_rozpis = [(hraci[i], hraci[len(hraci)-1-i]) for i in range(len(hraci)//2)]

    # Zobrazování zápasů
    vysledky_input = []
    for idx, (t1, t2) in enumerate(aktualni_rozpis):
        with st.expander(f"Hřiště {idx+
