import streamlit as st
import pandas as pd
from amadeus import Client as AmadeusClient, ResponseError
from supabase import create_client, Client
import datetime
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression

# ================= CONFIGURAÇÕES =================
st.set_page_config(
    page_title="FlyShark - Radar de Passagens Inteligentes",
    page_icon="🦈",
    layout="wide"
)

APP_NAME = "FlyShark"
LOGO_PATH = "assets/logo_flyshark.png"

try:
    st.image(LOGO_PATH, width=150)
except Exception:
    st.warning("Logo não encontrada. Verifique se está em /assets/logo_flyshark.png")

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

companhias = {
    "LA": "LATAM Airlines",
    "AA": "American Airlines",
    "UA": "United Airlines",
    "DL": "Delta Airlines",
    "AF": "Air France",
    "LH": "Lufthansa",
    "BA": "British Airways",
    "AZ": "ITA Airways",
    "KL": "KLM Royal Dutch",
    "IB": "Iberia",
    "TP": "TAP Portugal",
    "CM": "Copa Airlines",
    "G3": "Gol Linhas Aéreas",
    "AD": "Azul Linhas Aéreas",
}

# ================= FUNÇÕES =================

def salvar_historico(origem, destino, data_ida, data_volta, companhia, classe, preco, status_termometro, conexoes, duracao_voo, itinerario):
    data_consulta = datetime.datetime.now().isoformat()

    data = {
        "origem": origem or "",
        "destino": destino or "",
        "data_ida": data_ida.isoformat() if data_ida else None,
        "data_volta": data_volta.isoformat() if data_volta else None,
        "companhia": companhia or "",
        "classe": classe or "",
        "preco": float(preco) if preco is not None else 0,
        "data_consulta": data_consulta,
        "status_termometro": status_termometro or "",
        "conexoes": int(conexoes) if conexoes is not None else 0,
        "duracao_voo": duracao_voo or "",
        "itinerario": itinerario or ""
    }

    try:
        supabase.table("historico_buscas").insert(data).execute()
    except Exception as e:
        st.error(f"Erro ao salvar no histórico: {e}")
        st.write("Dados:", data)


def carregar_historico():
    try:
        response = supabase.table("historico_buscas").select("*").execute()
        dados = response.data
        if not dados:
            return pd.DataFrame(columns=[
                "origem", "destino", "data_ida", "data_volta", "companhia",
                "classe", "preco", "data_consulta", "status_termometro", "conexoes",
                "duracao_voo", "itinerario"
            ])
        return pd.DataFrame(dados)
    except Exception as e:
        st.error(f"Erro ao carregar histórico: {e}")
        return pd.DataFrame()


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


def gerar_datas_no_intervalo(data_inicio, dias_range):
    return [data_inicio + datetime.timedelta(days=i) for i in range(dias_range + 1)]


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
            ida = itineraries[0]['segments']
            partida = ida[0]['departure']['iataCode']
            chegada = ida[-1]['arrival']['iataCode']
            hora_partida = ida[0]['departure']['at'][:10]
            hora_saida = ida[0]['departure']['at'][11:16]
            hora_chegada = ida[-1]['arrival']['at'][11:16]

            qtd_conexoes = len(ida) - 1

            inicio = datetime.datetime.fromisoformat(ida[0]['departure']['at'])
            fim = datetime.datetime.fromisoformat(ida[-1]['arrival']['at'])
            duracao = fim - inicio
            horas = duracao.seconds // 3600
            minutos = (duracao.seconds % 3600) // 60
            duracao_formatada = f"{duracao.days * 24 + horas}h{minutos:02d}min"

            itinerario_list = [segment['departure']['iataCode'] for segment in ida]
            itinerario_list.append(ida[-1]['arrival']['iataCode'])
            itinerario = ' → '.join(itinerario_list)

            volta = None
            hora_volta = None
            if tipo == "Ida e Volta" and len(itineraries) > 1:
                volta = itineraries[1]['segments']
                hora_volta = volta[-1]['arrival']['at'][:10]

            companhia_codigo = ida[0]['carrierCode']
            companhia_nome = companhias.get(companhia_codigo, companhia_codigo)

            status = calcular_termometro(partida, chegada, classe, price)

            resultados.append({
                "Origem": partida,
                "Destino": chegada,
                "Companhia": companhia_nome,
                "Código Companhia": companhia_codigo,
                "Data Ida": hora_partida,
                "Hora Saída": hora_saida,
                "Hora Chegada": hora_chegada,
                "Itinerário": itinerario,
                "Data Volta": hora_volta,
                "Classe": classe,
                "Preço (R$)": price,
                "Status": status,
                "Conexões": qtd_conexoes,
                "Duração Voo": duracao_formatada
            })

        return pd.DataFrame(resultados)

    except ResponseError as error:
        st.error(f"Ocorreu um erro na busca: {error}")
        return pd.DataFrame()
