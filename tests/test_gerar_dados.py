"""Testes do gerador de dados fictícios (data/gerar_dados_ficticios.py)."""

import sqlite3


def test_total_de_chamados_gerado(banco_teste, gerador):
    conn = sqlite3.connect(banco_teste)
    total = conn.execute("SELECT COUNT(*) FROM chamados").fetchone()[0]
    conn.close()
    assert total == gerador.N_CHAMADOS


def test_todas_as_categorias_foram_criadas(banco_teste, gerador):
    conn = sqlite3.connect(banco_teste)
    total = conn.execute("SELECT COUNT(*) FROM categorias").fetchone()[0]
    conn.close()
    assert total == len(gerador.CATEGORIAS)


def test_todos_os_analistas_foram_criados(banco_teste, gerador):
    conn = sqlite3.connect(banco_teste)
    total = conn.execute("SELECT COUNT(*) FROM analistas").fetchone()[0]
    conn.close()
    assert total == len(gerador.ANALISTAS)


def test_severidades_sao_validas(banco_teste):
    conn = sqlite3.connect(banco_teste)
    severidades = {row[0] for row in conn.execute("SELECT DISTINCT severidade FROM chamados")}
    conn.close()
    assert severidades <= {"Baixa", "Média", "Alta", "Crítica"}


def test_status_sao_validos(banco_teste):
    conn = sqlite3.connect(banco_teste)
    status = {row[0] for row in conn.execute("SELECT DISTINCT status FROM chamados")}
    conn.close()
    assert status <= {"Aberto", "Em Atendimento", "Resolvido", "Reaberto", "Cancelado"}


def test_chamados_resolvidos_tem_data_resolucao_e_causa_raiz(banco_teste):
    conn = sqlite3.connect(banco_teste)
    linhas = conn.execute(
        """
        SELECT data_resolucao, causa_raiz FROM chamados
        WHERE status IN ('Resolvido', 'Reaberto')
        """
    ).fetchall()
    conn.close()
    assert linhas, "deveria haver pelo menos um chamado resolvido para testar"
    for data_resolucao, causa_raiz in linhas:
        assert data_resolucao is not None
        assert causa_raiz is not None


def test_chamados_abertos_nao_tem_data_resolucao(banco_teste):
    conn = sqlite3.connect(banco_teste)
    linhas = conn.execute(
        "SELECT data_resolucao FROM chamados WHERE status IN ('Aberto', 'Em Atendimento')"
    ).fetchall()
    conn.close()
    assert linhas, "deveria haver pelo menos um chamado em aberto para testar"
    for (data_resolucao,) in linhas:
        assert data_resolucao is None


def test_chamados_em_aberto_nao_concentram_tudo_no_mesmo_dia(banco_teste):
    """Regressão: um bug anterior fazia a maior parte dos chamados em
    aberto caírem no mesmo dia (hoje), criando um pico artificial no
    gráfico de volume (chegava a ~300 chamados em um único dia, contra
    uma média de ~10/dia nos demais). Este teste garante que nenhum dia
    isolado concentra uma fração desproporcional do backlog em aberto."""
    import collections

    conn = sqlite3.connect(banco_teste)
    datas = [
        row[0]
        for row in conn.execute(
            """
            SELECT DATE(data_abertura) FROM chamados
            WHERE status IN ('Aberto', 'Em Atendimento')
            """
        )
    ]
    conn.close()

    assert datas, "deveria haver chamados em aberto para testar"

    contagem_por_dia = collections.Counter(datas)
    dia_mais_concentrado, maior_contagem = contagem_por_dia.most_common(1)[0]
    fracao_no_dia_mais_concentrado = maior_contagem / len(datas)

    assert len(contagem_por_dia) >= 2, (
        "chamados em aberto concentrados em um único dia — "
        "possível regressão do bug do pico no gráfico"
    )
    assert fracao_no_dia_mais_concentrado < 0.6, (
        f"{fracao_no_dia_mais_concentrado:.0%} dos chamados em aberto caíram "
        f"no mesmo dia ({dia_mais_concentrado}) — possível regressão do bug "
        "do pico no gráfico de volume"
    )


def test_seed_fixa_gera_banco_reprodutivel(tmp_path, gerador):
    """A seed fixa (random.seed(42)) garante que qualquer pessoa que rodar
    o script gera exatamente o mesmo banco — isso é o que o README promete."""
    import random

    def gerar_total(caminho):
        random.seed(42)
        conn = sqlite3.connect(caminho)
        try:
            gerador.criar_schema(conn)
            gerador.popular_dimensoes(conn)
            gerador.gerar_chamados(conn)
            conn.commit()
            return conn.execute("SELECT COUNT(*) FROM chamados").fetchone()[0]
        finally:
            conn.close()

    total_1 = gerar_total(tmp_path / "db1.db")
    total_2 = gerar_total(tmp_path / "db2.db")
    assert total_1 == total_2 == gerador.N_CHAMADOS
