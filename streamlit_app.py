import streamlit as st
import pandas as pd
from fpdf import FPDF
import base64

# --- NASTAVENÍ ---
KLUB_NAZEV = "Club přátel pétanque HK"
st.set_page_config(page_title=KLUB_NAZEV, layout="wide")

# CSS pro hezčí vzhled
st.markdown("""
    <style>
    .stButton>button { width: 100%; margin-bottom: 10px; }
    .reportview-container .main .block-container { padding-top: 2rem; }
    </style>
    """, unsafe_allow_html=True)

# Funkce pro zobrazení loga
def zobraz_logo():
    try:
        st.image("logo.jpg", width=150)
    except:
        st.markdown(f"### {KLUB_NAZEV}")

# --- FUNKCE PRO PDF ---
def generuj_pdf_odkaz(df, nazev_akce, typ="vysledky"):
    pdf = FPDF()
    pdf.add_page()
    # Použití standardního fontu pro stabilitu (bez diakritiky pro teď, aby to nespadlo)
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, txt=KLUB_NAZEV.encode('latin-1', 'ignore').decode('latin-1'), ln=True, align='C')
    pdf.set_font("Arial", '', 12)
    pdf.cell(190, 10, txt=f"{typ.capitalize()}: {nazev_akce}".encode('latin-1', 'ignore').decode('latin-1'), ln=True, align='C')
    pdf.ln(10)
    
    # Hlavička
    pdf.set_font("Arial", 'B', 10)
    if typ == "vysledky":
        cols = ["Poz", "Tym", "Vyhry", "Skore+", "Skore-", "Rozdil"]
        data_cols = ["Tým", "Výhry", "Skóre +", "Skóre -", "Rozdíl"]
    else:
        cols = ["Kolo", "Tym 1", "Tym 2", "S1", "S2"]
        data_cols = ["Kolo", "Tým 1", "Tým 2", "S1", "S2"]

    for col in cols:
        pdf.cell(38, 10, col, border=1)
    pdf.ln()
    
    pdf.set_font("Arial", '', 10)
    for i, row in df.iterrows():
        if typ == "vysledky": pdf.cell(38, 10, str(i), border=1)
        else: pdf.cell(38, 10, str(row[data_cols[0]]), border=1)
        
        for idx, c in enumerate(data_cols[(1 if typ=="vysledky" else 1):]):
            val = str(row[c]).encode('latin-1', 'ignore').decode('latin-1')
            pdf.cell(38, 10, val, border=1)
        pdf.ln()
    
    return pdf.output(dest='S').encode('latin-1', 'ignore')

# --- POMOCNÉ FUNKCE ---
def vypocti_buchholz(tym_jmeno, df_tymy, historie):
    souperi = []
    for k, t1, t2, s1, s2 in historie:
        if t1 == tym_jmeno: souperi.append(t2)
        elif t2 == tym_jmeno: souperi.append(t1)
    bhz = 0
    for s in souperi:
        shoda = df_tymy[df_tymy["Tým"] == s]
        if not shoda.empty:
            bhz += shoda.iloc[0]["Výhry"]
    return bhz

# --- INICIALIZACE STAVU ---
if 'tymy' not in st.session_state:
    st.session_state.tymy = []
if 'kolo' not in st.session_state:
    st.session_state.kolo = 0
if 'historie_zapasu' not in st.session_state:
    st.session_state.historie_zapasu = []

# --- 1. START ---
if st.session_state.kolo == 0:
    zobraz_logo()
    st.title("🏆 Turnajový manažer")
    st.session_state.nazev_akce = st.text_input("Název turnaje:", value="Hradecká koule")
    vstup = st.text_area("Seznam týmů (každý na nový řádek):", height=200)
    st.session_state.max_kol = st.number_input("Počet kol:", 1, 10, 3)

    if st.button("Zahájit turnaj", type="primary"):
        seznam = [s.strip() for s in vstup.split('\n') if s.strip()]
        if len(seznam) >= 2:
            tymy_data = [{"Tým": j, "Výhry": 0, "Skóre +": 0, "Skóre -": 0, "Rozdíl": 0, "Buchholz": 0} for j in seznam]
            if len(tymy_data) % 2 != 0:
                tymy_data.append({"Tým": "VOLNÝ LOS (BYE)", "Výhry": 0, "Skóre +": 0, "Skóre -": 0, "Rozdíl": 0, "Buchholz": 0})
            st.session_state.tymy = pd.DataFrame(tymy_data)
            st.session_state.kolo = 1
            st.rerun()

