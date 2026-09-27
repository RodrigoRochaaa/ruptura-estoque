-- Versão original (reconstruída em 27/09/2026). Reproduz analytics.silver_stock_features:
-- EXCEPT ALL nas duas direções retorna 0 linhas (3.923 produtos).
-- Observação: transac_d7/d14/d28 somam QUANTIDADE vendida na janela, não contam transações.
DROP TABLE IF EXISTS analytics.silver_stock_features;
CREATE TABLE analytics.silver_stock_features AS
WITH metricas_padrao AS (
  SELECT stockcode,
    MIN(invoicedate)                              AS primeira_venda,
    MAX(invoicedate)                              AS ultima_venda,
    SUM(quantity * price) / SUM(quantity)         AS preco_medio_ponderado,
    SUM(quantity * price)                         AS lifetime_revenue,
    COUNT(DISTINCT invoicedate::date)             AS dias_com_venda,
    (DATE '2010-12-09' - MIN(invoicedate::date))  AS lifetime_days,
    (DATE '2010-12-09' - MAX(invoicedate::date))  AS periodo_silencio
  FROM raw.silver_retail
  GROUP BY stockcode
),
metricas_padrao_filtrada AS (
  SELECT *,
    (ultima_venda::date - primeira_venda::date)::numeric / NULLIF(dias_com_venda - 1, 0) AS ritmo_medio_dias
  FROM metricas_padrao
  WHERE lifetime_days >= 60
),
tb_sumario_transacoes AS (
  SELECT stockcode,
    COALESCE(SUM(quantity) FILTER (WHERE invoicedate::date >= DATE '2010-12-09' - 7), 0)  AS transac_d7,
    COALESCE(SUM(quantity) FILTER (WHERE invoicedate::date >= DATE '2010-12-09' - 14), 0) AS transac_d14,
    COALESCE(SUM(quantity) FILTER (WHERE invoicedate::date >= DATE '2010-12-09' - 28), 0) AS transac_d28
  FROM raw.silver_retail
  GROUP BY stockcode
),
tb_perfil_comportamental AS (
  SELECT stockcode,
    periodo_silencio / ritmo_medio_dias AS silencio_relativo,
    CASE WHEN periodo_silencio / ritmo_medio_dias <= 1 THEN 'Comportamento Normal'
         WHEN periodo_silencio / ritmo_medio_dias <= 2 THEN 'Atraso Relevante'
         WHEN periodo_silencio / ritmo_medio_dias <= 3 THEN 'Indício de Ruptura'
         ELSE 'Ruptura' END AS medidor_ruptura,
    CASE WHEN ritmo_medio_dias <= 2  THEN 'diario'
         WHEN ritmo_medio_dias <= 7  THEN 'semanal'
         WHEN ritmo_medio_dias <= 20 THEN 'mensal'
         ELSE 'ocasional' END AS perfil_frequencia,
    lifetime_revenue / dias_com_venda AS receita_dia_vendido
  FROM metricas_padrao_filtrada
),
tb_max_value AS (
  SELECT SUM(lifetime_revenue) AS total_price FROM metricas_padrao_filtrada
),
tb_curva_abc AS (
  SELECT stockcode, pct AS percent_revenue,
    CASE WHEN SUM(pct) OVER (ORDER BY pct DESC) <= 80 THEN 'A'
         WHEN SUM(pct) OVER (ORDER BY pct DESC) <= 95 THEN 'B'
         ELSE 'C' END AS curva_abc
  FROM (SELECT stockcode, (lifetime_revenue / total_price) * 100 AS pct
        FROM metricas_padrao_filtrada CROSS JOIN tb_max_value) s
),
tb_description AS (
  SELECT stockcode, MIN(description) AS description FROM raw.silver_retail GROUP BY stockcode
)
SELECT t1.*, t2.transac_d7, t2.transac_d14, t2.transac_d28,
  t3.silencio_relativo, t3.medidor_ruptura, t3.perfil_frequencia, t3.receita_dia_vendido,
  t4.percent_revenue, t4.curva_abc, t5.description
FROM metricas_padrao_filtrada t1
LEFT JOIN tb_sumario_transacoes    t2 ON t1.stockcode = t2.stockcode
LEFT JOIN tb_perfil_comportamental t3 ON t1.stockcode = t3.stockcode
LEFT JOIN tb_curva_abc             t4 ON t1.stockcode = t4.stockcode
LEFT JOIN tb_description           t5 ON t1.stockcode = t5.stockcode
WHERE t1.ritmo_medio_dias IS NOT NULL AND t3.silencio_relativo IS NOT NULL
;
