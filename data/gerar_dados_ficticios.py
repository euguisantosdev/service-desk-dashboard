"""
gerar_dados_ficticios.py

Cria o banco SQLite a partir do schema e popula com chamados fictícios,
mas com distribuição realista (SLA estourando mais em categorias críticas,
reabertura ocorrendo mais em categorias complexas, etc).

Uso:
    python data/gerar_dados_ficticios.py

Gera: data/service_desk.db
"""

import sqlite3
import random
from datetime import datetime, timedelta
from pathlib import Path

random.seed(42)  # reprodutibilidade

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "service_desk.db"
SCHEMA_PATH = BASE_DIR / "sql" / "schema.sql"

N_CHAMADOS = 2000
DIAS_HISTORICO = 180  # últimos 6 meses

ANALISTAS = [
    ("Carla Nogueira", "N1"),
    ("Bruno Castilho", "N1"),
    ("Fernanda Lima", "N2"),
    ("Rafael Souza", "N2"),
    ("Juliana Prado", "N3"),
    ("Diego Martins", "N3"),
]

CATEGORIAS = [
    ("Acesso/Senha", 4),
    ("ERP - Financeiro", 8),
    ("ERP - Estoque", 8),
    ("Rede/VPN", 6),
    ("Hardware", 24),
    ("E-mail/Office 365", 4),
    ("Impressora", 12),
    ("Sistema Interno Legado", 48),
    ("Banco de Dados/SQL", 24),
]

SEVERIDADES = ["Baixa", "Média", "Alta", "Crítica"]
PESOS_SEVERIDADE = [0.40, 0.35, 0.18, 0.07]  # a maioria é baixa/média, igual na vida real

CAUSAS_RAIZ = [
    "Erro de configuração do usuário",
    "Falha de integração entre sistemas",
    "Senha expirada",
    "Permissão de acesso incorreta",
    "Falha de hardware",
    "Queda de link/rede",
    "Atualização de sistema sem comunicação prévia",
    "Procedimento não seguido pelo usuário",
    "Bug em módulo do ERP",
    "Capacidade/performance de banco de dados",
]


def criar_schema(conn: sqlite3.Connection) -> None:
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    conn.executescript(sql)


def popular_dimensoes(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.executemany(
        "INSERT INTO analistas (nome, nivel) VALUES (?, ?)", ANALISTAS
    )
    cur.executemany(
        "INSERT INTO categorias (nome, sla_horas) VALUES (?, ?)", CATEGORIAS
    )
    conn.commit()


def escolher_severidade() -> str:
    return random.choices(SEVERIDADES, weights=PESOS_SEVERIDADE, k=1)[0]


def gerar_chamados(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()

    cur.execute("SELECT id_categoria, sla_horas FROM categorias")
    categorias = cur.fetchall()  # [(id, sla_horas), ...]

    cur.execute("SELECT id_analista FROM analistas")
    analistas_ids = [row[0] for row in cur.fetchall()]

    agora = datetime.now()
    linhas = []

    for _ in range(N_CHAMADOS):
        id_categoria, sla_horas = random.choice(categorias)
        severidade = escolher_severidade()

        # decide primeiro se o chamado está resolvido ou ainda em aberto,
        # porque isso muda a janela de datas plausível:
        # - resolvido: pode ter sido aberto a qualquer momento nos últimos 6 meses
        # - ainda aberto/em atendimento: só faz sentido ser recente (ninguém
        #   deixa um chamado parado por meses sem status)
        resolvido = random.random() < 0.80

        if resolvido:
            dias_atras = random.uniform(0.1, DIAS_HISTORICO)
        else:
            # até 3x o SLA da categoria (em dias) ou no máximo 5 dias,
            # o que for menor, pra simular backlog realista
            dias_atras = random.uniform(0.05, min(5, max(0.5, sla_horas / 24 * 3)))

        data_abertura = agora - timedelta(days=dias_atras)

        # severidade mais alta tende a ser atendida mais rápido (prática comum),
        # mas com alguma chance de estourar o SLA mesmo assim
        multiplicador_severidade = {
            "Crítica": 0.5,
            "Alta": 0.7,
            "Média": 1.0,
            "Baixa": 1.3,
        }[severidade]

        status = None
        data_resolucao = None
        causa_raiz = None
        reaberto = 0

        if resolvido:
            # tempo de resolução: a maioria dentro do SLA, uma fração estoura
            estourou_sla = random.random() < 0.22
            if estourou_sla:
                horas_resolucao = sla_horas * random.uniform(1.1, 3.0) * multiplicador_severidade
            else:
                horas_resolucao = sla_horas * random.uniform(0.15, 0.95) * multiplicador_severidade

            data_resolucao_dt = data_abertura + timedelta(hours=horas_resolucao)
            if data_resolucao_dt > agora:
                data_resolucao_dt = agora

            data_resolucao = data_resolucao_dt.strftime("%Y-%m-%d %H:%M:%S")
            causa_raiz = random.choice(CAUSAS_RAIZ)

            # chamados de categorias mais complexas reabrem mais
            chance_reabertura = 0.18 if sla_horas >= 24 else 0.06
            reaberto = 1 if random.random() < chance_reabertura else 0
            status = "Reaberto" if reaberto else "Resolvido"
        else:
            status = random.choices(
                ["Aberto", "Em Atendimento"], weights=[0.3, 0.7], k=1
            )[0]

        id_analista = random.choice(analistas_ids) if status != "Aberto" else None

        linhas.append(
            (
                id_categoria,
                id_analista,
                severidade,
                status,
                data_abertura.strftime("%Y-%m-%d %H:%M:%S"),
                data_resolucao,
                reaberto,
                causa_raiz,
                f"Chamado de {severidade.lower()} severidade — categoria relacionada.",
            )
        )

    cur.executemany(
        """
        INSERT INTO chamados (
            id_categoria, id_analista, severidade, status,
            data_abertura, data_resolucao, reaberto, causa_raiz, descricao
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        linhas,
    )
    conn.commit()


def main() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    try:
        criar_schema(conn)
        popular_dimensoes(conn)
        gerar_chamados(conn)
        total = conn.execute("SELECT COUNT(*) FROM chamados").fetchone()[0]
        print(f"Banco gerado em {DB_PATH} com {total} chamados.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
