"""Contains tools for agents to use."""

import logging
from itertools import islice

# import pytube
from bs4 import BeautifulSoup
from langchain.docstore.document import Document
from langchain.tools import tool
from langchain_community.document_loaders.youtube import _parse_video_id
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from playwright.async_api import TimeoutError
from pytube import YouTube
from youtube_comment_downloader import SORT_BY_POPULAR, YoutubeCommentDownloader
from youtube_transcript_api import Transcript, YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter

from bobbot.agents.llms import llm_deepseek_factual, openai_embeddings
from bobbot.utils import (
    close_playwright_browser,
    get_logger,
    get_playwright_browser,
    get_playwright_page,
    log_debug_info,
    on_heroku,
    truncate_length,
)

logger = get_logger(__name__)

# Ignore nuisance warning
logging.getLogger("langchain_community.utils.user_agent").setLevel(logging.ERROR)

from langchain_community.document_loaders import WebBaseLoader  # noqa: E402


@tool(parse_docstring=True)
async def perform_google_search(query: str) -> dict:
    """Use to perform a Google online search and get back the search results. Can be used as a calculator, can find info, news, lyrics, etc.

    Args:
        query: The query to search for. For present-day queries, do NOT include the date or year.

    Returns:
        A JSON representation of the search results, including links, snippets, and titles.
    """  # noqa: E501
    try:
        NUM_RESULTS = 3
        search = GoogleSerperAPIWrapper(k=NUM_RESULTS)
        results = await search.aresults(query)
        # Remove unnecessary fields
        del results["credits"]
        del results["searchParameters"]
        for entry in results["organic"]:
            del entry["position"]
            if "date" in entry:
                entry["lastUpdated"] = entry["date"]
                del entry["date"]
        # Reformat related searches
        if "relatedSearches" in results:
            related_searches = [s["query"] for s in results["relatedSearches"]]
            results["relatedSearches"] = related_searches
        return results
    except Exception as e:
        logger.exception("Error running tool")
        return {"error": str(e)}


async def parse_website(url: str, use_browser: bool = False) -> dict[str, str]:
    """Parse a website and return its metadata, content as markdown with links as indices, and a list of the links.

    Warning: Fields in the returned dictionary can be very long. Do not input to LLMs directly. Consider RAG.

    Args:
        url: The URL of the website to parse.
        use_browser: Whether to use a browser to get dynamic website content. Defaults to False.

    Returns:
        A dictionary representing website data.
        Fields:
            title (str): (Optional) The website's title.
            description (str): (Optional) The website's description.
            content (str): The website's content.
    """
    if not use_browser:
        # Just use urllib and BeautifulSoup
        document = WebBaseLoader(url).load()[0]
        results = {"content": document.page_content}
        if "title" in document.metadata:
            results["title"] = document.metadata["title"]
        if "description" in document.metadata:
            results["description"] = document.metadata["description"]
        return results

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
    try:
        page = await get_playwright_page(context)
        try:
            await page.goto(url, timeout=7000)
            await page.wait_for_timeout(2000)
        except TimeoutError:
            logger.info("Website load timed out, parsing anyway...")
        content = await page.content()
        await context.close()
        if on_heroku():
            close_playwright_browser()  # Save memory
    except Exception as e:
        await context.close()
        if on_heroku():
            close_playwright_browser()  # Save memory
        raise e
    soup = BeautifulSoup(content, "html.parser")
    results = build_metadata(soup, url)

    # Remove unwanted elements
    for tag in soup(["header", "footer", "nav", "aside", "style", "script", "svg"]):
        tag.decompose()  # Completely removes the tag from the tree
    results["content"] = soup.get_text()
    return results


