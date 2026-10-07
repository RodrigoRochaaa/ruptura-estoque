# Decisões e números de referência

Registro das decisões do projeto, com o motivo de cada uma. Qualquer execução do pipeline que divirja dos
números da última seção precisa ser investigada antes de ser aceita.

## Arquitetura em camadas

| Camada | Onde | Responsabilidade | Nunca faz |
|---|---|---|---|
| Bronze | `pipeline.py` + `sql/01` | Ler o Excel e carregar como está (as duas abas, identificadores como texto) | Filtrar, renomear, arredondar |
| Silver | `sql/02` a `sql/05` | Regras estruturais: só venda de produto, código normalizado, sem sobreposição de abas; métricas por produto | Recortes de análise |
| Gold | `sql/06` a `sql/10` | Regras de decisão (escopo, categoria, impacto) e validação | Depender do futuro no diagnóstico |
| EDA | `notebooks/` | Explorar e validar as decisões | Reescrever regra de negócio |
| App | `app.py` | Apresentar | Calcular regra nova |

## Métricas

- **`ritmo_medio_dias`** = (última venda − primeira venda) / (dias com venda − 1). É a cadência **enquanto o
  produto estava ativo**; o silêncio atual fica fora para não contaminar a medida do normal. É igual à média dos
  intervalos entre dias de venda, e um check garante isso.
- **`periodo_silencio`** = data de referência − última venda, em dias corridos.
- **`silencio_relativo`** = `periodo_silencio / ritmo_medio_dias`. Quantas vezes o próprio ritmo o produto está
  parado.
- **`receita_dia_vendido`** = faturamento / dias com venda. É por dia com venda, não por dia corrido.
- **`taxa_semana`** = `receita_dia_vendido / ritmo_medio_dias × 7`. São os dias de venda esperados por semana
  vezes o faturamento de cada um. É uma taxa, não um acumulado, e por isso não cresce para quem está parado há um
  ano.
- **`prob_silencio_por_acaso`** = e^(−silêncio relativo). Se os dias de venda seguissem um processo de Poisson no
  ritmo histórico, esta seria a chance de um silêncio desse tamanho por acaso: 13,5% a 2×, 5% a 3×.
- **`curva_abc`** = participação acumulada no faturamento (80/95/100), com o denominador restrito aos produtos
  analisados e desempate por código.

## Decisões

**Universo analisado.** Produtos com pelo menos 60 dias desde a primeira venda e 2 dias com venda (sem intervalo
não há ritmo).

**Escopo do alerta.** Silêncio relativo acima de 2, faturamento acima da mediana e pelo menos 10 dias com venda.
A mediana é usada porque o faturamento é muito assimétrico (média £2.544, desvio £6.341, mediana £733,42). Ela é
calculada no SQL a cada execução. A versão anterior usava um valor digitado à mão que tinha ficado defasado.

**Categorias de ação.** A primeira regra verdadeira define a categoria:

1. **Cliente principal parou:** um cliente responde por 50% ou mais do faturamento do produto e não compra nada
   na loja há mais de 90 dias.
2. **Sazonal:** o nome indica temporada (Christmas, Easter, Valentine, Hot Water Bottle...). Antes de
   09/12/2010 há um único ciclo de vendas, então comparar ano contra ano exigiria usar o futuro. O nome é a
   aproximação possível; medir a concentração das vendas em poucas semanas é o próximo passo.
3. **Provável descontinuação:** parado há mais de 60 dias.
4. **Monitorar:** silêncio relativo até 3; ou o silêncio ainda não passou da maior pausa que o produto já teve;
   ou não passou do piso do perfil (diário 7 dias, semanal 14, mensal 28).
5. **Ruptura provável:** todo o resto.

O corte de 60 dias é uma escolha declarada. A ruptura provável fica assim com cada corte:

| Corte | Produtos em ruptura provável | Voltaram a vender em 90 dias |
|---:|---:|---:|
| 45 dias | 23 | 34,8% |
| **60 dias** | **36** | **33,3%** |
| 90 dias | 60 | 21,7% |

O de 90 dias quase dobra a lista, mas coloca nela produtos que voltam bem menos.

**Piso por perfil.** Veio da EDA: um produto "diário" com alta proporção de silêncio, mas parado há só 4 dias,
ainda não sustenta uma conclusão. Na versão original, o piso aparecia como `transac_d7 = 0` / `d14` / `d28`. A
reconstrução mostrou que essas colunas somavam a *quantidade* vendida na janela e que a regra equivalia
exatamente a `periodo_silencio > 7 / 14 / 28`. Agora ela é escrita assim.

**Validação (backtest).** As métricas do diagnóstico usam só dados até 09/12/2010, sem data leakage. A aba de 2011
entra apenas em `gold.retorno_produto`, `gold.calibracao` e `gold.backtest`. O alvo observável é *voltou a vender
em até 90 dias*. Isso não prova ruptura, mas separa o que ainda tinha demanda do que saiu de linha.

