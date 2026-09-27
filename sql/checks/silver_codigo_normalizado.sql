-- Nenhum código com minúscula ou espaço: 85099B e 85099b precisam ser o mesmo produto.
SELECT DISTINCT stockcode
FROM silver.vendas
WHERE stockcode <> UPPER(TRIM(stockcode));
