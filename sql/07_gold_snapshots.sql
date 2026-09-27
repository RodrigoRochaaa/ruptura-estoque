-- Snapshots: as métricas centrais recalculadas em várias datas, cada uma só com o próprio passado.
-- É a base da calibração: em cada data dá para ver o que aconteceu depois com cada produto.
DROP TABLE IF EXISTS gold.snapshots;
CREATE TABLE gold.snapshots AS
WITH datas AS (
  -- Timestamp sem fuso: com timestamptz, o horário de verão do servidor desloca as datas geradas.
  -- A última data mensal é setembro de 2011 porque a calibração precisa de 90 dias de futuro.
  SELECT g.d::date AS data_ref
  FROM generate_series(TIMESTAMP '2010-03-01', TIMESTAMP '2011-09-01', INTERVAL '1 month') AS g(d)
  UNION
  SELECT data_ref FROM meta.parametros
),
base AS (
  SELECT r.data_ref,
         v.stockcode,
         MIN(v.dia)         AS primeira_venda,
         MAX(v.dia)         AS ultima_venda,
         COUNT(*)           AS dias_com_venda,
         SUM(v.faturamento) AS faturamento_total
  FROM datas r
  -- Só o que era conhecido em cada data: sem isso o backtest vaza o futuro.
  JOIN silver.vendas_dia v ON v.dia <= r.data_ref
  GROUP BY r.data_ref, v.stockcode
),
metricas AS (
  SELECT *,
         data_ref - ultima_venda                                          AS periodo_silencio,
         (ultima_venda - primeira_venda)::numeric / (dias_com_venda - 1) AS ritmo_medio_dias
  FROM base
  -- Mesmos filtros da features, para que o snapshot de data_ref seja igual a ela.
  WHERE data_ref - primeira_venda >= 60
    AND dias_com_venda >= 2
)
SELECT *, periodo_silencio / ritmo_medio_dias AS silencio_relativo
FROM metricas;

ALTER TABLE gold.snapshots ADD PRIMARY KEY (data_ref, stockcode);
