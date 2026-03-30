from langchain_text_splitters import RecursiveCharacterTextSplitter


def chunk_document_text(raw_text: str) -> list[dict]:
    """
    Parent-child chunking strategy.
    - Parent (2000 tokens, 300 overlap): large semantic blocks for LLM context.
      Keeps full definitions, theorems, and explanations intact.
    - Child (600 tokens, 150 overlap): smaller precise chunks for embedding & retrieval.
      Overlap increased to 150 so definitions split across boundaries are still found.
    """
    parent_splitter = RecursiveCharacterTextSplitter(
        chunk_size=2000,
        chunk_overlap=300,
        separators=["\n\n", "\n", ".", " "]
    )

    child_splitter = RecursiveCharacterTextSplitter(
        chunk_size=600,
        chunk_overlap=150,
        separators=["\n\n", "\n", ".", " "]
    )

    parent_chunks = parent_splitter.split_text(raw_text)

    result = []
    for parent_idx, parent_text in enumerate(parent_chunks):
        child_chunks = child_splitter.split_text(parent_text)
        for child in child_chunks:
            result.append({
                "child": child,
                "parent": parent_text,
                "parent_index": parent_idx
            })

    return result