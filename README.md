# SPARQL TSV

Query SPARQL endpoints and download results as TSV files.

## Installation

```
$ pip install sparql-tsv

$ sparql-tsv --help
usage: sparql-tsv [-h] [--endpoint ENDPOINT] [--user-agent USER_AGENT] [--max-retries MAX_RETRIES] [--page-size PAGE_SIZE] [--header] [--version] [-v] sparql [sparql ...]

Query SPARQL endpoints and download results as TSV files

positional arguments:
  sparql                SPARQL query files to execute

options:
  -h, --help            show this help message and exit
  --endpoint ENDPOINT   SPARQL endpoint URL (default: https://query.wikidata.org/sparql)
  --user-agent USER_AGENT
                        User-Agent string for HTTP requests (default: Python urllib for sparql-tsv)
  --max-retries MAX_RETRIES
                        Maximum number of retries for failed requests (default: 3)
  --page-size PAGE_SIZE
                        Number of results per page (default: auto)
  --header              Include header row in output
  --version             show program's version number and exit
  -v, --verbose         Increase verbosity
```