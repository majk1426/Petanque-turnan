import streamlit as st
import pandas as pd
from fpdf import FPDF
import os

# --- KONFIGURACE ---
KLUB_NAZEV = "Club přátel pétanque HK"
st.set_page_config(page_title=KLUB_NAZEV, layout="wide")

def zobraz_logo():
    if os.path.exists("logo.jpg"):
        st.image("logo.jpg", width=150)
    else:
        st.subheader(KLUB_NAZEV)

# --- GENEROVÁNÍ PDF ---
def vytvor_pdf_bytes(df, nazev_akce, typ="vysledky"):
    pdf = FPDF()
    pdf.add_page()
    
    pismo = 'Arial'
    if os.path.exists("DejaVuSans.ttf"):
        pdf.add_font('DejaVu', '', 'DejaVuSans.ttf', uni=True)
        pismo = 'DejaVu'
    
    pdf.set_font(pismo, '', 16)
    if os.path.exists("logo.jpg"):
        pdf.image("logo.jpg", 10, 8, 30)
        pdf.set_x(45)
    
    pdf.cell(0, 10, KLUB_NAZEV, ln=True)
    pdf.set_font(pismo, '', 10)
    pdf.set_x(45)
    pdf.cell(0, 10, f"{typ.upper()}: {nazev_akce}", ln=True)
    pdf.ln(15)

    pdf.set_fill_color(230, 230, 230)
    
    if typ == "vysledky":
        df_clean = df[df["Tým"] != "VOLNÝ LOS"].copy()
        cols = ["Poz.", "Hráč/Tým", "V", "S+", "S-", "Diff"]
        widths = [15, 80, 20, 25, 25, 25]
        pdf.set_font(pismo, '', 10)
        for i, col in enumerate(cols):
            pdf.cell(widths[i], 10, col, border=1, fill=True)
        pdf.ln()
        for i, (_, row) in enumerate(df_clean.iterrows(), start=1):
            pdf.cell(widths[0], 10, str(i), border=1)
            pdf.cell(widths[1], 10, str(row['Tým']), border=1)
            pdf.cell(widths[2], 10, str(row['Výhry']), border=1)
            pdf.cell(widths[3], 10, str(row['Skóre +']), border=1)
            pdf.cell(widths[4], 10, str(row['Skóre -']), border=1)
            pdf.cell(widths[5], 10, str(row['Rozdíl']), border=1)
            pdf.ln()
    else:
        cols = ["Kolo", "Hráč 1", "Hráč 2", "S1", "S2"]
        widths = [15, 70, 70, 15, 15]
        pdf.set_font(pismo, '', 10)
        for i, col in enumerate(cols):
            pdf.cell(widths[i], 10, col, border=1, fill=True)
        pdf.ln()
        for _, row in df.iterrows():
            pdf.cell(widths[0], 10, str(row['Kolo']), border=1)
            pdf.cell(widths[1], 10, str(row['Tým 1']), border=1)
            pdf.cell(widths[2], 10, str(row['Tým 2']), border=1)
            pdf.cell(widths[3], 10, str(row['S1']), border=1)
            pdf.cell(widths[4], 10, str(row['S2']), border=1)
            pdf.ln()

    return pdf.output(dest='S').encode('latin-1', errors='replace')

