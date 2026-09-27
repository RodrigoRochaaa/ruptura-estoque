# %% [markdown]
# # Validação: o alerta de 09/12/2010 conferido com os 12 meses seguintes
#
# As tabelas de validação saem do SQL (sql/08 e sql/09). Aqui entra o que o SQL não faz bem:
# a AUC das duas regras. Requer DATABASE_URL no ambiente.

# %%
import os

import pandas as pd
import sqlalchemy

engine = sqlalchemy.create_engine(os.environ["DATABASE_URL"])
base = pd.read_sql_query(
    """
    SELECT g.stockcode, g.silencio_relativo, g.periodo_silencio, g.acima_da_mediana,
           g.medidor_ruptura, g.categoria_acao, r.dias_ate_voltar
    FROM gold.ruptura g
    JOIN gold.retorno_produto r USING (stockcode)
    """,
    engine,
)

# %%
# Taxa de retorno por grupo: pelo medidor antigo e pelas categorias novas.
pd.read_sql_query("SELECT * FROM gold.backtest ORDER BY agrupamento, taxa_voltou_90d DESC", engine)

# %%
# Silêncio relativo × dias parado como preditores de "parou de vez" (não vendeu nada em 12 meses).


def auc(score: pd.Series, alvo: pd.Series) -> float:
    """Probabilidade de um positivo ter score maior que um negativo (Mann-Whitney)."""
    posicoes = score.rank()
    positivos, negativos = alvo.sum(), (~alvo).sum()
    return (posicoes[alvo].sum() - positivos * (positivos + 1) / 2) / (positivos * negativos)


acima = base[base["acima_da_mediana"]]
parou = acima["dias_ate_voltar"].isna()
print(f"{parou.mean():.1%} dos produtos acima da mediana pararam de vez")
print("AUC silêncio relativo:", round(auc(acima["silencio_relativo"], parou), 3))
print("AUC dias parado:      ", round(auc(acima["periodo_silencio"], parou), 3))

# %%
# Mesmo número de alertas, precisão e antecedência: a tabela que o app mostra.
pd.read_sql_query("SELECT * FROM gold.comparacao_regra", engine)