# --- 2. PRŮBĚH ---
elif st.session_state.kolo <= st.session_state.max_kol:
    zobraz_logo()
    st.header(f"🏟️ {st.session_state.nazev_akce}")
    st.subheader(f"Kolo {st.session_state.kolo} z {st.session_state.max_kol}")

    # Průběžné pořadí pro nasazení
    for i, row in st.session_state.tymy.iterrows():
        st.session_state.tymy.at[i, "Buchholz"] = vypocti_buchholz(row["Tým"], st.session_state.tymy, st.session_state.historie_zapasu)
        st.session_state.tymy.at[i, "Rozdíl"] = row["Skóre +"] - row["Skóre -"]
    
    side_df = st.session_state.tymy.sort_values(by=["Výhry", "Buchholz", "Rozdíl"], ascending=False).reset_index(drop=True)
    serazene = side_df["Tým"].tolist()
    aktualni_rozpis = [(serazene[i], serazene[i+1]) for i in range(0, len(serazene), 2)]

    vysledky_kola = []
    for idx, (t1, t2) in enumerate(aktualni_rozpis):
        with st.expander(f"Zápas {idx+1}: {t1} vs {t2}", expanded=True):
            if "VOLNÝ LOS" in t1 or "VOLNÝ LOS" in t2:
                vitez = t1 if "VOLNÝ LOS" in t2 else t2
                st.write(f"⚪ {vitez} má volno (13:0)")
                vysledky_kola.append((t1, t2, (13 if "VOLNÝ LOS" in t2 else 0), (13 if "VOLNÝ LOS" in t1 else 0)))
            else:
                c1, c2 = st.columns(2)
                s1 = c1.number_input(f"{t1}", 0, 13, 0, key=f"s1_{idx}_{st.session_state.kolo}")
                s2 = c2.number_input(f"{t2}", 0, 13, 0, key=f"s2_{idx}_{st.session_state.kolo}")
                vysledky_kola.append((t1, t2, s1, s2))

    if st.button("Uložit kolo a pokračovat", type="primary"):
        for t1, t2, s1, s2 in vysledky_kola:
            idx1 = st.session_state.tymy[st.session_state.tymy["Tým"] == t1].index[0]
            idx2 = st.session_state.tymy[st.session_state.tymy["Tým"] == t2].index[0]
            st.session_state.tymy.at[idx1, "Skóre +"] += s1
            st.session_state.tymy.at[idx1, "Skóre -"] += s2
            st.session_state.tymy.at[idx2, "Skóre +"] += s2
            st.session_state.tymy.at[idx2, "Skóre -"] += s1
            if s1 > s2: st.session_state.tymy.at[idx1, "Výhry"] += 1
            elif s2 > s1: st.session_state.tymy.at[idx2, "Výhry"] += 1
            st.session_state.historie_zapasu.append((st.session_state.kolo, t1, t2, s1, s2))
        st.session_state.kolo += 1
        st.rerun()
    
    if st.session_state.kolo > 1:
        if st.button("⬅️ VRÁTIT ZPĚT POSLEDNÍ KOLO (Oprava chyb)"):
            predchozi_kolo = st.session_state.kolo - 1
            zápasy_k_mazání = [h for h in st.session_state.historie_zapasu if h[0] == predchozi_kolo]
            
            for k, t1, t2, s1, s2 in zápasy_k_mazání:
                idx1 = st.session_state.tymy[st.session_state.tymy["Tým"] == t1].index[0]
                idx2 = st.session_state.tymy[st.session_state.tymy["Tým"] == t2].index[0]
                st.session_state.tymy.at[idx1, "Skóre +"] -= s1
                st.session_state.tymy.at[idx1, "Skóre -"] -= s2
                st.session_state.tymy.at[idx2, "Skóre +"] -= s2
                st.session_state.tymy.at[idx2, "Skóre -"] -= s1
                if s1 > s2: st.session_state.tymy.at[idx1, "Výhry"] -= 1
                elif s2 > s1: st.session_state.tymy.at[idx2, "Výhry"] -= 1
            
            st.session_state.historie_zapasu = [h for h in st.session_state.historie_zapasu if h[0] != predchozi_kolo]
            st.session_state.kolo = predchozi_kolo
            st.rerun()

# --- 3. KONEC ---
else:
    zobraz_logo()
    st.balloons()
    st.title(f"🏁 {st.session_state.nazev_akce} - KONEC")
    
    for i, row in st.session_state.tymy.iterrows():
        st.session_state.tymy.at[i, "Buchholz"] = vypocti_buchholz(row["Tým"], st.session_state.tymy, st.session_state.historie_zapasu)
        st.session_state.tymy.at[i, "Rozdíl"] = row["Skóre +"] - row["Skóre -"]

    final_df = st.session_state.tymy.sort_values(by=["Výhry", "Buchholz", "Rozdíl"], ascending=False).reset_index(drop=True)
    final_df.index += 1
    
    st.header("Konečné pořadí")
    st.table(final_df[["Tým", "Výhry", "Skóre +", "Skóre -", "Rozdíl"]])

    # TLAČÍTKA PRO PDF EXPORT
    st.divider()
    col1, col2 = st.columns(2)
    
    pdf_vysledky = generuj_pdf_odkaz(final_df.reset_index(), st.session_state.nazev_akce, "vysledky")
    col1.download_button(label="📥 Stáhnout konečné pořadí (PDF)", data=pdf_vysledky, file_name="vysledky.pdf", mime="application/pdf")
    
    hist_df = pd.DataFrame(st.session_state.historie_zapasu, columns=["Kolo", "Tým 1", "Tým 2", "S1", "S2"])
    pdf_historie = generuj_pdf_odkaz(hist_df, st.session_state.nazev_akce, "historie")
    col2.download_button(label="📥 Stáhnout historii zápasů (PDF)", data=pdf_historie, file_name="historie.pdf", mime="application/pdf")
    st.divider()

    if st.button("Zahájit úplně nový turnaj"):
        st.session_state.clear()
        st.rerun()
    if st.button("Nový turnaj"):
        st.session_state.clear()
        st.rerun()
