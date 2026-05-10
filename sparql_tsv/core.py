from urllib.request import Request, urlopen
import socket
from urllib.error import URLError
from urllib.parse import urlencode
from io import TextIOWrapper
import csv
from textwrap import dedent
import re
from time import sleep
import logging
from urllib.error import HTTPError
from typing import Optional, Any
from tempfile import NamedTemporaryFile
from os import fsync, unlink, rename
from pathlib import Path
from http.client import IncompleteRead


logger = logging.getLogger(__name__)
re_sp = re.compile(r"\s+")
re_qst = re.compile(r"^\?\s*")
re_cmt = re.compile(r"(^\s*$|\s*#.*$)", flags=re.MULTILINE)

ENDPOINT_PAGE_SIZE = {
    "https://query.wikidata.org/sparql": 100000
}


class SparqlTsvError(Exception):
    """Base exception class for SPARQL TSV errors.

    Attributes:
        code: Error code identifier.
        msg: Error message.
    """
    def __init__(self, code: int, msg: Any):
        """Initialize SparqlTsvError.

        Args:
            code: Error code identifier.
            msg: Error message or object to convert to string.
        """
        self.__code = code
        self.__msg = str(msg) if msg else None

    @property
    def code(self):
        return self.__code

    @property
    def msg(self):
        return self.__msg

    def __str__(self):
        return f"[{self.__code}] {self.__msg}"


class QueryEmptyError(SparqlTsvError):
    """Exception raised when a query is empty."""
    def __init__(self, query: Optional[str] = None):
        """Initialize QueryEmptyError.

        Args:
            query: Optional query string for context.
        """
        super().__init__(0, query or "Query empty")


class QueryTypeError(SparqlTsvError):
    """Exception raised when query has an invalid type."""
    def __init__(self, query: Any):
        """Initialize QueryTypeError.

        Args:
            query: The query object with invalid type.
        """
        super().__init__(1, f"{type(query)}, but str|Path expected")


class QueryFileError(SparqlTsvError):
    """Exception raised when a query file does not exist."""
    def __init__(self, file: str):
        """Initialize QueryFileError.

        Args:
            file: Path to the file that does not exist.
        """
        super().__init__(2, f"{file} not exist")


class QueryFileEmptyError(SparqlTsvError):
    """Exception raised when a query file is empty."""
    def __init__(self, file: str):
        """Initialize QueryFileEmptyError.

        Args:
            file: Path to the empty file.
        """
        super().__init__(1, f"{file} is empty")


def _get_content(file_or_content: str | Path):
    if not isinstance(file_or_content, (str, Path)):
        raise QueryTypeError(file_or_content)

    content = file_or_content
    if isinstance(file_or_content, Path):
        if not file_or_content.is_file():
            raise QueryFileError(file_or_content)
        content = file_or_content.read_text()

    content = content.strip()
    if len(content) > 0:
        return content
    if isinstance(file_or_content, Path):
        raise QueryFileEmptyError(file_or_content)

    raise QueryEmptyError()


def _parse(x: str):
    if not isinstance(x, str):
        raise ValueError(x)
    x = re_sp.sub(" ", x)
    x = x.strip()
    return x


def _parse_head(x: str):
    x = _parse(x)
    x = re_qst.sub("", x)
    return x


def _compact(query: str):
    if not isinstance(query, str):
        return ''
    lines: list[str] = []
    query = re_cmt.sub("", query)
    query = dedent(query).strip()
    for ln in query.split("\n"):
        ln = ln.rstrip()
        if len(ln):
            lines.append(ln)
    qr = "\n".join(lines).strip()
    return qr


def _getCode(e: Exception):
    if isinstance(e, HTTPError):
        return e.code
    if isinstance(e, URLError):
        if isinstance(e.reason, socket.error):
            return e.reason.errno
    if isinstance(e, URLError):
        return "UrlOpen"
    if isinstance(e, IncompleteRead):
        return "IncompleteRead"
    return 0


def _getPositive(x, default=None):
    if not isinstance(x, int):
        return default
    if x <= 0:
        return default
    return x


