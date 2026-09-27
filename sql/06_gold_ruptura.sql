-- Gold: o que fazer com cada produto na data do diagnóstico. Toda regra de decisão fica aqui;
-- o app só lê o resultado.
DROP TABLE IF EXISTS gold.ruptura;
CREATE TABLE gold.ruptura AS
WITH params AS (
  SELECT p.data_ref,
         -- Recalculado a cada execução. O valor digitado à mão na versão anterior ficou defasado
         -- quando a features mudou.
         PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY f.faturamento_total) AS corte_faturamento
  FROM silver.features f
  CROSS JOIN meta.parametros p
  GROUP BY p.data_ref
),
base AS (
  SELECT f.*,
         p.corte_faturamento,
         f.faturamento_total >= p.corte_faturamento AS acima_da_mediana,
         -- Dias de venda esperados por semana × faturamento por dia de venda. É uma taxa, não um
         -- acumulado: não cresce para quem está parado há um ano.
         f.receita_dia_vendido / f.ritmo_medio_dias * 7 AS taxa_semana,
         -- Se os dias de venda seguissem um processo de Poisson no ritmo histórico, esta seria a chance
         -- de um silêncio deste tamanho acontecer por acaso.
         EXP(-LEAST(f.silencio_relativo, 50)) AS prob_silencio_por_acaso,
         -- Piso de dias por perfil (a confirmação da EDA): menos que isso é cedo para concluir.
         CASE f.perfil_frequencia
           WHEN 'diario'  THEN 7
           WHEN 'semanal' THEN 14
           WHEN 'mensal'  THEN 28
         END AS piso_silencio_dias
  FROM silver.features f
  CROSS JOIN params p
),
categorizado AS (
  -- A primeira regra verdadeira define a categoria. A ordem vai do motivo mais específico ao mais
  -- genérico: cada categoria pede uma ação e um dono diferentes.
  SELECT b.*,
         CASE
           WHEN b.silencio_relativo <= 2
             OR NOT b.acima_da_mediana
             -- Com menos de 10 dias de venda o ritmo é pura amostra pequena.
             OR b.dias_com_venda < 10                             THEN 'fora_do_escopo'
           WHEN b.share_top_cliente >= 0.5
            AND b.dias_sem_comprar_top_cliente > 90               THEN 'cliente_principal_parou'
           WHEN b.sazonal_por_nome                                THEN 'sazonal'
           -- Parado há mais de dois meses: é mais provável ter saído de linha do que estar sem estoque.
           WHEN b.periodo_silencio > 60                           THEN 'provavel_descontinuacao'
           WHEN b.silencio_relativo <= 3
             -- Já ficou parado tanto tempo antes e voltou: ainda não é anomalia para este produto.
             OR b.periodo_silencio <= b.maior_intervalo_dias
             OR b.periodo_silencio <= COALESCE(b.piso_silencio_dias, 0) THEN 'monitorar'
           ELSE                                                        'ruptura_provavel'
         END AS categoria_acao
  FROM base b
)
SELECT c.*,
       CASE WHEN c.categoria_acao <> 'fora_do_escopo'
            THEN ROW_NUMBER() OVER (PARTITION BY c.categoria_acao ORDER BY c.taxa_semana DESC, c.stockcode)
       END AS prioridade_na_categoria
FROM categorizado c;

ALTER TABLE gold.ruptura ADD PRIMARY KEY (stockcode);
