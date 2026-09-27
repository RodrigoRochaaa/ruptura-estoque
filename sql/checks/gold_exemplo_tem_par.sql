-- O gráfico explicativo do app precisa dos dois papéis.
SELECT papel
FROM (VALUES ('frequente'), ('ocasional')) AS esperado(papel)
WHERE papel NOT IN (SELECT papel FROM gold.exemplo_silencio);
