import streamlit as st
import pandas as pd
from fpdf import FPDF
import os

# --- KONFIGURACE A NASTAVENÍ ---
KLUB_NAZEV = "Club přátel pétanque HK"
st.set_page_config(page_title=KLUB_NAZEV, layout="wide")

# Funkce pro zobrazení loga v aplikaci
def zobraz_logo():
    if os.path.exists("logo.jpg"):
        st.image("logo.jpg", width=150)
    else:
        st.subheader(KLUB_NAZEV)

# --- FUNKCE PRO GENEROVÁNÍ PDF ---
def vytvor_pdf(df, nazev_akce, typ="vysledky"):
    pdf = FPDF()
    pdf.add_page()
    
    # Registrace fontu pro češtinu
    if os.path.exists("DejaVuSans.ttf"):
        pdf.add_font('DejaVu', '', 'DejaVuSans.ttf', uni=True)
        pismo = 'DejaVu'
    else:
        pismo = 'Arial'

    pdf.set_font(pismo, '', 14)

    # Hlavička s logem v PDF
    if os.path.exists("logo.jpg"):
        pdf.image("logo.jpg", 10, 8, 33)
        pdf.set_x(45)
    
    pdf.cell(0, 10, KLUB_NAZEV, ln=True)
    pdf.set_font(pismo, '', 10)
    pdf.set_x(45)
    pdf.cell(0, 10, f"{typ.capitalize()}: {nazev_akce}", ln=True)
    pdf.ln(15)

    # Definice barev a tabulky
    pdf.set_fill_color(230, 230, 230)
    pdf.set_font(pismo, '', 10)

    if typ == "vysledky":
        cols = ["Poř.", "Tým", "V", "S+", "S-", "Diff"]
        widths = [15, 80, 20, 25, 25, 25]
        # Hlavička
        for i, col in enumerate(cols):
            pdf.cell(widths[i], 10, col, border=1, fill=True)
        pdf.ln()
        # Data
        for i, row in df.iterrows():
            pdf.cell(widths[0], 10, str(i), border=1)
            pdf.cell(widths[1], 10, str(row['Tým']), border=1)
            pdf.cell(widths[2], 10, str(row['Výhry']), border=1)
            pdf.cell(widths[3], 10, str(row['Skóre +']), border=1)
            pdf.cell(widths[4], 10, str(row['Skóre -']), border=1)
            pdf.cell(widths[5], 10, str(row['Rozdíl']), border=1)
            pdf.ln()
    else:
        cols = ["Kolo", "Tým 1", "Tým 2", "S1", "S2"]
        widths = [20, 65, 65, 20, 20]
        # Hlavička
        for i, col in enumerate(cols):
            pdf.cell(widths[i], 10, col, border=1, fill=True)
        pdf.ln()
        # Data
        for _, row in df.iterrows():
            pdf.cell(widths[0], 10, str(row['Kolo']), border=1)
            pdf.cell(widths[1], 10, str(row['Tým 1']), border=1)
            pdf.cell(widths[2], 10, str(row['Tým 2']), border=1)
            pdf.cell(widths[3], 10, str(row['S1']), border=1)
            pdf.cell(widths[4], 10, str(row['S2']), border=1)
            pdf.ln()

    return pdf.output(dest='S')

# --- POMOCNÉ VÝPOČTY ---
def vypocti_buchholz(tym_jmeno, df_tymy, historie):
    souperi = []
    for h in historie:
        # historie je list slovníků: {"Kolo": k, "Tým 1": t1, "Tým 2": t2, "S1": s1, "S2": s2}
        if h["Tým 1"] == tym_jmeno: souperi.append(h["Tým 2"])
        elif h["Tým 2"] == tym_jmeno: souperi.append(h["Tým 1"])
    bhz = 0
    for s in souperi:
        shoda = df_tymy[df_tymy["Tým"] == s]
        if not shoda.empty:
            bhz += shoda.iloc[0]["Výhry"]
    return bhz