class SparqlTsv:
    """Client for querying SPARQL endpoints and downloading results as TSV.

    Provides functionality to execute SPARQL queries against a SPARQL endpoint
    and save results in Tab-Separated Values (TSV) format.
    """
    def __init__(
        self,
        endpoint: str,
        user_agent: str,
        wait_if_status={
            429: 120,
            500: 60,
            502: 60,
            503: 60,
            504: 60,
            101: 60,
            "IncompleteRead": 60,
        },
        max_retries=10,
        page_size: Optional[int] = None,
        max_page_size: Optional[int] = None,
    ):
        """Initialize SparqlTsv client.

        Args:
            endpoint: URL of the SPARQL endpoint.
            user_agent: User-Agent string for HTTP requests.
            wait_if_status: Dict mapping HTTP status codes to wait times in seconds.
                Default includes common server error codes and rate limit handling.
            max_retries: Maximum number of retry attempts for failed requests.
                Defaults to 10.
            page_size: Number of results per page. If None, auto-determined.
            max_page_size: Maximum allowed page size for the endpoint.
                If None, determined from endpoint defaults.
        """
        self.__headers = {
            "User-Agent": user_agent,
            "Accept": "text/tab-separated-values",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        self.__endpoint = endpoint
        self.__wait_if_status = wait_if_status
        self.__page_size = _getPositive(page_size)
        self.__max_page_size = _getPositive(
            max_page_size,
            ENDPOINT_PAGE_SIZE.get(endpoint, 1)
        )
        self.__max_retries = _getPositive(max_retries, 1)

    def dwn(self, query_or_file: str | Path, header: bool = False):
        """Download SPARQL query results as TSV file.

        Executes a SPARQL query and saves results to a TSV file. If a Path object
        is provided, creates a .tsv file next to the source file.

        Args:
            query_or_file: Either a SPARQL query string or path to a query file.
            header: If True, include header row with variable names in output.

        Returns:
            Path to the TSV file created/updated.
        """
        query = _get_content(query_or_file)
        tmp = self.__dwn(query, header=header)
        if not isinstance(query_or_file, Path):
            return tmp
        out = f"{query_or_file}.tsv"
        logger.debug(f"{tmp} -> {out}")
        rename(tmp, out)
        return out

    def __dwn(self, query: str, header: bool = False):
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".tsv",
            delete=False,
        ) as tmp:
            logger.debug(f"Writting in {tmp.name}")
            try:
                gen = self.query(query, header=header)
                head = next(gen, None)
                if head:
                    tmp.write("\t".join(head))
                    for r in gen:
                        tmp.write("\n" + "\t".join(r))
                tmp.flush()
                fsync(tmp.fileno())
            except Exception:
                unlink(tmp.name)
                raise
            return tmp.name

    def query(self, query_or_file: str, header: bool = False):
        """Execute a SPARQL query and yield results.

        Executes a SPARQL query against the endpoint and yields results as tuples
        of values. Results are paginated if necessary.

        Args:
            query_or_file: Either a SPARQL query string or path to a query file.
            header: If True, yield header (variable names) as first result.

        Yields:
            Tuples of values for each result row. First yield is header if requested.

        Raises:
            QueryEmptyError: If query is empty after parsing.
            SparqlTsvError: If results differ between pages or other SPARQL errors.
        """
        ori_query = _get_content(query_or_file)
        query = _compact(ori_query)
        if len(query) == 0:
            raise QueryEmptyError(ori_query)

        page = 0
        offset = 0
        total_count = 0
        main_head = None
        page_size = self.__page_size

        while True:
            page += 1
            tail = []
            if page_size:
                tail.append(f"LIMIT {page_size}")
            if offset:
                tail.append(f"OFFSET {offset}")
            if tail:
                p_query = query + "\n" + "\n".join(tail)
            else:
                p_query = str(query)
            reader = self.__yield_page(p_query)
            head = next(reader, None)
            if head is None:
                break
            if page == 1:
                main_head = head
                if header:
                    yield head
            elif main_head != head:
                raise SparqlTsvError(0, f"{main_head} != {head}")
            count = 0
            for row in reader:
                count += 1
                yield row
            total_count = total_count + count
            logger.debug(f"page={page} rows={count} {' '.join(tail)}".rstrip())
            max_size = max(count, self.__max_page_size)
            if self.__max_page_size < max_size:
                logger.debug(f"{self.__endpoint} max_page_size={max_size}")
                self.__max_page_size = max_size
            if count < (page_size or self.__max_page_size):
                break
            offset += count

        logger.debug(f"total_rows={total_count}")

    def __yield_page(self, query: str):
        max_retries = max(1, self.__max_retries)
        for attempt in range(1, max_retries+1):
            try:
                req = Request(
                    self.__endpoint,
                    data=urlencode({
                        "query": query
                    }).encode("utf-8"),
                    headers=self.__headers
                )
                with urlopen(req) as r:
                    with TextIOWrapper(r, encoding="utf-8") as text:
                        reader = csv.reader(text, delimiter="\t")
                        first_line = next(reader, None)
                        if first_line is not None:
                            head = tuple(map(_parse_head, first_line))
                            if len(head) == 0 or '' in head:
                                raise SparqlTsvError(0, head)
                            yield head
                            for row in reader:
                                val = tuple(map(_parse, row))
                                if any(x != '' for x in val):
                                    yield val
            except Exception as e:
                code = _getCode(e)
                wait = (self.__wait_if_status or {}).get(code, 0)
                if attempt < max_retries and wait > 0:
                    logger.warning(f"[{code}] attempt={attempt}/{max_retries} wait={wait}")
                    sleep(wait)
                    continue
                if code is not None:
                    logger.critical(f"HTTP ERROR {code}")
                logger.critical(query)
                raise
            break
