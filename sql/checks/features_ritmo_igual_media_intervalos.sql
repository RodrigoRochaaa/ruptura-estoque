-- O ritmo médio é, por definição, a média dos intervalos entre dias de venda.
WITH intervalos AS (
  SELECT v.stockcode, v.dia - LAG(v.dia) OVER (PARTITION BY v.stockcode ORDER BY v.dia) AS intervalo
  FROM silver.vendas_dia v
  CROSS JOIN meta.parametros p
  WHERE v.dia <= p.data_ref
)
SELECT f.stockcode
FROM silver.features f
JOIN (
  SELECT stockcode, AVG(intervalo) AS media
  FROM intervalos
  WHERE intervalo IS NOT NULL
  GROUP BY stockcode
) m USING (stockcode)
WHERE ABS(f.ritmo_medio_dias - m.media) > 0.000001;
