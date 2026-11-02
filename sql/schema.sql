-- Relational model of the 156 tickets. Recreated on every load (full refresh).

DROP TABLE IF EXISTS tickets;
DROP TABLE IF EXISTS services;
DROP TABLE IF EXISTS service_groups;
DROP TABLE IF EXISTS neighborhoods;

CREATE TABLE service_groups (
    group_code  integer PRIMARY KEY,
    group_name  text NOT NULL
);

CREATE TABLE services (
    service_code  integer PRIMARY KEY,
    service_name  text NOT NULL,
    group_code    integer NOT NULL REFERENCES service_groups (group_code)
);

-- RPA: Recife's six political-administrative regions
CREATE TABLE neighborhoods (
    neighborhood_id    integer PRIMARY KEY,
    neighborhood_name  text NOT NULL UNIQUE,
    rpa                smallint NOT NULL CHECK (rpa BETWEEN 1 AND 6)
);

CREATE TABLE tickets (
    ticket_id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    service_code         integer NOT NULL REFERENCES services (service_code),
    neighborhood_id      integer REFERENCES neighborhoods (neighborhood_id),
    street               text,
    street_number        text,
    opened_on            date NOT NULL,
    status               text NOT NULL,
    status_updated_on    date,
    -- For resolved tickets (status ATENDIDA) this is the resolution time
    days_to_last_update  integer GENERATED ALWAYS AS (status_updated_on - opened_on) STORED,
    latitude             double precision,
    longitude            double precision,
    source_year          smallint NOT NULL
);

COMMENT ON TABLE tickets IS 'One row per 156 request, with its latest known status';
COMMENT ON COLUMN tickets.source_year IS 'Yearly file the latest snapshot of the ticket came from';