# --- LOGIKA ROUND ROBIN ---
def generuj_round_robin(tymy):
    temp_tymy = tymy[:]
    if len(temp_tymy) % 2 != 0:
        temp_tymy.append("VOLNÝ LOS")
    n = len(temp_tymy)
    kola = []
    pro_rotaci = temp_tymy[:]
    for i in range(n - 1):
        zápasy_kola = []
        for j in range(n // 2):
            zápasy_kola.append((pro_rotaci[j], pro_rotaci[n - 1 - j]))
        kola.append(zápasy_kola)
        pro_rotaci.insert(1, pro_rotaci.pop())
    return kola

def vypocti_buchholz(jmeno, df, historie):
    souperi = [h["Tým 2"] if h["Tým 1"] == jmeno else h["Tým 1"] for h in historie if h["Tým 1"] == jmeno or h["Tým 2"] == jmeno]
    bhz = 0
    for s in souperi:
        shoda = df[df["Tým"] == s]
        if not shoda.empty:
            bhz += shoda.iloc[0]["Výhry"]
    return bhz

# --- STAV APLIKACE ---
if 'kolo' not in st.session_state:
    st.session_state.update({'kolo': 0, 'historie': [], 'tymy': None, 'system': "Švýcar", 'vsechna_kola': None})

# --- 1. SETUP ---
if st.session_state.kolo == 0:
    zobraz_logo()
    st.title("🏆 Turnajový manažer")
    st.session_state.nazev_akce = st.text_input("Název turnaje:", "Hradecká koule")
    st.session_state.system = st.radio("Systém turnaje:", ["Švýcar", "Každý s každým"])
    vstup = st.text_area("Seznam hráčů (jméno na každý řádek):")
    
    if st.session_state.system == "Švýcar":
        st.session_state.max_kol = st.number_input("Počet kol:", 1, 10, 3)
    
    if st.button("Zahájit turnaj", type="primary"):
        hraci = [h.strip() for h in vstup.split('\n') if h.strip()]
        if len(hraci) >= 2:
            tymy_list = hraci[:]
            if len(tymy_list) % 2 != 0: 
                tymy_list.append("VOLNÝ LOS")
            st.session_state.tymy = pd.DataFrame([{"Tým": h, "Výhry": 0, "Skóre +": 0, "Skóre -": 0, "Rozdíl": 0, "Buchholz": 0} for h in tymy_list])
            if st.session_state.system == "Každý s každým":
                st.session_state.vsechna_kola = generuj_round_robin(tymy_list)
                st.session_state.max_kol = len(st.session_state.vsechna_kola)
            st.session_state.kolo = 1
            st.rerun()

# --- 2. PRŮBĚH ---
elif st.session_state.kolo <= st.session_state.max_kol:
    zobraz_logo()
    st.header(f"🏟️ {st.session_state.nazev_akce} | Kolo {st.session_state.kolo}/{st.session_state.max_kol}")
    
    if st.session_state.system == "Švýcar":
        for i, r in st.session_state.tymy.iterrows():
            st.session_state.tymy.at[i, "Buchholz"] = vypocti_buchholz(r["Tým"], st.session_state.tymy, st.session_state.historie)
            st.session_state.tymy.at[i, "Rozdíl"] = r["Skóre +"] - r["Skóre -"]
        
        df_serazene = st.session_state.tymy.sort_values(by=["Výhry", "Buchholz", "Rozdíl"], ascending=False)
        serazene_tymy = df_serazene["Tým"].tolist()
        aktualni_rozpis = [(serazene_tymy[i], serazene_tymy[i+1]) for i in range(0, len(serazene_tymy), 2)]
    else:
        aktualni_rozpis = st.session_state.vsechna_kola[st.session_state.kolo - 1]

    vysledky_input = []
    for idx, (t1, t2) in enumerate(aktualni_rozpis):
        hriste = f"Hřiště {idx+1}" if idx < 5 else "Čeká na volné hřiště"
        with st.expander(f"{hriste}: {t1} vs {t2}", expanded=True):
            if "VOLNÝ LOS" in [t1, t2]:
                v = t1 if t2 == "VOLNÝ LOS" else t2
                st.info(f"⚪ {v} má volno (13:0)")
                vysledky_input.append((t1, t2, (13 if t2 == "VOLNÝ LOS" else 0), (13 if t1 == "VOLNÝ LOS" else 0)))
            else:
                c1, c2 = st.columns(2)
                s1 = c1.number_input(f"{t1}", 0, 13, 0, key=f"s1_{st.session_state.kolo}_{idx}")
                s2 = c2.number_input(f"{t2}", 0, 13, 0, key=f"s2_{st.session_state.kolo}_{idx}")
                vysledky_input.append((t1, t2, s1, s2))

    col_save, col_undo = st.columns(2)
    if col_save.button("Uložit kolo", type="primary"):
        for t1, t2, s1, s2 in vysledky_input:
            idx1 = st.session_state.tymy[st.session_state.tymy["Tým"] == t1].index[0]
            idx2 = st.session_state.tymy[st.session_state.tymy["Tým"] == t2].index[0]
            st.session_state.tymy.at[idx1, "Skóre +"] += s1
            st.session_state.tymy.at[idx1, "Skóre -"] += s2
            st.session_state.tymy.at[idx2, "Skóre +"] += s2
            st.session_state.tymy.at[idx2, "Skóre -"] += s1
            if s1 > s2: st.session_state.tymy.at[idx1, "Výhry"] += 1
            elif s2 > s1: st.session_state.tymy.at[idx2, "Výhry"] += 1
            st.session_state.historie.append({"Kolo": st.session_state.kolo, "Tým 1": t1, "Tým 2": t2, "S1": s1, "S2": s2})
        st.session_state.kolo += 1
        st.rerun()

    if st.session_state.kolo > 1:
        if col_undo.button("⬅️ Smazat poslední kolo (Oprava)"):
            naposledy = st.session_state.kolo - 1
            zápasy_k_mazání = [h for h in st.session_state.historie if h["Kolo"] == naposledy]
            for h in zápasy_k_mazání:
                idx1 = st.session_state.tymy[st.session_state.tymy["Tým"] == h["Tým 1"]].index[0]
                idx2 = st.session_state.tymy[st.session_state.tymy["Tým"] == h["Tým 2"]].index[0]
                st.session_state.tymy.at[idx1, "Skóre +"] -= h["S1"]
                st.session_state.tymy.at[idx1, "Skóre -"] -= h["S2"]
                st.session_state.tymy.at[idx2, "Skóre +"] -= h["S2"]
                st.session_state.tymy.at[idx2, "Skóre -"] -= h["S1"]
                if h["S1"] > h["S2"]: st.session_state.tymy.at[idx1, "Výhry"] -= 1
                elif h["S2"] > h["S1"]: st.session_state.tymy.at[idx2, "Výhry"] -= 1
            st.session_state.historie = [h for h in st.session_state.historie if h["Kolo"] != naposledy]
            st.session_state.kolo = naposledy
            st.rerun()

# --- 3. KONEC ---
else:
    zobraz_logo()
    st.balloons()
    st.title("🏁 Konečné výsledky")
    
    for i, r in st.session_state.tymy.iterrows():
        st.session_state.tymy.at[i, "Rozdíl"] = r["Skóre +"] - r["Skóre -"]
    
    res_display = st.session_state.tymy[st.session_state.tymy["Tým"] != "VOLNÝ LOS"].copy()
    res_display = res_display.sort_values(by=["Výhry", "Buchholz", "Rozdíl"], ascending=False).reset_index(drop=True)
    res_display.index += 1
    
    st.table(res_display[["Tým", "Výhry", "Skóre +", "Skóre -", "Rozdíl"]])
    
    col1, col2 = st.columns(2)
    with col1:
        st.download_button("📥 PDF Výsledky", vytvor_pdf_bytes(res_display, st.session_state.nazev_akce, "vysledky"), "vysledky.pdf", "application/pdf")
    with col2:
        h_df = pd.DataFrame(st.session_state.historie)
        st.download_button("📥 PDF Historie", vytvor_pdf_bytes(h_df, st.session_state.nazev_akce, "historie"), "historie.pdf", "application/pdf")
    
    if st.button("Založit nový turnaj"):
        st.session_state.clear()
        st.rerun()
