"""Ruptura de Estoque: apresenta o diagnóstico que o pipeline gravou em data/app.

O app não calcula regra de negócio. Tudo o que decide vem da camada gold (sql/06_gold_ruptura.sql).
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

RAIZ = Path(__file__).resolve().parent
DADOS = RAIZ / "data" / "app"
PASTA_SQL = RAIZ / "sql"

# ── Design system ────────────────────────────────────────────────────────────
COR_RUPTURA = "#E24B4A"  # ação imediata
COR_INDICIO = "#EF9F27"  # monitoramento
COR_NEUTRO = "#7A7975"  # contexto; o #5F5E5A original ficava abaixo de 3:1 sobre o fundo
COR_FUTURO = "#4E4E55"  # o que aconteceu depois do diagnóstico: presente, mas recuado
COR_FUNDO = "#111113"
COR_CARD = "#1C1C1E"
COR_BORDA = "#2A2A2E"
COR_TEXTO = "#F5F5F5"
COR_MUTED = "#9A9AA0"  # texto secundário: 6:1 sobre o card (o #6B6B70 original tinha 3,2:1)

CATEGORIAS = {
    "ruptura_provavel": {
        "rotulo": "Ruptura provável",
        "cor": COR_RUPTURA,
        "acao": "Checar estoque e fornecedor; repor",
        "regra": "Silêncio acima de 3× o próprio ritmo, parado há até 60 dias, sem explicação comercial ou sazonal.",
    },
    "monitorar": {
        "rotulo": "Monitorar",
        "cor": COR_INDICIO,
        "acao": "Acompanhar na próxima semana",
        "regra": "Silêncio entre 2× e 3× o ritmo, ou ainda dentro de uma pausa que o produto já teve antes.",
    },
    "cliente_principal_parou": {
        "rotulo": "Cliente principal parou",
        "cor": COR_NEUTRO,
        "acao": "Ação comercial, não de estoque",
        "regra": "Um cliente respondia por metade ou mais do faturamento do produto e não compra há mais de 90 dias.",
    },
    "sazonal": {
        "rotulo": "Sazonal",
        "cor": COR_NEUTRO,
        "acao": "Planejar a compra da próxima temporada",
        "regra": "O nome indica produto de temporada (Natal, Páscoa, bolsa de água quente...).",
    },
    "provavel_descontinuacao": {
        "rotulo": "Provável descontinuação",
        "cor": COR_NEUTRO,
        "acao": "Confirmar com compras e limpar o catálogo",
        "regra": "Parado há mais de 60 dias: é mais provável ter saído de linha do que estar sem estoque.",
    },
}
PERFIS = {"diario": "Diário", "semanal": "Semanal", "mensal": "Mensal", "ocasional": "Ocasional"}
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

st.set_page_config(page_title="Ruptura de Estoque", page_icon="🔴", layout="wide")

st.markdown(
    f"""
<style>
  .card {{
      background: {COR_CARD}; border: 1px solid {COR_BORDA}; border-radius: 10px;
      padding: 14px 16px; height: 100%;
  }}
  .card-rotulo {{ font-size: 12px; font-weight: 600; color: {COR_MUTED}; display: flex; align-items: center; gap: 8px; }}
  .card-ponto {{ width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }}
  .card-valor {{ font-size: 30px; font-weight: 600; color: {COR_TEXTO}; line-height: 1.2; margin-top: 6px; }}
  .card-sub {{ font-size: 12px; color: {COR_MUTED}; margin-top: 2px; }}
  .titulo-secao {{ font-size: 17px; font-weight: 600; color: {COR_TEXTO}; margin: 8px 0 2px; }}
  .sub-secao {{ font-size: 13px; color: {COR_MUTED}; margin-bottom: 8px; }}
  .grande-ideia {{
      border-left: 3px solid {COR_RUPTURA}; padding: 4px 0 4px 16px; margin: 4px 0 18px;
      font-size: 17px; line-height: 1.6; color: {COR_TEXTO}; max-width: 900px;
  }}
  .fluxo {{ display: flex; flex-wrap: wrap; align-items: stretch; gap: 8px; }}
  .fluxo-etapa {{ background: {COR_CARD}; border: 1px solid {COR_BORDA}; border-radius: 8px; padding: 10px 14px; min-width: 150px; }}
  .fluxo-etapa b {{ color: {COR_TEXTO}; font-size: 13px; }}
  .fluxo-etapa span {{ display: block; color: {COR_MUTED}; font-size: 12px; margin-top: 2px; }}
  .fluxo-seta {{ color: {COR_MUTED}; align-self: center; }}
