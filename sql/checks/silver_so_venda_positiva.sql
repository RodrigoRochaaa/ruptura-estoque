-- Cancelamentos, devoluções e ajustes não entram na silver.
SELECT invoice, stockcode
FROM silver.vendas
WHERE quantity <= 0 OR price <= 0;
