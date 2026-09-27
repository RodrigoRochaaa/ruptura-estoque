"""Teste de fumaça do app: roda o script inteiro, como o Streamlit faz a cada interação."""

from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

RAIZ = Path(__file__).resolve().parents[1]
APP = str(RAIZ / "app.py")


def rodar(**query_params) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=120)
    for chave, valor in query_params.items():
        at.query_params[chave] = valor
    return at.run()


def test_app_roda_sem_erros():
    at = rodar()
    assert not at.exception
    assert [aba.label for aba in at.tabs] == ["Esta semana", "Confiabilidade", "Metodologia"]
    assert len(at.get("plotly_chart")) >= 5


def test_filtro_com_todas_as_categorias():
    at = rodar()
    filtro = at.get("button_group")[0]
    filtro.set_value(["ruptura_provavel", "monitorar", "cliente_principal_parou", "sazonal", "provavel_descontinuacao"])
    at.run()
    assert not at.exception
    ruptura = pd.read_csv(RAIZ / "data" / "app" / "ruptura.csv", dtype={"stockcode": str})
    no_escopo = (ruptura["categoria_acao"] != "fora_do_escopo").sum()
    assert any(c.value.startswith(f"{no_escopo} produtos") for c in at.caption)


def test_link_abre_o_detalhe_do_produto():
    exemplo = pd.read_csv(RAIZ / "data" / "app" / "exemplo_silencio.csv", dtype={"stockcode": str})
    frequente = exemplo.loc[exemplo["papel"] == "frequente", "stockcode"].iloc[0]
    at = rodar(produto=frequente)
    assert not at.exception
    assert any("Depois do diagnóstico" in m.value for m in at.markdown)


def test_link_com_codigo_inexistente_avisa_sem_quebrar():
    at = rodar(produto="NAO-EXISTE")
    assert not at.exception
    assert at.warning
