-- A participação no faturamento soma 100% dentro do universo analisado.
SELECT SUM(pct_faturamento) AS soma
FROM silver.features
HAVING ABS(SUM(pct_faturamento) - 100) > 0.000001;
