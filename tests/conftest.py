"""
Configuração compartilhada dos testes.

Gera um banco de dados temporário (isolado do data/service_desk.db real)
para cada sessão de testes, usando o mesmo gerador de dados do projeto.
Isso garante que os testes nunca mexem no banco que o dashboard usa.
"""

import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "data"))


def _carregar_modulo_gerador():
    spec = importlib.util.spec_from_file_location(
        "gerar_dados_ficticios", BASE_DIR / "data" / "gerar_dados_ficticios.py"
    )
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="session")
def gerador():
    """O módulo gerar_dados_ficticios.py carregado, para os testes usarem
    diretamente as funções de geração (criar_schema, popular_dimensoes, etc.)."""
    return _carregar_modulo_gerador()


@pytest.fixture(scope="session")
def banco_teste(tmp_path_factory, gerador):
    """Gera um banco de dados fictício isolado, só para os testes.

    Usa as mesmas funções do script real (criar_schema, popular_dimensoes,
    gerar_chamados), mas aponta para um arquivo temporário em vez do
    data/service_desk.db de verdade — assim os testes não interferem no
    banco usado pelo dashboard.
    """
    db_path = tmp_path_factory.mktemp("db") / "service_desk_teste.db"
    conn = sqlite3.connect(db_path)
    try:
        gerador.criar_schema(conn)
        gerador.popular_dimensoes(conn)
        gerador.gerar_chamados(conn)
        conn.commit()
    finally:
        conn.close()
    return db_path
