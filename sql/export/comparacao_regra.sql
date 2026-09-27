SELECT regra,
       criterio,
       alertas,
       ROUND(precisao, 4)                          AS precisao,
       ROUND(dias_ate_alertar_mediana::numeric, 1) AS dias_ate_alertar_mediana
FROM gold.comparacao_regra
ORDER BY regra DESC
