-- queries_analise.sql
-- Consultas que um gestor de service desk realmente pede.
-- Rodar contra data/service_desk.db (SQLite).

-- 1) Volume de chamados por dia (últimos 30 dias)
SELECT
    DATE(data_abertura)        AS dia,
    COUNT(*)                   AS total_chamados
FROM chamados
WHERE data_abertura >= DATE('now', '-30 days')
GROUP BY dia
ORDER BY dia;

-- 2) SLA cumprido vs. estourado (apenas chamados resolvidos)
SELECT
    CASE
        WHEN (JULIANDAY(c.data_resolucao) - JULIANDAY(c.data_abertura)) * 24 <= cat.sla_horas
            THEN 'Dentro do SLA'
        ELSE 'Fora do SLA'
    END AS status_sla,
    COUNT(*) AS total
FROM chamados c
JOIN categorias cat ON cat.id_categoria = c.id_categoria
WHERE c.data_resolucao IS NOT NULL
GROUP BY status_sla;

-- 3) Tempo médio de resolução por categoria (em horas)
SELECT
    cat.nome                                           AS categoria,
    ROUND(AVG((JULIANDAY(c.data_resolucao) - JULIANDAY(c.data_abertura)) * 24), 1) AS tempo_medio_horas,
    cat.sla_horas                                      AS sla_padrao_horas,
    COUNT(*)                                            AS qtd_chamados
FROM chamados c
JOIN categorias cat ON cat.id_categoria = c.id_categoria
WHERE c.data_resolucao IS NOT NULL
GROUP BY cat.nome
ORDER BY tempo_medio_horas DESC;

-- 4) Taxa de reabertura por categoria
SELECT
    cat.nome                                            AS categoria,
    COUNT(*)                                            AS total_resolvidos,
    SUM(c.reaberto)                                     AS total_reabertos,
    ROUND(100.0 * SUM(c.reaberto) / COUNT(*), 1)        AS taxa_reabertura_pct
FROM chamados c
JOIN categorias cat ON cat.id_categoria = c.id_categoria
WHERE c.data_resolucao IS NOT NULL
GROUP BY cat.nome
ORDER BY taxa_reabertura_pct DESC;

-- 5) Chamados fora do SLA por categoria (visão de risco)
SELECT
    cat.nome AS categoria,
    COUNT(*) AS total_fora_sla
FROM chamados c
JOIN categorias cat ON cat.id_categoria = c.id_categoria
WHERE c.data_resolucao IS NOT NULL
  AND (JULIANDAY(c.data_resolucao) - JULIANDAY(c.data_abertura)) * 24 > cat.sla_horas
GROUP BY cat.nome
ORDER BY total_fora_sla DESC;

-- 6) Ranking de causas raiz mais recorrentes
SELECT
    causa_raiz,
    COUNT(*) AS ocorrencias
FROM chamados
WHERE causa_raiz IS NOT NULL
GROUP BY causa_raiz
ORDER BY ocorrencias DESC;

-- 7) Distribuição de chamados por severidade e status atual
SELECT
    severidade,
    status,
    COUNT(*) AS total
FROM chamados
GROUP BY severidade, status
ORDER BY
    CASE severidade
        WHEN 'Crítica' THEN 1
        WHEN 'Alta' THEN 2
        WHEN 'Média' THEN 3
        WHEN 'Baixa' THEN 4
    END,
    status;

-- 8) Produtividade por analista (chamados resolvidos e tempo médio)
SELECT
    a.nome                                              AS analista,
    a.nivel,
    COUNT(*)                                             AS chamados_resolvidos,
    ROUND(AVG((JULIANDAY(c.data_resolucao) - JULIANDAY(c.data_abertura)) * 24), 1) AS tempo_medio_horas
FROM chamados c
JOIN analistas a ON a.id_analista = c.id_analista
WHERE c.data_resolucao IS NOT NULL
GROUP BY a.nome, a.nivel
ORDER BY chamados_resolvidos DESC;

-- 9) Chamados abertos agora que estão perto de estourar o SLA (>80% do prazo consumido)
SELECT
    c.id_chamado,
    cat.nome                                            AS categoria,
    c.severidade,
    c.data_abertura,
    cat.sla_horas,
    ROUND((JULIANDAY('now') - JULIANDAY(c.data_abertura)) * 24, 1) AS horas_decorridas,
    ROUND(100.0 * (JULIANDAY('now') - JULIANDAY(c.data_abertura)) * 24 / cat.sla_horas, 0) AS pct_sla_consumido
FROM chamados c
JOIN categorias cat ON cat.id_categoria = c.id_categoria
WHERE c.status IN ('Aberto', 'Em Atendimento')
  AND (JULIANDAY('now') - JULIANDAY(c.data_abertura)) * 24 / cat.sla_horas >= 0.8
ORDER BY pct_sla_consumido DESC;
