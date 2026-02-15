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
        st.session_state.nazev_akce = data.get("nazev_akce", "Pétanque Turnaj")
        st.session_state.kolo = data.get("kolo", 0)
        st.session_state.max_kol = data.get("max_kol", 3)
        st.session_state.system = data.get("system", "Švýcar")
        st.session_state.tymy = pd.DataFrame(data["tymy"])
        st.session_state.historie = data.get("historie", [])
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
        nove_buchholzy.append(int(b_skore))
    st.session_state.tymy["Buchholz"] = nove_buchholzy

# --- PDF EXPORT (OPRAVENÝ VÝSTUP) ---
def export_pdf():
    pdf = FPDF()
    pdf.add_page()
    font_path = "DejaVuSans.ttf"
    
    if os.path.exists(font_path):
        pdf.add_font("DejaVu", "", font_path, uni=True)
        pdf.set_font("DejaVu", "", 14)
        use_font = "DejaVu"
    else:
        pdf.set_font("Arial", "B", 14)
        use_font = "Arial"

    pdf.cell(190, 10, f"Výsledky: {st.session_state.nazev_akce}", ln=True, align="C")
    pdf.ln(5)
    
    pdf.cell(190, 10, "Konečné pořadí:", ln=True)
    pdf.set_font(use_font, "", 10)
    
    df_v = st.session_state.tymy.sort_values(by=["Výhry", "Buchholz", "Rozdíl"], ascending=False)
    for i, (_, r) in enumerate(df_v.iterrows(), 1):
        rozdil = int(r['Skóre +'] - r['Skóre -'])
        line = f"{i}. {r['Hráč/Tým']} | Výhry: {int(r['Výhry'])} | Buchholz: {int(r['Buchholz'])} | Rozdíl: {rozdil}"
        if use_font == "Arial":
            line = line.translate(str.maketrans("áéěíóúůýčďňřšťžÁÉĚÍÓÚŮÝČĎŇŘŠŤŽ", "aeeiouuycdnrstzAEEIOUUYCDNRSTZ"))
        pdf.cell(190, 7, line, ln=True)
    
    pdf.ln(10)
    pdf.set_font(use_font, "", 12)
    pdf.cell(190, 10, "Přehled všech zápasů:", ln=True)
    pdf.set_font(use_font, "", 9)
    for h in st.session_state.historie:
        line = f"Kolo {h['Kolo']}: {h['Hráč/Tým 1']} {h['S1']} : {h['S2']} {h['Hráč/Tým 2']}"
        if use_font == "Arial":
            line = line.translate(str.maketrans("áéěíóúůýčďňřšťžÁÉĚÍÓÚŮÝČĎŇŘŠŤŽ", "aeeiouuycdnrstzAEEIOUUYCDNRSTZ"))
        pdf.cell(190, 6, line, ln=True)
        
    # Změna: převedení na bytes pomocí latin1 s nahrazením pro maximální kompatibilitu
    return pdf.output(dest='S').encode('latin-1', 'replace')

# --- HLAVNÍ STRÁNKA ---
st.title("🏆 Organizátor pétanque")

if st.session_state.kolo == 0:
    st.session_state.nazev_akce = st.text_input("Název turnaje:", st.session_state.nazev_akce)
    st.session_state.system = st.radio("Systém:", ["Švýcar", "Každý s každým"])
    v = st.text_area("Seznam hráčů (každý na nový řádek):")
    h_list = [i.strip() for i in v.split('\n') if i.strip()]
    
    if st.session_state.system == "Každý s každým":
        v_kol = len(h_list) - 1 if len(h_list) % 2 == 0 else len(h_list) if len(h_list) > 0 else 0
        st.session_state.max_kol = v_kol
        st.info(f"Počet kol pro 'Každý s každým' (automaticky): {v_kol}")
    else:
        st.session_state.max_kol = st.number_input("Počet kol:", 1, 15, 3)

    if st.button("Zahájit turnaj", type="primary"):
        if len(h_list) >= 2:
            h = h_list.copy()
            if len(h) % 2 != 0: h.append("VOLNÝ LOS")
            st.session_state.tymy = pd.DataFrame([{"Hráč/Tým": x, "Výhry": 0, "Skóre +": 0, "Skóre -": 0, "Rozdíl": 0, "Buchholz": 0} for x in h])
            st.session_state.kolo = 1
            st.session_state.historie = []
            uloz_do_google()
            st.rerun()

elif st.session_state.kolo <= st.session_state.max_kol:
    st.header(f"🏟️ {st.session_state.kolo}. kolo / {st.session_state.max_kol}")
    
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
        with st.container():
            col1, col2, col3, col4 = st.columns([3, 1, 1, 3])
            
            # Detekce volného losu
            is_bye = (t1 == "VOLNÝ LOS" or t2 == "VOLNÝ LOS")
            
            with col1: st.markdown(f"**{t1}**")
            with col2: 
                if is_bye:
                    val1 = 13 if t2 == "VOLNÝ LOS" else 0
                    st.write(f"**{val1}**")
                    s1 = val1
                else:
                    s1 = st.number_input(f"Body {t1}", 0, 13, 0, key=f"k{st.session_state.kolo}_s1_{i}")
            with col3: 
                if is_bye:
                    val2 = 13 if t1 == "VOLNÝ LOS" else 0
                    st.write(f"**{val2}**")
                    s2 = val2
                else:
                    s2 = st.number_input(f"Body {t2}", 0, 13, 0, key=f"k{st.session_state.kolo}_s2_{i}")
            with col4: st.markdown(f"**{t2}**")
            
            aktualni_vysledky.append((t1, s1, t2, s2))
            st.divider()

    if st.button("Uložit kolo a pokračovat", type="primary"):
        for t1, s1, t2, s2 in aktualni_vysledky:
            for t, s_p, s_m in [(t1, s1, s2), (t2, s2, s1)]:
                idx = st.session_state.tymy[st.session_state.tymy["Hráč/Tým"] == t].index[0]
                st.session_state.tymy.at[idx, "Skóre +"] += s_p
                st.session_state.tymy.at[idx, "Skóre -"] += s_m
                if s_p > s_m: st.session_state.tymy.at[idx, "Výhry"] += 1
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
    
    # Export do PDF
    try:
        pdf_data = export_pdf()
        st.download_button("📥 Stáhnout kompletní výsledky (PDF)", data=pdf_data, file_name="konecne_vysledky.pdf", mime="application/pdf")
    except Exception as e:
        st.error(f"Chyba při generování PDF: {e}")
    
    if st.button("Smazat vše a začít nový turnaj"):
        st.session_state.kolo = 0
        uloz_do_google()
        st.rerun()
