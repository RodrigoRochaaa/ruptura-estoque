"""Contrato dos arquivos que o pipeline exporta e o app lê. Roda sem banco."""

import json
from pathlib import Path

import pandas as pd
import pytest

DADOS = Path(__file__).resolve().parents[1] / "data" / "app"
CATEGORIAS = {
    "fora_do_escopo",
    "ruptura_provavel",
    "monitorar",
    "cliente_principal_parou",
    "sazonal",
    "provavel_descontinuacao",
}


@pytest.fixture(scope="module")
def execucao() -> dict:
    return json.loads((DADOS / "execucao.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ruptura() -> pd.DataFrame:
    return pd.read_csv(DADOS / "ruptura.csv", dtype={"stockcode": str}, parse_dates=["ultima_venda"])


def test_pipeline_passou_nos_checks(execucao):
    assert execucao["checks"], "a execução não registrou checks"
    assert all(c["ok"] for c in execucao["checks"])


def test_um_produto_por_linha_e_categoria_conhecida(ruptura):
    assert ruptura["stockcode"].is_unique
    assert set(ruptura["categoria_acao"]) <= CATEGORIAS
    assert (ruptura["stockcode"] == ruptura["stockcode"].str.upper()).all()


def test_diagnostico_nao_ve_o_futuro(ruptura, execucao):
    assert ruptura["ultima_venda"].max() <= pd.Timestamp(execucao["data_ref"])


def test_produtos_no_escopo_tem_impacto(ruptura):
    no_escopo = ruptura[ruptura["categoria_acao"] != "fora_do_escopo"]
    assert len(no_escopo) > 0
    assert no_escopo["taxa_semana"].notna().all()
    # O CSV arredonda para 2 casas: 2,004 vira 2,00, por isso >= em vez de >.
    assert (no_escopo["silencio_relativo"] >= 2).all()
    assert no_escopo["acima_da_mediana"].all()


def test_serie_semanal_cobre_quem_o_app_detalha(ruptura):
    semanas = pd.read_csv(DADOS / "vendas_semana.csv", dtype={"stockcode": str})
    exemplo = pd.read_csv(DADOS / "exemplo_silencio.csv", dtype={"stockcode": str})
    detalhados = set(ruptura.loc[ruptura["categoria_acao"] != "fora_do_escopo", "stockcode"]) | set(
        exemplo["stockcode"]
    )
    assert set(semanas["stockcode"]) <= detalhados
    assert set(exemplo["papel"]) == {"frequente", "ocasional"}
    assert set(exemplo["stockcode"]) <= set(ruptura["stockcode"])


def test_taxas_da_validacao_sao_proporcoes():
    calibracao = pd.read_csv(DADOS / "calibracao.csv")
    backtest = pd.read_csv(DADOS / "backtest.csv")
    taxas = [calibracao["taxa_voltou_90d"], calibracao["taxa_voltou_365d"].dropna()]
    taxas += [backtest[c] for c in ("taxa_voltou_30d", "taxa_voltou_90d", "taxa_voltou_1_ano")]
    for serie in taxas:
        assert serie.between(0, 1).all(), serie.name
