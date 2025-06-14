import streamlit as st
import pandas as pd
from amadeus import Client as AmadeusClient, ResponseError
from supabase import create_client, Client
import datetime
import matplotlib.pyplot as plt

# ================= CONFIGURAÇÕES =================
st.set_page_config(
    page_title="FlyShark - Radar de Passagens Inteligentes",
    page_icon="🦈",
    layout="wide"
)

APP_NAME = "FlyShark"
LOGO_PATH = "assets/logo_flyshark.png"

st.image(LOGO_PATH, width=150)
st.title(f"{APP_NAME} 🦈✈️")
st.subheader("Radar de Passagens Inteligentes — Voe como Tubarão, pague como Sardinha.")
st.markdown("---")

# ================= CONEXÕES =================
# Supabase
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

# Amadeus
amadeus = AmadeusClient(
    client_id=st.secrets["AMADEUS_CLIENT_ID"],
    client_secret=st.secrets["AMADEUS_CLIENT_SECRET"]
)

# ================= FUNÇÕES =================

# Função: salvar no histórico
def salvar_historico(origem, destino, data_ida, data_volta, companhia, classe, preco, status_termometro):
    data_consulta = datetime.datetime.now().isoformat()

    data = {
        "origem": origem,
        "destino": destino,
        "data_ida": data_ida.isoformat(),
        "data_volta": data_volta.isoformat() if data_volta else None,
        "companhia": companhia,
        "classe": classe,
        "preco": preco,
        "data_consulta": data_consulta,
        "status_termometro": status_termometro
    }

    supabase.table("historico_buscas").insert(data).execute()

# Função: carregar histórico
def carregar_historico():
    response = supabase.table("historico_buscas").select("*").execute()
    return pd.DataFrame(response.data)

# Função: calcular termômetro
def calcular_termometro(origem, destino, classe, preco_atual):
    df = carregar_historico()
    df = df[(df['origem'] == origem) & (df['destino'] == destino) & (df['classe'] == classe)]

    if df.empty or len(df) < 5:
        return "🟡 Está na média"

    media = df['preco'].mean()
    if preco_atual >= media * 1.15:
        return "🔴 Caro"
    elif preco_atual <= media * 0.75:
        return "🔥 Oportunidade"
    elif preco_atual <= media * 0.9:
        return "🟢 Barato"
    else:
        return "🟡 Está na média"

# Função: buscar passagens
def buscar_passagens(origem, destino, data_ida, data_volta, classe, tipo):
    try:
        params = {
            "originLocationCode": origem,
            "destinationLocationCode": destino,
            "departureDate": str(data_ida),
            "adults": 1,
            "currencyCode": "BRL",
            "max": 10,
        }

        if tipo == "Ida e Volta" and data_volta:
            params["returnDate"] = str(data_volta)

        if classe != "Ambas":
            params["travelClass"] = "ECONOMY" if classe == "Econômica" else "BUSINESS"

        response = amadeus.shopping.flight_offers_search.get(**params)
        data = response.data

        resultados = []
        for offer in data:
            price = float(offer['price']['total'])
            itineraries = offer['itineraries']
            ida = itineraries[0]['segments'][0]
            companhia = ida['carrierCode']
            partida = ida['departure']['iataCode']
            chegada = ida['arrival']['iataCode']
            hora_partida = ida['departure']['at'][:10]

            volta = None
            hora_volta = None
            if tipo == "Ida e Volta" and len(itineraries) > 1:
                volta = itineraries[1]['segments'][0]
                hora_volta = volta['departure']['at'][:10]

            status = calcular_termometro(partida, chegada, classe, price)

            resultados.append({
                "Origem": partida,
                "Destino": chegada,
                "Companhia": companhia,
                "Data Ida": hora_partida,
                "Data Volta": hora_volta,
                "Classe": classe,
                "Preço (R$)": price,
                "Status": status
            })

        return pd.DataFrame(resultados)

    except ResponseError as error:
        st.error(f"Ocorreu um erro na busca: {error}")
        return pd.DataFrame()

