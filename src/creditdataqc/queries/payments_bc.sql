-- Query: payments_bc.sql
-- Descripción: Consulta datos de pagos y facturas desde Business Central (BC)
--
-- Tablas principales:
--   - CUST_LEDGER_ENTRY: Movimientos contables de clientes
--   - CUSTOMER: Datos maestros de clientes
--   - SALES_INVOICE_HEADER: Cabeceras de facturas
--   - SALES_CR_MEMO_HEADER: Cabeceras de notas de crédito
--
-- Parámetros esperados (inyectados por Python):
--   - {nif_list}: Lista de NIFs en formato SQL: 'NIF1','NIF2','NIF3'
--
-- IMPORTANTE: Este archivo contiene un placeholder {nif_list} que DEBE ser
-- reemplazado por Python antes de ejecutar la query.

SELECT  *
FROM (
    SELECT DISTINCT
        COALESCE(E.VAT_REGISTRATION_NO_, b.NIF)    AS "cif_nif",
        LEFT(C."DUE_DATE",10)                      AS "due_date",
        LEFT(b.POSTING_DATE,10)                     AS "posting_date",
        CAST(C."REMAINING_AMOUNT__LCY_STATS_" AS DECIMAL(16,2)) AS "remaining_amount"

    FROM  NEURON_PRO.BC_ESP.CUST_LEDGER_ENTRY  C
    JOIN  NEURON_PRO.BC_ESP.CUSTOMER           E
        ON C."CUSTOMER_NO_" = E.NO_

    LEFT JOIN (
        SELECT NO_ AS Factura,
            VAT_REGISTRATION_NO_ AS NIF,
            POSTING_DATE,
            DUE_DATE
        FROM NEURON_PRO.BC_ESP.SALES_INVOICE_HEADER
        UNION
        SELECT NO_,
            VAT_REGISTRATION_NO_,
            POSTING_DATE,
            DUE_DATE
        FROM NEURON_PRO.BC_ESP.SALES_CR_MEMO_HEADER
    ) b  ON b.Factura = C."DOCUMENT_NO_"
    WHERE b.NIF IN ({nif_list})
) sub
WHERE "remaining_amount" <> 0
