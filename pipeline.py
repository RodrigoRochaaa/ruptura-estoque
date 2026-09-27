"""Pipeline completo: Excel → bronze → silver → gold → checks → arquivos do app.

    python pipeline.py              # reaproveita data/raw/bronze_retail.csv, se existir
    python pipeline.py --extrair    # relê o Excel (leva alguns minutos)

Requer DATABASE_URL no ambiente ou num arquivo .env na raiz (ver .env.example).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import psycopg2

RAIZ = Path(__file__).resolve().parent
XLSX = RAIZ / "data" / "raw" / "online_retail_II.xlsx"
BRONZE_CSV = RAIZ / "data" / "raw" / "bronze_retail.csv"
PASTA_SQL = RAIZ / "sql"
PASTA_APP = RAIZ / "data" / "app"
ABAS = ["Year 2009-2010", "Year 2010-2011"]
COLUNAS_BRONZE = "invoice, stockcode, description, quantity, invoicedate, price, customer_id, country, aba"
TABELAS_CONTADAS = [
    "bronze.retail",
    "silver.vendas",
    "silver.produto",
    "silver.vendas_dia",
    "silver.features",
    "gold.ruptura",
    "gold.snapshots",
    "gold.calibracao",
    "gold.retorno_produto",
]


def carregar_env() -> None:
    """Lê o .env da raiz sem sobrescrever o que já estiver definido no ambiente."""
    arquivo = RAIZ / ".env"
    if not arquivo.exists():
        return
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        if "=" in linha and not linha.lstrip().startswith("#"):
            chave, valor = linha.split("=", 1)
            os.environ.setdefault(chave.strip(), valor.strip())


def extrair_bronze() -> None:
    """Lê as duas abas e exporta sem transformar; só acrescenta a aba de origem."""
    print("lendo o Excel (as duas abas)...")
    abas = pd.read_excel(
        XLSX,
        sheet_name=ABAS,
        # Identificadores não são números: sem isso o Customer ID vira 13085.0.
        dtype={"Invoice": str, "StockCode": str, "Customer ID": str},
    )
    bronze = pd.concat([df.assign(aba=nome) for nome, df in abas.items()], ignore_index=True)
    bronze.to_csv(BRONZE_CSV, index=False)
    print(f"bronze exportada: {len(bronze):,} linhas")


def executar(conexao, sql: str) -> list[tuple]:
    with conexao.cursor() as cursor:
        cursor.execute(sql)
        linhas = cursor.fetchall() if cursor.description else []
    conexao.commit()
    return linhas


def carregar_bronze(conexao) -> None:
    with conexao.cursor() as cursor, BRONZE_CSV.open(encoding="utf-8") as arquivo:
        cursor.copy_expert(f"COPY bronze.retail ({COLUNAS_BRONZE}) FROM STDIN WITH (FORMAT csv, HEADER true)", arquivo)
    conexao.commit()


def rodar_checks(conexao) -> list[dict]:
    resultados = []
    for arquivo in sorted((PASTA_SQL / "checks").glob("*.sql")):
        falhas = executar(conexao, arquivo.read_text(encoding="utf-8"))
        resultados.append({"check": arquivo.stem, "ok": not falhas, "linhas_com_falha": len(falhas)})
        print(f"  {'ok   ' if not falhas else 'FALHA'} {arquivo.stem}" + (f" ({len(falhas)})" if falhas else ""))
    return resultados


def exportar_app(conexao) -> None:
    """Cada arquivo em sql/export vira um CSV em data/app, que é tudo o que o app lê."""
    PASTA_APP.mkdir(parents=True, exist_ok=True)
    for arquivo in sorted((PASTA_SQL / "export").glob("*.sql")):
        consulta = arquivo.read_text(encoding="utf-8").strip().rstrip(";")
        destino = PASTA_APP / f"{arquivo.stem}.csv"
        with conexao.cursor() as cursor, destino.open("w", encoding="utf-8", newline="") as saida:
            cursor.copy_expert(f"COPY ({consulta}) TO STDOUT WITH (FORMAT csv, HEADER true)", saida)
        print(f"  {destino.relative_to(RAIZ).as_posix()}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--extrair", action="store_true", help="relê o Excel mesmo que o CSV da bronze exista")
    args = parser.parse_args()

    carregar_env()
    inicio = time.perf_counter()
    if args.extrair or not BRONZE_CSV.exists():
        extrair_bronze()

    conexao = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        for arquivo in sorted(PASTA_SQL.glob("[0-9][0-9]_*.sql")):
            print(f"executando {arquivo.name}")
            executar(conexao, arquivo.read_text(encoding="utf-8"))
            if arquivo.name.startswith("01_"):
                carregar_bronze(conexao)

        print("checks")
        checks = rodar_checks(conexao)
        if not all(c["ok"] for c in checks):
            sys.exit("checks falharam: os arquivos do app não foram atualizados")

        print("exportando os arquivos do app")
        exportar_app(conexao)
        data_ref = executar(conexao, "SELECT data_ref FROM meta.parametros")[0][0]
        linhas = {t: executar(conexao, f"SELECT COUNT(*) FROM {t}")[0][0] for t in TABELAS_CONTADAS}
    finally:
        conexao.close()

    execucao = {
        "executado_em": datetime.now(UTC).isoformat(timespec="seconds"),
        "data_ref": data_ref.isoformat(),
        "duracao_segundos": round(time.perf_counter() - inicio, 1),
        "linhas": linhas,
        "checks": checks,
    }
    (PASTA_APP / "execucao.json").write_text(
        json.dumps(execucao, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"pipeline ok em {execucao['duracao_segundos']} s")


if __name__ == "__main__":
    main()
