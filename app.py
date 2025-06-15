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
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

amadeus = AmadeusClient(
    client_id=st.secrets["AMADEUS_CLIENT_ID"],
    client_secret=st.secrets["AMADEUS_CLIENT_SECRET"]
)

# ================= FUNÇÕES =================

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


def carregar_historico():
    response = supabase.table("historico_buscas").select("*").execute()
    return pd.DataFrame(response.data)


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


def gerar_datas_no_intervalo(data_inicio, dias_range):
    return [data_inicio + datetime.timedelta(days=i) for i in range(dias_range + 1)]


def buscar_tubarao(origem, destino, datas_ida, classe, preco_max, permanencia_min, permanencia_max):
    resultados = []

    for data_ida in datas_ida:
        df_ida = buscar_passagens(origem, destino, data_ida, None, classe, "Só Ida")

        if not df_ida.empty:
            for _, row in df_ida.iterrows():
                preco_ida = row["Preço (R$)"]
                status = row["Status"]

                if preco_ida <= preco_max or status in ["🟢 Barato", "🔥 Oportunidade"]:
                    datas_volta = gerar_datas_no_intervalo(
                        pd.to_datetime(row["Data Ida"]).date() + datetime.timedelta(days=permanencia_min),
                        permanencia_max - permanencia_min
                    )

                    for data_volta in datas_volta:
                        df_volta = buscar_passagens(destino, origem, data_volta, None, classe, "Só Volta")

                        if not df_volta.empty:
                            for _, row2 in df_volta.iterrows():
                                resultados.append({
                                    "Origem": row["Origem"],
                                    "Destino": row["Destino"],
                                    "Companhia Ida": row["Companhia"],
                                    "Companhia Volta": row2["Companhia"],
                                    "Data Ida": row["Data Ida"],
                                    "Data Volta": row2["Data Ida"],
                                    "Classe": classe,
                                    "Preço Ida (R$)": preco_ida,
                                    "Preço Volta (R$)": row2["Preço (R$)"],
                                    "Preço Total (R$)": preco_ida + row2["Preço (R$)"],
                                    "Status Ida": status,
                                    "Status Volta": row2["Status"]
                                })
    return pd.DataFrame(resultados)


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

st.sidebar.subheader("🗓️ Intervalo de Datas")
usar_range = st.sidebar.checkbox("Ativar busca por intervalo de datas")

range_dias = 0
if usar_range:
    range_dias = st.sidebar.slider(
        "Quantos dias de intervalo?",
        min_value=1,
        max_value=300,
        value=7
    )

st.sidebar.subheader("🦈 Modo Tubarão")
modo_tubarao = st.sidebar.checkbox("Ativar Inteligência do Tubarão™")

if modo_tubarao:
    permanencia_min = st.sidebar.slider(
        "Permanência mínima (dias)",
        min_value=1,
        max_value=30,
        value=7
    )
    permanencia_max = st.sidebar.slider(
        "Permanência máxima (dias)",
        min_value=permanencia_min,
        max_value=60,
        value=15
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
            datas_ida = gerar_datas_no_intervalo(data_ida, range_dias) if usar_range else [data_ida]

            if modo_tubarao:
                df = buscar_tubarao(
                    "GRU", destino_codigo,
                    datas_ida=datas_ida,
                    classe=classe,
                    preco_max=preco_max,
                    permanencia_min=permanencia_min,
                    permanencia_max=permanencia_max
                )
            else:
                df = pd.DataFrame()
                for data in datas_ida:
                    df_parcial = buscar_passagens("GRU", destino_codigo, data, data_volta, classe, tipo_viagem)
                    df = pd.concat([df, df_parcial], ignore_index=True)

            if not df.empty:
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

            if "Data Ida" in todas_passagens.columns:
                todas_passagens["Data Ida"] = pd.to_datetime(todas_passagens["Data Ida"])
                menor_preco_por_dia = todas_passagens.groupby("Data Ida")["Preço (R$)" if "Preço (R$)" in todas_passagens.columns else "Preço Total (R$)"].min().reset_index()

                plt.figure(figsize=(10, 5))
                plt.bar(menor_preco_por_dia["Data Ida"].dt.strftime('%Y-%m-%d'), menor_preco_por_dia.iloc[:, 1])
                plt.xticks(rotation=45)
                plt.xlabel("Data")
                plt.ylabel("Menor Preço (R$)")
                plt.title("Menor preço encontrado por dia")
                st.pyplot(plt)

        else:
            st.warning("Nenhum resultado encontrado para os parâmetros selecionados.")

st.markdown("---")
st.caption("🦈 FlyShark — Radar de Passagens Inteligentes | V3 + Inteligência do Tubarão™ 🚀")
