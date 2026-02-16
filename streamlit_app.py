# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import json
from datetime import datetime

# Pokus o import volitelných knihoven
try:
    from fpdf import FPDF
    FPDF_AVAILABLE = True
except ImportError:
    FPDF_AVAILABLE = False

try:
    from streamlit_gsheets import GSheetsConnection
    GSHEETS_AVAILABLE = True
except ImportError:
    GSHEETS_AVAILABLE = False

# --- 1. KONFIGURACE A HESLO (MUSÍ BÝT PRVNÍ) ---
st.set_page_config(page_title="Pétanque Pro", layout="wide", initial_sidebar_state="collapsed")

def over_heslo():
    """Kontrola hesla s debug módem"""
    if "autentizovan" not in st.session_state:
        st.session_state.autentizovan = False
    
    if not st.session_state.autentizovan:
        # Načtení hesla ze Secrets (nebo nouzové admin123)
        try:
            master_heslo = str(st.secrets["access_password"]).strip()
            debug_msg = "✅ Heslo načteno ze Streamlit Secrets"
            secrets_funguje = True
        except Exception as e:
            master_heslo = "admin123"
            debug_msg = f"⚠️ Secrets nedostupné (chyba: {e}). Používám výchozí heslo: **admin123**"
            secrets_funguje = False
        
        st.title("🔒 Přístup omezen")
        
        # Debug info (odkomentuj pro testování)
        with st.expander("🔧 Debug info (klikni sem pokud máš problémy)"):
            st.info(debug_msg)
            if not secrets_funguje:
                st.warning("""
                **Jak nastavit vlastní heslo:**
                1. V Streamlit Cloud: Settings → Secrets → přidej:
                   ```
                   access_password = "tvoje_heslo"
                   ```
                2. Lokálně: Vytvoř `.streamlit/secrets.toml` se stejným obsahem
                """)
        
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
            st.session_state.datum_akce = datetime.now().strftime("%Y-%m-%d")
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
    """Generuje PDF s výsledky turnaje"""
    if not FPDF_AVAILABLE:
        st.error("PDF export není dostupný - chybí knihovna fpdf")
        return None
    
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, st.session_state.nazev_akce.encode('latin-1', 'ignore').decode('latin-1'), ln=True, align="C")
        
        pdf.set_font("Arial", "", 12)
        pdf.cell(0, 10, f"Datum: {st.session_state.datum_akce}", ln=True)
        pdf.cell(0, 10, f"System: {st.session_state.system}", ln=True)
        pdf.ln(10)
        
        # Tabulka výsledků
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, "Konecna tabulka:", ln=True)
        pdf.set_font("Arial", "", 10)
        
        df_sorted = st.session_state.tymy.sort_values(
            by=["Výhry", "Buchholz", "Rozdíl"], 
            ascending=False
        )
        
        for i, (_, row) in enumerate(df_sorted.iterrows(), 1):
            text = f"{i}. {row['Hráč/Tým']} - Vyhry: {row['Výhry']}, Skore: {row['Skóre +']}:{row['Skóre -']}"
            pdf.cell(0, 8, text.encode('latin-1', 'ignore').decode('latin-1'), ln=True)
        
        return pdf.output(dest='S').encode('latin-1')
    except Exception as e:
        st.error(f"Chyba při generování PDF: {e}")
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
        
        st.session_state.datum_akce = st.date_input(
            "Datum:", 
            value=datetime.now()
        ).strftime("%Y-%m-%d")
        
        st.session_state.system = st.radio(
            "Systém:", 
            ["Švýcar", "Každý s každým"],
            help="Švýcar = hráči se stejným skóre proti sobě, Každý s každým = všichni proti všem"
        )
        
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
            
            # Vytvoř DataFrame s hráči
            st.session_state.tymy = pd.DataFrame([
                {
                    "Hráč/Tým": x, 
                    "Výhry": 0, 
                    "Skóre +": 0, 
                    "Skóre -": 0, 
                    "Rozdíl": 0, 
                    "Buchholz": 0, 
                    "Zápasy": 0
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
    for i, (t1, t2) in enumerate(zapasy):
        st.markdown(f"**Zápas {i+1}:**")
        c1, c2, c3, c4 = st.columns([3, 1, 1, 3])
        
        is_bye = (t1 == "VOLNÝ LOS" or t2 == "VOLNÝ LOS")
        
        with c1:
            st.markdown(f"**{t1}**")
        
        with c2:
            s1 = st.number_input(
                "Body", 
                min_value=0, 
                max_value=13, 
                value=13 if t2 == "VOLNÝ LOS" else 0,
                key=f"s1_{i}",
                label_visibility="collapsed"
            )
        
        with c3:
            s2 = st.number_input(
                "Body", 
                min_value=0, 
                max_value=13, 
                value=13 if t1 == "VOLNÝ LOS" else 0,
                key=f"s2_{i}",
                label_visibility="collapsed"
            )
        
        with c4:
            st.markdown(f"**{t2}**")
        
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
    
    df_final = st.session_state.tymy.sort_values(
        by=["Výhry", "Buchholz", "Rozdíl"],
        ascending=False
    ).reset_index(drop=True)
    
    # Přidej medaile
    df_final.insert(0, "Pořadí", range(1, len(df_final) + 1))
    
    # Zobraz tabulku
    st.dataframe(
        df_final,
        use_container_width=True,
        hide_index=True
    )
    
    # Export tlačítka
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📊 Zobrazit historii", use_container_width=True):
            st.markdown("### 📜 Historie všech zápasů:")
            df_hist = pd.DataFrame(st.session_state.historie)
            st.dataframe(df_hist, use_container_width=True)
    
    with col2:
        if FPDF_AVAILABLE and st.button("📄 Stáhnout PDF", use_container_width=True):
            pdf_bytes = generuj_pdf_vysledky()
            if pdf_bytes:
                st.download_button(
                    label="💾 Stáhnout výsledky (PDF)",
                    data=pdf_bytes,
                    file_name=f"vysledky_{st.session_state.nazev_akce.replace(' ', '_')}.pdf",
                    mime="application/pdf"
                )
    
    with col3:
        # CSV export
        csv = df_final.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📊 Stáhnout CSV",
            data=csv,
            file_name=f"vysledky_{st.session_state.nazev_akce.replace(' ', '_')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    
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
        df_table = st.session_state.tymy.sort_values(
            by=["Výhry", "Buchholz", "Rozdíl"],
            ascending=False
        ).reset_index(drop=True)
        
        df_table.insert(0, "Pořadí", range(1, len(df_table) + 1))
        st.dataframe(df_table, use_container_width=True, hide_index=True)

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: gray;'>Pétanque Pro | Turnajový systém</div>", 
    unsafe_allow_html=True
)
