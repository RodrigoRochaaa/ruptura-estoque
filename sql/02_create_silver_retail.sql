-- Versão original (reconstruída em 27/09/2026). Reproduz raw.silver_retail linha a linha:
-- EXCEPT ALL nas duas direções retorna 0 linhas (510.232 linhas).
DROP TABLE IF EXISTS raw.silver_retail;
CREATE TABLE raw.silver_retail AS
SELECT *
FROM raw.bronze_retail
WHERE quantity > 0
  AND price > 0
  AND stockcode NOT IN ('POST', 'M', 'D');
