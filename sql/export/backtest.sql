SELECT agrupamento,
       grupo,
       produtos,
       ROUND(taxa_voltou_30d, 4)   AS taxa_voltou_30d,
       ROUND(taxa_voltou_90d, 4)   AS taxa_voltou_90d,
       ROUND(taxa_voltou_1_ano, 4) AS taxa_voltou_1_ano,
       ROUND(taxa_semana_total, 2) AS taxa_semana_total
FROM gold.backtest
ORDER BY agrupamento, grupo
