-- Calibração: em cada data e faixa de silêncio relativo, quantos produtos voltaram a vender.
-- Voltar a vender é o sinal observável de que o silêncio era temporário. Não prova ruptura, mas
-- separa o que parou de vez do que ainda estava vivo.
DROP TABLE IF EXISTS gold.calibracao;
CREATE TABLE gold.calibracao AS
WITH fim_dos_dados AS (
  SELECT MAX(dia) AS dia FROM silver.vendas_dia
),
retorno AS (
  SELECT s.data_ref, s.stockcode, MIN(v.dia) AS primeira_venda_depois
  FROM gold.snapshots s
  JOIN silver.vendas_dia v
    ON v.stockcode = s.stockcode
   AND v.dia > s.data_ref
  GROUP BY s.data_ref, s.stockcode
),
faixas AS (
  SELECT s.data_ref,
         r.primeira_venda_depois,
         CASE
           WHEN s.silencio_relativo <= 1  THEN 1
           WHEN s.silencio_relativo <= 2  THEN 2
           WHEN s.silencio_relativo <= 3  THEN 3
           WHEN s.silencio_relativo <= 5  THEN 4
           WHEN s.silencio_relativo <= 10 THEN 5
           ELSE                                6
         END AS faixa_ordem
  FROM gold.snapshots s
  LEFT JOIN retorno r USING (data_ref, stockcode)
)
SELECT f.data_ref,
       f.faixa_ordem,
       CASE f.faixa_ordem
         WHEN 1 THEN '0 a 1'
         WHEN 2 THEN '1 a 2'
         WHEN 3 THEN '2 a 3'
         WHEN 4 THEN '3 a 5'
         WHEN 5 THEN '5 a 10'
         ELSE        'acima de 10'
       END                                                                        AS faixa,
       COUNT(*)                                                                   AS produtos,
       COUNT(*) FILTER (WHERE f.primeira_venda_depois <= f.data_ref + 90)::numeric
         / COUNT(*)                                                               AS taxa_voltou_90d,
       -- Um ano de futuro só existe para as datas até dezembro de 2010.
       CASE WHEN f.data_ref + 365 <= fim.dia
            THEN COUNT(*) FILTER (WHERE f.primeira_venda_depois <= f.data_ref + 365)::numeric / COUNT(*)
       END                                                                        AS taxa_voltou_365d
FROM faixas f
CROSS JOIN fim_dos_dados fim
-- Só datas com 90 dias de futuro observável.
WHERE f.data_ref + 90 <= fim.dia
GROUP BY f.data_ref, f.faixa_ordem, fim.dia;

ALTER TABLE gold.calibracao ADD PRIMARY KEY (data_ref, faixa_ordem);
