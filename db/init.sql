-- Seed mínimo para a API ter o que consultar.
CREATE TABLE IF NOT EXISTS service_checks (
    id         serial PRIMARY KEY,
    checked_at timestamptz NOT NULL DEFAULT now(),
    note       text        NOT NULL
);

INSERT INTO service_checks (note)
VALUES ('mini-noc inicializado');
