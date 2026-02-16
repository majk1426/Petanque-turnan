# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime
from io import BytesIO

# Pokus o import volitelných knihoven
try:
    from fpdf import FPDF
    FPDF_AVAILABLE = True
except ImportError:
    FPDF_AVAILABLE = False

try:
    from st_gsheets_connection import GSheetsConnection
    GSHEETS_AVAILABLE = True
except ImportError:
    GSHEETS_AVAILABLE = False

# --- 1. KONFIGURACE A HESLO (MUSÍ BÝT PRVNÍ) ---
st.set_page_config(page_title="Pétanque Pro", layout="wide", initial_sidebar_state="collapsed")

def over_heslo():
    """Kontrola hesla - pouze z Secrets"""
    if "autentizovan" not in st.session_state:
        st.session_state.autentizovan = False
    
    if not st.session_state.autentizovan:
        # Načtení hesla POUZE ze Secrets
        try:
            master_heslo = str(st.secrets["access_password"]).strip()
        except Exception:
            st.error("❌ Heslo není nastaveno! Jděte do Settings → Secrets a přidejte: access_password = \"vase_heslo\"")
            st.stop()
        
        st.title("🔒 Přístup omezen")
        vstup = st.text_input("Zadejte heslo turnaje:", type="password", key="password_input")
        
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("🔓 Vstoupit", type="primary", use_container_width=True):
                if vstup.strip() == master_heslo:
                    st.session_state.autentizovan = True
                    st.rerun()
                else:
                    st.error(f"❌ Nesprávné heslo! Zkuste znovu.")
        
        st.stop()

# Spuštění kontroly hesla
over_heslo()

# --- 2. PŘIPOJENÍ GOOGLE SHEETS (VOLITELNÉ) ---
if GSHEETS_AVAILABLE:
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        GOOGLE_SHEETS_ENABLED = True
    except Exception as e:
        GOOGLE_SHEETS_ENABLED = False
        st.warning(f"⚠️ Google Sheets není nakonfigurované: {e}")
else:
    GOOGLE_SHEETS_ENABLED = False

def uloz_do_google():
    """Uloží stav do Google Sheets (pokud je dostupné)"""
    if not GOOGLE_SHEETS_ENABLED:
        return False
    
    try:
        stav = {
            "nazev_akce": st.session_state.nazev_akce,
            "datum_akce": st.session_state.get("datum_akce", ""),
            "kolo": st.session_state.kolo,
            "max_kol": st.session_state.max_kol,
            "system": st.session_state.system,
            "tymy": st.session_state.tymy.to_dict(orient="records") if st.session_state.tymy is not None else [],
            "historie": st.session_state.historie
        }
        df_save = pd.DataFrame([{"stav_json": json.dumps(stav, ensure_ascii=False)}])
        conn.update(worksheet="Stav", data=df_save)
        return True
    except Exception as e:
        st.error(f"Chyba při ukládání do Google Sheets: {e}")
        return False

def nacti_z_google():
    """Načte stav z Google Sheets (pokud je dostupné)"""
    if not GOOGLE_SHEETS_ENABLED:
        return None
    
    try:
        df = conn.read(worksheet="Stav", ttl=0)
        if not df.empty and "stav_json" in df.columns:
            r = df.iloc[0]["stav_json"]
            if r and r != "{}" and not pd.isna(r):
                return json.loads(r)
    except Exception as e:
        st.warning(f"Nepodařilo se načíst data z Google Sheets: {e}")
    return None

# --- 3. INICIALIZACE DAT ---
def inicializuj_session_state():
    """Inicializuje session state s výchozími hodnotami"""
    if "kolo" not in st.session_state:
        # Pokus o načtení z Google Sheets
        data = nacti_z_google()
        
        if data:
            st.session_state.nazev_akce = data.get("nazev_akce", "Pétanque Turnaj")
            st.session_state.datum_akce = data.get("datum_akce", "")
            st.session_state.kolo = data.get("kolo", 0)
            st.session_state.max_kol = data.get("max_kol", 3)
            st.session_state.system = data.get("system", "Švýcar")
            st.session_state.tymy = pd.DataFrame(data["tymy"]) if data.get("tymy") else None
            st.session_state.historie = data.get("historie", [])
            
            # Pojistka pro stará data: přidá chybějící sloupce
            if st.session_state.tymy is not None:
                for col in ["Výhry", "Skóre +", "Skóre -", "Rozdíl", "Buchholz", "Zápasy"]:
                    if col not in st.session_state.tymy.columns:
                        st.session_state.tymy[col] = 0
        else:
            # Výchozí hodnoty pro nový turnaj
            st.session_state.nazev_akce = "Pétanque Turnaj"
            st.session_state.datum_akce = datetime.now().strftime("%d/%m/%Y")
            st.session_state.kolo = 0
            st.session_state.max_kol = 3
            st.session_state.system = "Švýcar"
            st.session_state.tymy = None
            st.session_state.historie = []

