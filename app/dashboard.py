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

import os
import sqlite3
import sys
import time
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.io as pio
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "service_desk.db"
LOCK_PATH = DB_PATH.with_suffix(".lock")

# ---------------------------------------------------------------------------
# Paleta de cores — usada em todos os gráficos para manter identidade visual
# consistente. Cores semânticas (SLA, severidade) carregam significado, não
# são só decoração.
# ---------------------------------------------------------------------------
COR_PRIMARIA = "#4F8EF7"
COR_SLA = {"Dentro do SLA": "#3DDC84", "Fora do SLA": "#FF5C5C"}
COR_SEVERIDADE = {
    "Baixa": "#3DDC84",
    "Média": "#F5C542",
    "Alta": "#FF8C42",
    "Crítica": "#FF5C5C",
}
SEQUENCIA_CATEGORICA = [
    "#4F8EF7", "#6FD3C7", "#F5C542", "#FF8C42", "#C792EA",
    "#5CC8FF", "#FF5C5C", "#8FD14F", "#A78BFA",
]

pio.templates.default = "plotly_dark"


def _ensure_db() -> None:
    """Garante que o banco existe, gerando-o na primeira execução.

    Necessário em plataformas de deploy (ex: Streamlit Community Cloud) onde
    não há como rodar o script de geração antes do deploy. Usa um lock de
    arquivo (O_CREAT|O_EXCL, atômico no SO) para que, se mais de uma sessão
    cair aqui ao mesmo tempo (comum em plataformas que podem iniciar o app
    mais de uma vez), só uma gere o banco — as outras aguardam o resultado
    em vez de tentar gerar em paralelo e corromper o arquivo.
    """
    if DB_PATH.exists():
        return

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    try:
        lock_fd = os.open(LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        # outra execução já está gerando o banco: aguarda até 60s por ela
        for _ in range(120):
            if DB_PATH.exists():
                return
            time.sleep(0.5)
        raise RuntimeError(
            "Timeout aguardando a geração do banco por outra execução."
        )

    try:
        os.close(lock_fd)
        sys.path.insert(0, str(BASE_DIR / "data"))
        import gerar_dados_ficticios
        gerar_dados_ficticios.main()
    finally:
        LOCK_PATH.unlink(missing_ok=True)


st.set_page_config(
    page_title="Service Desk Dashboard",
    page_icon="🎫",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    div[data-testid="stMetric"] {
        background-color: rgba(255, 255, 255, 0.04);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 10px;
        padding: 14px 16px 10px 16px;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 0.85rem;
        opacity: 0.75;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if not DB_PATH.exists():
    with st.spinner("Preparando o banco de dados fictício (só acontece na primeira vez)..."):
        _ensure_db()


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
    _ensure_db()

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
        st.divider()
        st.caption(
            "[Código no GitHub](https://github.com/euguisantosdev/service-desk-dashboard)"
        )

    df_filtrado = df.copy()
    if categorias_sel:
        df_filtrado = df_filtrado[df_filtrado["categoria"].isin(categorias_sel)]
    if severidades_sel:
        df_filtrado = df_filtrado[df_filtrado["severidade"].isin(severidades_sel)]
    if status_sel:
        df_filtrado = df_filtrado[df_filtrado["status"].isin(status_sel)]

    if df_filtrado.empty:
        st.warning("Nenhum chamado corresponde aos filtros selecionados.")
        st.stop()

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
        fig = px.line(
            volume_dia, x="data_abertura", y="chamados", markers=True,
            color_discrete_sequence=[COR_PRIMARIA],
        )
        fig.update_layout(xaxis_title="Data", yaxis_title="Chamados abertos")
        fig.update_traces(line_width=2.5)
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
        fig = px.pie(
            sla_df, names="status_sla", values="total", hole=0.5,
            color="status_sla", color_discrete_map=COR_SLA,
        )
        fig.update_traces(textinfo="percent+label")
        st.plotly_chart(fig, use_container_width=True)

    col_c, col_d = st.columns(2)

    with col_c:
        st.subheader("Distribuição por severidade")
        sev_df = df_filtrado.groupby("severidade").size().reset_index(name="total")
        ordem = ["Baixa", "Média", "Alta", "Crítica"]
        sev_df["severidade"] = pd.Categorical(sev_df["severidade"], categories=ordem, ordered=True)
        sev_df = sev_df.sort_values("severidade")
        fig = px.bar(
            sev_df, x="severidade", y="total", color="severidade",
            color_discrete_map=COR_SEVERIDADE,
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col_d:
        st.subheader("Tempo médio de resolução por categoria (h)")
        tempo_df = (
            df_filtrado.dropna(subset=["tempo_resolucao_horas"])
            .groupby("categoria")["tempo_resolucao_horas"]
            .mean()
            .round(1)
            .sort_values(ascending=True)
            .reset_index()
        )
        fig = px.bar(
            tempo_df, x="tempo_resolucao_horas", y="categoria", orientation="h",
            color_discrete_sequence=[COR_PRIMARIA],
        )
        fig.update_layout(yaxis_title="", xaxis_title="Horas")
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    col_e, col_f = st.columns(2)

    with col_e:
        st.subheader("Causas raiz mais recorrentes")
        causa_df = (
            df_filtrado.dropna(subset=["causa_raiz"])
            .groupby("causa_raiz")
            .size()
            .sort_values(ascending=True)
            .reset_index(name="ocorrencias")
            .tail(10)
        )
        fig = px.bar(
            causa_df, x="ocorrencias", y="causa_raiz", orientation="h",
            color_discrete_sequence=[COR_PRIMARIA],
        )
        fig.update_layout(yaxis_title="", xaxis_title="Ocorrências")
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
        st.dataframe(
            prod_df.rename(columns={
                "analista": "Analista",
                "nivel_analista": "Nível",
                "chamados_atendidos": "Chamados atendidos",
            }),
            use_container_width=True,
            hide_index=True,
        )

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
        if risco_df.empty:
            st.info("Nenhum chamado em risco de estourar o SLA no momento.")
        else:
            exibir = risco_df[
                ["id_chamado", "categoria", "severidade", "sla_horas",
                 "horas_decorridas", "pct_sla_consumido"]
            ].round(1).rename(columns={
                "id_chamado": "Chamado",
                "categoria": "Categoria",
                "severidade": "Severidade",
                "sla_horas": "SLA (h)",
                "horas_decorridas": "Horas decorridas",
                "pct_sla_consumido": "% do SLA consumido",
            })
            st.dataframe(
                exibir.style.background_gradient(
                    subset=["% do SLA consumido"], cmap="Reds",
                ),
                use_container_width=True,
                hide_index=True,
            )
    else:
        st.info("Nenhum chamado em risco de estourar o SLA no momento.")

    st.caption(
        "Dados fictícios, gerados automaticamente. "
        "[Guilherme dos Santos Bueno](https://github.com/euguisantosdev) — Sorocaba/SP"
    )


if __name__ == "__main__":
    main()
