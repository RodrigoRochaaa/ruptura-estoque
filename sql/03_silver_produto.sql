-- Nome canônico de cada produto. O mesmo código aparece com descrições diferentes (o 85099B tem três):
-- fica a mais frequente, e a ordem alfabética só desempata.
DROP TABLE IF EXISTS silver.produto;
CREATE TABLE silver.produto AS
SELECT DISTINCT ON (stockcode)
       stockcode,
       descricao
FROM (
  SELECT stockcode, TRIM(description) AS descricao, COUNT(*) AS linhas
  FROM silver.vendas
  WHERE NULLIF(TRIM(description), '') IS NOT NULL
  GROUP BY 1, 2
) d
ORDER BY stockcode, linhas DESC, descricao;

ALTER TABLE silver.produto ADD PRIMARY KEY (stockcode);
