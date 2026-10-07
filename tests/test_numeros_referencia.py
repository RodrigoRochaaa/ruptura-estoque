"""Números de referência e frases do README conferidos contra os arquivos do app. Roda sem banco.

Os números publicados foram digitados uma vez, à mão. Sem este teste, eles poderiam ficar velhos sem ninguém
perceber, como a mediana fixa da primeira versão. Se uma mudança de regra alterar algum deles, o teste falha, e a
mudança precisa ser justificada em docs/decisoes.md.
"""

import json
from pathlib import Path

import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[1]
DADOS = RAIZ / "data" / "app"

REFERENCIA = {
    "linhas": {"bronze.retail": 1_067_371, "silver.vendas": 1_015_071, "silver.features": 3_808},
    "mediana_faturamento": 733.42,
    # produtos, £/semana, voltou a vender em 90 dias (as taxas com as 4 casas do export)
    "categorias": {
        "ruptura_provavel": (36, 2_519, 0.3333),
        "monitorar": (101, 5_888, 0.5941),
        "sazonal": (27, 2_895, 0.3704),
        "provavel_descontinuacao": (159, 13_553, 0.0755),
        "cliente_principal_parou": (20, 1_358, 0.0500),
    },
    # O rótulo único antigo ("ruptura"), acima da mediana: alertas e parcela que não voltou a vender em 1 ano.
    "rotulo_antigo": (305, 0.7639),
    "calibracao_na_data_ref": [0.92, 0.73, 0.67, 0.41, 0.24, 0.07],
    # precision com o mesmo número de alertas, dias parado até o alerta (mediana)
    "comparacao": {"silencio_relativo": (0.7639, 13), "dias_parado": (0.7869, 18)},
    "par_exemplo": {"frequente": "22353", "ocasional": "46138B"},
}
ROTULOS = {
    "ruptura_provavel": "Ruptura provável",
    "monitorar": "Monitorar",
    "sazonal": "Sazonal",
    "provavel_descontinuacao": "Provável descontinuação",
    "cliente_principal_parou": "Cliente principal parou",
}


# Mesma formatação do app.py. Não dá para importar de lá: importar o app executa o Streamlit.
def numero(valor: float, casas: int = 0) -> str:
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "§").replace(".", ",").replace("§", ".")


def pct(valor: float, casas: int = 0) -> str:
    return f"{numero(100 * valor, casas)}%"


