import re
import requests
from langchain_community.document_loaders import AsyncChromiumLoader
from langchain_community.document_transformers import BeautifulSoupTransformer
from langchain.text_splitter import CharacterTextSplitter
import fitz

from langchain_chroma import Chroma

from langchain_community.embeddings.sentence_transformer import (
    SentenceTransformerEmbeddings,
)

# retrieves pages and extracts text by tag
def get_page(urls, html_only=False):
    loader = AsyncChromiumLoader(urls)
    html = loader.load()
    if html_only:
        body = []
        # Regular expression to match <style></style> and <script></script> tags and their content
        regex_pattern = r'<style.*?</style>|<script.*?</script>'
        for ht in html:
            # Using re.sub to remove the matched content
            cleaned_html = re.sub(regex_pattern, '', ht.page_content, flags=re.DOTALL)
            body.append(cleaned_html)
        return "\n\n".join(body)
    bs_transformer = BeautifulSoupTransformer()
    docs_transformed = bs_transformer.transform_documents(html, tags_to_extract=["p"], remove_unwanted_tags=["a"])
    return docs_transformed


def webRag(urls, max_response_size, query):
    text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
    docs = text_splitter.split_documents(get_page(urls))
    embedding_function = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")
    db = Chroma.from_documents(docs, embedding_function)
    docs = db.search(query, "mmr", k=10)
    text = ""
    for doc in docs:
        # Check if adding the next doc would exceed the limit
        next_chunk = f"\n\n{doc.page_content}"
        if len(text) + len(next_chunk) > max_response_size:
            # If adding the whole chunk exceeds, try adding a truncated part
            remaining_space = max_response_size - len(text)
            if remaining_space > 2: # Need space for at least "\n\n"
                 text += next_chunk[:remaining_space]
            break # Stop adding more docs
        else:
             text += next_chunk

    # Ensure final text does not exceed max_response_size (optional safeguard)
    # return text[:max_response_size]
    return text


def getPDFContent(url):
    response = requests.get(url)
    # Check if the request was successful
    if response.status_code == 200:
        # Open the PDF from the bytes in memory
        pdf = fitz.open(stream=response.content, filetype="pdf")
        text_content = ''
        # Extract text from each page
        for page_num in range(len(pdf)):
            page = pdf[page_num]
            text_content += page.get_text()
        
        # Close the PDF after extracting text
        pdf.close()
        
        return text_content
    else:
        print(f"Failed to download PDF. Status code: {response.status_code}")
        return None
