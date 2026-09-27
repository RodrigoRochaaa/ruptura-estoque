# Como obter os dados

O arquivo bruto não está no repositório (45 MB). Para rodar o pipeline do zero:

1. Baixe o **Online Retail II** no [UCI Machine Learning Repository](https://archive.ics.uci.edu/dataset/502/online+retail+ii)
   (há uma cópia no Kaggle com o mesmo arquivo).
2. Salve como `data/raw/online_retail_II.xlsx`. O arquivo tem duas abas, `Year 2009-2010` e `Year 2010-2011`,
   e o pipeline usa as duas.
3. Rode `python pipeline.py`. Na primeira execução ele lê o Excel (alguns minutos) e grava
   `data/raw/bronze_retail.csv`, que é reaproveitado nas execuções seguintes.

O app **não** precisa disso: ele lê os arquivos já exportados em `data/app/`.

Conferência: a bronze tem 525.461 linhas da primeira aba e 541.910 da segunda (o check
`sql/checks/bronze_linhas_por_aba.sql` falha se o arquivo for outro).
