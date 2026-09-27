-- O que aconteceu depois da data de referência (validação; não entra no diagnóstico).
SELECT stockcode,
       primeira_venda_depois,
       dias_ate_voltar,
       ROUND(faturamento_1_ano_depois, 2) AS faturamento_1_ano_depois
FROM gold.retorno_produto
ORDER BY stockcode
