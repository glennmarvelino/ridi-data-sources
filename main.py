import argparse
import urllib.error

from retrieval import search_chunks, split_text
from sources import load_source


def main():
	parser = argparse.ArgumentParser(
		description="Load web pages and data files, then search their contents."
	)
	parser.add_argument("sources", nargs="+", help="URLs or local file paths")
	parser.add_argument("--query", help="Keyword or phrase to search for")
	parser.add_argument(
		"--chunk-size",
		type=int,
		default=100,
		help="Words per searchable chunk (default: 100)",
	)
	args = parser.parse_args()

	if args.chunk_size < 1:
		parser.error("--chunk-size must be greater than zero")

	documents = []
	for source in args.sources:
		try:
			document = load_source(source)
		except (OSError, ValueError, RuntimeError, urllib.error.URLError) as error:
			print(f"Could not load {source}: {error}")
			continue

		if not document.content.strip():
			print(f"No extractable text found in {source}")
			continue
		documents.append(document)
		print(f"Loaded {document.title}: {len(document.content.split())} words")

	if not documents:
		print("No sources could be searched.")
		return 1

	query = args.query if args.query is not None else input("\nEnter a search term: ")
	if not query.strip():
		print("Search term cannot be empty.")
		return 1

	matches = []
	for document in documents:
		chunks = split_text(document.content, chunk_size=args.chunk_size)
		matches.extend((document, chunk) for chunk in search_chunks(chunks, query))

	if not matches:
		print("No matching chunks found.")
		return 0

	for number, (document, chunk) in enumerate(matches, start=1):
		print(f"\nMatch {number} - {document.title} ({document.source})")
		print(chunk)
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
