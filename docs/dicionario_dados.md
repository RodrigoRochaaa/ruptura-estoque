# Dicionário de dados

O que existe em cada camada do banco, os data quality checks que protegem essas tabelas e as colunas dos
arquivos que o app lê. Os números de linhas são da execução de 27/09/2026 (`data/app/execucao.json`).

## Tabelas por camada

| Tabela | Camada | Grão (uma linha por…) | Chave | Linhas | Arquivo |
|---|---|---|---|---:|---|
| `meta.parametros` | meta | parâmetro vigente (data do diagnóstico) | `id`, sempre uma linha | 1 | `sql/00_schemas.sql` |
| `bronze.retail` | bronze | linha do Excel, das duas abas, como está | sem chave: cópia fiel | 1.067.371 | `sql/01_bronze.sql` + `pipeline.py` |
| `silver.vendas` | silver | item de fatura que é venda de produto | índice em (`stockcode`, `invoicedate`) | 1.015.071 | `sql/02_silver_vendas.sql` |
| `silver.produto` | silver | produto | `stockcode` | 4.724 | `sql/03_silver_produto.sql` |
| `silver.vendas_dia` | silver | produto × dia com venda | (`stockcode`, `dia`) | 529.860 | `sql/04_silver_vendas_dia.sql` |
| `silver.features` | silver | produto, na data do diagnóstico | `stockcode` | 3.808 | `sql/05_silver_features.sql` |
| `gold.ruptura` | gold | produto, na data do diagnóstico | `stockcode` | 3.808 | `sql/06_gold_ruptura.sql` |
| `gold.snapshots` | gold | data de referência × produto | (`data_ref`, `stockcode`) | 74.367 | `sql/07_gold_snapshots.sql` |
| `gold.calibracao` | gold | data de referência × faixa de silêncio relativo | (`data_ref`, `faixa_ordem`) | 120 | `sql/08_gold_calibracao.sql` |
| `gold.retorno_produto` | gold | produto | `stockcode` | 3.808 | `sql/09_gold_validacao.sql` |
| `gold.backtest` | gold | agrupamento × grupo | (`agrupamento`, `grupo`) | 10 | `sql/09_gold_validacao.sql` |
| `gold.comparacao_regra` | gold | regra de alerta | — | 2 | `sql/09_gold_validacao.sql` |
| `gold.exemplo_silencio` | gold | papel no gráfico explicativo | — | 2 | `sql/10_gold_exemplo.sql` |

As únicas tabelas que olham para depois de uma data de referência são `gold.calibracao`,
`gold.retorno_produto`, `gold.backtest` e `gold.comparacao_regra`. Elas existem para o backtest e não alimentam
nenhuma regra de decisão.

### `bronze.retail`

As colunas do Excel com nomes em `snake_case`, mais a aba de origem. Nada é filtrado, renomeado no conteúdo
ou arredondado.

| Coluna | Tipo | Conteúdo |
|---|---|---|
| `invoice` | text | Número da fatura. Começa com "C" nos cancelamentos |
| `stockcode` | text | Código do produto, como digitado (pode ter minúscula) |
| `description` | text | Descrição da linha. Nos ajustes de estoque, é o motivo (*damaged*, *missing*…) |
| `quantity` | integer | Quantidade. Negativa em cancelamentos e ajustes |
| `invoicedate` | timestamp | Data e hora da fatura |
| `price` | numeric | Preço unitário em £, sem arredondar |
| `customer_id` | text | Cliente. Texto, porque é identificador; vazio em cerca de 20% das linhas |
| `country` | text | País do cliente |
| `aba` | text | `Year 2009-2010` ou `Year 2010-2011`. As abas se sobrepõem de 01 a 09/12/2010 |

### `silver.features`

Tem as colunas de `ruptura.csv` que vêm da features (ver abaixo), mais quatro que não vão para o app:
`idade_dias` (dias desde a primeira venda), `preco_medio_ponderado` (faturamento ÷ quantidade),
`pct_faturamento` (participação no faturamento do universo analisado) e `cv_intervalo` (coeficiente de variação
dos intervalos entre dias de venda; perto de 1, vendas espalhadas ao acaso).

## Data quality checks

Cada arquivo em `sql/checks/` é uma consulta que deve retornar **zero linhas**. Se algum retornar linhas, o
`pipeline.py` para antes de atualizar `data/app`.

| Check | O que garante |
|---|---|
| `bronze_linhas_por_aba` | A bronze tem exatamente as linhas das duas abas (525.461 e 541.910) |
| `silver_so_venda_positiva` | Nenhum cancelamento, devolução ou ajuste (quantidade ou preço não positivos) na silver |
| `silver_codigo_normalizado` | Nenhum código com minúscula ou espaço (`85099B` e `85099b` são o mesmo produto) |
| `silver_sem_fatura_nas_duas_abas` | A sobreposição entre as abas foi removida |
| `features_sem_dado_do_futuro` | Nenhuma venda depois da data do diagnóstico nas features (sem data leakage) |
| `features_ritmo_igual_media_intervalos` | O ritmo médio é igual à média dos intervalos entre dias de venda |
| `features_abc_soma_100` | A participação no faturamento soma 100% no universo analisado |
| `snapshot_igual_features` | O snapshot da data do diagnóstico, calculado por outro caminho, reproduz a features |
| `gold_categoria_valida` | Todo produto da features está na gold, com uma categoria conhecida |
| `gold_exemplo_tem_par` | O gráfico explicativo tem os dois produtos (frequente e ocasional) |

## Arquivos do app (`data/app/`)

Cada consulta em `sql/export/` vira um CSV com o mesmo nome. O app lê só esses arquivos e o `execucao.json`.