# ================= SIDEBAR =================

st.sidebar.header("Configurações da Busca")

aba = st.sidebar.selectbox(
    "Escolha a aba:",
    ["🔍 Buscador de Passagens", "📊 Dashboard Histórico + Tendências"]
)

origem = st.sidebar.selectbox(
    "**Origem:**",
    ["GRU (Guarulhos)", "BSB (Brasília)", "GIG (Galeão)", "VCP (Viracopos)"]
).split(" ")[0]

destinos = st.sidebar.multiselect(
    "Selecione os destinos:",
    ["CDG (Paris)", "FCO (Roma)", "LHR (Londres)", "JFK (Nova York)", "MIA (Miami)", "YYZ (Toronto)",
     "MAD (Madrid)", "BCN (Barcelona)", "FRA (Frankfurt)", "AMS (Amsterdam)", "LAX (Los Angeles)", "SFO (San Francisco)",
     "ORD (Chicago)", "DFW (Dallas)", "ATL (Atlanta)", "BOS (Boston)", "IAD (Washington)", "SEA (Seattle)",
     "DEN (Denver)", "LAS (Las Vegas)", "MCO (Orlando)", "FLL (Fort Lauderdale)", "BNA (Nashville)"],
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

st.sidebar.subheader("✈️ Filtrar Conexões")
filtro_conexoes = st.sidebar.selectbox(
    "Quantidade máxima de conexões:",
    ["Sem filtro", "Voo Direto", "Até 1 conexão", "Até 2 conexões", "Até 3 conexões"]
)

st.sidebar.markdown("---")
buscar = st.sidebar.button("🔍 Buscar")


# ================= BUSCADOR =================

if aba == "🔍 Buscador de Passagens":
    if buscar:
        if not destinos:
            st.warning("Selecione pelo menos um destino.")
        else:
            st.subheader("🦈 Resultados da Busca")
            todas_passagens = pd.DataFrame()

            for destino in destinos:
                destino_codigo = destino.split(" ")[0]
                datas_ida = gerar_datas_no_intervalo(data_ida, range_dias) if usar_range else [data_ida]

                for data in datas_ida:
                    df_parcial = buscar_passagens(origem, destino_codigo, data, data_volta, classe, tipo_viagem)

                    if not df_parcial.empty:
                        for index, row in df_parcial.iterrows():
                            salvar_historico(
                                origem=row["Origem"],
                                destino=row["Destino"],
                                data_ida=pd.to_datetime(row["Data Ida"]).date(),
                                data_volta=pd.to_datetime(row["Data Volta"]).date() if pd.notnull(row["Data Volta"]) else None,
                                companhia=row["Companhia"],
                                classe=row["Classe"],
                                preco=row["Preço (R$)"],
                                status_termometro=row["Status"],
                                conexoes=row["Conexões"],
                                duracao_voo=row["Duração Voo"],
                                itinerario=row["Itinerário"]
                            )
                        todas_passagens = pd.concat([todas_passagens, df_parcial], ignore_index=True)

            if filtro_conexoes != "Sem filtro" and not todas_passagens.empty:
                limite = {"Voo Direto": 0, "Até 1 conexão": 1, "Até 2 conexões": 2, "Até 3 conexões": 3}[filtro_conexoes]
                todas_passagens = todas_passagens[todas_passagens["Conexões"] <= limite]

            if not todas_passagens.empty:
                st.dataframe(todas_passagens)

                csv = todas_passagens.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Baixar resultados em CSV",
                    data=csv,
                    file_name='resultados_flyshark.csv',
                    mime='text/csv',
                )

                st.subheader("📊 Menor preço por dia")
                if "Data Ida" in todas_passagens.columns:
                    todas_passagens["Data Ida"] = pd.to_datetime(todas_passagens["Data Ida"])
                    coluna_preco = "Preço (R$)" if "Preço (R$)" in todas_passagens.columns else "Preço Total (R$)"
                    menor_preco_por_dia = todas_passagens.groupby("Data Ida")[coluna_preco].min().reset_index()

                    plt.figure(figsize=(10, 5))
                    plt.bar(menor_preco_por_dia["Data Ida"].dt.strftime('%Y-%m-%d'), menor_preco_por_dia[coluna_preco])
                    plt.xticks(rotation=45)
                    plt.xlabel("Data")
                    plt.ylabel("Menor Preço (R$)")
                    plt.title("Menor preço encontrado por dia")
                    plt.grid(True)
                    st.pyplot(plt)

            else:
                st.warning("Nenhum resultado encontrado para os parâmetros selecionados.")


