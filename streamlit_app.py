import streamlit as st
import pandas as pd
from fpdf import FPDF
import os
from streamlit_gsheets import GSheetsConnection
import json

# --- KONFIGURACE ---
KLUB_NAZEV = "Club přátel pétanque HK"
st.set_page_config(page_title=KLUB_NAZEV, layout="wide")

# Inicializace propojení s Google Sheets
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception:
    st.error("Chyba v připojení ke Google Tabulce. Zkontroluj 'Secrets' v nastavení Streamlitu.")

def zobraz_logo():
    if os.path.exists("logo.jpg"):
        st.image("logo.jpg", width=150)
    else:
        st.subheader(KLUB_NAZEV)

# --- FUNKCE PRO UKLÁDÁNÍ/NAČÍTÁNÍ Z GOOGLE ---
def uloz_do_google():
    data_k_ulozeni = {
        "kolo": st.session_state.kolo,
        "historie": st.session_state.historie,
        "tymy": st.session_state.tymy.to_dict('records') if st.session_state.tymy is not None else None,
        "system": st.session_state.system,
        "nazev_akce": st.session_state.nazev_akce,
        "max_kol": st.session_state.max_kol
    }
    # Uložíme jako jeden JSON řetězec do buňky A1 v listu "Stav"
    df = pd.DataFrame([{"stav_json": json.dumps(data_k_ulozeni)}])
    conn.update(worksheet="Stav", data=df)

def nacti_z_google():
    try:
        df = conn.read(worksheet="Stav", ttl=0)
        if not df.empty and "stav_json" in df.columns:
            data = json.loads(df.iloc[0]["stav_json"])
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

# --- PDF GENERÁTOR (STEJNÝ JAKO MINULE) ---
def vytvor_pdf_bytes(df, nazev_akce, typ="vysledky"):
    pdf = FPDF()
    pdf.add_page()
    pismo = 'Arial'
    if os.path.exists("DejaVuSans.ttf"):
        pdf.add_font('DejaVu', '', 'DejaVuSans.ttf', uni=True)
        pismo = 'DejaVu'
    pdf.set_font(pismo, '', 16)
    pdf.cell(0, 10, f"{KLUB_NAZEV} - {typ.upper()}", ln=True)
    pdf.set_font(pismo, '', 10)
    pdf.cell(0, 10, f"Akce: {nazev_akce}", ln=True)
    pdf.ln(10)
    
    # ... zkráceno pro přehlednost, v ostrém kódu ponechej tvou plnou verzi PDF exportu ...
    return pdf.output(dest='S').encode('latin-1', errors='replace')

# --- LOGIKA TURNÁJE ---
if 'kolo' not in st.session_state:
    # Zkusíme načíst rozdělaný turnaj z Google při startu
    if not nacti_z_google():
        st.session_state.update({'kolo': 0, 'historie': [], 'tymy': None, 'system': "Švýcar", 'nazev_akce': "", 'max_kol': 3})

# --- 1. SETUP ---
if st.session_state.kolo == 0:
    zobraz_logo()
    st.title("🏆 Nový Turnaj")
    st.session_state.nazev_akce = st.text_input("Název turnaje:", "Hradecká koule")
    st.session_state.system = st.radio("Systém:", ["Švýcar", "Každý s každým"])
    st.session_state.max_kol = st.number_input("Počet kol:", 1, 10, 3)
    vstup = st.text_area("Seznam hráčů:")
    
    if st.button("Zahájit a uložit do cloudu"):
        hraci = [h.strip() for h in vstup.split('\n') if h.strip()]
        if len(hraci) >= 2:
            if len(hraci) % 2 != 0: hraci.append("VOLNÝ LOS")
            st.session_state.tymy = pd.DataFrame([{"Tým": h, "Výhry": 0, "Skóre +": 0, "Skóre -": 0, "Rozdíl": 0, "Buchholz": 0} for h in hraci])
            st.session_state.kolo = 1
            uloz_do_google() # PRVNÍ ZÁPIS DO TABULKY
            st.rerun()

# --- 2. PRŮBĚH TURNÁJE ---
elif st.session_state.kolo <= st.session_state.max_kol:
    zobraz_logo()
    st.header(f"🏟️ {st.session_state.nazev_akce} | Kolo {st.session_state.kolo}")
    
    # ... (Zde je tvoje stávající logika pro zadávání výsledků kol) ...
    # DOPLNĚNÍ: Na konci sekce "Uložit kolo" vždy volej uloz_do_google()
    
    if st.button("Uložit výsledky kola"):
        # ... (zpracování výsledků) ...
        st.session_state.kolo += 1
        uloz_do_google() # ZÁPIS PO KAŽDÉM KOLE
        st.rerun()

# --- 3. KONEC A RESET ---
else:
    st.title("🏁 Výsledky")
    # ... (Zobrazení výsledků) ...
    
    if st.button("🗑️ VYMAZAT TURNAJ A ZAČÍT NOVÝ"):
        # Vymažeme tabulku v Google Sheets
        df_empty = pd.DataFrame([{"stav_json": "{}"}])
        conn.update(worksheet="Stav", data=df_empty)
        # Vymažeme lokální paměť
        st.session_state.clear()
        st.rerun()