</style>
""",
    unsafe_allow_html=True,
)


# ── Formatação (padrão brasileiro, moeda em libra) ───────────────────────────
def numero(valor: float, casas: int = 0) -> str:
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "§").replace(".", ",").replace("§", ".")


def libras(valor: float) -> str:
    return f"£{numero(valor)}"


def pct(valor: float) -> str:
    return f"{numero(100 * valor)}%"


def data_br(valor: pd.Timestamp) -> str:
    return valor.strftime("%d/%m/%Y")


def mes_br(valor: pd.Timestamp) -> str:
    return f"{MESES[valor.month - 1]}/{valor:%y}"


def aplicar_layout(fig: go.Figure, altura: int) -> go.Figure:
    fig.update_layout(
        height=altura,
        margin=dict(l=0, r=0, t=8, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=COR_TEXTO, size=12),
        showlegend=False,
        barcornerradius=4,
        hoverlabel=dict(bgcolor=COR_CARD, bordercolor=COR_BORDA, font_color=COR_TEXTO),
    )
    fig.update_xaxes(showgrid=False, linecolor=COR_BORDA, tickfont_color=COR_MUTED, title=None)
    fig.update_yaxes(gridcolor=COR_BORDA, gridwidth=1, zeroline=False, tickfont_color=COR_MUTED, title=None)
    return fig


def mostrar_grafico(fig: go.Figure) -> None:
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def titulo(texto: str, sub: str = "") -> None:
    st.markdown(f'<div class="titulo-secao">{texto}</div>', unsafe_allow_html=True)
    if sub:
        st.markdown(f'<div class="sub-secao">{sub}</div>', unsafe_allow_html=True)


# ── Dados ────────────────────────────────────────────────────────────────────
@st.cache_data
def carregar() -> dict:
    def ler(nome: str, datas: tuple[str, ...] = ()) -> pd.DataFrame:
        # Códigos como 22353 viram número se o pandas adivinhar o tipo.
        return pd.read_csv(DADOS / f"{nome}.csv", dtype={"stockcode": str}, parse_dates=list(datas))

    execucao = json.loads((DADOS / "execucao.json").read_text(encoding="utf-8"))
    return {
        "ruptura": ler("ruptura", ("primeira_venda", "ultima_venda")),
        "retorno": ler("retorno", ("primeira_venda_depois",)),
        "semanas": ler("vendas_semana", ("semana",)),
        "calibracao": ler("calibracao", ("data_ref",)),
        "backtest": ler("backtest"),
        "comparacao": ler("comparacao_regra"),
        "exemplo": ler("exemplo_silencio"),
        "execucao": execucao,
        "data_ref": pd.Timestamp(execucao["data_ref"]),
    }


dados = carregar()
ruptura = dados["ruptura"]
DATA_REF = dados["data_ref"]
no_escopo = ruptura[ruptura["categoria_acao"] != "fora_do_escopo"]


def resumo_categoria(codigo: str) -> tuple[int, float]:
    grupo = ruptura[ruptura["categoria_acao"] == codigo]
    return len(grupo), grupo["taxa_semana"].sum()


# ── Gráfico da linha do tempo de um produto ─────────────────────────────────
def linha_do_tempo(
    stockcode: str, cor_passado: str, mostrar_futuro: bool, inicio: pd.Timestamp | None = None
) -> go.Figure:
    serie = dados["semanas"][dados["semanas"]["stockcode"] == stockcode]
    if inicio is not None:
        serie = serie[serie["semana"] >= inicio]
    produto = ruptura.loc[ruptura["stockcode"] == stockcode].iloc[0]
    fig = go.Figure()
    passado = serie[~serie["depois_da_ref"]]
    fig.add_bar(
        x=passado["semana"],
        y=passado["faturamento"],
        marker_color=cor_passado,
        name="Antes do diagnóstico",
        hovertemplate="semana de %{x|%d/%m/%Y}<br>£%{y:,.0f}<extra></extra>",
    )
    if mostrar_futuro:
        futuro = serie[serie["depois_da_ref"]]
        fig.add_bar(
            x=futuro["semana"],
            y=futuro["faturamento"],
            marker_color=COR_FUTURO,
            name="Depois (não usado no alerta)",
            hovertemplate="semana de %{x|%d/%m/%Y} · depois do diagnóstico<br>£%{y:,.0f}<extra></extra>",
        )
    # O silêncio: da última venda até a data do diagnóstico.
    fig.add_vrect(x0=produto["ultima_venda"], x1=DATA_REF, fillcolor=COR_RUPTURA, opacity=0.14, line_width=0)
    fig.add_vline(x=DATA_REF, line_color=COR_MUTED, line_width=1)
    fig.add_annotation(
        x=DATA_REF,
        y=1,
        yref="paper",
        text="diagnóstico" + (" · depois →" if mostrar_futuro else ""),
        showarrow=False,
        xanchor="left",
        xshift=4,
        font=dict(color=COR_MUTED, size=11),
    )
    fig.update_layout(barmode="stack", bargap=0.25)
    fig.update_xaxes(tickformat="%m/%Y")
    return aplicar_layout(fig, 240)


def evidencias(stockcode: str) -> list[str]:
    p = ruptura.loc[ruptura["stockcode"] == stockcode].iloc[0]
    itens = [
        f"Parado há **{p['periodo_silencio']} dias**. O normal era vender a cada {numero(p['ritmo_medio_dias'], 1)} dias: "
        f"**{numero(p['silencio_relativo'], 1)}× o próprio ritmo**.",
        f"Maior pausa anterior: {int(p['maior_intervalo_dias'])} dias.",
    ]
    prob = p["prob_silencio_por_acaso"]
    itens.append(
        "Chance de um silêncio desse tamanho por acaso: "
        + ("menos de 0,1%." if prob < 0.001 else f"{numero(100 * prob, 1)}%.")
    )
    if pd.notna(p["share_top_cliente"]):
        itens.append(
            f"Maior cliente: {pct(p['share_top_cliente'])} do faturamento do produto; "
            f"sem comprar nada há {int(p['dias_sem_comprar_top_cliente'])} dias."
        )
    if p["sazonal_por_nome"]:
        itens.append("O nome indica produto de temporada.")
    itens.append(f"No ritmo histórico, vendia **{libras(p['taxa_semana'])} por semana**.")
    return itens


@st.dialog("Detalhe do produto", width="large")
def detalhe_produto(stockcode: str) -> None:
    linhas = ruptura.loc[ruptura["stockcode"] == stockcode]
    if linhas.empty:
        st.warning(f"Produto {stockcode} não encontrado.")
        return
    p = linhas.iloc[0]
    categoria = CATEGORIAS.get(p["categoria_acao"])
    st.markdown(f"#### {p['descricao']}")
    st.caption(
        f"Código {stockcode} · perfil {PERFIS[p['perfil_frequencia']].lower()} · curva {p['curva_abc']}"
        + (f" · **{categoria['rotulo']}**: {categoria['acao'].lower()}" if categoria else "")
    )
    if stockcode in set(dados["semanas"]["stockcode"]):
        mostrar_grafico(linha_do_tempo(stockcode, COR_NEUTRO, mostrar_futuro=True))
        st.caption(
            "Faturamento semanal. Faixa vermelha: o silêncio até o diagnóstico. Barras escuras: o que aconteceu depois, que não entra no alerta."
        )
    for item in evidencias(stockcode):
        st.markdown(f"- {item}")
    retorno = dados["retorno"].loc[dados["retorno"]["stockcode"] == stockcode].iloc[0]
    if pd.isna(retorno["dias_ate_voltar"]):
        st.markdown("**Depois do diagnóstico:** não voltou a vender nos 12 meses seguintes.")
    else:
        st.markdown(
            f"**Depois do diagnóstico:** voltou a vender {int(retorno['dias_ate_voltar'])} dias depois "
            f"e faturou {libras(retorno['faturamento_1_ano_depois'])} no ano seguinte."
        )


# ── Cabeçalho ────────────────────────────────────────────────────────────────
n_ruptura, taxa_ruptura = resumo_categoria("ruptura_provavel")
n_descontinuacao, _ = resumo_categoria("provavel_descontinuacao")

st.markdown("## Ruptura de Estoque")
st.caption(
    f"Online Retail II · varejo britânico · diagnóstico em {data_br(DATA_REF)}, "
    "conferido com as vendas dos 12 meses seguintes"
)
st.markdown(
    f'<div class="grande-ideia">{n_ruptura} produtos que vendiam com regularidade pararam de vender sem '
    f"explicação comercial ou sazonal. Juntos, vendiam <b>{libras(taxa_ruptura)} por semana</b>. "
    f"Outros {n_descontinuacao} provavelmente saíram de linha e pedem uma decisão de catálogo, não de reposição.</div>",
    unsafe_allow_html=True,
)

aba_semana, aba_confianca, aba_metodo = st.tabs(["Esta semana", "Confiabilidade", "Metodologia"])

# ════════════════════════════════════════════════════════════════════════════
# ESTA SEMANA
# ════════════════════════════════════════════════════════════════════════════
with aba_semana:
    colunas = st.columns(len(CATEGORIAS))
    for coluna, (codigo, cat) in zip(colunas, CATEGORIAS.items(), strict=True):
        quantidade, taxa = resumo_categoria(codigo)
        coluna.markdown(
            f"""<div class="card" title="{cat["regra"]}">
              <div class="card-rotulo"><span class="card-ponto" style="background:{cat["cor"]}"></span>{cat["rotulo"]}</div>
              <div class="card-valor">{quantidade}</div>
              <div class="card-sub">{libras(taxa)}/semana no ritmo histórico</div>
              <div class="card-sub">{cat["acao"]}</div>
            </div>""",
            unsafe_allow_html=True,
        )

    st.write("")
    escolhidas = st.pills(
        "Categorias na lista",
        options=list(CATEGORIAS),
        format_func=lambda c: CATEGORIAS[c]["rotulo"],
        selection_mode="multi",
        default=["ruptura_provavel"],
    )
    escolhidas = escolhidas or list(CATEGORIAS)

    ordem = {codigo: i for i, codigo in enumerate(CATEGORIAS)}
    lista = (
        no_escopo[no_escopo["categoria_acao"].isin(escolhidas)]
        .assign(_ordem=lambda d: d["categoria_acao"].map(ordem))
        .sort_values(["_ordem", "taxa_semana"], ascending=[True, False])
        .reset_index(drop=True)
    )

    # Minigráfico: as 26 semanas até o diagnóstico, sem nada do que veio depois.
    semanas_passadas = pd.date_range(end=DATA_REF.to_period("W-SUN").start_time, periods=26, freq="W-MON")
    grade = (
        dados["semanas"][~dados["semanas"]["depois_da_ref"]]
        .pivot_table(index="stockcode", columns="semana", values="faturamento", aggfunc="sum")
        .reindex(columns=semanas_passadas, fill_value=0)
        .fillna(0)
    )
    lista["tendencia"] = lista["stockcode"].map(lambda sc: grade.loc[sc].round(0).tolist() if sc in grade.index else [])
    lista["categoria"] = lista["categoria_acao"].map(lambda c: CATEGORIAS[c]["rotulo"])
    lista["perfil"] = lista["perfil_frequencia"].map(PERFIS)

    colunas_tabela = {
        "descricao": st.column_config.TextColumn("Produto", width="large"),
        "stockcode": st.column_config.TextColumn("Código"),
        "categoria": st.column_config.TextColumn("Categoria"),
        "taxa_semana": st.column_config.NumberColumn(
            "£/semana", format="£%d", help="Faturamento semanal no ritmo histórico"
        ),
        "periodo_silencio": st.column_config.NumberColumn("Parado há", format="%d dias"),
        "silencio_relativo": st.column_config.NumberColumn(
            "Silêncio", format="%.1f×", help="Quantas vezes o próprio ritmo"
        ),
        "tendencia": st.column_config.BarChartColumn("26 semanas até o diagnóstico", y_min=0, color=COR_NEUTRO),
        "perfil": st.column_config.TextColumn("Perfil"),
        "curva_abc": st.column_config.TextColumn("ABC"),
    }
    st.caption(f"{len(lista)} produtos · clique numa linha para ver o histórico e as evidências")
    evento = st.dataframe(
        lista[list(colunas_tabela)],
        column_config=colunas_tabela,
        hide_index=True,
        width="stretch",
        height=min(38 + 35 * len(lista), 460),
        on_select="rerun",
        selection_mode="single-row",
        key="lista_acao",
    )

    selecionado = lista.iloc[evento.selection.rows[0]]["stockcode"] if evento.selection.rows else None
    # Abre o diálogo só quando a seleção muda; sem isso, qualquer clique reabriria o último produto.
    if selecionado and selecionado != st.session_state.get("ultimo_detalhe"):
        st.session_state["ultimo_detalhe"] = selecionado
        detalhe_produto(selecionado)
    elif not selecionado:
        st.session_state.pop("ultimo_detalhe", None)

    # Link compartilhável: ?produto=22353 abre o detalhe direto.
    produto_url = st.query_params.get("produto")
    if produto_url and not st.session_state.get("produto_url_aberto"):
        st.session_state["produto_url_aberto"] = True
        detalhe_produto(produto_url.upper())

    download = lista[
        [
            "stockcode",
            "descricao",
            "categoria",
            "taxa_semana",
            "periodo_silencio",
            "silencio_relativo",
            "ritmo_medio_dias",
            "perfil",
            "curva_abc",
            "ultima_venda",
        ]
    ]
    st.download_button(
        "Baixar lista (CSV)",
        download.to_csv(index=False).encode("utf-8"),
        file_name=f"lista_ruptura_{DATA_REF:%Y%m%d}.csv",
        mime="text/csv",
    )

# ════════════════════════════════════════════════════════════════════════════
# CONFIABILIDADE
# ════════════════════════════════════════════════════════════════════════════
with aba_confianca:
    calibracao = dados["calibracao"]
    na_data = calibracao[calibracao["data_ref"] == DATA_REF].sort_values("faixa_ordem")

    titulo(
        "Quanto maior o silêncio relativo, menor a chance de o produto voltar a vender",
        f"Produtos que voltaram a vender em até 90 dias, por faixa de silêncio relativo · diagnóstico de "
        f"{data_br(DATA_REF)}, conferido com as vendas de 2011",
    )
    alerta = na_data["faixa_ordem"] >= 4  # acima de 3× o ritmo: a faixa que o projeto chama de ruptura
    fig = go.Figure(
        go.Bar(
            x=na_data["faixa"] + "×",
            y=na_data["taxa_voltou_90d"],
            marker_color=[COR_RUPTURA if a else COR_NEUTRO for a in alerta],
            text=[pct(v) for v in na_data["taxa_voltou_90d"]],
            textposition="outside",
            textfont=dict(color=COR_TEXTO),
            customdata=na_data["produtos"],
            hovertemplate="%{x}: %{y:.0%} voltaram em 90 dias<br>%{customdata} produtos<extra></extra>",
        )
    )
    fig.update_yaxes(tickformat=".0%", range=[0, 1.08])
    fig.update_layout(bargap=0.6)
    mostrar_grafico(aplicar_layout(fig, 300))
    st.caption("Em vermelho, as faixas acima de 3× o ritmo, onde o projeto dispara o alerta.")

    st.divider()
    backtest = dados["backtest"]
    cats = (
        backtest[backtest["agrupamento"] == "categoria_acao"]
        .set_index("grupo")
        .reindex(list(CATEGORIAS)[::-1])
        .reset_index()
    )
    taxa_rp = cats.loc[cats["grupo"] == "ruptura_provavel", "taxa_voltou_90d"].iloc[0]
    taxa_desc = cats.loc[cats["grupo"] == "provavel_descontinuacao", "taxa_voltou_90d"].iloc[0]
    titulo(
        "As categorias separam o que ainda vive do que saiu de linha",
        f"De cada 10 produtos em ruptura provável, {numero(10 * taxa_rp)} voltaram a vender em 90 dias; "
        f"na provável descontinuação, {'menos de 1' if 10 * taxa_desc < 1 else numero(10 * taxa_desc)}.",
    )
    fig = go.Figure(
        go.Bar(
            y=cats["grupo"].map(lambda c: CATEGORIAS[c]["rotulo"]),
            x=cats["taxa_voltou_90d"],
            orientation="h",
            marker_color=cats["grupo"].map(lambda c: CATEGORIAS[c]["cor"]),
            text=[f"{pct(v)}  ·  {n} produtos" for v, n in zip(cats["taxa_voltou_90d"], cats["produtos"], strict=True)],
            textposition="outside",
            textfont=dict(color=COR_TEXTO),
            hovertemplate="%{y}: %{x:.0%} voltaram em 90 dias<extra></extra>",
        )
    )
    fig.update_xaxes(tickformat=".0%", range=[0, 1], showgrid=True, gridcolor=COR_BORDA)
    fig.update_yaxes(showgrid=False, tickfont_color=COR_TEXTO)
    fig.update_layout(bargap=0.4)
    mostrar_grafico(aplicar_layout(fig, 260))
    st.caption(
        "Voltar a vender é o sinal observável de que o silêncio era temporário. Não prova ruptura: "
        "mostra que o produto ainda tinha demanda e estava no catálogo."
    )

    st.divider()
    comparacao = dados["comparacao"].set_index("regra")
    relativo, dias = comparacao.loc["silencio_relativo"], comparacao.loc["dias_parado"]
    titulo(
        f"O silêncio relativo acerta quase tanto quanto a regra simples, e avisa {numero(dias['dias_ate_alertar_mediana'] - relativo['dias_ate_alertar_mediana'])} dias antes",
        f"Os {relativo['alertas']} alertas de cada regra, nos produtos acima da mediana de faturamento. "
        "Acerto = o produto parou de vez (não vendeu nada em 12 meses).",
    )
    c1, c2, c3 = st.columns(3)
    for coluna, rotulo, valor, sub in [
        (c1, "Acerto · silêncio relativo", pct(relativo["precisao"]), relativo["criterio"]),
        (c2, "Acerto · regra simples", pct(dias["precisao"]), dias["criterio"]),
        (
            c3,
            "Antecedência",
            f"{numero(dias['dias_ate_alertar_mediana'] - relativo['dias_ate_alertar_mediana'])} dias antes",
            f"alerta com {numero(relativo['dias_ate_alertar_mediana'])} dias parado (mediana, nos que pararam de vez); "
            f"a regra simples espera {numero(dias['dias_ate_alertar_mediana'])}",
        ),
    ]:
        coluna.markdown(
            f"""<div class="card"><div class="card-rotulo">{rotulo}</div>
            <div class="card-valor">{valor}</div><div class="card-sub">{sub}</div></div>""",
            unsafe_allow_html=True,
        )
    st.caption(
        "O ganho da métrica não é prever melhor quem vai parar, e sim perceber mais cedo a parada dos produtos "
        "que vendem com frequência, que é onde a ruptura temporária aparece."
    )

    st.divider()
    titulo(
        "Uma data só engana: em dezembro, o silêncio é mais definitivo",
        "Produtos que voltaram a vender em até 90 dias, por faixa e data de referência. Cada coluna usa só os "
        "dados anteriores àquela data.",
    )
    grade_cal = calibracao.pivot_table(index="faixa", columns="data_ref", values="taxa_voltou_90d")
    faixas = calibracao.drop_duplicates("faixa").sort_values("faixa_ordem")["faixa"].tolist()
    grade_cal = grade_cal.reindex(faixas[::-1])
    rotulos_data = [mes_br(d) if d != DATA_REF else f"{DATA_REF:%d}/{mes_br(DATA_REF)}" for d in grade_cal.columns]
    fig = go.Figure(
        go.Heatmap(
            z=grade_cal.values,
            x=rotulos_data,
            y=[f"{f}×" for f in grade_cal.index],
            zmin=0,
            zmax=1,
            colorscale=[[0, COR_CARD], [1, COR_TEXTO]],
            xgap=2,
            ygap=2,
            colorbar=dict(tickformat=".0%", outlinewidth=0, tickfont=dict(color=COR_MUTED), thickness=10),
            hovertemplate="%{x} · faixa %{y}<br>%{z:.0%} voltaram em 90 dias<extra></extra>",
        )
    )
    fig.update_xaxes(tickangle=-45, type="category")
    fig.update_yaxes(showgrid=False, tickfont_color=COR_TEXTO)
    mostrar_grafico(aplicar_layout(fig, 300))
    st.caption(
        "Mais claro = mais produtos voltaram. De março a novembro, a maioria dos produtos entre 3× e 10× o ritmo "
        "volta em 90 dias, o perfil de uma falta temporária. Em dezembro, poucos voltam: é quando o catálogo "
        "gira. Em jan/11, logo depois do recesso de Natal (loja fechada), todos parecem parados e a relação se "
        "inverte. Contar o tempo em dias comerciais é a próxima etapa."
    )
    with st.expander("Tabela da calibração"):
        st.dataframe(
            calibracao.assign(data_ref=calibracao["data_ref"].dt.date),
            hide_index=True,
            width="stretch",
            column_config={
                "taxa_voltou_90d": st.column_config.NumberColumn("voltou em 90 dias", format="percent"),
                "taxa_voltou_365d": st.column_config.NumberColumn("voltou em 1 ano", format="percent"),
            },
        )

# ════════════════════════════════════════════════════════════════════════════
# METODOLOGIA
# ════════════════════════════════════════════════════════════════════════════
with aba_metodo:
    exemplo = dados["exemplo"].set_index("papel")["stockcode"]
    frequente = ruptura.loc[ruptura["stockcode"] == exemplo["frequente"]].iloc[0]
    ocasional = ruptura.loc[ruptura["stockcode"] == exemplo["ocasional"]].iloc[0]
    titulo(
        f"Os mesmos {frequente['periodo_silencio']} dias parados significam coisas diferentes",
        "O silêncio relativo divide os dias sem venda pelo ritmo normal do próprio produto. "
        "Um produto que vendia quase todo dia e parou é um alarme; um que vendia uma vez por mês, não.",
    )
    inicio = DATA_REF - pd.DateOffset(months=9)
    col_a, col_b = st.columns(2)
    for coluna, produto, cor in [(col_a, frequente, COR_RUPTURA), (col_b, ocasional, COR_NEUTRO)]:
        with coluna:
            st.markdown(f"**{produto['descricao'].title()}**")
            st.caption(
                f"Vendia a cada {numero(produto['ritmo_medio_dias'], 1)} dias · parado há "
                f"{produto['periodo_silencio']} dias = **{numero(produto['silencio_relativo'], 1)}× o ritmo**"
            )
            mostrar_grafico(linha_do_tempo(produto["stockcode"], cor, mostrar_futuro=False, inicio=inicio))
    st.caption("Faturamento semanal nos 9 meses antes do diagnóstico. Faixa vermelha: o período sem venda.")

    st.divider()
    execucao = dados["execucao"]
    linhas = execucao["linhas"]
    checks_ok = sum(c["ok"] for c in execucao["checks"])
    titulo(
        "Pipeline",
        f"Última execução em {pd.Timestamp(execucao['executado_em']):%d/%m/%Y} · "
        f"{checks_ok} de {len(execucao['checks'])} checks de qualidade passaram · "
        f"{numero(execucao['duracao_segundos'])} segundos do Excel ao app",
    )
    etapas = [
        ("Excel", "2 abas · dez/2009 a dez/2011"),
        ("bronze.retail", f"{numero(linhas['bronze.retail'])} linhas, fiel ao original"),
        ("silver.vendas", f"{numero(linhas['silver.vendas'])} vendas de produto"),
        ("silver.features", f"{numero(linhas['silver.features'])} produtos até {data_br(DATA_REF)}"),
        ("gold.ruptura", "categoria de ação e £/semana"),
        ("gold.calibracao", f"{numero(linhas['gold.snapshots'])} snapshots para validar"),
    ]
    blocos = '<span class="fluxo-seta">→</span>'.join(
        f'<div class="fluxo-etapa"><b>{nome}</b><span>{desc}</span></div>' for nome, desc in etapas
    )
    st.markdown(f'<div class="fluxo">{blocos}</div>', unsafe_allow_html=True)
    st.caption("PostgreSQL faz todo o trabalho. O app lê só os CSVs que o pipeline exporta, e por isso roda sem banco.")

    st.divider()
    titulo("Decisões")
    st.markdown(
        f"""