# --- INICIALIZACE STAVU APLIKACE ---
if 'kolo' not in st.session_state:
    st.session_state.kolo = 0
if 'historie_zapasu' not in st.session_state:
    st.session_state.historie_zapasu = []

# --- 1. ÚVODNÍ OBRAZOVKA (NASTAVENÍ) ---
if st.session_state.kolo == 0:
    zobraz_logo()
    st.title("🏆 Turnajový manažer")
    st.session_state.nazev_akce = st.text_input("Název turnaje:", value="Hradecká koule")
    vstup = st.text_area("Seznam týmů (každý na nový řádek):", height=200)
    st.session_state.max_kol = st.number_input("Počet kol turnaje:", 1, 10, 3)

    if st.button("Zahájit turnaj", type="primary"):
        seznam = [s.strip() for s in vstup.split('\n') if s.strip()]
        if len(seznam) >= 2:
            tymy_data = [{"Tým": j, "Výhry": 0, "Skóre +": 0, "Skóre -": 0, "Rozdíl": 0, "Buchholz": 0} for j in seznam]
            if len(tymy_data) % 2 != 0:
                tymy_data.append({"Tým": "VOLNÝ LOS (BYE)", "Výhry": 0, "Skóre +": 0, "Skóre -": 0, "Rozdíl": 0, "Buchholz": 0})
            st.session_state.tymy = pd.DataFrame(tymy_data)
            st.session_state.kolo = 1
            st.rerun()

# --- 2. OBRAZOVKA KOLA ---
elif st.session_state.kolo <= st.session_state.max_kol:
    zobraz_logo()
    st.header(f"🏟️ {st.session_state.nazev_akce}")
    st.subheader(f"Zapisování výsledků: Kolo {st.session_state.kolo} z {st.session_state.max_kol}")

    # Aktualizace pomocných hodnot pro rozlosování
    for i, row in st.session_state.tymy.iterrows():
        st.session_state.tymy.at[i, "Buchholz"] = vypocti_buchholz(row["Tým"], st.session_state.tymy, st.session_state.historie_zapasu)
        st.session_state.tymy.at[i, "Rozdíl"] = row["Skóre +"] - row["Skóre -"]
    
    # Švýcarské nasazení podle Výher, pak BHZ, pak Rozdílu
    side_df = st.session_state.tymy.sort_values(by=["Výhry", "Buchholz", "Rozdíl"], ascending=False).reset_index(drop=True)
    serazene_tymy = side_df["Tým"].tolist()
    rozpis = [(serazene_tymy[i], serazene_tymy[i+1]) for i in range(0, len(serazene_tymy), 2)]

    vysledky_input = []
    for idx, (t1, t2) in enumerate(rozpis):
        with st.expander(f"Zápas {idx+1}: {t1} vs {t2}", expanded=True):
            if "VOLNÝ LOS" in t1 or "VOLNÝ LOS" in t2:
                vitez = t1 if "VOLNÝ LOS" in t2 else t2
                st.info(f"⚪ {vitez} obdržel volný los (automatická výhra 13:0)")
                vysledky_input.append((t1, t2, (13 if "VOLNÝ LOS" in t2 else 0), (13 if "VOLNÝ LOS" in t1 else 0)))
            else:
                c1, c2 = st.columns(2)
                s1 = c1.number_input(f"Skóre {t1}", 0, 13, 0, key=f"k{st.session_state.kolo}z{idx}s1")
                s2 = c2.number_input(f"Skóre {t2}", 0, 13, 0, key=f"k{st.session_state.kolo}z{idx}s2")
                vysledky_input.append((t1, t2, s1, s2))

    col_save, col_undo = st.columns(2)
    if col_save.button("Uložit kolo a pokračovat", type="primary"):
        for t1, t2, s1, s2 in vysledky_input:
            idx1 = st.session_state.tymy[st.session_state.tymy["Tým"] == t1].index[0]
            idx2 = st.session_state.tymy[st.session_state.tymy["Tým"] == t2].index[0]
            st.session_state.tymy.at[idx1, "Skóre +"] += s1
            st.session_state.tymy.at[idx1, "Skóre -"] += s2
            st.session_state.tymy.at[idx2, "Skóre +"] += s2
            st.session_state.tymy.at[idx2, "Skóre -"] += s1
            if s1 > s2: st.session_state.tymy.at[idx1, "Výhry"] += 1
            elif s2 > s1: st.session_state.tymy.at[idx2, "Výhry"] += 1
            st.session_state.historie_zapasu.append({"Kolo": st.session_state.kolo, "Tým 1": t1, "Tým 2": t2, "S1": s1, "S2": s2})
        st.session_state.kolo += 1
        st.rerun()

    if st.session_state.kolo > 1:
        if col_undo.button("⬅️ Smazat poslední kolo (Oprava)"):
            naposledy = st.session_state.kolo - 1
            zápasy_k_mazání = [h for h in st.session_state.historie_zapasu if h["Kolo"] == naposledy]
            for h in zápasy_k_mazání:
                idx1 = st.session_state.tymy[st.session_state.tymy["Tým"] == h["Tým 1"]].index[0]
                idx2 = st.session_state.tymy[st.session_state.tymy["Tým"] == h["Tým 2"]].index[0]
                st.session_state.tymy.at[idx1, "Skóre +"] -= h["S1"]
                st.session_state.tymy.at[idx1, "Skóre -"] -= h["S2"]
                st.session_state.tymy.at[idx2, "Skóre +"] -= h["S2"]
                st.session_state.tymy.at[idx2, "Skóre -"] -= h["S1"]
                if h["S1"] > h["S2"]: st.session_state.tymy.at[idx1, "Výhry"] -= 1
                elif h["S2"] > h["S1"]: st.session_state.tymy.at[idx2, "Výhry"] -= 1
            st.session_state.historie_zapasu = [h for h in st.session_state.historie_zapasu if h["Kolo"] != naposledy]
            st.session_state.kolo = naposledy
            st.rerun()

