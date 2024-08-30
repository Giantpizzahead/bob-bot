"""Contains tools for agents to use."""

from itertools import islice

from langchain.tools import tool
from langchain_community.document_loaders import YoutubeLoader
from langchain_community.utilities import GoogleSerperAPIWrapper
from pytube import YouTube
from youtube_comment_downloader import SORT_BY_POPULAR, YoutubeCommentDownloader

from bobbot.utils import get_logger, truncate_length

logger = get_logger(__name__)


@tool(parse_docstring=True)
async def perform_google_search(query: str) -> dict:
    """Performs a Google search and returns the search results. Works best when the query is a complete question.

    Args:
        query: The query to search for. Can be a question or a general search.

    Returns:
        A JSON representation of the search results, including links, snippets, and titles.
    """
    try:
        NUM_RESULTS = 3
        search = GoogleSerperAPIWrapper(k=NUM_RESULTS)
        results = await search.aresults(query)
        # Remove unnecessary fields
        del results["credits"]
        del results["searchParameters"]
        for entry in results["organic"]:
            del entry["position"]
        # Reformat related searches
        if "relatedSearches" in results:
            related_searches = [s["query"] for s in results["relatedSearches"]]
            results["relatedSearches"] = related_searches
        return results
    except Exception as e:
        return {"error": str(e)}


@tool(parse_docstring=True)
async def perform_image_search(query: str) -> dict:
    """Performs an online image search and returns the retrieved image URLs (with metadata).

    Args:
        query: The query to search for.

    Returns:
        A JSON representation of the images found, including URLs and metadata.
    """
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
                "caption": raw_image["caption"],
                "source": raw_image["source"],
            }
            images.append(image)
        results = {"images": images}
        return results
    except Exception as e:
        return {"error": str(e)}


@tool(parse_docstring=True)
async def watch_youtube_video(url: str) -> dict:
    """Fetches info about a YouTube video (transcript, comments, etc). Use comments as a reference for your reaction.

    Args:
        url: The URL of the YouTube video.

    Returns:
        A JSON representation of the video info.
    """
    NUM_COMMENTS = 5  # Number of top comments to fetch
    MAX_TEXT_LENGTH = 4096  # Maximum number of characters in description/transcript
    try:
        # Get video info and transcript
        loader = YoutubeLoader.from_youtube_url(url, add_video_info=True)
        raw_results = await loader.aload()
        if len(raw_results) == 0:
            return {"error": "Unable to find video."}
        result = raw_results[0].dict()
        del result["id"]
        del result["type"]

        # Get description manually (see https://github.com/pytube/pytube/issues/1626)
        yt = YouTube.from_id(loader.video_id)
        description = ""
        for n in range(6):
            try:
                description = yt.initial_data["engagementPanels"][n]["engagementPanelSectionListRenderer"]["content"][
                    "structuredDescriptionContentRenderer"
                ]["items"][1]["expandableVideoDescriptionBodyRenderer"]["attributedDescriptionBodyText"]["content"]
                break
            except Exception:
                pass
        result["metadata"]["description"] = truncate_length(description, MAX_TEXT_LENGTH)
        result["transcript"] = truncate_length(result["page_content"], MAX_TEXT_LENGTH)
        del result["page_content"]

        # Get top comments
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
        result["reference_comments"] = comments
        return result
    except Exception as e:
        return {"error": str(e)}


TOOL_BY_NAME = {
    "perform_google_search": perform_google_search,
    "perform_image_search": perform_image_search,
    "watch_youtube_video": watch_youtube_video,
}

TOOL_LIST = list(TOOL_BY_NAME.values())
