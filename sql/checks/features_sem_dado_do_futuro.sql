-- As features usam só o que se sabia na data do diagnóstico.
SELECT f.stockcode
FROM silver.features f
CROSS JOIN meta.parametros p
WHERE f.ultima_venda > p.data_ref;
