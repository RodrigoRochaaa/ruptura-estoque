-- Série semanal só dos produtos que o app detalha: os que estão no escopo e o par do gráfico explicativo.
-- A semana da data de referência é partida em antes/depois, para o minigráfico da lista não ver o futuro.
SELECT v.stockcode,
       DATE_TRUNC('week', v.dia)::date AS semana,
       (v.dia > p.data_ref)::text      AS depois_da_ref,
       SUM(v.quantidade)               AS quantidade,
       ROUND(SUM(v.faturamento), 2)    AS faturamento
FROM silver.vendas_dia v
CROSS JOIN meta.parametros p
WHERE v.stockcode IN (
  SELECT stockcode FROM gold.ruptura WHERE categoria_acao <> 'fora_do_escopo'
  UNION
  SELECT stockcode FROM gold.exemplo_silencio
)
GROUP BY 1, 2, 3
ORDER BY 1, 2, 3