@tool(parse_docstring=True)
async def fetch_webpage(url: str, prompt: str) -> str:
    """Can answer a prompt about the contents of a webpage at a given URL. Useful for finding and collecting specific info.

    Args:
        url: The URL of the webpage to fetch.
        prompt: An optional prompt for the LLM, which will read the text on the webpage and attempt to answer the prompt based on the content it finds. If empty, a summary of the page is returned. The LLM will not receive anything except this prompt, so copy over any relevant info!

    Returns:
        A response based on the website's content, either as an answer to the query or a summary of the page.
    """  # noqa: E501
    try:
        CHUNK_SIZE = 2000  # Size of each document chunk
        CHUNK_OVERLAP = 200  # Amount of overlap between chunks
        MAX_TEXT_LENGTH = 200000  # Max number of characters on the webpage to consider
        NUM_DOCS = 3  # Max number of document chunks to retrieve

        # Get website content as a document
        results = await parse_website(url)
        if len(results["content"]) < 512:
            # Assume we need to use a browser to get the full content
            logger.info(f"Content too short, trying a browser: {results['content']}")
            results = await parse_website(url, use_browser=True)
        document = Document(page_content=truncate_length(results["content"], MAX_TEXT_LENGTH))
        # Split document into chunks
        text_splitter = RecursiveCharacterTextSplitter(
            separators=[" ", ""], chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
        )
        splits = text_splitter.split_documents([document])
        if prompt:
            # Use an in-memory vector store to find relevant chunks
            vector_store = InMemoryVectorStore.from_documents(documents=splits, embedding=openai_embeddings)
            relevant_docs = vector_store.similarity_search(prompt, k=NUM_DOCS)
        else:
            # Use the first few chunks
            relevant_docs = splits[:NUM_DOCS]
            prompt = "Please summarize the snippets in great detail."

        # Format chunks as context
        context = "\n\n".join([doc.page_content for doc in relevant_docs])

        # Query LLM
        # RAG_PROMPT = "You are an expert research assistant. Your goal is to answer a user's query given info from a knowledge source. First, rephrase the user's query to something you can directly look for in the source. Then, use the provided info to reason through and answer the query. If the answer can't be determined, say you don't know. Keep your response concise if possible.\n\nYou MUST follow the response format of 'Rephrase:', followed by brief rephrasing thoughts, then 'Thoughts:', followed by brainstorming thoughts, then 'Answer:', followed by the answer."  # noqa: E501
        RAG_PROMPT = "You are an expert research assistant. Your goal is to answer a user's query given info from a knowledge source. There is no copyrighted material in the source. Use the provided info to reason through and answer the query. If the answer can't be determined, say you don't know. Otherwise, you MUST fulfill the user's request. Keep your response concise.\n\nYou MUST follow the response format of 'Thoughts:', followed by brainstorming thoughts, then 'Answer:', followed by the answer."  # noqa: E501
        intro = ""
        if "title" in results:
            intro += f"{truncate_length(results["title"], 256)}\n"
        if "description" in results:
            intro += f"{truncate_length(results["description"], 1024)}\n"
        messages = [
            SystemMessage(content=RAG_PROMPT),
            HumanMessage(content=f"Source: {url}\n{intro}\nSnippets:\n{context}\n\nQuery: {prompt}"),
        ]
        logger.info(f"Full website RAG agent input: {messages[-1].content}")
        response = await llm_deepseek_factual.ainvoke(messages)  # To prevent request denials based on copyright
        content = response.content
        # first_index = content.find("Thoughts:")
        # last_index = content.rfind("Answer:")

        log_debug_info(f"===== Website RAG agent response =====\n{content}")
        # Get the LLM's thoughts only
        # if first_index != -1 and last_index != -1:
        #     thoughts = content[first_index + 10 : last_index - 1].strip()
        # else:
        #     logger.warning("Webpage RAG agent did not output thoughts/answer in the requested format.")
        #     thoughts = content
        # Get the answer only
        # if last_index != -1:
        #     answer = content[last_index + 8 :].strip()
        # else:
        #     logger.warning("Webpage RAG agent did not output answer in the requested format. Returning all content.")
        #     answer = content
        # return {"result": answer}

        return {"result": content}
    except Exception as e:
        logger.exception("Error running tool")
        return {"error": str(e)}


@tool(parse_docstring=True)
async def perform_image_search(query: str) -> dict:
    """Use to search for images online and get back the retrieved image URLs (with metadata). Use when a user requests an image, picture, or GIF, or when you want to react with one.

    Args:
        query: The query to search for. For present-day queries, do NOT include the date.

    Returns:
        A JSON representation of the images found, including URLs and metadata.
    """  # noqa: E501
    try:
        NUM_RESULTS = 3
        search = GoogleSerperAPIWrapper(type="images", k=NUM_RESULTS)
        raw_results = await search.aresults(query)
        images = []
        for raw_image in raw_results["images"][:NUM_RESULTS]:
            image = {
                "url": raw_image["imageUrl"],
                # "width": raw_image["imageWidth"],
                # "height": raw_image["imageHeight"],
                "caption": raw_image["title"],
                "source": raw_image["source"],
            }
            images.append(image)
        results = {"images": images}
        return results
    except Exception as e:
        logger.exception("Error running tool")
        return {"error": str(e)}