### `ruptura.csv`: o diagnóstico, uma linha por produto

Sai de `gold.ruptura`. Os valores decimais são arredondados no export.

| Coluna | Definição | Unidade |
|---|---|---|
| `stockcode` | Código do produto, normalizado com `UPPER(TRIM())` | texto |
| `descricao` | Descrição mais frequente do código na silver | texto |
| `categoria_acao` | `ruptura_provavel`, `monitorar`, `sazonal`, `provavel_descontinuacao`, `cliente_principal_parou` ou `fora_do_escopo`. A primeira regra verdadeira vale (ver [decisões](decisoes.md#decisões)) | código |
| `prioridade_na_categoria` | Posição dentro da categoria, por `taxa_semana` decrescente. Vazio fora do escopo | posição |
| `perfil_frequencia` | `diario` (ritmo até 2 dias), `semanal` (até 7), `mensal` (até 20) ou `ocasional` | código |
| `curva_abc` | A (participação acumulada até 80%), B (até 95%) ou C | classe |
| `medidor_ruptura` | `normal` (silêncio relativo até 1), `atraso` (até 2), `indicio` (até 3) ou `ruptura`. É o rótulo antigo, mantido para o backtest comparar | código |
| `primeira_venda`, `ultima_venda` | Primeiro e último dia com venda até a data do diagnóstico | data |
| `dias_com_venda` | Dias distintos com venda até a data do diagnóstico | dias |
| `periodo_silencio` | Data do diagnóstico − última venda | dias corridos |
| `ritmo_medio_dias` | (última venda − primeira venda) ÷ (dias com venda − 1): a cadência enquanto o produto estava ativo | dias |
| `silencio_relativo` | `periodo_silencio ÷ ritmo_medio_dias`: quantas vezes o próprio ritmo o produto está parado | vezes o ritmo |
| `maior_intervalo_dias` | Maior intervalo entre dois dias de venda seguidos, antes do silêncio atual | dias |
| `piso_silencio_dias` | Mínimo de dias parado para sair de "monitorar": 7 (diário), 14 (semanal), 28 (mensal). Vazio para ocasional | dias |
| `faturamento_total` | Soma de quantidade × preço até a data do diagnóstico | £ |
| `quantidade_total` | Unidades vendidas até a data do diagnóstico | unidades |
| `receita_dia_vendido` | `faturamento_total ÷ dias_com_venda`: por dia com venda, não por dia corrido | £ por dia com venda |
| `taxa_semana` | `receita_dia_vendido ÷ ritmo_medio_dias × 7`: o que o produto vendia por semana no ritmo histórico | £/semana |
| `prob_silencio_por_acaso` | e^(−silêncio relativo): chance de um silêncio desse tamanho por acaso, se os dias de venda seguissem um processo de Poisson | proporção |
| `share_top_cliente` | Participação do maior cliente identificado no faturamento do produto. O denominador inclui as vendas sem cliente. Vazio se nenhuma venda tem cliente | proporção |
| `dias_sem_comprar_top_cliente` | Data do diagnóstico − última compra do maior cliente, de qualquer produto | dias |
| `sazonal_por_nome` | O nome contém Christmas, Xmas, Easter, Valentine, Halloween, Santa, Reindeer, Advent, Snowflake ou Hot Water Bottle | `true`/`false` |
| `acima_da_mediana` | `faturamento_total ≥ corte_faturamento` | `true`/`false` |
| `corte_faturamento` | Mediana do `faturamento_total` na features, calculada a cada execução. Igual em todas as linhas | £ |

### Os outros arquivos

| Arquivo | Origem | Grão | Colunas |
|---|---|---|---|
| `vendas_semana.csv` | `silver.vendas_dia` | produto × semana × antes/depois do diagnóstico | `stockcode`, `semana` (segunda-feira), `depois_da_ref` (a semana do diagnóstico é partida em duas, para o minigráfico não ver o futuro), `quantidade`, `faturamento` (£). Só os produtos no escopo e o par do gráfico explicativo |
| `retorno.csv` | `gold.retorno_produto` | produto | `primeira_venda_depois`, `dias_ate_voltar` (vazio se não voltou a vender até o fim dos dados), `faturamento_1_ano_depois` (£) |
| `calibracao.csv` | `gold.calibracao` | data de referência × faixa | `faixa_ordem` (1 a 6), `faixa` (0 a 1, 1 a 2, 2 a 3, 3 a 5, 5 a 10, acima de 10), `produtos`, `taxa_voltou_90d`, `taxa_voltou_365d` (vazio quando não há um ano de dados depois da data) |
| `backtest.csv` | `gold.backtest` | agrupamento × grupo | `agrupamento` (`categoria_acao`, ou `medidor_ruptura` restrito aos produtos acima da mediana), `grupo`, `produtos`, `taxa_voltou_30d`, `taxa_voltou_90d`, `taxa_voltou_1_ano`, `taxa_semana_total` (£/semana) |
| `comparacao_regra.csv` | `gold.comparacao_regra` | regra | `regra` (`silencio_relativo` ou `dias_parado`, o baseline), `criterio`, `alertas` (o mesmo número para as duas), `precisao` (precision: parcela dos alertas que parou de vez), `dias_ate_alertar_mediana` |
| `exemplo_silencio.csv` | `gold.exemplo_silencio` | papel | `papel` (`frequente` ou `ocasional`), `stockcode`: dois produtos parados há o mesmo número de dias, com ritmos opostos |
| `execucao.json` | `pipeline.py` | execução | Data e duração da execução, data do diagnóstico, linhas por tabela e resultado de cada check |
