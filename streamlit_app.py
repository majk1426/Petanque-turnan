import streamlit as st
import pandas as pd
from fpdf import FPDF
import base64

# --- NASTAVENÍ ---
KLUB_NAZEV = "Club přátel pétanque HK"
st.set_page_config(page_title=KLUB_NAZEV, layout="wide")

# Funkce pro zobrazení loga (pokud je soubor v repozitáři)
def zobraz_logo():
    try:
        st.image("logo.jpg", width=150) # Ujisti se, že se soubor jmenuje logo.jpg
    except:
        st.write(f"### {KLUB_NAZEV}")

# CSS pro skrytí Buchholze v tabulce pro uživatele
hide_table_row_index = """
            <style>
            thead tr th:first-child {display:none}
            tbody th {display:none}
            </style>
            """

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

def vytvor_pdf_vysledky(df, nazev_akce):
    pdf = FPDF()
    pdf.add_page()
    pdf.add_font('DejaVu', '', 'https://github.com/reingart/pyfpdf/raw/master/font/DejaVuSans.ttf', uni=True)
    pdf.set_font('DejaVu', '', 16)
    pdf.cell(190, 10, txt=f"{KLUB_NAZEV}", ln=True, align='C')
    pdf.set_font('DejaVu', '', 14)
    pdf.cell(190, 10, txt=f"Výsledky: {nazev_akce}", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font('DejaVu', '', 10)
    
    # Hlavička tabulky (bez BHZ)
    cols = ["Pořadí", "Tým", "Výhry", "Skóre +", "Skóre -", "Rozdíl"]
    for col in cols:
        pdf.cell(30, 10, col, border=1)
    pdf.ln()
    
    for i, row in df.iterrows():
        pdf.cell(30, 10, str(i), border=1)
        pdf.cell(30, 10, str(row['Tým']), border=1)
        pdf.cell(30, 10, str(row['Výhry']), border=1)
        pdf.cell(30, 10, str(row['Skóre +']), border=1)
        pdf.cell(30, 10, str(row['Skóre -']), border=1)
        pdf.cell(30, 10, str(row['Rozdíl']), border=1)
        pdf.ln()
    return pdf.output(dest='S').encode('latin-1', errors='ignore')

# --- INICIALIZACE STAVU ---
if 'tymy' not in st.session_state:
    st.session_state.tymy = []
if 'kolo' not in st.session_state:
    st.session_state.kolo = 0
if 'historie_zapasu' not in st.session_state:
    st.session_state.historie_zapasu = []

# --- 1. ÚVODNÍ NASTAVENÍ ---
if st.session_state.kolo == 0:
    zobraz_logo()
    st.title("🏆 Turnajový manažer")
    st.session_state.nazev_akce = st.text_input("Název turnaje:", value="Hradecká koule")
    st.session_state.system = st.radio("Herní systém:", ["Švýcarský systém", "Každý s každým"])
    
    vstup = st.text_area("Seznam týmů (každý na nový řádek):")
    max_kol_input = st.number_input("Počet kol:", 1, 10, 3)

    if st.button("Zahájit turnaj", type="primary"):
        seznam = [s.strip() for s in vstup.split('\n') if s.strip()]
        if len(seznam) >= 2:
            tymy_data = [{"Tým": j, "Výhry": 0, "Skóre +": 0, "Skóre -": 0, "Rozdíl": 0, "Buchholz": 0} for j in seznam]
            if len(tymy_data) % 2 != 0:
                tymy_data.append({"Tým": "VOLNÝ LOS (BYE)", "Výhry": 0, "Skóre +": 0, "Skóre -": 0, "Rozdíl": 0, "Buchholz": 0})
            st.session_state.tymy = pd.DataFrame(tymy_data)
            st.session_state.kolo = 1
            st.session_state.max_kol = max_kol_input
            st.rerun()

# --- 2. PRŮBĚH TURNAJE ---
elif st.session_state.kolo <= st.session_state.max_kol:
    zobraz_logo()
    st.header(f"🏟️ {st.session_state.nazev_akce}")
    st.subheader(f"Kolo {st.session_state.kolo} z {st.session_state.max_kol}")

    # Výpočet pořadí (pro rozlosování)
    for i, row in st.session_state.tymy.iterrows():
        st.session_state.tymy.at[i, "Buchholz"] = vypocti_buchholz(row["Tým"], st.session_state.tymy, st.session_state.historie_zapasu)
        st.session_state.tymy.at[i, "Rozdíl"] = row["Skóre +"] - row["Skóre -"]
    
    side_df = st.session_state.tymy.sort_values(by=["Výhry", "Buchholz", "Rozdíl"], ascending=False).reset_index(drop=True)
    
    # Rozlosování Švýcar
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

    col1, col2 = st.columns(2)
    if col1.button("Uložit kolo a pokračovat", type="primary", use_container_width=True):
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
    
    if col2.button("⚠️ Opravit výsledky tohoto kola", use_container_width=True):
        st.session_state.historie_zapasu = [h for h in st.session_state.historie_zapasu if h[0] != st.session_state.kolo]
        st.warning("Výsledky kola byly smazány. Zadejte je znovu a uložte.")

# --- 3. KONEC TURNAJE ---
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
    # Zobrazení tabulky bez Buchholze pro uživatele
    st.table(final_df[["Tým", "Výhry", "Skóre +", "Skóre -", "Rozdíl"]])

    with st.expander("Kompletní historie zápasů"):
        st.table(pd.DataFrame(st.session_state.historie_zapasu, columns=["Kolo", "Tým 1", "Tým 2", "S1", "S2"]))

    if st.button("Nový turnaj"):
        st.session_state.clear()
        st.rerun()
