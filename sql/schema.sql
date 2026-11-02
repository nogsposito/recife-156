-- Relational model of the 156 tickets. Recreated on every load (full refresh).

DROP VIEW IF EXISTS v_tickets;
DROP TABLE IF EXISTS tickets;
DROP TABLE IF EXISTS daily_weather;
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

-- Daily weather in Recife from Open-Meteo, one row per day of the ticket period
CREATE TABLE daily_weather (
    weather_date      date PRIMARY KEY,
    precipitation_mm  real,
    temp_max_c        real,
    temp_min_c        real,
    temp_mean_c       real
);

CREATE TABLE tickets (
    ticket_id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    service_code         integer NOT NULL REFERENCES services (service_code),
    neighborhood_id      integer REFERENCES neighborhoods (neighborhood_id),
    street               text,
    street_number        text,
    opened_on            date NOT NULL REFERENCES daily_weather (weather_date),
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

-- Tickets with their service, group and neighborhood, as read by the dashboard
CREATE VIEW v_tickets AS
SELECT
    t.ticket_id,
    t.opened_on,
    t.status,
    t.status_updated_on,
    t.days_to_last_update,
    t.status <> 'ATENDIDA' AS is_open,
    s.service_name,
    g.group_name,
    n.neighborhood_name,
    n.rpa
FROM tickets AS t
JOIN services AS s USING (service_code)
JOIN service_groups AS g USING (group_code)
LEFT JOIN neighborhoods AS n USING (neighborhood_id);
