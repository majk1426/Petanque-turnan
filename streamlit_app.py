import streamlit as st
import pandas as pd
from fpdf import FPDF
import os, json
from streamlit_gsheets import GSheetsConnection

# --- KONFIGURACE ---
KLUB_NAZEV = "Club přátel pétanque HK"
st.set_page_config(page_title=KLUB_NAZEV, layout="wide")

# --- PŘIPOJENÍ KE GOOGLE SHEETS ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception:
    conn = None
    st.error("Chyba připojení ke Google Tabulkám. Zkontrolujte 'Secrets'.")

# --- FUNKCE PRO UKLÁDÁNÍ A NAČÍTÁNÍ ---
def uloz_do_google():
    if conn is None: return
    try:
        d = {
            "kolo": st.session_state.kolo, 
            "historie": st.session_state.historie, 
            "tymy": st.session_state.tymy.to_dict('records') if st.session_state.tymy is not None else None, 
            "system": st.session_state.system, 
            "nazev_akce": st.session_state.nazev_akce, 
            "max_kol": st.session_state.max_kol
        }
        conn.update(worksheet="Stav", data=pd.DataFrame([{"stav_json": json.dumps(d)}]))
    except: pass

def nacti_z_google():
    if conn is None: return False
    try:
        df = conn.read(worksheet="Stav", ttl=0)
        if not df.empty and "stav_json" in df.columns:
            r = df.iloc[0]["stav_json"]
            if r and r != "{}" and not pd.isna(r):
                d = json.loads(r)
                st.session_state.update({
                    "kolo": d["kolo"], 
                    "historie": d["historie"], 
                    "tymy": pd.DataFrame(d["tymy"]) if d["tymy"] else None, 
                    "system": d["system"], 
                    "nazev_akce": d["nazev_akce"], 
                    "max_kol": d["max_kol"]
                })
                return True
    except: pass
    return False

# --- PDF GENEROVÁNÍ S LOGEM ---
def vytvor_pdf(data, nazev, typ="v"):
    pdf = FPDF()
    pdf.add_page()
    p = 'DejaVu' if os.path.exists("DejaVuSans.ttf") else 'Arial'
    if p == 'DejaVu': pdf.add_font('DejaVu', '', "DejaVuSans.ttf", uni=True)
    
    # Logo v PDF záhlaví
    if os.path.exists("logo.jpg"):
        pdf.image("logo.jpg", x=10, y=8, w=25)
        pdf.set_x(40)
    
    pdf.set_font(p, '', 16)
    pdf.cell(0, 10, KLUB_NAZEV, ln=True)
    pdf.set_font(p, '', 12)
    if os.path.exists("logo.jpg"): pdf.set_x(40)
    pdf.cell(0, 10, f"{'VÝSLEDKY' if typ=='v' else 'HISTORIE'}: {nazev}", ln=True)
    pdf.ln(15)
    pdf.set_font(p, '', 10)

    if typ == "v":
        cols = ["Poz.", "Hráč/Tým", "V", "S+", "S-", "Diff"]
        for c in cols:
            pdf.cell(15 if c=="Poz." else 70 if "Hráč" in c else 20, 10, c, border=1)
        pdf.ln()
        for i, (_, r) in enumerate(data.iterrows(), 1):
            pdf.cell(15, 10, str(i), border=1)
            pdf.cell(70, 10, str(r['Hráč/Tým']), border=1)
            pdf.cell(20, 10, str(r['Výhry']), border=1)
            pdf.cell(20, 10, str(r['Skóre +']), border=1)
            pdf.cell(20, 10, str(r['Skóre -']), border=1)
            pdf.cell(20, 10, str(r['Rozdíl']), border=1)
            pdf.ln()
    else:
        for c in ["Kolo", "Hráč/Tým 1", "S1", "S2", "Hráč/Tým 2"]:
            pdf.cell(15 if "S" in c or "K" in c else 65, 10, c, border=1)
        pdf.ln()
        for h in data:
            pdf.cell(15, 10, str(h['Kolo']), border=1)
            pdf.cell(65, 10, str(h['Hráč/Tým 1']), border=1)
            pdf.cell(15, 10, str(h['S1']), border=1)
