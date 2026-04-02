# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

"""Generic entity fetch helpers for querying DB tables by column and operator."""

import logging
from utils.db.connection import get_connection


def fetch_entities_by(
    table_name,
    column_name,
    operator,
    values,
    return_ids_only=False,
    blocklist_clause=None,
    logger=None,
):
    """
    General-purpose fetch for entities from a table by column and operator.
    - table_name: str, e.g. 'tracks'
    - column_name: str, e.g. 'id'
    - operator: str, '=', 'IN', etc.
    - values: single value or list of values
    - return_ids_only: if True, return only the id column; else, return all columns
    - blocklist_clause: optional SQL predicate appended with AND (e.g. "COALESCE(blocklisted, 0) = 0")
    Returns a list of dicts (all columns) or a list of ids (if return_ids_only).
    """
    norm_operator = _normalize_operator(operator)
    if logger:
        logger.debug(
            f"Query database for table_name={table_name}, column_name={column_name}, "
            f"operator={norm_operator}, values={values}, return_ids_only={return_ids_only}, "
            f"blocklist_clause={blocklist_clause}"
        )
    if not table_name or not column_name or not norm_operator or values is None:
        return []
    if norm_operator == 'IN':
        if not isinstance(values, (list, tuple, set)) or not values:
            return []
        placeholders = ','.join('?' * len(values))
        where_clause = f"{column_name} IN ({placeholders})"
        params = list(values)
    else:
        where_clause = f"{column_name} {norm_operator} ?"
        params = [values]
    select_cols = 'id' if return_ids_only else '*'
    query = f"SELECT {select_cols} FROM {table_name} WHERE {where_clause}"
    if blocklist_clause:
        query = f"{query} AND {blocklist_clause}"
    try:
        with get_connection(logger) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            if return_ids_only:
                result = [row['id'] for row in rows]
                if logger:
                    logger.debug(f"Returning IDs: {result[:5]}{'...' if len(result) > 5 else ''}")
            else:
                result = [dict(row) for row in rows]
                if logger and logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"Returning dict. Sample: {result[0] if result else None}")
            if logger and result:
                logger.debug(f"Fetched {len(result)} rows from {table_name} where {column_name} {operator} {values}.")
            return result
    except Exception as e:
        if logger:
            logger.error(f"DB Error: Failed to fetch from {table_name} by {column_name} {operator}: {e}")
        return []


def _normalize_operator(operator):
    """Maps common aliases to standard SQL operators."""
    if not operator:
        return '='
    op = operator.strip().upper()
    aliases = {
        'EQ': '=',
        'EQUALS': '=',
        'IS': '=',
        'NE': '!=',
        'NOT': '!=',
        'NEQ': '!=',
        'GT': '>',
        'LT': '<',
        'GTE': '>=',
        'GE': '>=',
        'LTE': '<=',
        'LE': '<=',
        'IN': 'IN',
        'NOT IN': 'NOT IN',
        'LIKE': 'LIKE',
        'ILIKE': 'LIKE',  # SQLite doesn't support ILIKE
    }
    return aliases.get(op, op)
