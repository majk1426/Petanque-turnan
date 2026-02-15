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
    st.error("Chyba připojení ke Google Tabulkám.")

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
            pdf.cell(15, 10, str(h['S2']), border=1)
            pdf.cell(65, 10, str(h['Hráč/Tým 2']), border=1)
            pdf.ln()
    return pdf.output(dest='S').encode('latin-1', errors='replace')

# --- START ---
if 'kolo' not in st.session_state and not nacti_z_google():
    st.session_state.update({'kolo': 0, 'historie': [], 'tymy': None, 'system': "Švýcar", 'nazev_akce': "Turnaj", 'max_kol': 3})

if st.session_state.kolo == 0:
    if os.path.exists("logo.jpg"): st.image("logo.jpg", width=150)
    st.title("🏆 Turnajový manažer")
    st.session_state.nazev_akce = st.text_input("Název:", st.session_state.nazev_akce)
    st.session_state.system = st.radio("Systém:", ["Švýcar", "Každý s každým"])
    st.session_state.max_kol = st.number_input("Počet kol:", 1, 15, st.session_state.max_kol)
    v = st.text_area("Hráči/Týmy (každý na nový řádek):")
    if st.button("Zahájit turnaj", type="primary"):
        h = [i.strip() for i in v.split('\n') if i.strip()]
        if len(h) >= 2:
            if len(h) % 2 != 0: h.append("VOLNÝ LOS")
            st.session_state.tymy = pd.DataFrame([{"Hráč/Tým": i, "Výhry": 0, "Skóre +": 0, "Skóre -": 0, "Rozdíl": 0, "Buchholz": 0} for i in h])
            st.session_state.kolo = 1; uloz_do_google(); st.rerun()

elif st.session_state.kolo <= st.session_state.max_kol:
    st.header(f"🏟️ {st.session_state.nazev_akce} | Kolo {st.session_state.kolo}")
    df_t = st.session_state.tymy
    if st.session_state.system == "Švýcar":
        for i, r in df_t.iterrows():
            sou = [h["Hráč/Tým 2"] if h["Hráč/Tým 1"] == r["Hráč/Tým"] else h["Hráč/Tým 1"] for h in st.session_state.historie if r["Hráč/Tým"] in (h["Hráč/Tým 1"], h["Hráč/Tým 2"])]
            df_t.at[i, "Buchholz"] = sum([df_t[df_t["Hráč/Tým"] == s].iloc[0]["Výhry"] for s in sou if not df_t[df_t["Hráč/Tým"] == s].empty])
            df_t.at[i, "Rozdíl"] = r["Skóre +"] - r["Skóre -"]
        roz = df_t.sort_values(by=["Výhry", "Buchholz", "Rozdíl"], ascending=False)["Hráč/Tým"].tolist()
        zap = [(roz[i], roz[i+1]) for i in range(0, len(roz), 2)]
    else:
        h = df_t["Hráč/Tým"].tolist(); zap = [(h[i], h[len(h)-1-i]) for i in range(len(h)//2)]
    
    res_in = []
    for idx, (t1, t2) in enumerate(zap):
        with st.expander(f"Hřiště {idx+1}: {t1} vs {t2}", expanded=True):
            if "VOLNÝ LOS" in (t1, t2):
                res_in.append((t1, t2, 13 if t2 == "VOLNÝ LOS" else 0, 13 if t1 == "VOLNÝ LOS" else 0))
                st.info(f"Hráč {t1 if t2=='VOLNÝ LOS' else t2} má volný los.")
            else:
                c1, c2 = st.columns(2)
                s1 = c1.number_input(f"Skóre {t1}", 0, 13, 0, key=f"s1_{st.session_state.kolo}_{idx}")
                s2 = c2.number_input(f"Skóre {t2}", 0, 13, 0, key=f"s2_{st.session_state.kolo}_{idx}")
                res_in.append((t1, t2, s1, s2))
    
    if st.button("Uložit výsledky", type="primary"):
        for t1, t2, s1, s2 in res_in:
            i1, i2 = df_t.index[df_t["Hráč/Tým"] == t1][0], df_t.index[df_t["Hráč/Tým"] == t2][0]
            df_t.at[i1, "Skóre +"] += s1; df_t.at[i1, "Skóre -"] += s2
            df_t.at[i2, "Skóre +"] += s2; df_t.at[i2, "Skóre -"] += s1
            if s1 > s2: df_t.at[i1, "Výhry"] += 1
            elif
