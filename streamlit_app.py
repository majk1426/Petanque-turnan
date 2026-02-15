import streamlit as st
import pandas as pd
from fpdf import FPDF
import os
from streamlit_gsheets import GSheetsConnection
import json

KLUB_NAZEV = "Club přátel pétanque HK"
st.set_page_config(page_title=KLUB_NAZEV, layout="wide")

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception:
    conn = None
    st.error("Chyba připojení ke Google Tabulkám.")

def uloz_do_google():
    if conn is None: return
    try:
        d = {"kolo": st.session_state.kolo, "historie": st.session_state.historie, "tymy": st.session_state.tymy.to_dict('records') if st.session_state.tymy is not None else None, "system": st.session_state.system, "nazev_akce": st.session_state.nazev_akce, "max_kol": st.session_state.max_kol}
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
                st.session_state.update({"kolo": d["kolo"], "historie": d["historie"], "tymy": pd.DataFrame(d["tymy"]) if d["tymy"] else None, "system": d["system"], "nazev_akce": d["nazev_akce"], "max_kol": d["max_kol"]})
                return True
    except: pass
    return False

def vytvor_pdf(df, nazev):
    pdf = FPDF()
    pdf.add_page()
    pismo = 'DejaVu' if os.path.exists("DejaVuSans.ttf") else 'Arial'
    if pismo == 'DejaVu': pdf.add_font('DejaVu', '', "DejaVuSans.ttf", uni=True)
    pdf.set_font(pismo, '', 16); pdf.cell(0, 10, KLUB_NAZEV, ln=True)
    pdf.set_font(pismo, '', 12); pdf.cell(0, 10, f"VÝSLEDKY: {nazev}", ln=True); pdf.ln(10)
    pdf.set_font(pismo, '', 10)
    for c in ["Poz.", "Tým", "V", "S+", "S-", "Diff"]: pdf.cell(20 if c!="Tým" else 75, 10, c, border=1)
    pdf.ln()
    for i, (_, row) in enumerate(df.iterrows(), 1):
        if row['Tým'] != "VOLNÝ LOS":
            pdf.cell(20, 10, str(i), border=1); pdf.cell(75, 10, str(row['Tým']), border=1)
            for c in ['Výhry', 'Skóre +', 'Skóre -', 'Rozdíl']: pdf.cell(20, 10, str(row[c]), border=1)
            pdf.ln()
    return pdf.output(dest='S').encode('latin-1', errors='replace')

if 'kolo' not in st.session_state and not nacti_z_google():
    st.session_state.update({'kolo': 0, 'historie': [], 'tymy': None, 'system': "Švýcar", 'nazev_akce': "Turnaj", 'max_kol': 3})

if st.session_state.kolo == 0:
    if os.path.exists("logo.jpg"): st.image("logo.jpg", width=150)
    st.title("🏆 Turnajový manažer")
    st.session_state.nazev_akce = st.text_input("Název:", st.session_state.nazev_akce)
    st.session_state.system = st.radio("Systém:", ["Švýcar", "Každý s každým"])
    st.session_state.max_kol = st.number_input("Počet kol:", 1, 10, st.session_state.max_kol)
    vstup = st.text_area("Hráči (každý na nový řádek):")
    if st.button("Zahájit turnaj", type="primary"):
        hraci = [h.strip() for h in vstup.split('\n') if h.strip()]
        if len(hraci) >= 2:
            if len(hraci) % 2 != 0: hraci.append("VOLNÝ LOS")
            st.session_state.tymy = pd.DataFrame([{"Tým": h, "Výhry": 0, "Skóre +": 0, "Skóre -": 0, "Rozdíl": 0, "Buchholz": 0} for h in hraci])
            st.session_state.kolo = 1; uloz_do_google(); st.rerun()

