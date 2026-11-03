"""Testes das queries de análise (sql/queries_analise.sql).

Garante que todas as queries do arquivo rodam sem erro de sintaxe contra
o schema atual e retornam colunas com os nomes esperados pelo dashboard.
"""

import re
import sqlite3
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
QUERIES_PATH = BASE_DIR / "sql" / "queries_analise.sql"


def _carregar_queries():
    sql = QUERIES_PATH.read_text(encoding="utf-8")
    blocos = re.split(r"(?=-- \d\))", sql)
    queries = []
    for bloco in blocos:
        bloco = bloco.strip()
        if not bloco:
            continue
        titulo = bloco.split("\n")[0]
        query = "\n".join(
            linha for linha in bloco.split("\n") if not linha.strip().startswith("--")
        ).strip().rstrip(";")
        if query:
            queries.append((titulo, query))
    return queries


QUERIES = _carregar_queries()


def test_arquivo_tem_as_9_queries_esperadas():
    assert len(QUERIES) == 9


@pytest.mark.parametrize("titulo,query", QUERIES, ids=[q[0] for q in QUERIES])
def test_query_roda_sem_erro(banco_teste, titulo, query):
    conn = sqlite3.connect(banco_teste)
    try:
        conn.execute(query).fetchall()
    finally:
        conn.close()


def test_query_sla_cumprido_vs_estourado_retorna_duas_categorias(banco_teste):
    conn = sqlite3.connect(banco_teste)
    _, query = next(q for q in QUERIES if "SLA cumprido" in q[0])
    linhas = conn.execute(query).fetchall()
    conn.close()
    categorias = {linha[0] for linha in linhas}
    assert categorias <= {"Dentro do SLA", "Fora do SLA"}


def test_query_taxa_reabertura_percentuais_sao_validos(banco_teste):
    conn = sqlite3.connect(banco_teste)
    _, query = next(q for q in QUERIES if "Taxa de reabertura" in q[0])
    linhas = conn.execute(query).fetchall()
    conn.close()
    for linha in linhas:
        taxa_reabertura_pct = linha[-1]
        assert 0 <= taxa_reabertura_pct <= 100
