from langchain_text_splitters import RecursiveCharacterTextSplitter

def chunk_document_text(raw_text: str) -> list[str]:
    """
    Takes raw extracted text and splits it into semantic chunks using LangChain.
    We approximate 1 token to 4 characters.
    Blueprint specs: 500 tokens (~2000 chars) size, 100 tokens (~400 chars) overlap.
    """
    # Initialize the text splitter
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=2000,      # roughly 500 tokens
        chunk_overlap=400,    # roughly 100 tokens overlap to maintain context between chunks
        length_function=len,
        separators=["\n\n", "\n", " ", ""] # Tries to split by paragraphs first, then sentences
    )
    
    # Generate the chunks
    chunks = text_splitter.split_text(raw_text)
    
    return chunks