- **Ritmo só no período ativo.** `ritmo_medio_dias = (última venda − primeira venda) / (dias com venda − 1)`. O silêncio atual fica fora, para não contaminar o comportamento normal.
- **Escopo:** silêncio relativo acima de 2, faturamento acima da mediana ({libras(ruptura["corte_faturamento"].iloc[0])}, calculada no SQL) e pelo menos 10 dias com venda. Mediana porque o faturamento é muito assimétrico.
- **Categorias em vez de um rótulo único.** A primeira regra verdadeira vale: cliente principal parou → sazonal → parado há mais de 60 dias → monitorar → ruptura provável. Cada uma pede uma ação diferente.
- **Piso por perfil.** Diário precisa de mais de 7 dias parado, semanal de 14 e mensal de 28 antes de virar ruptura provável.
- **Impacto como taxa.** £/semana no ritmo histórico, e não perda acumulada: a versão anterior multiplicava faturamento por dia de venda por dias corridos e inflava o número 3,9 vezes.
- **Validação fora do diagnóstico.** As métricas usam só dados até {data_br(DATA_REF)}; a aba de 2011 serve só para conferir.
"""
    )
    titulo("Limitações")
    st.markdown(
        """
- **Não há posição de estoque, fornecedor nem prazo de reposição.** O projeto identifica o sintoma (o produto parou) e a causa provável, não a causa confirmada.
- **Sazonalidade é aproximada pelo nome do produto.** Com 25 meses, a comparação ano contra ano é a próxima etapa.
- **O tempo é contado em dias corridos.** A loja não abre aos sábados nem no recesso de Natal, o que distorce datas logo depois de feriados.
- **£/semana é uma projeção do ritmo histórico**, não uma perda observada.
- **Voltar a vender não prova que houve ruptura**: é o indicador indireto que o dado permite.
"""
    )

    st.divider()
    titulo("SQL do pipeline", "Os arquivos exatos que o pipeline executa, na ordem.")
    arquivos = sorted(PASTA_SQL.glob("[0-9][0-9]_*.sql"))
    escolhido = st.selectbox("Arquivo", arquivos, index=6, format_func=lambda p: p.name, label_visibility="collapsed")
    st.code(escolhido.read_text(encoding="utf-8"), language="sql")
