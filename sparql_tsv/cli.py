"""Command-line interface for sparql-tsv."""

import argparse
import logging
import sys
from pathlib import Path
from .core import SparqlTsv
from . import __version__


def main():
    DEF_ENDPOINT = 'https://query.wikidata.org/sparql'
    DEF_USER_AGENT = 'python3/sparql-tsv'
    parser = argparse.ArgumentParser(
        description='Query SPARQL endpoints and download results as TSV files',
    )
    parser.add_argument(
        '--endpoint',
        type=str,
        default=DEF_ENDPOINT,
        help=f'SPARQL endpoint URL (default: {DEF_ENDPOINT})'
    )
    parser.add_argument(
        '--user-agent',
        type=str,
        default=DEF_USER_AGENT,
        help=f'User-Agent string for HTTP requests (default: {DEF_USER_AGENT})'
    )
    parser.add_argument(
        '--max-retries',
        type=int,
        default=3,
        help='Maximum number of retries for failed requests (default: 3)'
    )
    parser.add_argument(
        '--page-size',
        type=int,
        help='Number of results per page (default: auto)'
    )
    parser.add_argument(
        '--header',
        action='store_true',
        help='Include header row in output'
    )
    parser.add_argument(
        '--version',
        action='version',
        version='%(prog)s '+__version__
    )
    parser.add_argument(
        '-v',
        '--verbose',
        action='count',
        default=0,
        help='Increase verbosity'
    )
    parser.add_argument(
        'sparql',
        type=str,
        nargs='+',
        help='SPARQL query files to execute'
    )

    args = parser.parse_args()

    log_level, log_format = getLevel(args.verbose)

    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt="%H:%M:%S"
    )

    client = SparqlTsv(
        user_agent=args.user_agent,
        endpoint=args.endpoint,
        max_retries=args.max_retries,
        page_size=args.page_size,
    )

    success = True
    for f in map(Path, args.sparql):
        if dwn(client, f, header=args.header) is False:
            success = False

    sys.exit(0 if success else 1)


def getLevel(v: int):
    if v == 0:
        return logging.WARNING, "%(levelname)s %(message)s"
    if v == 1:
        return logging.INFO, "%(asctime)s %(levelname)s %(message)s"
    return logging.DEBUG, "%(asctime)s %(levelname)s %(message)s"


def dwn(client: SparqlTsv, f: Path, *args, **kwargs):
    if not f.is_file():
        print(f"[KO] {f} is not a file", file=sys.stderr)
        return False
    try:
        out = client.dwn(f, *args, **kwargs)
        print(f"[OK] {out}")
        return True
    except Exception as e:
        print(f"[KO] {f}: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    main()
