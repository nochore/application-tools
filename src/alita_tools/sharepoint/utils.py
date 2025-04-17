from docx import Document
from io import BytesIO

def read_docx_from_bytes(file_content):
    """Read and return content from a .docx file using a byte stream."""
    try:
        doc = Document(BytesIO(file_content))
        text = []
        for paragraph in doc.paragraphs:
            text.append(paragraph.text)
        return '\n'.join(text)
    except Exception as e:
        # Use logging instead of print to be captured by caplog in tests
        import logging
        logging.error(f"Error reading .docx from bytes: {e}")
        return ""
