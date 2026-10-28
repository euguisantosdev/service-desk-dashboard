"""
alerta_sla.py

Varre os chamados abertos/em atendimento e identifica quais estão perto de
estourar o SLA (>= 80% do prazo consumido) ou já estouraram.

Gera um relatório em texto (automacao/relatorio_sla.txt) — em um cenário
real, esse mesmo resultado dispararia um e-mail/Slack para o analista
responsável. Aqui ele só escreve o arquivo para manter o projeto 100%
executável sem precisar de credenciais de SMTP.

Uso:
    python automacao/alerta_sla.py
"""

import sqlite3
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "service_desk.db"
RELATORIO_PATH = BASE_DIR / "automacao" / "relatorio_sla.txt"

QUERY_RISCO = """
SELECT
    c.id_chamado,
    cat.nome AS categoria,
    c.severidade,
    c.data_abertura,
    cat.sla_horas,
    ROUND((JULIANDAY('now') - JULIANDAY(c.data_abertura)) * 24, 1) AS horas_decorridas,
    ROUND(100.0 * (JULIANDAY('now') - JULIANDAY(c.data_abertura)) * 24 / cat.sla_horas, 0) AS pct_sla_consumido
FROM chamados c
JOIN categorias cat ON cat.id_categoria = c.id_categoria
WHERE c.status IN ('Aberto', 'Em Atendimento')
  AND (JULIANDAY('now') - JULIANDAY(c.data_abertura)) * 24 / cat.sla_horas >= 0.8
ORDER BY pct_sla_consumido DESC
"""


def gerar_relatorio() -> list[tuple]:
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Banco não encontrado em {DB_PATH}. "
            "Rode antes: python data/gerar_dados_ficticios.py"
        )

    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(QUERY_RISCO)
        linhas = cur.fetchall()
    finally:
        conn.close()
    return linhas


def escrever_relatorio(linhas: list[tuple]) -> None:
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    estourados = [l for l in linhas if l[6] >= 100]
    em_risco = [l for l in linhas if l[6] < 100]

    with open(RELATORIO_PATH, "w", encoding="utf-8") as f:
        f.write(f"RELATÓRIO DE ALERTA DE SLA — gerado em {agora}\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Total de chamados em risco ou estourados: {len(linhas)}\n")
        f.write(f"  - Já estourados: {len(estourados)}\n")
        f.write(f"  - Em risco (>=80% do SLA consumido): {len(em_risco)}\n\n")

        if estourados:
            f.write("CHAMADOS ESTOURADOS (ação imediata):\n")
            f.write("-" * 60 + "\n")
            for (id_chamado, categoria, sev, abertura, sla_h, horas, pct) in estourados[:20]:
                f.write(
                    f"#{id_chamado:<6} {categoria:<25} {sev:<8} "
                    f"SLA: {sla_h}h | decorrido: {horas}h ({pct:.0f}%)\n"
                )
            if len(estourados) > 20:
                f.write(f"... e mais {len(estourados) - 20} chamados estourados.\n")
            f.write("\n")

        if em_risco:
            f.write("CHAMADOS EM RISCO (agir antes de estourar):\n")
            f.write("-" * 60 + "\n")
            for (id_chamado, categoria, sev, abertura, sla_h, horas, pct) in em_risco[:20]:
                f.write(
                    f"#{id_chamado:<6} {categoria:<25} {sev:<8} "
                    f"SLA: {sla_h}h | decorrido: {horas}h ({pct:.0f}%)\n"
                )
            if len(em_risco) > 20:
                f.write(f"... e mais {len(em_risco) - 20} chamados em risco.\n")

    print(f"Relatório gerado em {RELATORIO_PATH}")
    print(f"  {len(estourados)} estourados | {len(em_risco)} em risco")


def main() -> None:
    linhas = gerar_relatorio()
    escrever_relatorio(linhas)


if __name__ == "__main__":
    main()