As faixas de silêncio relativo foram validadas nas 20 datas de `gold.snapshots`. **As categorias, só em
09/12/2010**, uma das datas em que menos produtos voltam a vender (véspera do recesso de Natal). Validá-las em
todas as datas exige calcular features e gold por data de referência, e é o próximo passo. Até lá, "ruptura
provável" quer dizer "o grupo onde vale checar o estoque primeiro": voltou a vender 4 vezes mais que a provável
descontinuação (33,3% contra 7,5% em 90 dias), não "stockout confirmado".

**Correlação.** O Spearman entre silêncio relativo e faturamento é −0,41, mas parte disso é mecânica: quem está
parado há mais tempo teve menos tempo para faturar. Por dia ativo, o valor cai para −0,24. Ele fica na EDA como
associação. A validação do alerta é o backtest.

## Fontes externas avaliadas

O dado novo que importava era a segunda aba do próprio Excel, e ele já entrou. Fontes externas só entram se
responderem a uma pergunta de negócio que o projeto não consegue responder sozinho. Avaliação de outubro de 2026:

| Fonte | Decisão | Por quê |
|---|---|---|
| [FreshRetailNet-50K](https://arxiv.org/abs/2505.16319) (2025, CC BY 4.0): 50 mil séries loja × produto, 90 dias, por hora, com o status de stockout de cada hora | Projeto separado | É o único dataset público encontrado com ground truth de stockout, o que ataca a maior limitação daqui ("voltar a vender não prova ruptura"). Mas não se junta ao Online Retail II: é outro varejo, de perecíveis, em escala horária. Serve para validar o método, não para complementar este diagnóstico |
| M5 (Walmart), Favorita, Dunnhumby | Não entra | Não têm rótulo de stockout: venda zero continua ambígua, o mesmo problema daqui |
| Feriados do Reino Unido, clima, câmbio, índices de varejo | Não entra | Não respondem à pergunta de negócio. O calendário da loja sai do próprio dado (dias com venda) |
| Ajustes de saída (*damaged*, *missing*, *No Stock*) e cancelamentos, que já estão na bronze | Próximo passo | É o mais perto de dado de estoque que o dataset tem. Hoje a silver os descarta ao ficar só com as vendas |

## Da versão original para a atual

A versão original foi reconstruída a partir do banco e versionada no primeiro commit. O `EXCEPT ALL` contra as
tabelas antigas retornou 0 linhas nas duas direções. As mudanças vieram depois, em commits separados.

| Tema | Versão original | Versão atual | Por quê |
|---|---|---|---|
| Período | 1 aba (13 meses) | 2 abas (25 meses), diagnóstico em 09/12/2010 | A segunda aba valida o alerta |
| Código do produto | `85099B` ≠ `85099b` | `UPPER(TRIM(stockcode))` | 148 códigos duplicados pela caixa geravam falsos alertas |
| Códigos que não são produto | tirava só POST, M e D | tira também DOT, C2, ajustes, vales, testes, taxas | O frete do site (DOT) aparecia como um produto de £116 mil |
| Produtos analisados | 3.923 | 3.808 | Consequência das duas linhas acima |
| Corte de faturamento | £638,245 fixo no código (defasado) | mediana calculada: £733,42 | Valor derivado do dado não se digita |
| Impacto | £2,8M de "faturamento perdido" acumulado | £/semana no ritmo histórico | A conta antiga misturava dia de venda com dia corrido (inflada 3,9×) |
| Rótulo | "Ruptura" (341 produtos) | 5 categorias de ação | 76% dos marcados como ruptura nunca mais venderam |
| Validação | correlação de Spearman | backtest com 12 meses e comparação com um baseline | Mede se o alerta acerta |
| Regra de negócio | repetida no app e na EDA | só no SQL (gold) | Um lugar só, versionado e testado |

## Números de referência (execução de 27/09/2026)

`tests/test_numeros_referencia.py` confere estes números contra os arquivos do app e confere o README contra os
mesmos arquivos. Uma mudança de regra que altere algum deles faz o teste falhar e precisa ser justificada aqui.

| Métrica | Valor |
|---|---:|
| Linhas na bronze | 1.067.371 (525.461 + 541.910) |
| Linhas na silver.vendas | 1.015.071 |
| Produtos na features | 3.808 |
| Mediana do faturamento | £733,42 |
| Ruptura provável | 36 produtos · £2.519/semana |
| Monitorar | 101 · £5.888/semana |
| Sazonal | 27 · £2.895/semana |
| Provável descontinuação | 159 · £13.553/semana |
| Cliente principal parou | 20 · £1.358/semana |
| Voltaram em 90 dias: ruptura provável / descontinuação | 33,3% / 7,5% |
| Calibração em 09/12/2010, voltou em 90 dias (0–1× … acima de 10×) | 92% · 73% · 67% · 41% · 24% · 7% |
| Silêncio relativo × baseline (305 alertas): precision | 76,4% × 78,7% |
| Dias parado até o alerta (mediana) | 13 × 18 |
| AUC (parou de vez em 12 meses) | 0,959 × 0,966 |
| Spearman silêncio × faturamento (total / por dia ativo) | −0,41 / −0,24 |
