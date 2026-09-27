-- Toda linha tem uma categoria conhecida, e todo produto da features está na gold.
SELECT f.stockcode
FROM silver.features f
LEFT JOIN gold.ruptura g USING (stockcode)
WHERE g.categoria_acao IS NULL
   OR g.categoria_acao NOT IN ('fora_do_escopo', 'cliente_principal_parou', 'sazonal',
                               'provavel_descontinuacao', 'monitorar', 'ruptura_provavel');
