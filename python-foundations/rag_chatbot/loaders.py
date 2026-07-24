import os
from pypdf import PdfReader

def load_document(path):

    if path.endswith(".txt"):

        with open(path, "r", encoding="utf-8") as file:
            return file.read()

    elif path.endswith(".pdf"):

        reader = PdfReader(path)

        text = ""

        for page in reader.pages:

            page_text = page.extract_text()

            if page_text:
                text += page_text + "\n"

        return text

    else:

        raise ValueError(
            f"Unsupported file type: {path}"
        )