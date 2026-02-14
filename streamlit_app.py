
import streamlit as st
import pandas as pd

# Nastavení vzhledu stránky
st.set_page_config(page_title="Pétanque Hradec Králové", layout="wide")

# Záhlaví s názvem klubu - OPRAVENO
st.markdown("<h3 style='text-align: center; color: #555;'>Klub přátel pétanque Hradec Králové</h3>", unsafe_allow_html=True)
st.title("🏆 Turnajový manažer")
st.divider()

# Inicializace stavu
if 'tymy' not in st.session_state:
    st.session_state.tymy = []
if 'kolo' not in st.session_state:
    st.session_state.kolo = 0
if 'max_kol' not in st.session_state:
    st.session_state.max_kol = 3
if 'rozpis' not in st.session_state:
    st.session_state.rozpis = []
if 'nazev_akce' not in st.session_state:
    st.session_state.nazev_akce = "Místní turnaj"

# --- 1. NASTAVENÍ TURNAJE ---
if st.session_state.kolo == 0:
    st.header("⚙️ Nastavení turnaje")
    
    st.session_state.nazev_akce = st.text_input("Název turnaje:", value="Pohár Hradce Králové")
    
    col_a, col_b = st.columns(2)
    with col_a:
        vstup = st.text_area("Seznam týmů (každý tým na nový řádek):", height=200, placeholder="Např.:\nKoule HK\nDraci z Pardubic\nStřelci")
    with col_b:
        st.session_state.max_kol = st.number_input("Počet kol (Švýcarský systém):", min_value=1, max_value=12, value=3)
        st.info("Švýcar se obvykle hraje na 3 až 5 kol.")

    if st.button("Zahájit turnaj", type="primary", use_container_width=True):
        seznam = [s.strip() for s in vstup.split('\n') if s.strip()]
        if len(seznam) < 2:
            st.error("Zadejte prosím alespoň 2 týmy!")
        else:
            tymy_data = []
            for jmeno in seznam:
                tymy_data.append({"Tým": jmeno, "Výhry": 0, "Skóre +": 0, "Skóre -": 0, "Rozdíl": 0})
            
            if len(tymy_data) % 2 != 0:
                tymy_data.append({"Tým": "VOLNÝ LOS (BYE)", "Výhry": 0, "Skóre +": 0, "Skóre -": 0, "Rozdíl": 0})
            
            st.session_state.tymy = pd.DataFrame(tymy_data)
            st.session_state.kolo = 1
            st.rerun()

# --- 2. PRŮBĚH TURNAJE ---
else:
    st.subheader(f"🏟️ {st.session_state.nazev_akce}")
    
    # Konec turnaje
    if st.session_state.kolo > st.session_state.max_kol:
        st.balloons()
        st.header("🏁 Turnaj skončil!")
        
        st.session_state.tymy["Rozdíl"] = st.session_state.tymy["Skóre +"] - st.session_state.tymy["Skóre -"]
        final_df = st.session_state.tymy.sort_values(by=["Výhry", "Rozdíl", "Skóre +"], ascending=False).reset_index(drop=True)
        final_df.index += 1
        
        st.write("### Konečná tabulka")
        st.table(final_df)
        
        vitez = final_df.iloc[0]["Tým"]
        st.success(f"🥇 Na 1. místě se umístil tým: **{vitez}**")
        
        if st.button("Nový turnaj"):
            st.session_state.clear()
            st.rerun()

    # Probíhající kolo
    else:
        st.session_state.tymy["Rozdíl"] = st.session_state.tymy["Skóre +"] - st.session_state.tymy["Skóre -"]
        st.session_state.tymy = st.session_state.tymy.sort_values(by=["Výhry", "Rozdíl", "Skóre +"], ascending=False).reset_index(drop=True)

        # Boční panel s tabulkou
        st.sidebar.header("Průběžné pořadí")
        side_df = st.session_state.tymy.copy()
        side_df.index += 1
        st.sidebar.table(side_df[["Tým", "Výhry", "Rozdíl"]])

        st.info(f"Kolo {st.session_state.kolo} z {st.session_state.max_kol}")

        # Rozpis
        if not st.session_state.rozpis:
            t_list = st.session_state.tymy["Tým"].tolist()
            parovani = []
            for i in range(0, len(t_list), 2):
                parovani.append((t_list[i], t_list[i+1]))
            st.session_state.rozpis = parovani

        st.write("#### Rozlosování a výsledky")
        vysledky_kola = []

        for idx, (t1, t2) in enumerate(st.session_state.rozpis):
            with st.expander(f"Zápas {idx+1}: {t1} vs {t2}", expanded=True):
                if "VOLNÝ LOS" in t2:
                    st.write(f"⚪ {t1} má v tomto kole volno.")
                    vysledky_kola.append((t1, t2, 13, 0))
                elif "VOLNÝ LOS" in t1:
                    st.write(f"⚪ {t2} má v tomto kole volno.")
                    vysledky_kola.append((t1, t2, 0, 13))
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
            
            st.session_state.kolo += 1
            st.session_state.rozpis = []
            st.rerun()
