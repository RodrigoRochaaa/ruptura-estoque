-- Features: uma linha por produto, calculada só com o que se sabia na data do diagnóstico.
DROP TABLE IF EXISTS silver.features;
CREATE TABLE silver.features AS
WITH params AS (
  SELECT data_ref FROM meta.parametros
),
dias AS (
  -- Sem este filtro as métricas de 09/12/2010 enxergariam 2011, e a validação ficaria otimista.
  SELECT v.*
  FROM silver.vendas_dia v
  CROSS JOIN params p
  WHERE v.dia <= p.data_ref
),
base AS (
  SELECT d.stockcode,
         MIN(d.dia)              AS primeira_venda,
         MAX(d.dia)              AS ultima_venda,
         COUNT(*)                AS dias_com_venda,
         SUM(d.quantidade)       AS quantidade_total,
         SUM(d.faturamento)      AS faturamento_total,
         p.data_ref - MIN(d.dia) AS idade_dias,
         p.data_ref - MAX(d.dia) AS periodo_silencio
  FROM dias d
  CROSS JOIN params p
  GROUP BY d.stockcode, p.data_ref
),
metricas AS (
  SELECT *,
         -- Cadência enquanto o produto estava ativo: o silêncio atual fica de fora para não contaminar
         -- a medida do comportamento normal.
         (ultima_venda - primeira_venda)::numeric / (dias_com_venda - 1) AS ritmo_medio_dias
  FROM base
  -- 60 dias de idade para haver histórico; 2 dias com venda para existir ao menos um intervalo.
  WHERE idade_dias >= 60
    AND dias_com_venda >= 2
),
intervalos AS (
  SELECT stockcode, dia - LAG(dia) OVER (PARTITION BY stockcode ORDER BY dia) AS intervalo
  FROM dias
),
historico AS (
  SELECT stockcode,
         MAX(intervalo)                                     AS maior_intervalo_dias,
         -- Perto de 1: vendas espalhadas ao acaso. Bem acima de 1: rajadas, e o ritmo médio engana.
         STDDEV_SAMP(intervalo) / NULLIF(AVG(intervalo), 0) AS cv_intervalo
  FROM intervalos
  WHERE intervalo IS NOT NULL
  GROUP BY stockcode
),
vendas_ate_ref AS (
  SELECT v.stockcode, v.customer_id, v.invoicedate, v.quantity * v.price AS faturamento
  FROM silver.vendas v
  CROSS JOIN params p
  WHERE v.invoicedate::date <= p.data_ref
    AND v.customer_id IS NOT NULL
),
ultima_compra AS (
  SELECT customer_id, MAX(invoicedate)::date AS dia
  FROM vendas_ate_ref
  GROUP BY customer_id
),
top_cliente AS (
  -- Maior cliente de cada produto e há quanto tempo ele não compra nada na loja: se ele sumiu,
  -- o produto parou por um motivo comercial, não de estoque.
  SELECT DISTINCT ON (pc.stockcode)
         pc.stockcode,
         -- O denominador inclui as vendas sem cliente identificado (cerca de 20% das linhas).
         pc.faturamento / m.faturamento_total AS share_top_cliente,
         p.data_ref - u.dia                   AS dias_sem_comprar_top_cliente
  FROM (
    SELECT stockcode, customer_id, SUM(faturamento) AS faturamento
    FROM vendas_ate_ref
    GROUP BY 1, 2
  ) pc
  JOIN metricas m USING (stockcode)
  JOIN ultima_compra u USING (customer_id)
  CROSS JOIN params p
  ORDER BY pc.stockcode, pc.faturamento DESC, pc.customer_id
),
abc AS (
  SELECT stockcode,
         100 * faturamento_total / SUM(faturamento_total) OVER () AS pct_faturamento,
         -- ROWS com desempate por código: com o RANGE padrão, produtos empatados somariam de uma vez.
         100 * SUM(faturamento_total) OVER (ORDER BY faturamento_total DESC, stockcode
                                            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
             / SUM(faturamento_total) OVER ()                     AS pct_acumulado
  FROM metricas
)
SELECT m.stockcode,
       pr.descricao,
       m.primeira_venda,
       m.ultima_venda,
       m.dias_com_venda,
       m.idade_dias,
       m.periodo_silencio,
       m.ritmo_medio_dias,
       -- Métrica central: quantas vezes o próprio ritmo histórico o produto está parado.
       m.periodo_silencio / m.ritmo_medio_dias AS silencio_relativo,
       CASE
         WHEN m.periodo_silencio / m.ritmo_medio_dias <= 1 THEN 'normal'
         WHEN m.periodo_silencio / m.ritmo_medio_dias <= 2 THEN 'atraso'
         WHEN m.periodo_silencio / m.ritmo_medio_dias <= 3 THEN 'indicio'
         ELSE 'ruptura'
       END                                     AS medidor_ruptura,
       CASE
         WHEN m.ritmo_medio_dias <= 2  THEN 'diario'
         WHEN m.ritmo_medio_dias <= 7  THEN 'semanal'
         WHEN m.ritmo_medio_dias <= 20 THEN 'mensal'
         ELSE 'ocasional'
       END                                     AS perfil_frequencia,
       m.quantidade_total,
       m.faturamento_total,
       m.faturamento_total / m.quantidade_total AS preco_medio_ponderado,
       -- Por dia em que houve venda, não por dia corrido: não distorce quem vende muito em poucos dias.
       m.faturamento_total / m.dias_com_venda   AS receita_dia_vendido,
       a.pct_faturamento,
       CASE
         WHEN a.pct_acumulado <= 80 THEN 'A'
         WHEN a.pct_acumulado <= 95 THEN 'B'
         ELSE 'C'
       END                                     AS curva_abc,
       h.maior_intervalo_dias,
       h.cv_intervalo,
       t.share_top_cliente,
       t.dias_sem_comprar_top_cliente,
       -- Aproximação pelo nome: com um único ciclo de 13 meses não dá para medir sazonalidade no dado.
       COALESCE(pr.descricao ~* '(CHRISTMAS|XMAS|EASTER|VALENTINE|HALLOWEEN|SANTA|REINDEER|ADVENT|SNOWFLAKE|HOT WATER BOTTLE)', false)
                                               AS sazonal_por_nome
FROM metricas m
JOIN abc a USING (stockcode)
LEFT JOIN historico h USING (stockcode)
LEFT JOIN top_cliente t USING (stockcode)
LEFT JOIN silver.produto pr USING (stockcode);

ALTER TABLE silver.features ADD PRIMARY KEY (stockcode);
