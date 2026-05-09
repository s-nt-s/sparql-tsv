"""SPARQL TSV - Query SPARQL endpoints and download results as TSV files.

This package provides a client library and CLI tool to execute SPARQL queries
against any SPARQL endpoint and download results in Tab-Separated Values (TSV) format.

Usage:
    from sparql_tsv import SparqlTsv

    client = SparqlTsv(
        endpoint='https://query.wikidata.org/sparql',
        user_agent='MyApp/1.0'
    )
    results = client.dwn('query.sparql', header=True)
"""
from importlib.metadata import version, PackageNotFoundError


def _get_version(name: str):
    try:
        return version(name)
    except PackageNotFoundError:
        return '?.?.?'


__version__ = _get_version("sparql-tsv")


from .core import (
    SparqlTsv,
    SparqlTsvError,
    QueryEmptyError,
    QueryTypeError,
    QueryFileError,
    QueryFileEmptyError
)

__all__ = [
    "SparqlTsv",
    "SparqlTsvError",
    "QueryEmptyError",
    "QueryTypeError",
    "QueryFileError",
    "QueryFileEmptyError"
]
