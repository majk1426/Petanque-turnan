import streamlit as st
import pandas as pd
import itertools

# Nastavení vzhledu stránky
st.set_page_config(page_title="Pétanque Hradec Králové", layout="wide")

# Záhlaví s názvem klubu
st.markdown("<h3 style='text-align: center; color: #555;'>Club přátel pétanque Hradec Králové</h3>", unsafe_allow_html=True)
st.title("🏆 Turnajový manažer")
st.divider()

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
    st.session_state.nazev_akce = "Místní turnaj"

# Funkce pro generování systému každý s každým (Round Robin)
def generuj_round_robin(tymy):
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

# --- 1. NASTAVENÍ TURNAJE ---
if st.session_state.kolo == 0:
    st.header("⚙️ Nastavení turnaje")
    st.session_state.nazev_akce = st.text_input("Název turnaje:", value="Pohár Hradce Králové")
    
    st.session_state.system = st.radio("Zvolte herní systém:", ["Švýcarský systém", "Každý s každým"])
    
    col_a, col_b = st.columns(2)
    with col_a:
        vstup = st.text_area("Seznam týmů (každý na nový řádek):", height=200)
    with col_b:
        if st.session_state.system == "Švýcarský systém":
            max_kol_val = st.number_input("Počet kol:", min_value=1, max_value=12, value=3)
            st.info("Ve Švýcaru se týmy párují podle výsledků po každém kole.")
        else:
            st.info("V systému 'Každý s každým' bude počet kol určen automaticky podle počtu týmů.")
            max_kol_val = 0 

    if st.button("Zahájit turnaj", type="primary", use_container_width=True):
        seznam = [s.strip() for s in vstup.split('\n') if s.strip()]
        if len(seznam) < 2:
            st.error("Zadejte aspoň 2 týmy!")
        else:
            tymy_data = [{"Tým": j, "Výhry": 0, "Skóre +": 0, "Skóre -": 0, "Rozdíl": 0} for j in seznam]
            if len(tymy_data) % 2 != 0:
                tymy_data.append({"Tým": "VOLNÝ LOS (BYE)", "Výhry": 0, "Skóre +": 0, "Skóre -": 0, "Rozdíl": 0})
            
            st.session_state.tymy = pd.DataFrame(tymy_data)
            st.session_state.kolo = 1
            
            if st.session_state.system == "Každý s každým":
                st.session_state.rozpis_vsech_kol = generuj_round_robin(st.session_state.tymy["Tým"].tolist())
                st.session_state.max_kol = len(st.session_state.rozpis_vsech_kol)
            else:
                st.session_state.max_kol = max_kol_val
            st.rerun()

# --- 2. PRŮBĚH TURNAJE ---
elif st.session_state.kolo > st.session_state.max_kol:
    st.balloons()
    st.header("🏁 Turnaj skončil!")
    st.session_state.tymy["Rozdíl"] = st.session_state.tymy["Skóre +"] - st.session_state.tymy["Skóre -"]
    final_df = st.session_state.tymy.sort_values(by=["Výhry", "Rozdíl", "Skóre +"], ascending=False).reset_index(drop=True)
    final_df.index += 1
    st.table(final_df)
    st.success(f"🥇 Vítěz: **{final_df.iloc[0]['Tým']}**")
    if st.button("Nový turnaj"):
        st.session_state.clear()
        st.rerun()

else:
    st.subheader(f"🏟️ {st.session_state.nazev_akce} ({st.session_state.system})")
    st.info(f"Kolo {st.session_state.kolo} z {st.session_state.max_kol}")

    # Příprava rozpisu pro aktuální kolo
    if st.session_state.system == "Každý s každým":
        aktualni_rozpis = st.session_state.rozpis_vsech_kol[st.session_state.kolo - 1]
    else:
        # Švýcar: párujeme podle aktuálního pořadí
        st.session_state.tymy["Rozdíl"] = st.session_state.tymy["Skóre +"] - st.session_state.tymy["Skóre -"]
        serazene = st.session_state.tymy.sort_values(by=["Výhry", "Rozdíl", "Skóre +"], ascending=False)["Tým"].tolist()
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

    if st.button("Uložit výsledky", type="primary", use_container_width=True):
        for t1, t2, s1, s2 in vysledky_kola:
            idx1 = st.session_state.tymy[st.session_state.tymy["Tým"] == t1].index[0]
            idx2 = st.session_state.tymy[st.session_state.tymy["Tým"] == t2].index[0]
            st.session_state.tymy.at[idx1, "Skóre +"] += s1
            st.session_state.tymy.at[idx1, "Skóre -"] += s2
            st.session_state.tymy.at[idx2, "Skóre +"] += s2
            st.session_state.tymy.at[idx2, "Skóre -"] += s1
            if s1 > s2: st.session_state.tymy.at[idx1, "Výhry"] += 1
            elif s2 > s1: st.session_state.tymy.at[idx2, "Výhry"] += 1
        st.session_state.kolo += 1
        st.rerun()
