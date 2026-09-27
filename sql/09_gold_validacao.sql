-- Validação do diagnóstico com o que aconteceu depois da data de referência (a aba de 2011).
-- Fica fora da gold.ruptura de propósito: o diagnóstico não pode depender do futuro.

DROP TABLE IF EXISTS gold.retorno_produto;
CREATE TABLE gold.retorno_produto AS
SELECT r.stockcode,
       MIN(v.dia)              AS primeira_venda_depois,
       MIN(v.dia) - p.data_ref AS dias_ate_voltar,
       COALESCE(SUM(v.faturamento) FILTER (WHERE v.dia <= p.data_ref + 365), 0) AS faturamento_1_ano_depois
FROM gold.ruptura r
CROSS JOIN meta.parametros p
LEFT JOIN silver.vendas_dia v
  ON v.stockcode = r.stockcode
 AND v.dia > p.data_ref
GROUP BY r.stockcode, p.data_ref;

ALTER TABLE gold.retorno_produto ADD PRIMARY KEY (stockcode);


-- Quanto cada grupo voltou a vender: pelas categorias novas e pelo medidor antigo, para comparar.
DROP TABLE IF EXISTS gold.backtest;
CREATE TABLE gold.backtest AS
WITH base AS (
  SELECT 'categoria_acao' AS agrupamento, g.categoria_acao AS grupo, g.taxa_semana, rp.dias_ate_voltar
  FROM gold.ruptura g
  JOIN gold.retorno_produto rp USING (stockcode)
  UNION ALL
  -- O medidor antigo só no universo acima da mediana, que é o recorte que o app antigo mostrava.
  SELECT 'medidor_ruptura', g.medidor_ruptura, g.taxa_semana, rp.dias_ate_voltar
  FROM gold.ruptura g
  JOIN gold.retorno_produto rp USING (stockcode)
  WHERE g.acima_da_mediana
)
SELECT agrupamento,
       grupo,
       COUNT(*)                                                            AS produtos,
       COUNT(*) FILTER (WHERE dias_ate_voltar <= 30)::numeric  / COUNT(*) AS taxa_voltou_30d,
       COUNT(*) FILTER (WHERE dias_ate_voltar <= 90)::numeric  / COUNT(*) AS taxa_voltou_90d,
       COUNT(*) FILTER (WHERE dias_ate_voltar <= 365)::numeric / COUNT(*) AS taxa_voltou_1_ano,
       SUM(taxa_semana)                                                    AS taxa_semana_total
FROM base
GROUP BY agrupamento, grupo;

ALTER TABLE gold.backtest ADD PRIMARY KEY (agrupamento, grupo);


-- O silêncio relativo contra a regra ingênua "dias parado", com o mesmo número de alertas.
-- Uma métrica elaborada precisa ganhar da simples em algum ponto, ou a simples é a escolha certa.
DROP TABLE IF EXISTS gold.comparacao_regra;
CREATE TABLE gold.comparacao_regra AS
WITH base AS (
  SELECT g.stockcode,
         g.silencio_relativo,
         g.periodo_silencio,
         g.ritmo_medio_dias,
         rp.primeira_venda_depois IS NULL AS parou_de_vez
  FROM gold.ruptura g
  JOIN gold.retorno_produto rp USING (stockcode)
  WHERE g.acima_da_mediana
),
alertas AS (
  -- O número de alertas é o da regra atual (silêncio relativo acima de 3); a ingênua recebe o mesmo.
  SELECT COUNT(*) FILTER (WHERE silencio_relativo > 3) AS n FROM base
),
ranqueado AS (
  SELECT b.*,
         ROW_NUMBER() OVER (ORDER BY b.silencio_relativo DESC, b.stockcode) <= a.n AS alerta_relativo,
         ROW_NUMBER() OVER (ORDER BY b.periodo_silencio DESC, b.stockcode)  <= a.n AS alerta_dias
  FROM base b
  CROSS JOIN alertas a
),
corte_dias AS (
  SELECT MIN(periodo_silencio) AS dias FROM ranqueado WHERE alerta_dias
)
SELECT 'silencio_relativo'                                            AS regra,
       'silêncio relativo acima de 3'                                 AS criterio,
       COUNT(*) FILTER (WHERE alerta_relativo)                        AS alertas,
       AVG(parou_de_vez::int) FILTER (WHERE alerta_relativo)          AS precisao,
       -- Dias de silêncio no momento em que a regra dispara, nos produtos que pararam de vez.
       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY 3 * ritmo_medio_dias)
         FILTER (WHERE parou_de_vez)                                  AS dias_ate_alertar_mediana
FROM ranqueado
UNION ALL
SELECT 'dias_parado',
       'parado há ' || c.dias || ' dias ou mais',
       COUNT(*) FILTER (WHERE r.alerta_dias),
       AVG(r.parou_de_vez::int) FILTER (WHERE r.alerta_dias),
       c.dias
FROM ranqueado r
CROSS JOIN corte_dias c
GROUP BY c.dias;
