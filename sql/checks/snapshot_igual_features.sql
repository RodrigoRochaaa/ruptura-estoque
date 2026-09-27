-- O snapshot da data do diagnóstico reproduz a features: as duas calculam a mesma coisa por caminhos diferentes.
SELECT COALESCE(f.stockcode, s.stockcode) AS stockcode
FROM silver.features f
FULL JOIN (
  SELECT s.*
  FROM gold.snapshots s
  JOIN meta.parametros p ON s.data_ref = p.data_ref
) s USING (stockcode)
WHERE f.stockcode IS NULL
   OR s.stockcode IS NULL
   OR f.periodo_silencio  <> s.periodo_silencio
   OR f.faturamento_total <> s.faturamento_total
   OR ABS(f.silencio_relativo - s.silencio_relativo) > 0.000001;
