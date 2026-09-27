# %% [markdown]
# # EDA: onde as decisões do projeto foram tomadas
#
# Exploratório (as "ostras"). As decisões tomadas aqui são executadas no SQL
# (sql/06_gold_ruptura.sql); este arquivo só lê as tabelas e valida.
# Requer DATABASE_URL no ambiente (ver .env.example).

# %%
import os

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import sqlalchemy

engine = sqlalchemy.create_engine(os.environ["DATABASE_URL"])
features = pd.read_sql_query("SELECT * FROM silver.features", engine)
gold = pd.read_sql_query("SELECT * FROM gold.ruptura", engine)
print(f"{len(features):,} produtos")

# %%
# O SQL já exclui quem vendeu em um único dia (sem intervalo, não há ritmo): nenhum nulo deve sobrar.
features[["ritmo_medio_dias", "silencio_relativo"]].isnull().sum()

# %%
features[["silencio_relativo", "faturamento_total", "periodo_silencio", "dias_com_venda"]].describe()

# %%
# Distribuição do silêncio relativo. O corte em 10 é só de visualização; acima de 3 já é a faixa de alerta.
fig, ax = plt.subplots()
ax.hist(features["silencio_relativo"].clip(upper=10), bins=40)
ax.axvline(2, color="gray", linewidth=1)
ax.axvline(3, color="red", linewidth=1)
ax.set_title("Silêncio relativo (valores acima de 10 agrupados em 10)")
plt.show()

# %%
# Faturamento é muito assimétrico: média e desvio padrão bem acima da mediana.
# Por isso o corte de escopo é a mediana, calculada no SQL a cada execução.
faturamento = features["faturamento_total"]
print(f"média £{faturamento.mean():,.0f} · desvio £{faturamento.std():,.0f} · mediana £{faturamento.median():,.2f}")
fig, ax = plt.subplots()
ax.hist(faturamento, bins=50, log=True)
ax.set_title("Faturamento por produto (escala log na contagem)")
plt.show()

# %%
sns.scatterplot(data=features, x="silencio_relativo", y="faturamento_total", s=10, alpha=0.4)
plt.xscale("log")
plt.yscale("log")
plt.show()

# %%
# Spearman por causa da assimetria. Parte da relação inversa é mecânica: quem está parado há mais tempo
# teve menos tempo para acumular faturamento. Por dia ativo, a relação enfraquece.
ativo = (pd.to_datetime(features["ultima_venda"]) - pd.to_datetime(features["primeira_venda"])).dt.days + 1
print(
    "faturamento total:", round(features["faturamento_total"].corr(features["silencio_relativo"], method="spearman"), 2)
)
print(
    "faturamento por dia ativo:",
    round((features["faturamento_total"] / ativo).corr(features["silencio_relativo"], method="spearman"), 2),
)

# %%
# O recorte de risco: silêncio acima de 2× o ritmo e faturamento acima da mediana.
risco = gold[(gold["silencio_relativo"] > 2) & gold["acima_da_mediana"]]
print(f"{len(risco)} produtos · {risco['faturamento_total'].sum() / faturamento.sum():.1%} do faturamento")
risco.groupby("perfil_frequencia")["faturamento_total"].agg(["count", "sum", "median"])

# %%
# Piso de dias por perfil: com transações recentes, o "silêncio" ainda é cedo demais para concluir.
# Diário precisa de mais de 7 dias parado, semanal de 14, mensal de 28.
risco.groupby("perfil_frequencia").apply(
    lambda g: pd.Series({"produtos": len(g), "acima_do_piso": (g["periodo_silencio"] > g["piso_silencio_dias"]).sum()}),
    include_groups=False,
)

# %%
# Resultado: a categoria de ação e o impacto em £/semana (taxa, não acumulado).
gold[gold["categoria_acao"] != "fora_do_escopo"].groupby("categoria_acao").agg(
    produtos=("stockcode", "size"),
    taxa_semana=("taxa_semana", "sum"),
    silencio_mediano=("periodo_silencio", "median"),
).sort_values("taxa_semana", ascending=False)
