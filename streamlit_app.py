import streamlit as st
import pandas as pd

# Nastavení vzhledu stránky
st.set_page_config(page_title="Pétanque Hradec Králové", layout="wide")

# Záhlaví s názvem klubu - OPRAVENO (správný parametr)
st.markdown("<h3 style='text-align: center; color: #555;'>Club přátel pétanque Hradec Králové</h3>", unsafe_allow_html=True)

# Inicializace stavu
if 'tymy' not in st.session_state:
    st.session_state.tymy = []
if 'kolo' not in st.session_state:
    st.session_state.kolo = 0
if 'system' not in st.session_state:
    st.session_state.system = "Švýcarský systém"
if 'rozpis_vsech_kol' not in st.session_state:
    st.session_state.rozpis_vsech_kol = []
if 'nazev_akce' not in st.session_state:
    st.session_state.nazev_akce = "Pohár Hradce Králové"
if 'historie_zapasu' not in st.session_state:
    st.session_state.historie_zapasu = []

# Funkce pro Round Robin
def generuj_round_robin(seznam_tymu):
    tymy = list(seznam_tymu)
    if len(tymy) % 2 != 0:
        tymy.append("VOLNÝ LOS (BYE)")
    n = len(tymy)
    kola = []
    indexy = list(range(n))
    for i in range(n - 1):
        parovani = []
        for j in range(n // 2):
            parovani.append((tymy[indexy[j]], tymy[indexy[n - 1 - j]]))
        kola.append(parovani)
        indexy.insert(1, indexy.pop())
    return kola

# Funkce pro výpočet Buchholze
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

# --- 1. NASTAVENÍ TURNAJE ---
if st.session_state.kolo == 0:
    st.title("🏆 Nový turnaj")
    st.session_state.nazev_akce = st.text_input("Název turnaje:", value="Pohár Hradce Králové")
    st.session_state.system = st.radio("Zvolte herní systém:", ["Švýcarský systém", "Každý s každým"])
    
    col_a, col_b = st.columns(2)
    with col_a:
        vstup = st.text_area("Seznam týmů (každý na nový řádek):", height=200)
    with col_b:
        if st.session_state.system == "Švýcarský systém":
            st.session_state.max_kol = st.number_input("Počet kol:", min_value=1, max_value=12, value=3)
        else:
            st.info("Počet kol bude určen automaticky podle počtu týmů.")

    if st.button("Zahájit turnaj", type="primary", use_container_width=True):
        seznam = [s.strip() for s in vstup.split('\n') if s.strip()]
        if len(seznam) < 2:
            st.error("Zadejte aspoň 2 týmy!")
        else:
            tymy_data = [{"Tým": j, "Výhry": 0, "Skóre +": 0, "Skóre -": 0, "Rozdíl": 0, "Buchholz": 0} for j in seznam]
            if len(tymy_data) % 2 != 0:
                tymy_data.append({"Tým": "VOLNÝ LOS (BYE)", "Výhry": 0, "Skóre +": 0, "Skóre -": 0, "Rozdíl": 0, "Buchholz": 0})
            
            st.session_state.tymy = pd.DataFrame(tymy_data)
            st.session_state.kolo = 1
            if st.session_state.system == "Každý s každým":
                st.session_state.rozpis_vsech_kol = generuj_round_robin(st.session_state.tymy["Tým"].tolist())
                st.session_state.max_kol = len(st.session_state.rozpis_vsech_kol)
            st.rerun()

# --- 2. PRŮBĚH TURNAJE ---
elif st.session_state.kolo <= st.session_state.max_kol:
    st.title(f"🏟️ {st.session_state.nazev_akce}")
    st.subheader(f"Kolo {st.session_state.kolo} z {st.session_state.max_kol} ({st.session_state.system})")

    # Aktualizace Buchholze pro průběžnou tabulku
    for i, row in st.session_state.tymy.iterrows():
        st.session_state.tymy.at[i, "Buchholz"] = vypocti_buchholz(row["Tým"], st.session_state.tymy, st.session_state.historie_zapasu)
    
    # Boční panel s pořadím - OPRAVENO (správné názvy sloupců)
    side_df = st.session_state.tymy.sort_values(by=["Výhry", "Buchholz", "Rozdíl"], ascending=False).reset_index(drop=True)
    side_df.index += 1
    st.sidebar.header("Průběžné pořadí")
    st.sidebar.table(side_df[["Tým", "Výhry", "Buchholz"]])

    # Rozpis zápasů
    if st.session_state.system == "Každý s každým":
        aktualni_rozpis = st.session_state.rozpis_vsech_kol[st.session_state.kolo - 1]
    else:
        serazene = side_df["Tým"].tolist()
        aktualni_rozpis = [(serazene[i], serazene[i+1]) for i in range(0, len(serazene), 2)]

    vysledky_kola = []
    for idx, (t1, t2) in enumerate(aktualni_rozpis):
        with st.expander(f"Zápas {idx+1}: {t1} vs {t2}", expanded=True):
            if "VOLNÝ LOS" in t1 or "VOLNÝ LOS" in t2:
                vitez_bye = t1 if "VOLNÝ LOS" in t2 else t2
                st.write(f"⚪ {vitez_bye} má volno (13:0)")
                vysledky_kola.append((t1, t2, (13 if "VOLNÝ LOS" in t2 else 0), (13 if "VOLNÝ LOS" in t1 else 0)))
            else:
                c1, c2 = st.columns(2)
                s1 = c1.number_input(f"{t1}", 0, 13, 0, key=f"s1_{idx}_{st.session_state.kolo}")
                s2 = c2.number_input(f"{t2}", 0, 13, 0, key=f"s2_{idx}_{st.session_state.kolo}")
                vysledky_kola.append((t1, t2, s1, s2))

    if st.button("Uložit kolo a pokračovat", type="primary", use_container_width=True):
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

# --- 3. KONEC TURNAJE ---
else:
    st.balloons()
    st.title(f"🏁 {st.session_state.nazev_akce} - KONEC")
    for i, row in st.session_state.tymy.iterrows():
        st.session_state.tymy.at[i, "Buchholz"] = vypocti_buchholz(row["Tým"], st.session_state.tymy, st.session_state.historie_zapasu)
    
    final_df = st.session_state.tymy.sort_values(by=["Výhry", "Buchholz", "Rozdíl"], ascending=False).reset_index(drop=True)
    final_df.index += 1
    st.header("Konečné pořadí")
    st.table(final_df)
    
    with st.expander("Zobrazit kompletní historii zápasů"):
        hist_df = pd.DataFrame(st.session_state.historie_zapasu, columns=["Kolo", "Tým 1", "Tým 2", "Body 1", "Body 2"])
        st.table(hist_df)

    if st.button("Začít nový turnaj"):
        st.session_state.clear()
        st.rerun()
