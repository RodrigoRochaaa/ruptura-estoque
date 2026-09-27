-- A bronze tem exatamente as linhas das duas abas do Excel.
SELECT aba, COUNT(*) AS linhas
FROM bronze.retail
GROUP BY aba
HAVING (aba = 'Year 2009-2010' AND COUNT(*) <> 525461)
    OR (aba = 'Year 2010-2011' AND COUNT(*) <> 541910)
    OR aba NOT IN ('Year 2009-2010', 'Year 2010-2011');