# --- 3. FINÁLNÍ VÝSLEDKY ---
else:
    zobraz_logo()
    st.balloons()
    st.title(f"🏁 {st.session_state.nazev_akce} - Výsledky")
    
    for i, row in st.session_state.tymy.iterrows():
        st.session_state.tymy.at[i, "Buchholz"] = vypocti_buchholz(row["Tým"], st.session_state.tymy, st.session_state.historie_zapasu)
        st.session_state.tymy.at[i, "Rozdíl"] = row["Skóre +"] - row["Skóre -"]

    final_df = st.session_state.tymy.sort_values(by=["Výhry", "Buchholz", "Rozdíl"], ascending=False).reset_index(drop=True)
    final_df.index += 1
    
    st.table(final_df[["Tým", "Výhry", "Skóre +", "Skóre -", "Rozdíl"]])

    st.divider()
    c1, c2 = st.columns(2)
    
    with c1:
        pdf_res = vytvor_pdf(final_df.reset_index(), st.session_state.nazev_akce, "vysledky")
        st.download_button("📥 Stáhnout konečné pořadí (PDF)", data=pdf_res, file_name="vysledky.pdf", mime="application/pdf")
    
    with c2:
        h_df = pd.DataFrame(st.session_state.historie_zapasu)
        pdf_hist = vytvor_pdf(h_df, st.session_state.nazev_akce, "historie")
        st.download_button("📥 Stáhnout historii zápasů (PDF)", data=pdf_hist, file_name="historie.pdf", mime="application/pdf")

    st.divider()
    if st.button("Zahájit nový turnaj"):
        st.session_state.clear()
        st.rerun()
