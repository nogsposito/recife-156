import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

# The only relations the assistant may read: the gold star schema and the dashboard view
ALLOWED_TABLES = {"fact_tickets", "dim_service", "dim_neighborhood", "dim_date", "v_tickets"}
MAX_ROWS = 200

WRITE_NODES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Merge,
    exp.Create,
    exp.Drop,
    exp.Alter,
    exp.TruncateTable,
    exp.Command,
)
# Server functions that could sleep, read files, change settings or reach other servers
BLOCKED_FUNCTIONS = {
    "pg_sleep",
    "pg_read_file",
    "pg_read_binary_file",
    "pg_ls_dir",
    "lo_import",
    "lo_export",
    "dblink",
    "set_config",
    "pg_terminate_backend",
    "pg_cancel_backend",
}


class UnsafeQueryError(ValueError):
    pass


def _parse_single(sql: str) -> exp.Expression:
    try:
        statements = [s for s in sqlglot.parse(sql, read="postgres") if s is not None]
    except ParseError as error:
        raise UnsafeQueryError(f"SQL inválida: {error}") from error
    if len(statements) != 1:
        raise UnsafeQueryError("Envie exatamente um comando SQL.")
    return statements[0]


# Checks that the SQL is one read-only query over the allowed tables and returns it wrapped
# with a row limit. One extra row is fetched so the caller can tell the result was cut.
def validate_sql(sql: str, max_rows: int = MAX_ROWS) -> str:
    tree = _parse_single(sql)
    if not isinstance(tree, exp.Query):
        raise UnsafeQueryError("Só consultas SELECT são permitidas.")
    if any(isinstance(node, WRITE_NODES) for node in tree.walk()):
        raise UnsafeQueryError("A consulta contém um comando que altera dados.")

    cte_names = {cte.alias_or_name for cte in tree.find_all(exp.CTE)}
    for table in tree.find_all(exp.Table):
        schema = table.db.lower() if table.db else ""
        name = table.name.lower()
        if name in cte_names and not schema:
            continue
        if schema not in ("", "public") or name not in ALLOWED_TABLES:
            raise UnsafeQueryError(f"Tabela não permitida: {table.sql(dialect='postgres')}.")

    for function in tree.find_all(exp.Anonymous):
        if function.name.lower() in BLOCKED_FUNCTIONS:
            raise UnsafeQueryError(f"Função não permitida: {function.name}.")

    query = tree.sql(dialect="postgres")
    return f"SELECT * FROM ({query}) AS limited_result LIMIT {max_rows + 1}"
