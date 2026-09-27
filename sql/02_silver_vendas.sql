-- Silver: só venda de produto, uma linha por item de fatura, com as duas abas sem repetição.
DROP TABLE IF EXISTS silver.vendas;
CREATE TABLE silver.vendas AS
WITH fim_primeira_aba AS (
  SELECT MAX(invoicedate)::date AS dia
  FROM bronze.retail
  WHERE aba = 'Year 2009-2010'
)
SELECT b.invoice,
       -- 85099B e 85099b são o mesmo produto; sem normalizar, um parecia parado enquanto o outro vendia.
       UPPER(TRIM(b.stockcode)) AS stockcode,
       b.description,
       b.quantity,
       b.invoicedate,
       b.price,
       b.customer_id,
       b.country,
       b.aba
FROM bronze.retail b
CROSS JOIN fim_primeira_aba f
-- Cancelamentos, devoluções e ajustes de estoque têm quantidade ou preço não positivos: não são venda.
WHERE b.quantity > 0
  AND b.price > 0
  -- As abas repetem as faturas de 01 a 09/12/2010: da segunda, só entra o que vem depois da primeira.
  AND NOT (b.aba = 'Year 2010-2011' AND b.invoicedate::date <= f.dia)
  -- Códigos que não são produto: frete, taxas, ajustes manuais, vales-presente, testes e amostras.
  -- A versão original tirava só POST, M e D, e o frete do site (DOT) entrava como um produto de £116 mil.
  AND UPPER(TRIM(b.stockcode)) !~ '^(POST|DOT|C2|M|D|S|B|CRUK|PADS|AMAZONFEE|BANK CHARGES|ADJUST.*|TEST.*|GIFT_.*)$';

CREATE INDEX ON silver.vendas (stockcode, invoicedate);