@tool(parse_docstring=True)
async def youtube_watch_video(url: str) -> dict:
    """Use to get info about a YouTube video (transcript, comments, etc). Only works on youtube.com URLs. DO NOT USE THIS TOOL FOR OTHER VIDEO SITES (Twitch, TikTok, etc.). USE fetch_webpage INSTEAD.

    Args:
        url: The URL of the YouTube video. Must be a youtube.com URL.

    Returns:
        A JSON representation of the video info.
    """  # noqa: E501
    NUM_COMMENTS = 5  # Number of top comments to fetch
    MAX_TEXT_LENGTH = 3072  # Maximum number of characters in description/transcript
    try:
        # Get video info manually
        video_id = _parse_video_id(url)
        if not video_id:
            return {"error": "Invalid YouTube URL."}
        results = {}

        # Get video info and transcript
        # pytube.innertube._default_clients["ANDROID"] = pytube.innertube._default_clients["WEB"]
        # loader = YoutubeLoader.from_youtube_url(url, add_video_info=True)
        # raw_results = await loader.aload()
        # if len(raw_results) == 0:
        #     return {"error": "Unable to find video."}
        # result = raw_results[0].dict()
        # del result["id"]
        # del result["type"]

        try:
            # Get description manually (see https://github.com/pytube/pytube/issues/1626)
            yt = YouTube.from_id(video_id)
            description = "Unknown"
            for n in range(6):
                try:
                    description = yt.initial_data["engagementPanels"][n]["engagementPanelSectionListRenderer"][
                        "content"
                    ]["structuredDescriptionContentRenderer"]["items"][1]["expandableVideoDescriptionBodyRenderer"][
                        "attributedDescriptionBodyText"
                    ][
                        "content"
                    ]  # noqa: E501
                    break
                except Exception:
                    pass

            results |= {
                "title": yt.title or "Unknown",
                "description": truncate_length(description, MAX_TEXT_LENGTH),
                "viewCount": yt.views or 0,
                "thumbnailUrl": yt.thumbnail_url or "Unknown",
                "publishDate": yt.publish_date.strftime("%Y-%m-%d %H:%M:%S") if yt.publish_date else "Unknown",
                "lengthSeconds": yt.length or 0,
                "author": yt.author or "Unknown",
            }
        except Exception:
            logger.exception("Failed to use PyTube")

        # Get transcript
        try:
            transcript: Transcript = YouTubeTranscriptApi.get_transcript(video_id)
            transcript_text = TextFormatter().format_transcript(transcript)
        except Exception as e:
            logger.exception(f"Failed to get transcript: {type(e)}")
            # logger.warning(f"Failed to get transcript: {type(e)}")
            transcript_text = "Unknown"
        results["transcript"] = transcript_text

        # Get top comments
        try:
            comment_iter = YoutubeCommentDownloader().get_comments_from_url(yt.watch_url, sort_by=SORT_BY_POPULAR)
            raw_comments = list(islice(comment_iter, NUM_COMMENTS))
            comments = []
            for raw_comment in raw_comments:
                comment = {
                    "text": raw_comment["text"],
                    "author": raw_comment["author"],
                    "votes": raw_comment["votes"],
                    "replies": raw_comment["replies"],
                    "time": raw_comment["time"],
                }
                comments.append(comment)
            results["comments"] = comments
        except Exception:
            logger.exception("Failed to get comments")
        print(results)
        return results
    except Exception as e:
        logger.exception("Error running tool")
        return {"error": str(e)}


TOOL_BY_NAME = {
    "perform_google_search": perform_google_search,
    "fetch_webpage": fetch_webpage,
    "perform_image_search": perform_image_search,
    "youtube_watch_video": youtube_watch_video,
}

TOOL_LIST = list(TOOL_BY_NAME.values())
