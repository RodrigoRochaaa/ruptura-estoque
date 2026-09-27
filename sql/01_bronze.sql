-- Bronze: cópia fiel das duas abas do Excel. Identificadores ficam como texto (não são números)
-- e o preço fica sem arredondar. A carga (COPY) é feita pelo pipeline.py logo depois deste arquivo.
DROP TABLE IF EXISTS bronze.retail;
CREATE TABLE bronze.retail (
    invoice      text,
    stockcode    text,
    description  text,
    quantity     integer,
    invoicedate  timestamp,
    price        numeric,
    customer_id  text,
    country      text,
    -- As abas se sobrepõem entre 01 e 09/12/2010; a silver precisa saber de onde veio cada linha.
    aba          text NOT NULL
);
