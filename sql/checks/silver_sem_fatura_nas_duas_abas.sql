-- A sobreposição entre as abas foi removida: nenhuma fatura vem das duas.
SELECT invoice
FROM silver.vendas
GROUP BY invoice
HAVING COUNT(DISTINCT aba) > 1;
