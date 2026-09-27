"""Gera as figuras do README (versão clara e escura) a partir dos CSVs que o app lê.

python scripts/figuras_readme.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
DADOS = RAIZ / "data" / "app"
SAIDA = RAIZ / "docs" / "img"

# Superfícies do GitHub em cada tema; vermelho só onde o título aponta, o resto em cinza de contexto.
TEMAS = {
    "claro": {
        "fundo": "#ffffff",
        "texto": "#1f2328",
        "muted": "#59636e",
        "grade": "#d1d9e0",
        "destaque": "#d93f3e",
        "contexto": "#85847f",
        "faixa": "#d93f3e",
    },
    "escuro": {
        "fundo": "#0d1117",
        "texto": "#f0f6fc",
        "muted": "#9198a1",
        "grade": "#30363d",
        "destaque": "#e24b4a",
        "contexto": "#7a7975",
        "faixa": "#e24b4a",
    },
}


def ler(nome: str, datas: tuple[str, ...] = ()) -> pd.DataFrame:
    return pd.read_csv(DADOS / f"{nome}.csv", dtype={"stockcode": str}, parse_dates=list(datas))


def numero(valor: float, casas: int = 0) -> str:
    return f"{valor:,.{casas}f}".replace(",", "§").replace(".", ",").replace("§", ".")


def eixo_limpo(ax, t: dict) -> None:
    ax.set_facecolor(t["fundo"])
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    ax.spines["bottom"].set_color(t["grade"])
    ax.tick_params(colors=t["muted"], length=0, labelsize=9)
    ax.grid(axis="y", color=t["grade"], linewidth=0.8)
    ax.set_axisbelow(True)


def titulos(fig, t: dict, titulo: str, subtitulo: str) -> None:
    fig.text(0.012, 0.95, titulo, color=t["texto"], fontsize=14, fontweight="bold", va="top")
    fig.text(0.012, 0.865, subtitulo, color=t["muted"], fontsize=10, va="top")


def calibracao(t: dict, data_ref: pd.Timestamp) -> plt.Figure:
    cal = ler("calibracao", ("data_ref",))
    na_data = cal[cal["data_ref"] == data_ref].sort_values("faixa_ordem")
    fig, ax = plt.subplots(figsize=(10, 4.4), dpi=150, facecolor=t["fundo"])
    fig.subplots_adjust(left=0.06, right=0.99, top=0.70, bottom=0.12)
    cores = [t["destaque"] if f >= 4 else t["contexto"] for f in na_data["faixa_ordem"]]
    barras = ax.bar(na_data["faixa"] + "×", na_data["taxa_voltou_90d"], width=0.42, color=cores)
    for barra, valor in zip(barras, na_data["taxa_voltou_90d"], strict=True):
        ax.text(
            barra.get_x() + barra.get_width() / 2,
            valor + 0.025,
            f"{valor:.0%}",
            ha="center",
            color=t["texto"],
            fontsize=11,
            fontweight="bold",
        )
    eixo_limpo(ax, t)
    ax.set_ylim(0, 1.08)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1])
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax.set_xlabel("silêncio relativo (dias parado ÷ ritmo normal do produto)", color=t["muted"], fontsize=9)
    titulos(
        fig,
        t,
        "Quanto maior o silêncio relativo, menor a chance de o produto voltar a vender",
        f"Produtos que voltaram a vender em até 90 dias · diagnóstico de {data_ref:%d/%m/%Y}, conferido com as "
        "vendas de 2011\nEm vermelho, as faixas acima de 3× o ritmo, onde o alerta dispara",
    )
    return fig


def explicacao(t: dict, data_ref: pd.Timestamp) -> plt.Figure:
    ruptura = ler("ruptura", ("ultima_venda",)).set_index("stockcode")
    semanas = ler("vendas_semana", ("semana",))
    exemplo = ler("exemplo_silencio").set_index("papel")["stockcode"]
    inicio = data_ref - pd.DateOffset(months=9)

    fig, eixos = plt.subplots(1, 2, figsize=(10, 3.9), dpi=150, facecolor=t["fundo"], sharex=True)
    fig.subplots_adjust(left=0.05, right=0.99, top=0.66, bottom=0.1, wspace=0.12)
    for ax, papel, cor in zip(eixos, ("frequente", "ocasional"), (t["destaque"], t["contexto"]), strict=True):
        sc = exemplo[papel]
        p = ruptura.loc[sc]
        serie = semanas[(semanas["stockcode"] == sc) & (~semanas["depois_da_ref"]) & (semanas["semana"] >= inicio)]
        ax.bar(serie["semana"], serie["faturamento"], width=5, color=cor)
        ax.axvspan(p["ultima_venda"], data_ref, color=t["faixa"], alpha=0.13, linewidth=0)
        ax.axvline(data_ref, color=t["muted"], linewidth=1)
        eixo_limpo(ax, t)
        ax.set_xlim(inicio, data_ref + pd.Timedelta(days=6))
        ax.xaxis.set_major_locator(matplotlib.dates.MonthLocator(interval=2))
        ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%m/%Y"))
        ax.yaxis.set_major_formatter(lambda v, _: f"£{v:.0f}")
        ax.set_title(
            f"{p['descricao'].title()}\nvendia a cada {numero(p['ritmo_medio_dias'], 1)} dias · parado há "
            f"{p['periodo_silencio']} dias = {numero(p['silencio_relativo'], 1)}× o ritmo",
            loc="left",
            color=t["texto"],
            fontsize=9.5,
            pad=8,
        )
    dias = ruptura.loc[exemplo["frequente"], "periodo_silencio"]
    titulos(
        fig,
        t,
        f"Os mesmos {dias} dias parados significam coisas diferentes",
        "Faturamento semanal nos 9 meses antes do diagnóstico · faixa vermelha: o período sem venda",
    )
    return fig


def main() -> None:
    SAIDA.mkdir(parents=True, exist_ok=True)
    data_ref = pd.Timestamp(pd.read_json(DADOS / "execucao.json", typ="series")["data_ref"])
    for nome_tema, t in TEMAS.items():
        for nome, desenhar in (("calibracao", calibracao), ("silencio_relativo", explicacao)):
            fig = desenhar(t, data_ref)
            destino = SAIDA / f"{nome}_{nome_tema}.png"
            fig.savefig(destino, facecolor=t["fundo"])
            plt.close(fig)
            print(destino.relative_to(RAIZ).as_posix())


if __name__ == "__main__":
    main()
