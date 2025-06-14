import streamlit as st
import pandas as pd
from amadeus import Client, ResponseError
import os

# ========== CONFIGURAÇÕES DO APP ==========
st.set_page_config(
    page_title="FlyShark - Radar de Passagens Inteligentes",
    page_icon="🦈",
    layout="wide"
)

APP_NAME = "FlyShark"
LOGO_PATH = "assets/logo_flyshark.png"

# ========== CABEÇALHO ==========
st.image(LOGO_PATH, width=150)
st.title(f"{APP_NAME} 🦈✈️")
st.subheader("Radar de Passagens Inteligentes — Voe como Tubarão, pague como Sardinha.")

st.markdown("---")

# ========== CONEXÃO COM A API AMADEUS ==========
# Insira suas credenciais da Amadeus API
amadeus = Client(
    client_id=st.secrets["AMADEUS_CLIENT_ID"],
    client_secret=st.secrets["AMADEUS_CLIENT_SECRET"]
)

# ========== SIDEBAR ==========
st.sidebar.header("Configurações da Busca")

# Origem fixa (GRU)
st.sidebar.write("**Origem:** GRU (Guarulhos)")

# Destinos pré-definidos
destinos = st.sidebar.multiselect(
    "Selecione os destinos:",
    ["CDG (Paris)", "FCO (Roma)", "LHR (Londres)", "JFK (Nova York)",
     "MIA (Miami)", "YYZ (Toronto)", "MAD (Madrid)", "BCN (Barcelona)",
     "FRA (Frankfurt)", "AMS (Amsterdam)"],
    default=["CDG (Paris)", "JFK (Nova York)"]
)

# Tipo de viagem
tipo_viagem = st.sidebar.radio(
    "Tipo de Viagem:",
    ["Ida e Volta", "Só Ida", "Só Volta"]
)

# Classe
classe = st.sidebar.radio(
    "Classe:",
    ["Econômica", "Executiva", "Ambas"]
)

# Datas
data_ida = st.sidebar.date_input("Data de Ida")
data_volta = None
if tipo_viagem == "Ida e Volta":
    data_volta = st.sidebar.date_input("Data de Volta")

# Filtro de preço
preco_max = st.sidebar.number_input(
    "Preço máximo (R$):",
    min_value=1000,
    max_value=20000,
    value=6500
)

st.sidebar.markdown("---")
buscar = st.sidebar.button("🔍 Buscar")

# ========== FUNÇÃO DE BUSCA ==========
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
            price = offer['price']['total']
            itineraries = offer['itineraries']
            ida = itineraries[0]['segments'][0]
            companhia = ida['carrierCode']
            partida = ida['departure']['iataCode']
            chegada = ida['arrival']['iataCode']
            hora_partida = ida['departure']['at'][:10]

            volta = None
            if tipo == "Ida e Volta" and len(itineraries) > 1:
                volta = itineraries[1]['segments'][0]
                hora_volta = volta['departure']['at'][:10]
            else:
                hora_volta = None

            resultados.append({
                "Origem": partida,
                "Destino": chegada,
                "Companhia": companhia,
                "Data Ida": hora_partida,
                "Data Volta": hora_volta,
                "Classe": classe,
                "Preço (R$)": float(price)
            })

        return pd.DataFrame(resultados)

    except ResponseError as error:
        st.error(f"Ocorreu um erro na busca: {error}")
        return pd.DataFrame()

# ========== RESULTADO ==========
if buscar:
    if not destinos:
        st.warning("Selecione pelo menos um destino.")
    else:
        st.subheader("🦈 Resultados da Busca")
        todas_passagens = pd.DataFrame()

        for destino in destinos:
            destino_codigo = destino.split(" ")[0]
            df = buscar_passagens("GRU", destino_codigo, data_ida, data_volta, classe, tipo_viagem)
            todas_passagens = pd.concat([todas_passagens, df], ignore_index=True)

        if not todas_passagens.empty:
            st.dataframe(todas_passagens)

            # Download
            csv = todas_passagens.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Baixar resultados em CSV",
                data=csv,
                file_name='resultados_flyshark.csv',
                mime='text/csv',
            )
        else:
            st.warning("Nenhum resultado encontrado para os parâmetros selecionados.")

st.markdown("---")
st.caption("🦈 FlyShark — Radar de Passagens Inteligentes | V1")

