-- Gold layer: star schema of the 156 tickets. Recreated on every load (full refresh), which
-- keeps the load idempotent: the same silver files always produce the same tables.

DROP VIEW IF EXISTS v_tickets;
DROP TABLE IF EXISTS fact_tickets;
DROP TABLE IF EXISTS dim_service;
DROP TABLE IF EXISTS dim_neighborhood;
DROP TABLE IF EXISTS dim_date;
-- Tables of the earlier relational model, removed when an old database is upgraded
DROP TABLE IF EXISTS tickets, services, service_groups, neighborhoods, daily_weather;

CREATE TABLE dim_service (
    service_code  integer PRIMARY KEY,
    service_name  text NOT NULL,
    group_code    integer NOT NULL,
    group_name    text NOT NULL
);

-- RPA: Recife's six political-administrative regions
CREATE TABLE dim_neighborhood (
    neighborhood_id    integer PRIMARY KEY,
    neighborhood_name  text NOT NULL UNIQUE,
    rpa                smallint NOT NULL CHECK (rpa BETWEEN 1 AND 6)
);

-- One row per calendar day, with that day's weather in Recife (Open-Meteo)
CREATE TABLE dim_date (
    date_key          date PRIMARY KEY,
    year              smallint NOT NULL,
    month             smallint NOT NULL,
    day_of_week       smallint NOT NULL CHECK (day_of_week BETWEEN 1 AND 7),
    is_weekend        boolean NOT NULL,
    precipitation_mm  real,
    temp_max_c        real,
    temp_min_c        real,
    temp_mean_c       real
);

CREATE TABLE fact_tickets (
    ticket_id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    service_code         integer NOT NULL REFERENCES dim_service (service_code),
    neighborhood_id      integer REFERENCES dim_neighborhood (neighborhood_id),
    opened_on            date NOT NULL REFERENCES dim_date (date_key),
    status               text NOT NULL,
    status_updated_on    date,
    is_open              boolean GENERATED ALWAYS AS (status <> 'ATENDIDA') STORED,
    -- For resolved tickets this is the resolution time
    days_to_last_update  integer GENERATED ALWAYS AS (status_updated_on - opened_on) STORED,
    street               text,
    street_number        text,
    latitude             double precision,
    longitude            double precision,
    source_year          smallint NOT NULL
);

COMMENT ON TABLE fact_tickets IS 'One row per 156 request, with its latest known status';
COMMENT ON COLUMN fact_tickets.source_year IS 'Yearly file the latest snapshot came from';

-- Tickets with their service, group and neighborhood, as read by the dashboard
CREATE VIEW v_tickets AS
SELECT
    t.ticket_id,
    t.opened_on,
    t.status,
    t.status_updated_on,
    t.days_to_last_update,
    t.is_open,
    s.service_name,
    s.group_name,
    n.neighborhood_name,
    n.rpa
FROM fact_tickets AS t
JOIN dim_service AS s USING (service_code)
LEFT JOIN dim_neighborhood AS n USING (neighborhood_id);
