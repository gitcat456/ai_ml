from llama_index.core import SimpleDirectoryReader
from llama_index.readers.file import PDFReader


reader = PDFReader()

documents = SimpleDirectoryReader(
    "documents",
    file_extractor={
        ".pdf": reader
    }
).load_data()

for i, doc in enumerate(documents):
    print("="*50)
    print("DOCUMENT:", i)
    print(doc.metadata["file_name"])
    print(doc.metadata.get("page_label"))
    print(doc.text[:100])