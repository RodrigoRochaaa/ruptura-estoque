SELECT data_ref,
       faixa_ordem,
       faixa,
       produtos,
       ROUND(taxa_voltou_90d, 4)  AS taxa_voltou_90d,
       ROUND(taxa_voltou_365d, 4) AS taxa_voltou_365d
FROM gold.calibracao
ORDER BY data_ref, faixa_ordem
