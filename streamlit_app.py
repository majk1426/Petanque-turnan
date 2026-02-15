import streamlit as st
import pandas as pd
from fpdf import FPDF
import os
from streamlit_gsheets import GSheetsConnection
import json

# --- KONFIGURACE ---
KLUB_NAZEV = "Club přátel pétanque HK"
st.set_page_config(page_title=KLUB_NAZEV, layout="wide")

# Propojení s Google Sheets (na pozadí)
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"Chyba připojení ke cloudu: {e}")

def zobraz_logo():
    if os.path.exists("logo.jpg"):
        st.image("logo.jpg", width=150)
    else:
        st.subheader(KLUB_NAZEV)

# --- FUNKCE PRO CLOUD (tiché ukládání) ---
def uloz_do_google():
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
        pass 

def nacti_z_google():
    try:
        df = conn.read(worksheet="Stav", ttl=0)
        if not df.empty and "stav_json" in df.columns:
            raw_data = df.iloc[0]["stav_json"]
            if raw_data == "{}" or not raw_data: return False
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

# --- PDF GENERÁTOR ---
def vytvor_pdf_bytes(df, nazev_akce, typ="vysledky"):
    pdf = FPDF()
    pdf.add_page()
    pismo = 'Arial'
    if os.path.exists("DejaVuSans.ttf"):
        pdf.add_font('DejaVu', '', 'DejaVuSans.ttf', uni=True)
        pismo = 'DejaVu'
    pdf.set_font(pismo, '', 16)
    pdf.cell(0, 10, KLUB_NAZEV, ln=True)
    pdf.set_font(pismo, '', 10)
    pdf.cell(0, 10, f"{typ.upper()}: {nazev_akce}", ln=True)
    pdf.ln(10)
    
    if typ == "vysledky":
        df_clean = df[df["Tým"] != "VOLNÝ LOS"].copy()
        cols = ["Poz.", "Hráč/Tým", "V", "S+", "S-", "Diff"]
        widths = [15, 80, 20, 25, 25, 25]
        for i, col in enumerate(cols):
            pdf.cell(widths[i], 10, col, border=1)
        pdf.ln()
        for i, (_, row) in enumerate(df_clean.iterrows(), start=1):
            pdf.cell(widths[0], 10, str(i), border=1)
            pdf.cell(widths[1], 10, str(row['Tým']), border=1)
            pdf.cell(widths[2], 10, str(row['Výhry']), border=1)
            pdf.cell(widths[3], 10, str(row['Skóre +']), border=1)
            pdf.cell(widths[4], 10, str(row['Skóre -']), border=1)
            pdf.cell(widths[5], 10, str(row['Rozdíl']), border=1)
            pdf.ln()
    return pdf.output(dest='S').encode('latin-1', errors='replace')

# --- START APLIKACE ---
if 'kolo' not in st.session_state:
    if not nacti_z_google():
        st.session_state.update({'kolo': 0, 'historie': [], 'tymy': None, 'system': "Švýcar", 'nazev_akce': "Hradecká koule", 'max_kol': 3})

# --- 1. SETUP ---
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

# --- 2. PRŮBĚH ---
elif st.session_state.kolo <= st.session_state.max_kol:
    zobraz_logo()
    st.header(f"🏟️ {st.session_state.nazev_akce} | Kolo {st.session_state.kolo}/{st.session_state.max_kol}")
    
    if st.session_state.system == "Švýcar":
        for i, r in st.session_state.tymy.iterrows():
            souperi = [h["Tým 2"] if h["Tým 1"] == r["Tým"] else h["Tým 1"] for h in st.session_state.historie if h["Tým 1"] == r["Tým"] or h["Tým 2"] == r["Tým"]]
            bhz = 0
            for s in souperi:
                s_data = st.session_state.tymy[st.session_state.tymy["Tým"] == s]
                if not s_data.empty: bhz += s_data.iloc[0]["Výhry"]
            st.session_state.tymy.at[i, "Buchholz"] = bhz
            st.session_state.tymy.at[i, "Rozdíl"] = r["Skóre +"] - r["Skóre -"]
        
        df_serazene = st.session_state.tymy.sort_values(by=["Výhry", "Buchholz", "Rozdíl"], ascending=False)
        serazene_list = df_serazene["Tým"].tolist()
        aktualni_rozpis = [(serazene_list[i], serazene_list[i+1]) for i in range(0, len(serazene_list), 2)]
    else:
        hraci = st.session_state.tymy["Tým"].tolist()
        aktualni_rozpis = [(hraci[i], hraci[len(hraci)-1-i]) for i in range(len(hraci)//2)]

    vysledky_input = []
    for idx, (t1, t2) in enumerate(aktualni_rozpis):
        with st.expander(f"Hřiště {idx+1}: {t1} vs {t2}", expanded=True):
            if "VOLNÝ LOS" in [t1, t2]:
                st.info("Volný los (13:0)")
                vysledky_input.append((t1, t2, (13 if t2=="VOLNÝ LOS" else 0), (13 if t1=="VOLNÝ LOS" else 0)))
            else:
                c1, c2 = st.columns(2)
                s1 = c1.number_input(f"Skóre {t1}", 0, 13, 0, key=f"s1
