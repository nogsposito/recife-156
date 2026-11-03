import pytest

from src.ai.sql_guard import MAX_ROWS, UnsafeQueryError, validate_sql


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT group_name, COUNT(*) FROM v_tickets GROUP BY group_name",
        "WITH open AS (SELECT * FROM fact_tickets WHERE is_open) SELECT COUNT(*) FROM open",
        "SELECT s.group_name FROM fact_tickets t JOIN dim_service s USING (service_code)",
        "SELECT 1 FROM public.dim_date UNION SELECT 2 FROM dim_date",
    ],
)
def test_read_only_queries_over_gold_tables_are_accepted_with_a_row_limit(sql):
    checked = validate_sql(sql)

    assert checked.startswith("SELECT * FROM (")
    assert checked.endswith(f"LIMIT {MAX_ROWS + 1}")


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM fact_tickets",
        "UPDATE fact_tickets SET status = 'ATENDIDA'",
        "INSERT INTO dim_date (date_key) VALUES ('2030-01-01')",
        "DROP TABLE fact_tickets",
        "CREATE TABLE copy AS SELECT * FROM fact_tickets",
        "GRANT ALL ON fact_tickets TO PUBLIC",
        "COPY fact_tickets TO '/tmp/out.csv'",
    ],
)
def test_commands_that_change_anything_are_rejected(sql):
    with pytest.raises(UnsafeQueryError):
        validate_sql(sql)


def test_multiple_statements_are_rejected_even_if_the_first_is_a_select():
    with pytest.raises(UnsafeQueryError, match="exatamente um"):
        validate_sql("SELECT 1 FROM dim_date; DROP TABLE fact_tickets")


def test_a_data_modifying_cte_is_rejected():
    with pytest.raises(UnsafeQueryError):
        validate_sql("WITH gone AS (DELETE FROM fact_tickets RETURNING *) SELECT * FROM gone")


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM ops.pipeline_runs",
        "SELECT rolname FROM pg_roles",
        "SELECT * FROM information_schema.tables",
    ],
)
def test_tables_outside_the_gold_layer_are_rejected(sql):
    with pytest.raises(UnsafeQueryError, match="Tabela não permitida"):
        validate_sql(sql)


def test_dangerous_functions_are_rejected():
    with pytest.raises(UnsafeQueryError, match="pg_sleep"):
        validate_sql("SELECT pg_sleep(60) FROM dim_date")
