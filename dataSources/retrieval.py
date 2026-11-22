def split_text(text, chunk_size=100):
    words = text.split()
    chunks = []

    for start in range(0, len(words), chunk_size):
        chunk = " ".join(words[start:start + chunk_size])
        chunks.append(chunk)

    return chunks

def search_chunks(chunks, keyword):
    results = []

    for chunk in chunks:
        if keyword.lower() in chunk.lower():
            results.append(chunk)

    return results

if __name__ == "__main__":
    sample_text = (
        "LED lighting reduces energy consumption. "
        "Smart sensors adjust brightness automatically. "
        "Recycling materials can reduce production waste. "
    )

    results = split_text(sample_text, chunk_size=10)

    for number, chunk in enumerate(results, start=1):
        print(f"Chunk {number}: {chunk}")

    keyword = input("\nEnter a keyword: ")
    matches = search_chunks(results, keyword)

    if matches:
        for match in matches:
            print(f"Found: {match}")
    else:
        print("No matching chunks found.")