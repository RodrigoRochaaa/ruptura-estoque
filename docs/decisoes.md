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
2. **Sazonal:** o nome indica temporada (Christmas, Easter, Valentine, Hot Water Bottle...).
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

**Validação.** As métricas do diagnóstico usam só dados até 09/12/2010. A aba de 2011 entra apenas em
`gold.retorno_produto`, `gold.calibracao` e `gold.backtest`. O alvo observável é *voltou a vender em até 90 dias*.
Isso não prova ruptura, mas separa o que ainda tinha demanda do que saiu de linha.

**Correlação.** O Spearman entre silêncio relativo e faturamento é −0,41, mas parte disso é mecânica: quem está
parado há mais tempo teve menos tempo para faturar. Por dia ativo, o valor cai para −0,24. Ele fica na EDA como
associação. A validação do alerta é o backtest.

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
| Validação | correlação de Spearman | backtest com 12 meses e comparação com a regra simples | Mede se o alerta acerta |
| Regra de negócio | repetida no app e na EDA | só no SQL (gold) | Um lugar só, versionado e testado |

## Números de referência (execução de 27/09/2026)

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
| Silêncio relativo × regra simples (305 alertas): acerto | 76,4% × 78,7% |
| Dias parado até o alerta (mediana) | 13 × 18 |
| AUC (parou de vez em 12 meses) | 0,959 × 0,966 |
| Spearman silêncio × faturamento (total / por dia ativo) | −0,41 / −0,24 |
