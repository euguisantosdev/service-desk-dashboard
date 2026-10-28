-- schema.sql
-- Schema do "Service Desk Dashboard": banco simplificado de chamados de suporte
-- SGBD alvo: SQLite (compatível com MySQL/Postgres com pequenos ajustes de tipo)

PRAGMA foreign_keys = ON;

-- Analistas que atendem os chamados
CREATE TABLE IF NOT EXISTS analistas (
    id_analista     INTEGER PRIMARY KEY AUTOINCREMENT,
    nome            TEXT NOT NULL,
    nivel           TEXT NOT NULL CHECK (nivel IN ('N1', 'N2', 'N3'))
);

-- Categorias de chamado (ex: Acesso, ERP, Rede, Hardware...)
CREATE TABLE IF NOT EXISTS categorias (
    id_categoria    INTEGER PRIMARY KEY AUTOINCREMENT,
    nome            TEXT NOT NULL UNIQUE,
    sla_horas        INTEGER NOT NULL  -- prazo padrão de SLA para essa categoria, em horas
);

-- Chamados abertos pelos usuários/clientes
CREATE TABLE IF NOT EXISTS chamados (
    id_chamado          INTEGER PRIMARY KEY AUTOINCREMENT,
    id_categoria         INTEGER NOT NULL,
    id_analista          INTEGER,                     -- pode estar sem analista (fila)
    severidade           TEXT NOT NULL CHECK (severidade IN ('Baixa', 'Média', 'Alta', 'Crítica')),
    status                TEXT NOT NULL CHECK (status IN ('Aberto', 'Em Atendimento', 'Resolvido', 'Reaberto', 'Cancelado')),
    data_abertura         TEXT NOT NULL,   -- ISO 8601: 'YYYY-MM-DD HH:MM:SS'
    data_resolucao        TEXT,            -- NULL se ainda não resolvido
    reaberto              INTEGER NOT NULL DEFAULT 0 CHECK (reaberto IN (0, 1)),
    causa_raiz            TEXT,            -- preenchido na resolução
    descricao             TEXT,
    FOREIGN KEY (id_categoria) REFERENCES categorias(id_categoria),
    FOREIGN KEY (id_analista) REFERENCES analistas(id_analista)
);

CREATE INDEX IF NOT EXISTS idx_chamados_status ON chamados(status);
CREATE INDEX IF NOT EXISTS idx_chamados_categoria ON chamados(id_categoria);
CREATE INDEX IF NOT EXISTS idx_chamados_data_abertura ON chamados(data_abertura);
