"""Testes do script de automação de alerta de SLA (automacao/alerta_sla.py)."""

import importlib.util
import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def alerta_sla():
    sys.path.insert(0, str(BASE_DIR / "automacao"))
    spec = importlib.util.spec_from_file_location(
        "alerta_sla", BASE_DIR / "automacao" / "alerta_sla.py"
    )
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_gerar_relatorio_sem_banco_levanta_erro_claro(alerta_sla, tmp_path):
    db_inexistente = tmp_path / "nao_existe.db"
    with pytest.raises(FileNotFoundError, match="Rode antes"):
        alerta_sla.gerar_relatorio(db_path=db_inexistente)


def test_gerar_relatorio_retorna_apenas_chamados_em_risco_ou_estourados(
    alerta_sla, banco_teste
):
    linhas = alerta_sla.gerar_relatorio(db_path=banco_teste)
    for linha in linhas:
        pct_sla_consumido = linha[6]
        assert pct_sla_consumido >= 80


def test_escrever_relatorio_cria_arquivo_com_conteudo_esperado(
    alerta_sla, banco_teste, tmp_path
):
    linhas = alerta_sla.gerar_relatorio(db_path=banco_teste)
    relatorio_path = tmp_path / "relatorio_teste.txt"

    alerta_sla.escrever_relatorio(linhas, relatorio_path=relatorio_path)

    assert relatorio_path.exists()
    conteudo = relatorio_path.read_text(encoding="utf-8")
    assert "RELATÓRIO DE ALERTA DE SLA" in conteudo
    assert f"Total de chamados em risco ou estourados: {len(linhas)}" in conteudo


def test_escrever_relatorio_sem_chamados_em_risco_nao_quebra(alerta_sla, tmp_path):
    relatorio_path = tmp_path / "relatorio_vazio.txt"
    alerta_sla.escrever_relatorio([], relatorio_path=relatorio_path)

    conteudo = relatorio_path.read_text(encoding="utf-8")
    assert "Total de chamados em risco ou estourados: 0" in conteudo
