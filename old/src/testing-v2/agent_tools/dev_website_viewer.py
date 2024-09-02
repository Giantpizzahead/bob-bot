"""
I think this is pretty much the same impl as that markdown API site.

See scraping_test.txt for website scraping test results.
"""

import asyncio
import os
from pprint import pprint
from urllib.parse import urljoin, urlparse

import mdformat
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from langchain.docstore.document import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from markdownify import MarkdownConverter
from playwright.async_api import TimeoutError

from bobbot.agents.llms import llm_gpt4omini_factual, messages_to_string
from bobbot.utils import (
    close_playwright_browser,
    get_logger,
    get_playwright_browser,
    get_playwright_page,
    log_debug_info,
    truncate_length,
)

load_dotenv()
logger = get_logger(__name__)


async def parse_website(url: str) -> dict:
    """Parse a website and return its metadata, content as markdown with links as indices, and a list of the links.

    Warning: All fields in the returned dictionary can be very long. Do not input to LLMs directly. Consider RAG.

    Args:
        url (str): The URL of the website to parse.

    Returns:
        A dictionary representing website data.
        Fields:
            source (str): The URL of the website.
            content (str): The title, description, and content in markdown. Links/images are replaced by link_i/img_i.
            links (list): A zero-indexed list of hyperlinked URLs found on the website.
            images (list): A zero-indexed list of image URLs found on the website.
    """

    def build_metadata(soup: BeautifulSoup, url: str) -> dict:
        """Build metadata from BeautifulSoup output."""
        # https://python.langchain.com/v0.2/api_reference/_modules/langchain_community/document_loaders/web_base.html
        metadata = {}
        if title := soup.find("title"):
            metadata["title"] = title.get_text()
        if description := soup.find("meta", attrs={"name": "description"}):
            metadata["description"] = description.get("content", "No description found.")
        return metadata

    # Get the page's raw HTML content
    browser = await get_playwright_browser()
    context = await browser.new_context()
    page = await get_playwright_page(context)
    try:
        await page.goto(url, timeout=7000)
        await page.wait_for_timeout(2000)
    except TimeoutError:
        logger.info("Website load timed out, parsing anyway...")
    content = await page.content()
    soup = BeautifulSoup(content, "html.parser")
    return {"content": soup.get_text()}
    metadata = build_metadata(soup, url)
    results = {}
    print(f"HTML length {len(str(soup))} before cleaning.")

    # Remove unwanted elements
    for tag in soup(["header", "footer", "nav", "aside", "style", "script", "svg"]):
        tag.decompose()  # Completely removes the tag from the tree

    # # Fix links with absolute URLs
    # links = []
    # base_parsed = urlparse(url)
    # for a_tag in soup.find_all("a"):
    #     try:
    #         new_tag = soup.new_tag("p")
    #         new_tag.string = a_tag.get_text()
    #         a_tag.replace_with(new_tag)
    #         # href = a_tag["href"]
    #         # absolute_url = urljoin(url, href)
    #         # absolute_parsed = urlparse(absolute_url)
    #         # # Remove self-links (same domain and path, optional fragment)
    #         # is_self_link = (
    #         #     absolute_parsed.scheme == base_parsed.scheme
    #         #     and absolute_parsed.netloc == base_parsed.netloc
    #         #     and absolute_parsed.path == base_parsed.path
    #         #     and absolute_parsed.query == base_parsed.query
    #         # )
    #         # if is_self_link:
    #         #     a_tag.replace_with(f"{a_tag.get_text()} ")
    #         # else:
    #         #     # Replace link with ID
    #         #     try:
    #         #         link_id = links.index(absolute_url)
    #         #     except ValueError:
    #         #         link_id = len(links)
    #         #         links.append(absolute_url)
    #         #     a_tag["href"] = f"link_{link_id}"
    #     except Exception:
    #         # Broken link, replace with text
    #         a_tag.replace_with(f"{a_tag.get_text()} ")
    #         continue
    # results["links"] = links

    # # Replace images with IDs
    # images = []
    # for img_tag in soup.find_all("img"):
    #     try:
    #         absolute_url = urljoin(url, img_tag["src"])
    #         try:
    #             image_id = images.index(absolute_url)
    #         except ValueError:
    #             image_id = len(images)
    #             images.append(absolute_url)
    #         img_tag["src"] = f"img_{image_id}"
    #     except Exception:
    #         # Remove broken images
    #         img_tag.decompose()
    #         continue
    # results["images"] = images
    print(f"HTML length {len(str(soup))}.")

    # Combine title and description
    intro = ""
    # if "title" in metadata:
    #     intro += f"# {metadata['title']}\n\n"
    # if "description" in metadata:
    #     intro += f"{metadata['description']}\n\n"

    # Convert to markdown
    raw_markdown = f"{intro}{MarkdownConverter().convert_soup(soup)}"
    markdown = mdformat.text(raw_markdown)
    results["content"] = markdown
    print(f"Markdown length {len(markdown)}.")

    # Save to file
    with open("out.md", "w") as f:
        f.write(markdown)
    return results


async def main():
    # url = "https://leagueoflegends.fandom.com/wiki/List_of_champions"
    # query = "How many champs are there?"

    # url = "https://genius.com/Eden-wake-up-lyrics"
    # query = "What is the full chorus of this song?"

    url = "https://www.youtube.com/watch?v=Mdnace-jyNg&t=969s"
    query = None

    CHUNK_SIZE = 2000
    CHUNK_OVERLAP = 200
    MAX_TEXT_LENGTH = 200000
    NUM_DOCS = 3

    # Get website content as a document
    results = await parse_website(url)
    document = Document(page_content=truncate_length(results["content"], MAX_TEXT_LENGTH))
    # Split document into chunks
    text_splitter = RecursiveCharacterTextSplitter(
        separators=[" ", ""], chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
    )
    splits = text_splitter.split_documents([document])
    if query:
        # Use an in-memory vector store to find relevant chunks
        embedding = OpenAIEmbeddings(api_key=os.getenv("OPENAI_KEY"))
        vector_store = InMemoryVectorStore.from_documents(documents=splits, embedding=embedding)
        relevant_docs = vector_store.similarity_search(query, k=NUM_DOCS)
    else:
        # Use the first few chunks
        relevant_docs = splits[:NUM_DOCS]
        query = "Please summarize the above snippets."

    # Format chunks as context
    context = "\n\n".join([doc.page_content for doc in relevant_docs])
    logger.info(
        "Documents:\n"
        + "\n".join(
            [
                f"Document {i+1}: {truncate_length(doc.page_content, 255, replace_newlines=True)}"
                for i, doc in enumerate(relevant_docs)
            ]
        )
    )

    # Query LLM
    RAG_PROMPT = """You are an expert research assistant. Your goal is to answer a user's query given relevant snippets of a knowledge base. Use the snippets provided to reason through and answer the query, providing relevant links and/or images to the user (link_i and image_i). If the answer can't be determined, say you don't know. Keep your response concise.

You MUST follow the response format of 'Thoughts:', followed by brainstorming thoughts, then 'Answer:' on a new line, followed by your answer!"""
    messages = [
        SystemMessage(content=RAG_PROMPT),
        HumanMessage(content=f"Snippets:\n{context}\n\nQuery: {query}"),
    ]
    # print(messages_to_string(messages))
    response = await llm_gpt4omini_factual.ainvoke(messages)
    content = response.content

    log_debug_info(f"===== Website viewer response =====\n{content}")
    await close_playwright_browser()


asyncio.run(main())
