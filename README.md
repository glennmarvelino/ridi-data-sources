# ridi-data-sources

Load information from web pages and local or remote data files, then search the
extracted text for matching chunks.

## Supported formats

- Website articles: HTML pages over HTTP or HTTPS
- Documents: PDF, plain text, and Markdown
- Machine-readable data: CSV, JSON, and XML

The loaders use Python's standard library except for PDF extraction, which uses
`pypdf`.

## Setup

```powershell
python -m pip install -r requirements.txt
```

## Search sources

Pass one or more URLs or local file paths. The program prompts for a search term
if `--query` is omitted.

```powershell
python main.py https://example.org/article.html data/population.csv report.pdf
python main.py data/dataset.json --query "population growth"
python main.py report.pdf --query emissions --chunk-size 75
```

Results include the source and matching text chunk so retrieved information can
be traced back to its origin. Search is currently case-insensitive keyword or
phrase matching; answering natural-language questions will need a later
retrieval and answer-generation step.