# ================= DASHBOARD HISTÓRICO + TENDÊNCIAS =================

if aba == "📊 Dashboard Histórico + Tendências":
    st.subheader("📈 Histórico de Preços + Tendências")

    df = carregar_historico()

    if df.empty:
        st.info("O histórico ainda está vazio. Realize algumas buscas para gerar dados.")
    else:
        df["data_ida"] = pd.to_datetime(df["data_ida"])
        df["data_consulta"] = pd.to_datetime(df["data_consulta"])
        df["preco"] = df["preco"].astype(float)

        destinos_disponiveis = df["destino"].unique().tolist()
        origens_disponiveis = df["origem"].unique().tolist()

        col1, col2 = st.columns(2)
        with col1:
            origem_filtro = st.selectbox("Origem", origens_disponiveis)
        with col2:
            destino_filtro = st.selectbox("Destino", destinos_disponiveis)

        classe_filtro = st.radio(
            "Classe",
            ["Executiva", "Econômica", "Ambas"],
            horizontal=True
        )

        df_filtrado = df[
            (df["origem"] == origem_filtro) &
            (df["destino"] == destino_filtro)
        ]

        if classe_filtro != "Ambas":
            df_filtrado = df_filtrado[df_filtrado["classe"] == classe_filtro]

        if df_filtrado.empty:
            st.warning("Não há dados suficientes para esse filtro.")
        else:
            dados = df_filtrado.groupby("data_ida")["preco"].mean().reset_index()
            dados["data_ida_ordinal"] = dados["data_ida"].map(datetime.datetime.toordinal)

            X = dados[["data_ida_ordinal"]]
            y = dados["preco"]

            modelo = LinearRegression()
            modelo.fit(X, y)
            dados["tendencia"] = modelo.predict(X)

            plt.figure(figsize=(10, 5))
            plt.plot(dados["data_ida"], dados["preco"], marker='o', label='Preço Médio')
            plt.plot(dados["data_ida"], dados["tendencia"], color='red', linestyle='--', label='Tendência')
            plt.xlabel("Data de Ida")
            plt.ylabel("Preço (R$)")
            plt.title(f"Tendência de preços: {origem_filtro} → {destino_filtro} ({classe_filtro})")
            plt.legend()
            plt.grid(True)
            plt.xticks(rotation=45)
            st.pyplot(plt)

            st.subheader("📄 Dados do Histórico")
            st.dataframe(df_filtrado)

            csv = df_filtrado.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Baixar histórico em CSV",
                data=csv,
                file_name='historico_flyshark.csv',
                mime='text/csv',
            )

# ================= FOOTER =================
st.markdown("---")
st.caption("🦈 FlyShark — Radar de Passagens Inteligentes | V4 — powered by Fernando Tessaro 🚀")
