-- Versão original (reconstruída em 27/09/2026 a partir do banco).
-- A bronze foi carregada manualmente a partir do CSV exportado pelo pandas. A carga criou uma
-- coluna customer_id vazia e manteve o dado real em "Customer ID", do tipo real.
CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE raw.bronze_retail (
    invoice       varchar(20),
    stockcode     varchar(20),
    description   varchar(255),
    quantity      integer,
    invoicedate   timestamp,
    price         numeric(10, 2),
    customer_id   varchar(20),
    country       varchar(100),
    "Customer ID" real
);
