# Ruptura de Estoque

[![ci](https://github.com/RodrigoRochaaa/ruptura-estoque/actions/workflows/ci.yml/badge.svg)](https://github.com/RodrigoRochaaa/ruptura-estoque/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.12%2B-3776AB)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pipeline%20SQL-336791)
![Streamlit](https://img.shields.io/badge/Streamlit-app-FF4B4B)

Quais produtos que vendiam com regularidade pararam de vender, há quanto tempo estão parados, e o que fazer com
cada um? Um pipeline SQL em medallion architecture (bronze, silver, gold) sobre 1 milhão de linhas de um varejo
britânico, com o alerta de ruptura de estoque (stockout) **validado por backtest com os 12 meses seguintes** e um
app Streamlit para o time de supply chain.

> **36 produtos que vendiam com regularidade pararam de vender sem explicação comercial ou sazonal. Juntos,
> vendiam £2.519 por semana. Outros 159 provavelmente saíram de linha e pedem uma decisão de catálogo, não de
> reposição.**
>
> Diagnóstico em 09/12/2010.

![Tour pelo app](docs/img/app_tour.gif)

## A ideia central: silêncio relativo

Dias sem vender não dizem muito sozinhos. Trinta dias parado é alarme para um produto que vendia quase todo dia,
e é rotina para um que vendia uma vez por mês. O projeto mede o silêncio **em múltiplos do ritmo do próprio
produto**:

```
silencio_relativo = dias desde a última venda / ritmo médio entre vendas (calculado só no período ativo)
```

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/img/silencio_relativo_escuro.png">
  <img alt="Dois produtos parados há 30 dias: um vendia a cada 1,7 dia (17,9× o ritmo), o outro a cada 28 dias (1,1×)" src="docs/img/silencio_relativo_claro.png">
</picture>

## O alerta funciona? Backtest com os 12 meses seguintes

O arquivo original tem duas abas. O diagnóstico usa só os dados até 09/12/2010. A segunda aba, com os 12 meses
seguintes, fica guardada para responder se o alerta acertou.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/img/calibracao_escuro.png">
  <img alt="Produtos que voltaram a vender em 90 dias por faixa de silêncio relativo: 92%, 73%, 67%, 41%, 24% e 7%" src="docs/img/calibracao_claro.png">
</picture>

A parcela de produtos que voltam a vender cai de faixa em faixa. O padrão se repete nas 19 datas de referência
mensais testadas (mar/2010 a set/2011), com uma exceção explicada abaixo (janeiro de 2011) e uma inversão de meio
ponto entre as duas primeiras faixas em maio de 2011. O rótulo único "Ruptura", porém, misturava situações
diferentes: dos 305 produtos que ele marcava, 76% nunca mais venderam. Isso é descontinuação, não falta de
estoque. Por isso o projeto separa os alertas por **causa provável**, e cada categoria pede uma ação diferente:

| Categoria | Produtos | £/semana no ritmo histórico | Voltou a vender em 90 dias | Em 1 ano | Ação |
|---|---:|---:|---:|---:|---|
| Ruptura provável | 36 | £2.519 | 33% | 39% | Checar estoque e fornecedor; repor |
| Monitorar | 101 | £5.888 | 59% | 67% | Acompanhar na próxima semana |
| Sazonal | 27 | £2.895 | 37% | 48% | Planejar a próxima temporada |
| Provável descontinuação | 159 | £13.553 | 8% | 10% | Confirmar com compras e limpar o catálogo |
| Cliente principal parou | 20 | £1.358 | 5% | 5% | Ação comercial, não de estoque |

"Ruptura provável" não é stockout confirmado: é o grupo onde vale checar o estoque primeiro. As outras
explicações que o dado permite testar (cliente, temporada, saída de linha) são separadas antes, e o que sobra
voltou a vender 4 vezes mais que a provável descontinuação.

**A métrica contra um baseline.** Com o mesmo número de alertas (305), o baseline "parado há 18 dias ou mais" tem
precision de 78,7% (produto que parou de vez), e o silêncio relativo, de 76,4%. A AUC é de 0,966 contra 0,959. O
silêncio relativo **não** prevê melhor quem vai parar. O ganho dele é outro, de early warning: dispara com 13 dias
de silêncio (mediana), contra 18 do baseline, ou seja, **avisa 5 dias antes**, justamente nos produtos que vendem
com frequência.

**Uma data só engana.** Entre 3× e 5× o ritmo, de 61% a 86% dos produtos voltam a vender em 90 dias nas datas de
março a novembro, o perfil de uma falta temporária. Em 09/12/2010, só 41%: a hipótese é a troca de coleção de fim
de ano, que o dado não permite confirmar. Em janeiro de 2011, logo depois do recesso de Natal (loja fechada),
todos os produtos parecem parados e a relação se inverte. A aba *Confiabilidade* do app mostra as 20 datas lado
a lado.

## Arquitetura

```mermaid
flowchart LR
  X["online_retail_II.xlsx<br/>2 abas"] -->|"Python: leitura fiel"| B[("bronze.retail<br/>1.067.371 linhas")]
  B -->|"SQL: só venda de produto,<br/>código normalizado, sem sobreposição"| S[("silver.vendas<br/>1.015.071")]
  S --> D[("silver.vendas_dia")]
  S --> P[("silver.produto")]
  D --> F[("silver.features<br/>3.808 produtos até a data de referência")]
  P --> F
  F --> G[("gold.ruptura<br/>categoria e £/semana")]
  D --> N[("gold.snapshots<br/>20 datas")]
  N --> C[("gold.calibracao")]
  G --> V[("gold.backtest<br/>e comparação com o baseline")]
  G & C & V -->|"CSV"| APP["app Streamlit"]
```

- **Toda regra de negócio fica no SQL** (`sql/`), numerada na ordem de execução. O app só apresenta.
- **`python pipeline.py`** roda tudo do Excel ao app em cerca de 1 minuto (a primeira execução, que lê o Excel,
  leva alguns minutos a mais). Os passos são: carga da bronze com `COPY`, os 11 arquivos SQL, **10 data quality
  checks** (`sql/checks/`, cada um deve retornar zero linhas) e o export dos CSVs em `data/app/`. Se um check
  falha, os arquivos do app não são atualizados.
- **Sem data leakage.** As features usam só `dia <= data_ref`, e há um check garantindo isso. O snapshot de
  09/12/2010 é calculado por outro caminho e precisa bater com a features.
- **O app roda sem banco** e é o que vai para o Streamlit Community Cloud. O CI roda lint e testes contra os
  CSVs versionados, inclusive um teste de regressão que confere os números deste README com os dados.

## O que o projeto não faz

- **Não há posição de estoque, fornecedor nem prazo de reposição no dado.** O projeto identifica o sintoma e a
  causa provável, não a causa confirmada.
- **Voltar a vender não prova que houve ruptura.** É o indicador indireto que o dado permite.
- **As categorias foram validadas em uma data só** (09/12/2010, uma das datas em que menos produtos voltam a
  vender). As faixas de silêncio relativo foram validadas em 20.
- **Sazonalidade é aproximada pelo nome do produto.** Antes do diagnóstico há um único ciclo de vendas, o que não
  permite comparar ano contra ano sem usar o futuro.
- **O tempo é contado em dias corridos.** A loja quase não abre aos sábados e fecha no Natal, o que distorce
  datas logo depois de feriados (o caso de janeiro de 2011).
- **£/semana é uma projeção do ritmo histórico**, não uma perda observada.

## Como rodar

Só o app (usa os CSVs já versionados):

```bash
pip install -r requirements.txt
streamlit run app.py
```

O pipeline completo requer PostgreSQL e o Excel original (ver [`data/instrucoes_download.md`](data/instrucoes_download.md)):

```bash
pip install -r requirements-pipeline.txt
cp .env.example .env          # preencha DATABASE_URL
python pipeline.py            # Excel → bronze → silver → gold → checks → data/app
pytest                        # contrato dos arquivos do app, números de referência e smoke test do app
```

## Estrutura

```
├── app.py                    # Streamlit: só lê data/app
├── pipeline.py               # roda tudo: extração, SQL, checks, export
├── sql/
│   ├── 00_schemas.sql … 10_gold_exemplo.sql
│   ├── checks/               # 10 data quality checks
│   └── export/               # cada SELECT vira um CSV do app
├── data/
│   ├── app/                  # o que o app lê (versionado)
│   └── instrucoes_download.md
├── notebooks/                # EDA e validação, formato # %%
├── scripts/figuras_readme.py # gera as figuras deste README
├── tests/
└── docs/                     # decisões, dicionário de dados e imagens
```

## O que aprendi

A primeira versão marcava como "ruptura" todo produto parado e estimava **£2,8 milhões** de faturamento perdido.
O número estava errado de duas formas. Primeiro, a conta multiplicava o faturamento *por dia de venda* por dias
*corridos*, o que inflava o valor 3,9 vezes. Segundo, quando rodei o backtest com os 12 meses seguintes, 76% dos
produtos marcados nunca mais venderam: eram produtos saindo de linha, não produtos sem estoque. A minha métrica
também empatava com o baseline "dias sem vender" para prever quem ia parar.

O projeto mudou por causa disso. O impacto virou uma taxa (£/semana), e os alertas foram separados por causa
provável, cada um com a taxa de acerto que teve no backtest. O silêncio relativo passou a ser apresentado pelo
que ele faz bem: avisar mais cedo. Além disso, a caixa dos códigos de produto (`85099B` e `85099b` são o mesmo
item) e uma mediana digitada à mão, que tinha ficado velha, também geravam alertas falsos. Os dois problemas
viraram data quality checks.

## Próximos passos

- **Validar as categorias nas 19 datas**, e não só em 09/12/2010, com features e gold calculadas por data de
  referência.
- **Usar os sinais de estoque que já estão na bronze:** ajustes de saída (*damaged*, *missing*, *No Stock*) e
  cancelamentos, como evidência no detalhe do produto.
- **Contar o tempo em dias comerciais**, o que explica a inversão de janeiro de 2011.
- **Validar o método com ground truth de stockout** num dataset público rotulado
  ([FreshRetailNet-50K](https://arxiv.org/abs/2505.16319)), em um projeto separado.

## Documentação

- [`docs/decisoes.md`](docs/decisoes.md): cada decisão, o motivo e os números de referência.
- [`docs/dicionario_dados.md`](docs/dicionario_dados.md): as tabelas de cada camada, os data quality checks e as
  colunas dos arquivos que o app lê.
- Os arquivos em `sql/` são comentados com o porquê de cada regra.

## Dados

Chen, D. (2012). *Online Retail II* [Dataset]. UCI Machine Learning Repository.
[https://doi.org/10.24432/C5CG6D](https://doi.org/10.24432/C5CG6D). Licença CC BY 4.0. Loja online britânica,
dezembro de 2009 a dezembro de 2011. Valores em libras (£).

## Licença

Código sob a licença [MIT](LICENSE). Os dados seguem a licença CC BY 4.0 da fonte.

## Autor

Rodrigo Rocha · [GitHub](https://github.com/RodrigoRochaaa) · [LinkedIn](https://www.linkedin.com/in/rodrigo-rocha-8a1039335/)
