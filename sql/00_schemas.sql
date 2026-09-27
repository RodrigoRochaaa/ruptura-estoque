-- Camadas do pipeline. Os schemas antigos (raw e analytics) ficam intocados como linha de base.
CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;
CREATE SCHEMA IF NOT EXISTS meta;

-- A data do diagnóstico fica num lugar só; as outras consultas leem daqui em vez de repetir a data.
-- A coluna id impede uma segunda linha: a tabela tem sempre exatamente um valor vigente.
DROP TABLE IF EXISTS meta.parametros;
CREATE TABLE meta.parametros (
    id        boolean PRIMARY KEY DEFAULT true CHECK (id),
    data_ref  date    NOT NULL
);
INSERT INTO meta.parametros (data_ref) VALUES (DATE '2010-12-09');