@pytest.fixture(scope="module")
def execucao() -> dict:
    return json.loads((DADOS / "execucao.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ruptura() -> pd.DataFrame:
    return pd.read_csv(DADOS / "ruptura.csv", dtype={"stockcode": str})


@pytest.fixture(scope="module")
def backtest() -> pd.DataFrame:
    return pd.read_csv(DADOS / "backtest.csv").set_index(["agrupamento", "grupo"])


@pytest.fixture(scope="module")
def calibracao() -> pd.DataFrame:
    return pd.read_csv(DADOS / "calibracao.csv", parse_dates=["data_ref"])


@pytest.fixture(scope="module")
def comparacao() -> pd.DataFrame:
    return pd.read_csv(DADOS / "comparacao_regra.csv").set_index("regra")


@pytest.fixture(scope="module")
def readme() -> str:
    texto = (RAIZ / "README.md").read_text(encoding="utf-8")
    # Junta as linhas quebradas e tira as marcas de citação, para comparar frases inteiras.
    return " ".join(texto.replace("\n>", "\n").split())


def test_linhas_por_camada(execucao):
    for tabela, linhas in REFERENCIA["linhas"].items():
        assert execucao["linhas"][tabela] == linhas, tabela


def test_mediana_do_faturamento(ruptura):
    assert ruptura["corte_faturamento"].unique().tolist() == [REFERENCIA["mediana_faturamento"]]


def test_categorias(ruptura, backtest):
    for codigo, (produtos, taxa_semana, voltou_90d) in REFERENCIA["categorias"].items():
        grupo = ruptura[ruptura["categoria_acao"] == codigo]
        assert len(grupo) == produtos, codigo
        assert round(grupo["taxa_semana"].sum()) == taxa_semana, codigo
        assert backtest.loc[("categoria_acao", codigo), "taxa_voltou_90d"] == pytest.approx(voltou_90d, abs=5e-5)


def test_rotulo_antigo_marcava_descontinuacao(backtest):
    alertas, nao_voltou = REFERENCIA["rotulo_antigo"]
    antigo = backtest.loc[("medidor_ruptura", "ruptura")]
    assert antigo["produtos"] == alertas
    assert 1 - antigo["taxa_voltou_1_ano"] == pytest.approx(nao_voltou, abs=5e-5)


def test_calibracao_na_data_do_diagnostico(calibracao, execucao):
    na_data = calibracao[calibracao["data_ref"] == pd.Timestamp(execucao["data_ref"])].sort_values("faixa_ordem")
    assert na_data["taxa_voltou_90d"].tolist() == pytest.approx(REFERENCIA["calibracao_na_data_ref"], abs=5e-3)


def test_silencio_relativo_contra_o_baseline(comparacao):
    for regra, (precisao, dias) in REFERENCIA["comparacao"].items():
        assert comparacao.loc[regra, "alertas"] == REFERENCIA["rotulo_antigo"][0], regra
        assert comparacao.loc[regra, "precisao"] == pytest.approx(precisao, abs=5e-5), regra
        assert comparacao.loc[regra, "dias_ate_alertar_mediana"] == dias, regra


def test_par_do_grafico_explicativo():
    exemplo = pd.read_csv(DADOS / "exemplo_silencio.csv", dtype={"stockcode": str})
    assert dict(zip(exemplo["papel"], exemplo["stockcode"], strict=True)) == REFERENCIA["par_exemplo"]


def test_readme_bate_com_os_dados(readme, ruptura, backtest, calibracao, comparacao, execucao):
    """Cada frase do README com número, montada a partir dos dados com a formatação do app."""
    data_ref = pd.Timestamp(execucao["data_ref"])
    rp = ruptura[ruptura["categoria_acao"] == "ruptura_provavel"]
    descontinuacao = ruptura[ruptura["categoria_acao"] == "provavel_descontinuacao"]
    antigo = backtest.loc[("medidor_ruptura", "ruptura")]
    relativo, dias = comparacao.loc["silencio_relativo"], comparacao.loc["dias_parado"]
    na_data = calibracao[calibracao["data_ref"] == data_ref].sort_values("faixa_ordem")
    faixas = [pct(t) for t in na_data["taxa_voltou_90d"]]
    faixa_3_5 = calibracao[calibracao["faixa_ordem"] == 4]
    meio_do_ano = faixa_3_5.loc[faixa_3_5["data_ref"].dt.month.between(3, 11), "taxa_voltou_90d"]
    na_ref_3_5 = faixa_3_5.loc[faixa_3_5["data_ref"] == data_ref, "taxa_voltou_90d"].iloc[0]

    esperadas = [
        f"{len(rp)} produtos que vendiam com regularidade pararam de vender",
        f"vendiam £{numero(rp['taxa_semana'].sum())} por semana",
        f"Outros {len(descontinuacao)} provavelmente saíram de linha",
        f"Diagnóstico em {data_ref:%d/%m/%Y}",
        "voltaram a vender em 90 dias por faixa de silêncio relativo: " + ", ".join(faixas[:-1]) + f" e {faixas[-1]}",
        f"dos {int(antigo['produtos'])} produtos que ele marcava, {pct(1 - antigo['taxa_voltou_1_ano'])} nunca mais venderam",
        f'baseline "{dias["criterio"]}" tem precision de {pct(dias["precisao"], 1)}',
        f"e o silêncio relativo, de {pct(relativo['precisao'], 1)}",
        f"dispara com {numero(relativo['dias_ate_alertar_mediana'])} dias de silêncio (mediana), "
        f"contra {numero(dias['dias_ate_alertar_mediana'])} do baseline",
        f"avisa {numero(dias['dias_ate_alertar_mediana'] - relativo['dias_ate_alertar_mediana'])} dias antes",
        f"de {pct(meio_do_ano.min())} a {pct(meio_do_ano.max())} dos produtos voltam a vender em 90 dias",
        f"Em {data_ref:%d/%m/%Y}, só {pct(na_ref_3_5)}",
    ]
    for codigo, rotulo in ROTULOS.items():
        grupo = ruptura[ruptura["categoria_acao"] == codigo]
        taxas = backtest.loc[("categoria_acao", codigo)]
        esperadas.append(
            f"| {rotulo} | {len(grupo)} | £{numero(grupo['taxa_semana'].sum())} "
            f"| {pct(taxas['taxa_voltou_90d'])} | {pct(taxas['taxa_voltou_1_ano'])} |"
        )

    faltando = [frase for frase in esperadas if frase not in readme]
    assert not faltando, f"README divergente dos dados: {faltando}"
