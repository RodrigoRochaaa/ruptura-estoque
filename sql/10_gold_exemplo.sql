-- Par de produtos que explica o silêncio relativo em um gráfico: os mesmos dias parados, ritmos
-- opostos. A escolha é por regra, não por código fixo, para acompanhar os dados se eles mudarem.
DROP TABLE IF EXISTS gold.exemplo_silencio;
CREATE TABLE gold.exemplo_silencio AS
WITH par AS (
  SELECT a.stockcode AS frequente, b.stockcode AS ocasional
  FROM gold.ruptura a
  JOIN gold.ruptura b
    ON b.periodo_silencio = a.periodo_silencio
   AND b.stockcode <> a.stockcode
  WHERE a.categoria_acao = 'ruptura_provavel'
    AND a.dias_com_venda >= 100
    AND b.silencio_relativo <= 1.2
    AND b.dias_com_venda >= 10
  ORDER BY a.silencio_relativo DESC, b.dias_com_venda DESC, b.stockcode
  LIMIT 1
)
SELECT 'frequente' AS papel, frequente AS stockcode FROM par
UNION ALL
SELECT 'ocasional', ocasional FROM par;