inicializuj_session_state()

# --- 4. LOGIKA PÁROVÁNÍ ---
def generuj_parovani_svycar(tymy_list, historie):
    """Generuje párování švýcarským systémem - hráči se stejným skóre, ale bez opakování"""
    hraci = tymy_list.copy()
    odehrane = set()
    
    # Zaznamenej už odehrané dvojice
    for h in historie:
        odehrane.add(tuple(sorted((h["Hráč/Tým 1"], h["Hráč/Tým 2"]))))
    
    parovani = []
    p_hraci = hraci.copy()
    
    while len(p_hraci) > 1:
        h1 = p_hraci[0]
        nasel = False
        
        # Najdi protihráče, se kterým h1 ještě nehrál
        for i in range(1, len(p_hraci)):
            h2 = p_hraci[i]
            if tuple(sorted((h1, h2))) not in odehrane:
                parovani.append((h1, h2))
                p_hraci.pop(i)
                p_hraci.pop(0)
                nasel = True
                break
        
        # Pokud nenašel nového soupeře, spáruj s nejbližším
        if not nasel and len(p_hraci) > 1:
            h2 = p_hraci[1]
            parovani.append((h1, h2))
            p_hraci.pop(1)
            p_hraci.pop(0)
    
    return parovani

def generuj_parovani_kazdy_s_kazdym(tymy_list, kolo_cislo):
    """Generuje párování rotačním systémem (Berger tables)"""
    h = tymy_list.copy()
    n = len(h)
    
    if n < 2:
        return []
    
    # Berger rotation
    s = (kolo_cislo - 1) % (n - 1) if n > 2 else 0
    rot = [h[0]] + (h[1:][-s:] + h[1:][:-s] if s > 0 else h[1:])
    
    zapasy = [(rot[i], rot[n-1-i]) for i in range(n//2)]
    return zapasy

def prepocitej_buchholz():
    """Přepočítá Buchholz skóre a rozdíly"""
    t_df = st.session_state.tymy
    hist = st.session_state.historie
    
    for idx, r in t_df.iterrows():
        jm = r["Hráč/Tým"]
        
        # Najdi všechny soupeře tohoto hráče
        souperi = [
            h["Hráč/Tým 2"] if h["Hráč/Tým 1"] == jm else h["Hráč/Tým 1"] 
            for h in hist 
            if h["Hráč/Tým 1"] == jm or h["Hráč/Tým 2"] == jm
        ]
        
        # Buchholz = součet výher soupeřů
        b = sum(
            t_df[t_df["Hráč/Tým"] == s]["Výhry"].iloc[0] 
            for s in souperi 
            if s != "VOLNÝ LOS" and s in t_df["Hráč/Tým"].values
        )
        
        st.session_state.tymy.at[idx, "Buchholz"] = int(b)
        st.session_state.tymy.at[idx, "Zápasy"] = len(souperi)
        st.session_state.tymy.at[idx, "Rozdíl"] = (
            st.session_state.tymy.at[idx, "Skóre +"] - 
            st.session_state.tymy.at[idx, "Skóre -"]
        )

# --- 5. EXPORT DO PDF ---
def generuj_pdf_vysledky():
    """Generuje PDF s výsledky turnaje a historií"""
    if not FPDF_AVAILABLE:
        st.error("PDF export není dostupný - chybí knihovna fpdf2")
        return None
    
    try:
        pdf = FPDF()
        
        # Pokus o načtení DejaVu fontu z kořenové složky
        font_path = "DejaVuSans.ttf"
        if os.path.exists(font_path):
            pdf.add_font('DejaVu', '', font_path, uni=True)
            pdf.add_font('DejaVu', 'B', font_path, uni=True)
            use_dejavu = True
        else:
            use_dejavu = False
        
        pdf.add_page()
        
        # Název turnaje
        if use_dejavu:
            pdf.set_font("DejaVu", "B", 16)
            pdf.cell(0, 10, st.session_state.nazev_akce, ln=True, align="C")
        else:
            pdf.set_font("Arial", "B", 16)
            nazev_ascii = st.session_state.nazev_akce.encode('ascii', 'ignore').decode('ascii')
            pdf.cell(0, 10, nazev_ascii if nazev_ascii else "Petanque Turnaj", ln=True, align="C")
        
        # Informace o turnaji
        if use_dejavu:
            pdf.set_font("DejaVu", "", 12)
            pdf.cell(0, 10, f"Datum: {st.session_state.datum_akce}", ln=True)
            pdf.cell(0, 10, f"Systém: {st.session_state.system}", ln=True)
        else:
            pdf.set_font("Arial", "", 12)
            pdf.cell(0, 10, f"Datum: {st.session_state.datum_akce}", ln=True)
            system_ascii = st.session_state.system.replace("Švýcar", "Svycar").replace("Každý s každým", "Kazdy s kazdym")
            pdf.cell(0, 10, f"System: {system_ascii}", ln=True)
        
        pdf.ln(5)
        
        # --- KONEČNÁ TABULKA ---
        if use_dejavu:
            pdf.set_font("DejaVu", "B", 14)
            pdf.cell(0, 10, "Konečné pořadí:", ln=True)
        else:
            pdf.set_font("Arial", "B", 14)
            pdf.cell(0, 10, "Konecne poradi:", ln=True)
        
        pdf.ln(2)
        
        # Hlavička tabulky
        if use_dejavu:
            pdf.set_font("DejaVu", "B", 10)
        else:
            pdf.set_font("Arial", "B", 10)
        
        pdf.cell(10, 8, "#", 1, 0, 'C')
        pdf.cell(60, 8, "Hrac/Tym", 1, 0, 'L')
        pdf.cell(20, 8, "Vyhry", 1, 0, 'C')
        pdf.cell(20, 8, "Zapasy", 1, 0, 'C')
        pdf.cell(20, 8, "Skore +", 1, 0, 'C')
        pdf.cell(20, 8, "Skore -", 1, 0, 'C')
        pdf.cell(20, 8, "Rozdil", 1, 0, 'C')
        pdf.cell(20, 8, "Buchholz", 1, 1, 'C')
        
        # Řádky tabulky - BEZ VOLNÉHO LOSU
        if use_dejavu:
            pdf.set_font("DejaVu", "", 10)
        else:
            pdf.set_font("Arial", "", 10)
        
        df_sorted = st.session_state.tymy[st.session_state.tymy["Hráč/Tým"] != "VOLNÝ LOS"].sort_values(
            by=["Výhry", "Buchholz", "Rozdíl"], 
            ascending=False
        )
        
        for i, (_, row) in enumerate(df_sorted.iterrows(), 1):
            if use_dejavu:
                jmeno = str(row['Hráč/Tým'])[:30]
            else:
                jmeno = str(row['Hráč/Tým']).encode('ascii', 'ignore').decode('ascii')[:30]
            
            pdf.cell(10, 8, str(i), 1, 0, 'C')
            pdf.cell(60, 8, jmeno, 1, 0, 'L')
            pdf.cell(20, 8, str(int(row['Výhry'])), 1, 0, 'C')
            pdf.cell(20, 8, str(int(row['Zápasy'])), 1, 0, 'C')
            pdf.cell(20, 8, str(int(row['Skóre +'])), 1, 0, 'C')
            pdf.cell(20, 8, str(int(row['Skóre -'])), 1, 0, 'C')
            pdf.cell(20, 8, str(int(row['Rozdíl'])), 1, 0, 'C')
            pdf.cell(20, 8, str(int(row['Buchholz'])), 1, 1, 'C')
        
        pdf.ln(10)
        
        # --- HISTORIE ZÁPASŮ ---
        if use_dejavu:
            pdf.set_font("DejaVu", "B", 14)
            pdf.cell(0, 10, "Historie zápasů:", ln=True)
        else:
            pdf.set_font("Arial", "B", 14)
            pdf.cell(0, 10, "Historie zapasu:", ln=True)
        
        pdf.ln(2)
        
        # Filtrovaná historie bez volného losu
        historie_bez_losu = [
            h for h in st.session_state.historie 
            if h["Hráč/Tým 1"] != "VOLNÝ LOS" and h["Hráč/Tým 2"] != "VOLNÝ LOS"
        ]
        
        if historie_bez_losu:
            # Hlavička
            if use_dejavu:
                pdf.set_font("DejaVu", "B", 10)
            else:
                pdf.set_font("Arial", "B", 10)
            
            pdf.cell(15, 8, "Kolo", 1, 0, 'C')
            pdf.cell(65, 8, "Hrac/Tym 1", 1, 0, 'L')
            pdf.cell(20, 8, "Skore", 1, 0, 'C')
            pdf.cell(65, 8, "Hrac/Tym 2", 1, 0, 'L')
            pdf.cell(20, 8, "Skore", 1, 1, 'C')
            
            # Řádky
            if use_dejavu:
                pdf.set_font("DejaVu", "", 9)
            else:
                pdf.set_font("Arial", "", 9)
            
            for h in historie_bez_losu:
                if use_dejavu:
                    h1 = str(h["Hráč/Tým 1"])[:30]
                    h2 = str(h["Hráč/Tým 2"])[:30]
                else:
                    h1 = str(h["Hráč/Tým 1"]).encode('ascii', 'ignore').decode('ascii')[:30]
                    h2 = str(h["Hráč/Tým 2"]).encode('ascii', 'ignore').decode('ascii')[:30]
                
                pdf.cell(15, 7, str(h["Kolo"]), 1, 0, 'C')
                pdf.cell(65, 7, h1, 1, 0, 'L')
                pdf.cell(20, 7, str(h["S1"]), 1, 0, 'C')
                pdf.cell(65, 7, h2, 1, 0, 'L')
                pdf.cell(20, 7, str(h["S2"]), 1, 1, 'C')
        else:
            if use_dejavu:
                pdf.set_font("DejaVu", "", 10)
                pdf.cell(0, 8, "Zatím nebyly odehrány žádné zápasy.", ln=True)
            else:
                pdf.set_font("Arial", "", 10)
                pdf.cell(0, 8, "Zatim nebyly odehrany zadne zapasy.", ln=True)
        
        # Vygeneruj PDF jako bytes
        pdf_bytes = pdf.output(dest='S')
        
        # Pokud je to bytearray, převeď na bytes
        if isinstance(pdf_bytes, bytearray):
            pdf_bytes = bytes(pdf_bytes)
        
        return pdf_bytes
        
    except Exception as e:
        st.error(f"Chyba při generování PDF: {e}")
        import traceback
        st.error(traceback.format_exc())
        return None

# --- 6. HLAVNÍ ROZHRANÍ ---

# Sidebar s navigací
with st.sidebar:
    st.title("🎯 Menu")
    
    if st.session_state.kolo > 0:
        if st.button("📊 Aktuální tabulka", use_container_width=True):
            st.session_state.show_table = True
        
        if st.button("📜 Historie zápasů", use_container_width=True):
            st.session_state.show_history = True
        
        st.divider()
        
        if st.button("🔄 Nový turnaj", type="secondary", use_container_width=True):
            if st.checkbox("Opravdu chcete začít nový turnaj? (Smaže se vše!)"):
                st.session_state.kolo = 0
                st.session_state.tymy = None
                st.session_state.historie = []
                st.rerun()
    
    st.divider()
    
    # Info o synchronizaci
    if GOOGLE_SHEETS_ENABLED:
        st.success("✅ Google Sheets připojeno")
    else:
        st.info("ℹ️ Offline režim")

# --- CSS PRO CENTROVÁNÍ TABULEK ---
st.markdown("""
<style>
/* Centrování všech buněk v dataframe */
.stDataFrame div[data-testid="stDataFrame"] table {
    margin-left: auto;
    margin-right: auto;
}

.stDataFrame div[data-testid="stDataFrame"] table th {
    text-align: center !important;
}

.stDataFrame div[data-testid="stDataFrame"] table td {
    text-align: center !important;
}

/* Centrování tabulky samotné */
div[data-testid="stDataFrame"] {
    display: flex;
    justify-content: center;
}
</style>
""", unsafe_allow_html=True)

# --- HLAVNÍ OBSAH ---

if st.session_state.kolo == 0:
    # --- NOVÝ TURNAJ ---
    st.title("🏆 Nový turnaj")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.session_state.nazev_akce = st.text_input(
            "Název turnaje:", 
            st.session_state.nazev_akce
        )
        
        # Datum ve formátu DD/MM/YYYY
        datum_text = st.text_input(
            "Datum (DD/MM/RRRR):",
            value=st.session_state.datum_akce,
            placeholder="15/02/2024"
        )
        st.session_state.datum_akce = datum_text
        
        st.session_state.system = st.radio(
            "Systém:", 
            ["Švýcar", "Každý s každým"],
            help="Švýcar = hráči se stejným skóre proti sobě, Každý s každým = všichni proti všem"
        )
        
        # Počet kol POUZE pro švýcarský systém
        if st.session_state.system == "Švýcar":
            st.session_state.max_kol = st.number_input(
                "Počet kol:", 
                min_value=1, 
                max_value=15, 
                value=3
            )
    
    with col2:
        st.markdown("**Zadejte hráče/týmy:**")
        v = st.text_area(
            "Jeden hráč na řádek:",
            height=200,
            placeholder="Jan Novák\nPetr Svoboda\nMarie Dvořáková\n..."
        )
        
        st.info("💡 Pokud je lichý počet hráčů, přidá se automaticky 'VOLNÝ LOS'")
    
    if st.button("🚀 Zahájit turnaj", type="primary", use_container_width=True):
        h_list = [i.strip() for i in v.split('\n') if i.strip()]
        
        if len(h_list) < 2:
            st.error("❌ Musíte zadat alespoň 2 hráče!")
        else:
            # Přidej volný los pokud je lichý počet
            if len(h_list) % 2 != 0:
                h_list.append("VOLNÝ LOS")
                st.info(f"✅ Přidán VOLNÝ LOS (celkem {len(h_list)} účastníků)")
            
            # Pro "Každý s každým" vypočítej počet kol automaticky
            if st.session_state.system == "Každý s každým":
                n = len(h_list)
                st.session_state.max_kol = n - 1  # Každý s každým = n-1 kol
            
            # Vytvoř DataFrame s hráči
            st.session_state.tymy = pd.DataFrame([
                {
                    "Hráč/Tým": x, 
                    "Výhry": 0, 
                    "Zápasy": 0,
                    "Skóre +": 0, 
                    "Skóre -": 0, 
                    "Rozdíl": 0, 
                    "Buchholz": 0
                } 
                for x in h_list
            ])
            
            st.session_state.kolo = 1
            uloz_do_google()
            st.success("✅ Turnaj zahájen!")
            st.rerun()

elif st.session_state.kolo <= st.session_state.max_kol:
    # --- PROBÍHAJÍCÍ KOLO ---
    st.header(f"🏟️ {st.session_state.nazev_akce}")
    st.subheader(f"Kolo {st.session_state.kolo} / {st.session_state.max_kol}")
    
    # Vygeneruj párování
    if st.session_state.system == "Švýcar":
        df_sorted = st.session_state.tymy.sort_values(
            by=["Výhry", "Buchholz", "Rozdíl"], 
            ascending=False
        )
        zapasy = generuj_parovani_svycar(
            df_sorted["Hráč/Tým"].tolist(), 
            st.session_state.historie
        )
    else:
        zapasy = generuj_parovani_kazdy_s_kazdym(
            st.session_state.tymy["Hráč/Tým"].tolist(),
            st.session_state.kolo
        )
    
    st.markdown("### 📋 Zápasy tohoto kola:")
    
    # Formulář pro zadávání výsledků
    aktualni = []
    
    # KLÍČ pro identifikaci kola - aby se skóre resetovalo mezi koly
    kolo_key = f"kolo_{st.session_state.kolo}"
    
    for i, (t1, t2) in enumerate(zapasy):
        is_bye = (t1 == "VOLNÝ LOS" or t2 == "VOLNÝ LOS")
        
        if is_bye:
            # VOLNÝ LOS - zobraz info, automaticky 13:0
            if t1 == "VOLNÝ LOS":
                st.info(f"🎯 **{t2}** má volný los (automaticky 13:0)")
                aktualni.append((t1, 0, t2, 13))
            else:
                st.info(f"🎯 **{t1}** má volný los (automaticky 13:0)")
                aktualni.append((t1, 13, t2, 0))
        else:
            # Normální zápas
            st.markdown(f"**Zápas {i+1}:**")
            
            # Jména hráčů NAD políčky
            col1, col2, col3 = st.columns([1, 0.2, 1])
            with col1:
                st.markdown(f"<div style='text-align: center; font-weight: bold; font-size: 16px; margin-bottom: 10px;'>{t1}</div>", unsafe_allow_html=True)
            with col2:
                st.markdown("<div style='text-align: center; font-weight: bold; font-size: 16px; margin-bottom: 10px;'>VS</div>", unsafe_allow_html=True)
            with col3:
                st.markdown(f"<div style='text-align: center; font-weight: bold; font-size: 16px; margin-bottom: 10px;'>{t2}</div>", unsafe_allow_html=True)
            
            # Políčka pro skóre s tlačítky + a - POD jmény
            col1, col2, col3 = st.columns([1, 0.2, 1])
            
            # Inicializace session state pro skóre TOHOTO zápasu v TOMTO kole
            score1_key = f"{kolo_key}_score1_{i}"
            score2_key = f"{kolo_key}_score2_{i}"
            
            if score1_key not in st.session_state:
                st.session_state[score1_key] = 0
            if score2_key not in st.session_state:
                st.session_state[score2_key] = 0
            
            with col1:
                # - | číslo | +
                subcol1, subcol2, subcol3 = st.columns([1, 2, 1])
                with subcol1:
                    if st.button("➖", key=f"{kolo_key}_minus1_{i}", use_container_width=True):
                        if st.session_state[score1_key] > 0:
                            st.session_state[score1_key] -= 1
                            st.rerun()
                with subcol2:
                    s1 = st.number_input(
                        "S1", 
                        min_value=0, 
                        max_value=13, 
                        value=st.session_state[score1_key],
                        key=f"{kolo_key}_s1_input_{i}",
                        label_visibility="collapsed"
                    )
                    st.session_state[score1_key] = s1
                with subcol3:
                    if st.button("➕", key=f"{kolo_key}_plus1_{i}", use_container_width=True):
                        if st.session_state[score1_key] < 13:
                            st.session_state[score1_key] += 1
                            st.rerun()
            
            with col3:
                # - | číslo | +
                subcol1, subcol2, subcol3 = st.columns([1, 2, 1])
                with subcol1:
                    if st.button("➖", key=f"{kolo_key}_minus2_{i}", use_container_width=True):
                        if st.session_state[score2_key] > 0:
                            st.session_state[score2_key] -= 1
                            st.rerun()
                with subcol2:
                    s2 = st.number_input(
                        "S2", 
                        min_value=0, 
                        max_value=13, 
                        value=st.session_state[score2_key],
                        key=f"{kolo_key}_s2_input_{i}",
                        label_visibility="collapsed"
                    )
                    st.session_state[score2_key] = s2
                with subcol3:
                    if st.button("➕", key=f"{kolo_key}_plus2_{i}", use_container_width=True):
                        if st.session_state[score2_key] < 13:
                            st.session_state[score2_key] += 1
                            st.rerun()
            
            aktualni.append((t1, s1, t2, s2))
        
        st.divider()
    
    # Tlačítko pro uložení kola
    col1, col2, col3 = st.columns([2, 1, 2])
    with col2:
        if st.button("💾 Uložit kolo", type="primary", use_container_width=True):
            # Zpracuj výsledky
            for t1, s1, t2, s2 in aktualni:
                # Aktualizuj statistiky pro oba týmy
                for t, sp, sm in [(t1, s1, s2), (t2, s2, s1)]:
                    if t == "VOLNÝ LOS":
                        continue
                    
                    idx = st.session_state.tymy[st.session_state.tymy["Hráč/Tým"] == t].index[0]
                    st.session_state.tymy.at[idx, "Skóre +"] += sp
                    st.session_state.tymy.at[idx, "Skóre -"] += sm
                    
                    if sp > sm:
                        st.session_state.tymy.at[idx, "Výhry"] += 1
                
                # Přidej zápas do historie
                st.session_state.historie.append({
                    "Kolo": st.session_state.kolo,
                    "Hráč/Tým 1": t1,
                    "S1": s1,
                    "S2": s2,
                    "Hráč/Tým 2": t2
                })
            
            # Přepočítej Buchholz a rozdíly
            prepocitej_buchholz()
            
            # Posuň na další kolo
            st.session_state.kolo += 1
            
            # Ulož do Google Sheets
            uloz_do_google()
            
            st.success("✅ Kolo uloženo!")
            st.rerun()

else:
    # --- KONEC TURNAJE ---
    st.title("🏆 Turnaj ukončen!")
    st.subheader(st.session_state.nazev_akce)
    
    # Konečná tabulka
    st.markdown("### 🥇 Konečné pořadí:")
    
    # FILTRUJ VOLNÝ LOS
    df_final = st.session_state.tymy[st.session_state.tymy["Hráč/Tým"] != "VOLNÝ LOS"].sort_values(
        by=["Výhry", "Buchholz", "Rozdíl"],
        ascending=False
    ).reset_index(drop=True)
    
    # Přidej pořadí a seřaď sloupce
    df_final.insert(0, "Pořadí", range(1, len(df_final) + 1))
    
    # Seřaď sloupce podle požadavku
    df_display = df_final[["Pořadí", "Hráč/Tým", "Výhry", "Zápasy", "Skóre +", "Skóre -", "Rozdíl", "Buchholz"]]
    
    # Zobraz tabulku
    st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True
    )
    
    # Export tlačítka
    col1, col2, col3 = st.columns([2, 1, 2])
    
    with col1:
        if st.button("📜 Zobrazit historii", use_container_width=True):
            st.markdown("### 📜 Historie všech zápasů:")
            # Filtruj historii bez volného losu
            historie_bez_losu = [
                h for h in st.session_state.historie 
                if h["Hráč/Tým 1"] != "VOLNÝ LOS" and h["Hráč/Tým 2"] != "VOLNÝ LOS"
            ]
            
            if historie_bez_losu:
                df_hist = pd.DataFrame(historie_bez_losu)
                st.dataframe(df_hist, use_container_width=True)
            else:
                st.info("Nebyly odehrány žádné zápasy (pouze volné losy)")
    
    with col2:
        if FPDF_AVAILABLE:
            pdf_bytes = generuj_pdf_vysledky()
            if pdf_bytes:
                st.download_button(
                    label="📄 Stáhnout PDF",
                    data=pdf_bytes,
                    file_name=f"vysledky_{st.session_state.nazev_akce.replace(' ', '_')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
        else:
            st.warning("PDF export nedostupný")
    
    st.divider()
    
    # Tlačítko pro nový turnaj
    if st.button("🔄 Začít nový turnaj", type="primary"):
        st.session_state.kolo = 0
        st.session_state.tymy = None
        st.session_state.historie = []
        st.rerun()

# --- AKTUÁLNÍ TABULKA (SIDEBAR TLAČÍTKO) ---
if st.session_state.kolo > 0 and st.session_state.kolo <= st.session_state.max_kol:
    with st.expander("📊 Aktuální tabulka", expanded=False):
        # FILTRUJ VOLNÝ LOS
        df_table = st.session_state.tymy[st.session_state.tymy["Hráč/Tým"] != "VOLNÝ LOS"].sort_values(
            by=["Výhry", "Buchholz", "Rozdíl"],
            ascending=False
        ).reset_index(drop=True)
        
        df_table.insert(0, "Pořadí", range(1, len(df_table) + 1))
        
        # Seřaď sloupce
        df_table_display = df_table[["Pořadí", "Hráč/Tým", "Výhry", "Zápasy", "Skóre +", "Skóre -", "Rozdíl", "Buchholz"]]
        
        st.dataframe(df_table_display, use_container_width=True, hide_index=True)

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: gray;'>Pétanque Pro | Turnajový systém</div>", 
    unsafe_allow_html=True
)