# ================= SIDEBAR =================

st.sidebar.header("Configurações da Busca")
st.sidebar.write("**Origem:** GRU (Guarulhos)")

destinos = st.sidebar.multiselect(
    "Selecione os destinos:",
    ["CDG (Paris)", "FCO (Roma)", "LHR (Londres)", "JFK (Nova York)", "MIA (Miami)", "YYZ (Toronto)",
     "MAD (Madrid)", "BCN (Barcelona)", "FRA (Frankfurt)", "AMS (Amsterdam)", "LAX (Los Angeles)", "SFO (San Francisco)",
     "ORD (Chicago)", "DFW (Dallas)", "ATL (Atlanta)", "BOS (Boston)", "IAD (Washington)", "SEA (Seattle)", "DEN (Denver)", "LAS (Las Vegas)"],
    default=["CDG (Paris)", "JFK (Nova York)"]
)

tipo_viagem = st.sidebar.radio(
    "Tipo de Viagem:",
    ["Ida e Volta", "Só Ida", "Só Volta"]
)

classe = st.sidebar.radio(
    "Classe:",
    ["Econômica", "Executiva", "Ambas"]
)

data_ida = st.sidebar.date_input("Data de Ida")
data_volta = None
if tipo_viagem == "Ida e Volta":
    data_volta = st.sidebar.date_input("Data de Volta")

preco_max = st.sidebar.number_input(
    "Preço máximo (R$):",
    min_value=1000,
    max_value=20000,
    value=6500
)

st.sidebar.markdown("---")
buscar = st.sidebar.button("🔍 Buscar")

# ================= RESULTADO =================

if buscar:
    if not destinos:
        st.warning("Selecione pelo menos um destino.")
    else:
        st.subheader("🦈 Resultados da Busca")
        todas_passagens = pd.DataFrame()

        for destino in destinos:
            destino_codigo = destino.split(" ")[0]
            df = buscar_passagens("GRU", destino_codigo, data_ida, data_volta, classe, tipo_viagem)

            if not df.empty:
                for index, row in df.iterrows():
                    salvar_historico(
                        origem=row["Origem"],
                        destino=row["Destino"],
                        data_ida=pd.to_datetime(row["Data Ida"]).date(),
                        data_volta=pd.to_datetime(row["Data Volta"]).date() if row["Data Volta"] else None,
                        companhia=row["Companhia"],
                        classe=row["Classe"],
                        preco=row["Preço (R$)"],
                        status_termometro=row["Status"]
                    )

            todas_passagens = pd.concat([todas_passagens, df], ignore_index=True)

        if not todas_passagens.empty:
            st.dataframe(todas_passagens)

            csv = todas_passagens.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Baixar resultados em CSV",
                data=csv,
                file_name='resultados_flyshark.csv',
                mime='text/csv',
            )

            # ========== GRÁFICO DE MENOR PREÇO ==========
            st.subheader("📊 Menor preço por dia")

            todas_passagens["Data Ida"] = pd.to_datetime(todas_passagens["Data Ida"])
            menor_preco_por_dia = todas_passagens.groupby("Data Ida")["Preço (R$)"].min().reset_index()

            plt.figure(figsize=(10, 5))
            plt.bar(menor_preco_por_dia["Data Ida"].dt.strftime('%Y-%m-%d'), menor_preco_por_dia["Preço (R$)"])
            plt.xticks(rotation=45)
            plt.xlabel("Data")
            plt.ylabel("Menor Preço (R$)")
            plt.title("Menor preço encontrado por dia")
            st.pyplot(plt)

        else:
            st.warning("Nenhum resultado encontrado para os parâmetros selecionados.")

st.markdown("---")
st.caption("🦈 FlyShark — Radar de Passagens Inteligentes | V2 🚀")