elif st.session_state.kolo <= st.session_state.max_kol:
    st.header(f"🏟️ {st.session_state.nazev_akce} | Kolo {st.session_state.kolo}")
    df_t = st.session_state.tymy
    if st.session_state.system == "Švýcar":
        for i, r in df_t.iterrows():
            souperi = [h["Tým 2"] if h["Tým 1"] == r["Tým"] else h["Tým 1"] for h in st.session_state.historie if r["Tým"] in (h["Tým 1"], h["Tým 2"])]
            df_t.at[i, "Buchholz"] = sum([df_t[df_t["Tým"] == s].iloc[0]["Výhry"] for s in souperi if not df_t[df_t["Tým"] == s].empty])
            df_t.at[i, "Rozdíl"] = r["Skóre +"] - r["Skóre -"]
        rozpis = df_t.sort_values(by=["Výhry", "Buchholz", "Rozdíl"], ascending=False)["Tým"].tolist()
        zapasy = [(rozpis[i], rozpis[i+1]) for i in range(0, len(rozpis), 2)]
    else:
        hraci = df_t["Tým"].tolist()
        zapasy = [(hraci[i], hraci[len(hraci)-1-i]) for i in range(len(hraci)//2)]

    vysl = []
    for idx, (t1, t2) in enumerate(zapasy):
        with st.expander(f"Hřiště {idx+1}: {t1} vs {t2}", expanded=True):
            if "VOLNÝ LOS" in (t1, t2):
                st.info("Volný los (13:0)"); vysl.append((t1, t2, 13 if t2 == "VOLNÝ LOS" else 0, 13 if t1 == "VOLNÝ LOS" else 0))
            else:
                c1, c2 = st.columns(2)
                vysl.append((t1, t2, c1.number_input(f"Skóre {t1}", 0, 13, 0, key=f"s1_{st.session_state.kolo}_{idx}"), c2.number_input(f"Skóre {t2}", 0, 13, 0, key=f"s2_{st.session_state.kolo}_{idx}")))

    if st.button("Uložit výsledky", type="primary"):
        for t1, t2, s1, s2 in vysl:
            i1, i2 = df_t.index[df_t["Tým"] == t1][0], df_t.index[df_t["Tým"] == t2][0]
            df_t.at[i1, "Skóre +"] += s1; df_t.at[i1, "Skóre -"] += s2
            df_t.at[i2, "Skóre +"] += s2; df_t.at[i2, "Skóre -"] += s1
            if s1 > s2: df_t.at[i1, "Výhry"] += 1
            elif s2 > s1: df_t.at[i2, "Výhry"] += 1
            st.session_state.historie.append({"Kolo": st.session_state.kolo, "Tým 1": t1, "Tým 2": t2, "S1": s1, "S2": s2})
        st.session_state.kolo += 1; uloz_do_google(); st.rerun()

else:
    st.title("🏁 Konečné výsledky")
    res = st.session_state.tymy[st.session_state.tymy["Tým"] != "VOLNÝ LOS"].copy()
    res["Rozdíl"] = res["Skóre +"] - res["Skóre -"]
    res = res.sort_values(by=["Výhry", "Buchholz", "Rozdíl"], ascending=False).reset_index(drop=True)
    res.index += 1
    st.subheader("Tabulka")
    st.table(res[["Tým", "Výhry", "Skóre +", "Skóre -", "Rozdíl"]])
    
    st.subheader("Historie zápasů")
    hist_df = pd.DataFrame(st.session_state.historie)
    st.dataframe(hist_df, use_container_width=True)
    
    c1, c2 = st.columns(2)
    pdf_data = vytvor_pdf(res.reset_index(), st.session_state.nazev_akce)
    c1.download_button("📥 Stáhnout PDF výsledky", pdf_data, "vysledky.pdf", "application/pdf")
    csv = hist_df.to_csv(index=False).encode('utf-8-sig')
    c2.download_button("📥 Stáhnout historii (CSV)", csv, "historie.csv", "text/csv")
    
    if st.button("🗑️ Začít nový turnaj"):
        if conn: conn.update(worksheet="Stav", data=pd.DataFrame([{"stav_json": "{}"}]))
        st.session_state.clear(); st.rerun()
