import csv
import io
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse


@dataclass
class SourceDocument:
	source: str
	title: str
	content: str


class _HTMLTextParser(HTMLParser):
	def __init__(self):
		super().__init__()
		self.parts = []
		self.title_parts = []
		self._in_title = False
		self._skip_depth = 0

	def handle_starttag(self, tag, attrs):
		if tag in {"script", "style", "noscript"}:
			self._skip_depth += 1
		elif tag == "title":
			self._in_title = True

	def handle_endtag(self, tag):
		if tag in {"script", "style", "noscript"} and self._skip_depth:
			self._skip_depth -= 1
		elif tag == "title":
			self._in_title = False
		elif tag in {"p", "div", "br", "li", "h1", "h2", "h3", "tr"}:
			self.parts.append("\n")

	def handle_data(self, data):
		if self._in_title:
			self.title_parts.append(data)
		if not self._skip_depth:
			self.parts.append(data)


def _format_for(source, content_type=""):
	path = urlparse(str(source)).path.lower()
	extension = Path(path).suffix
	mime = content_type.lower().split(";", 1)[0].strip()

	if extension == ".pdf" or mime == "application/pdf":
		return "pdf"
	if extension in {".html", ".htm"} or mime == "text/html":
		return "html"
	if extension == ".csv" or mime in {"text/csv", "application/csv"}:
		return "csv"
	if extension == ".json" or mime == "application/json" or mime.endswith("+json"):
		return "json"
	if extension == ".xml" or mime in {"application/xml", "text/xml"} or mime.endswith("+xml"):
		return "xml"
	if extension in {".txt", ".md"} or mime.startswith("text/"):
		return "text"
	raise ValueError(f"Unsupported source format: {source}")


def _decode(data, content_type=""):
	match = re.search(r"charset=([\w.-]+)", content_type, re.IGNORECASE)
	encoding = match.group(1).strip(" '\"\"") if match else "utf-8-sig"
	try:
		return data.decode(encoding)
	except (LookupError, UnicodeDecodeError):
		return data.decode("utf-8", errors="replace")


def _html_document(text):
	parser = _HTMLTextParser()
	parser.feed(text)
	title = " ".join(" ".join(parser.title_parts).split())
	content = " ".join(" ".join(parser.parts).split())
	return title, content


def _csv_text(text):
	rows = csv.DictReader(io.StringIO(text))
	lines = []
	for row_number, row in enumerate(rows, start=1):
		values = [f"{key}: {value}" for key, value in row.items() if value]
		lines.append(f"Row {row_number}: " + "; ".join(values))
	return "\n".join(lines)


def _extract_content(source, data, content_type=""):
	source_format = _format_for(source, content_type)
	if source_format == "pdf":
		try:
			from pypdf import PdfReader
		except ImportError as error:
			raise RuntimeError("PDF support requires pypdf. Install it with: pip install -r requirements.txt") from error
		reader = PdfReader(io.BytesIO(data))
		return "\n".join(page.extract_text() or "" for page in reader.pages), ""

	text = _decode(data, content_type)
	if source_format == "html":
		title, content = _html_document(text)
		return content, title
	if source_format == "csv":
		return _csv_text(text), ""
	if source_format == "json":
		return json.dumps(json.loads(text), ensure_ascii=False, indent=2), ""
	if source_format == "xml":
		return ET.tostring(ET.fromstring(text), encoding="unicode"), ""
	return text, ""


def load_source(source, timeout=30):
	"""Load a URL or local file and normalize its contents into searchable text."""
	source = str(source)
	parsed = urlparse(source)

	if parsed.scheme in {"http", "https"}:
		request = urllib.request.Request(source, headers={"User-Agent": "ridi-data-sources/1.0"})
		with urllib.request.urlopen(request, timeout=timeout) as response:
			data = response.read()
			content_type = response.headers.get("Content-Type", "")
		title = unquote(Path(parsed.path).name) or parsed.netloc
	elif parsed.scheme and not Path(source).drive:
		raise ValueError(f"Unsupported URL scheme: {parsed.scheme}")
	else:
		path = Path(source)
		data = path.read_bytes()
		content_type = ""
		title = path.name

	content, extracted_title = _extract_content(source, data, content_type)
	return SourceDocument(source=source, title=extracted_title or title, content=content)


def load_sources(sources, timeout=30):
	"""Load multiple URLs or paths, preserving the source of each document."""
	return [load_source(source, timeout=timeout) for source in sources]
