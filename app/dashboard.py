"""
dashboard.py — Service Desk Dashboard (Streamlit)

Painel de indicadores de um service desk simulado: volume de chamados,
SLA cumprido vs. estourado, distribuição por severidade, causas raiz
e produtividade por analista. Lê diretamente do SQLite gerado por
data/gerar_dados_ficticios.py.

Rodar localmente:
    streamlit run app/dashboard.py

Deploy gratuito: Streamlit Community Cloud (streamlit.io/cloud),
apontando para este mesmo arquivo como "main file".
"""

import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "service_desk.db"

st.set_page_config(
    page_title="Service Desk Dashboard",
    page_icon="🎫",
    layout="wide",
)


@st.cache_data(ttl=300)
def carregar_dados() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT
            c.id_chamado,
            cat.nome AS categoria,
            cat.sla_horas,
            a.nome AS analista,
            a.nivel AS nivel_analista,
            c.severidade,
            c.status,
            c.data_abertura,
            c.data_resolucao,
            c.reaberto,
            c.causa_raiz
        FROM chamados c
        JOIN categorias cat ON cat.id_categoria = c.id_categoria
        LEFT JOIN analistas a ON a.id_analista = c.id_analista
    """
    df = pd.read_sql_query(query, conn, parse_dates=["data_abertura", "data_resolucao"])
    conn.close()

    df["tempo_resolucao_horas"] = (
        df["data_resolucao"] - df["data_abertura"]
    ).dt.total_seconds() / 3600

    df["dentro_sla"] = (df["tempo_resolucao_horas"] <= df["sla_horas"]).astype("boolean")
    df.loc[df["data_resolucao"].isna(), "dentro_sla"] = pd.NA

    return df


def main() -> None:
    if not DB_PATH.exists():
        st.error(
            "Banco de dados não encontrado. Rode antes:\n\n"
            "`python data/gerar_dados_ficticios.py`"
        )
        st.stop()

    df = carregar_dados()

    st.title("🎫 Service Desk Dashboard")
    st.caption(
        "Painel de indicadores de suporte técnico — dados fictícios, "
        "estrutura e métricas baseadas em um ambiente real de service desk."
    )

    # ---- filtros na sidebar ----
    with st.sidebar:
        st.header("Filtros")
        categorias_sel = st.multiselect(
            "Categoria", sorted(df["categoria"].unique()), default=None
        )
        severidades_sel = st.multiselect(
            "Severidade", ["Baixa", "Média", "Alta", "Crítica"], default=None
        )
        status_sel = st.multiselect(
            "Status", sorted(df["status"].unique()), default=None
        )

    df_filtrado = df.copy()
    if categorias_sel:
        df_filtrado = df_filtrado[df_filtrado["categoria"].isin(categorias_sel)]
    if severidades_sel:
        df_filtrado = df_filtrado[df_filtrado["severidade"].isin(severidades_sel)]
    if status_sel:
        df_filtrado = df_filtrado[df_filtrado["status"].isin(status_sel)]

    # ---- KPIs ----
    total_chamados = len(df_filtrado)
    resolvidos = df_filtrado["data_resolucao"].notna().sum()
    taxa_reabertura = (
        100 * df_filtrado["reaberto"].sum() / resolvidos if resolvidos else 0
    )
    dentro_sla_pct = (
        100 * df_filtrado["dentro_sla"].sum() / resolvidos if resolvidos else 0
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total de chamados", f"{total_chamados:,}".replace(",", "."))
    col2.metric("Resolvidos", f"{resolvidos:,}".replace(",", "."))
    col3.metric("Dentro do SLA", f"{dentro_sla_pct:.1f}%")
    col4.metric("Taxa de reabertura", f"{taxa_reabertura:.1f}%")

    st.divider()

    # ---- gráficos ----
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Volume de chamados por dia")
        volume_dia = (
            df_filtrado.groupby(df_filtrado["data_abertura"].dt.date)
            .size()
            .reset_index(name="chamados")
        )
        fig = px.line(volume_dia, x="data_abertura", y="chamados", markers=True)
        fig.update_layout(xaxis_title="Data", yaxis_title="Chamados abertos")
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.subheader("SLA cumprido vs. estourado")
        sla_df = (
            df_filtrado.dropna(subset=["dentro_sla"])
            .assign(status_sla=lambda d: d["dentro_sla"].map({True: "Dentro do SLA", False: "Fora do SLA"}))
            .groupby("status_sla")
            .size()
            .reset_index(name="total")
        )
        fig = px.pie(sla_df, names="status_sla", values="total", hole=0.5)
        st.plotly_chart(fig, use_container_width=True)

    col_c, col_d = st.columns(2)

    with col_c:
        st.subheader("Distribuição por severidade")
        sev_df = df_filtrado.groupby("severidade").size().reset_index(name="total")
        ordem = ["Baixa", "Média", "Alta", "Crítica"]
        sev_df["severidade"] = pd.Categorical(sev_df["severidade"], categories=ordem, ordered=True)
        sev_df = sev_df.sort_values("severidade")
        fig = px.bar(sev_df, x="severidade", y="total", color="severidade")
        st.plotly_chart(fig, use_container_width=True)

    with col_d:
        st.subheader("Tempo médio de resolução por categoria (h)")
        tempo_df = (
            df_filtrado.dropna(subset=["tempo_resolucao_horas"])
            .groupby("categoria")["tempo_resolucao_horas"]
            .mean()
            .round(1)
            .sort_values(ascending=False)
            .reset_index()
        )
        fig = px.bar(tempo_df, x="tempo_resolucao_horas", y="categoria", orientation="h")
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    col_e, col_f = st.columns(2)

    with col_e:
        st.subheader("Causas raiz mais recorrentes")
        causa_df = (
            df_filtrado.dropna(subset=["causa_raiz"])
            .groupby("causa_raiz")
            .size()
            .sort_values(ascending=False)
            .reset_index(name="ocorrencias")
            .head(10)
        )
        fig = px.bar(causa_df, x="ocorrencias", y="causa_raiz", orientation="h")
        st.plotly_chart(fig, use_container_width=True)

    with col_f:
        st.subheader("Produtividade por analista")
        prod_df = (
            df_filtrado.dropna(subset=["analista"])
            .groupby(["analista", "nivel_analista"])
            .size()
            .reset_index(name="chamados_atendidos")
            .sort_values("chamados_atendidos", ascending=False)
        )
        st.dataframe(prod_df, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Chamados em aberto perto de estourar o SLA")
    risco_df = df_filtrado[
        df_filtrado["status"].isin(["Aberto", "Em Atendimento"])
    ].copy()
    if not risco_df.empty:
        risco_df["horas_decorridas"] = (
            pd.Timestamp.now() - risco_df["data_abertura"]
        ).dt.total_seconds() / 3600
        risco_df["pct_sla_consumido"] = (
            100 * risco_df["horas_decorridas"] / risco_df["sla_horas"]
        ).round(0)
        risco_df = risco_df[risco_df["pct_sla_consumido"] >= 80].sort_values(
            "pct_sla_consumido", ascending=False
        )
        st.dataframe(
            risco_df[
                ["id_chamado", "categoria", "severidade", "sla_horas",
                 "horas_decorridas", "pct_sla_consumido"]
            ].round(1),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Nenhum chamado em risco de estourar o SLA no momento.")


if __name__ == "__main__":
    main()
