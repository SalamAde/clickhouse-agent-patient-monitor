"""Thin ClickHouse helpers shared by every demo."""
import os
import time

import clickhouse_connect
from dotenv import load_dotenv

load_dotenv()


def get_client():
    # secure=True for ClickHouse Cloud (port 8443); False for local docker (8123)
    secure = os.getenv("CLICKHOUSE_SECURE", "false").lower() in ("1", "true", "yes")
    return clickhouse_connect.get_client(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        port=int(os.getenv("CLICKHOUSE_PORT", "8443" if secure else "8123")),
        username=os.getenv("CLICKHOUSE_USER", "default"),
        password=os.getenv("CLICKHOUSE_PASSWORD", ""),
        database=os.getenv("CLICKHOUSE_DATABASE", "demo"),
        secure=secure,
    )


def run_query(client, sql):
    """Run a query and return (rows, column_names, elapsed_ms)."""
    start = time.perf_counter()
    result = client.query(sql)
    elapsed_ms = (time.perf_counter() - start) * 1000
    return result.result_rows, result.column_names, elapsed_ms


def exec_script(client, sql_script):
    """Execute a multi-statement .sql file (split on ';')."""
    for statement in sql_script.split(";"):
        statement = statement.strip()
        if statement:
            client.command(statement)
