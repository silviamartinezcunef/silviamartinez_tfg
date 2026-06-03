"""
Query loader module for creditdataqc.

This module provides utilities to load SQL queries from external .sql files,
improving code maintainability and enabling syntax highlighting.
"""

from pathlib import Path
from typing import Dict


def load_query(query_name: str) -> str:
    """
    Load a SQL query from the queries/ directory.

    Args:
        query_name: Name of the query file (without .sql extension)

    Returns:
        SQL query as string

    Raises:
        FileNotFoundError: If the query file doesn't exist

    Example:
        >>> query = load_query('rating_features')
        >>> df = pd.read_sql(query, conn)
    """
    query_path = Path(__file__).parent / f"{query_name}.sql"

    if not query_path.exists():
        raise FileNotFoundError(
            f"Query file not found: {query_path}\n"
            f"Available queries: {list_available_queries()}"
        )

    with open(query_path, 'r', encoding='utf-8') as f:
        return f.read()


def load_query_with_params(query_name: str, params: Dict[str, str]) -> str:
    """
    Load a SQL query and replace placeholders with parameters.

    Placeholders in SQL files use format: {param_name}

    Args:
        query_name: Name of the query file (without .sql extension)
        params: Dictionary with parameter replacements

    Returns:
        SQL query with parameters replaced

    Example:
        >>> query = load_query_with_params(
        ...     'payments_bc',
        ...     {'nif_list': "'A12345678','B87654321'"}
        ... )
    """
    query = load_query(query_name)

    for param_name, param_value in params.items():
        placeholder = f"{{{param_name}}}"
        query = query.replace(placeholder, str(param_value))

    return query


def list_available_queries() -> list:
    """
    List all available SQL query files.

    Returns:
        List of query names (without .sql extension)
    """
    queries_dir = Path(__file__).parent
    return [
        f.stem for f in queries_dir.glob("*.sql")
    ]


# Public API
__all__ = [
    'load_query',
    'load_query_with_params',
    'list_available_queries'
]
