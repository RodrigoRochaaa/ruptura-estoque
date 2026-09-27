-- Vendas por produto e dia: a base de todo cálculo temporal (ritmo, intervalos, snapshots e gráficos).
DROP TABLE IF EXISTS silver.vendas_dia;
CREATE TABLE silver.vendas_dia AS
SELECT stockcode,
       invoicedate::date        AS dia,
       SUM(quantity)            AS quantidade,
       SUM(quantity * price)    AS faturamento,
       COUNT(DISTINCT invoice)  AS pedidos
FROM silver.vendas
GROUP BY 1, 2;

ALTER TABLE silver.vendas_dia ADD PRIMARY KEY (stockcode, dia);
