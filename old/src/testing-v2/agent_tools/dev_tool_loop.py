"""Main runner for the bot."""

import asyncio
import os
import pprint
from pprint import pprint

from dotenv import load_dotenv
from langchain.tools import Tool, tool
from langchain_community.document_loaders import YoutubeLoader
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tracers.context import tracing_v2_enabled

from bobbot.agents.llms import llm_gpt4omini_factual
from bobbot.utils import truncate_length

load_dotenv()


@tool(parse_docstring=True)
async def perform_google_search(query: str) -> dict:
    """Performs a Google search and returns the search results.

    Args:
        query: The query to search for.

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
async def get_youtube_video_info(url: str) -> dict:
    """
    Fetches and returns information about a YouTube video, such as its title, description, and transcript.

    Args:
        url: The URL of the YouTube video.

    Returns:
        A JSON representation of the video info.
    """
    MAX_TRANSCRIPT_LENGTH = 4096  # Maximum number of characters in transcript
    try:
        loader = YoutubeLoader.from_youtube_url(url, add_video_info=True)
        raw_results = await loader.aload()
        if len(raw_results) == 0:
            return {"error": "Unable to find video."}
        result = raw_results[0].dict()
        del result["id"]
        del result["type"]
        result["transcript"] = truncate_length(result["page_content"], MAX_TRANSCRIPT_LENGTH)
        del result["page_content"]
        return result
    except Exception as e:
        return {"error": str(e)}


async def main():
    messages = [
        SystemMessage(content="Answer the given query, using tools if needed."),
        # HumanMessage(content="How many league champs are there as of today (August 29, 2024)?"),
        # HumanMessage(content="What does zoe look like in league?"),
        HumanMessage(content="What's the lesson in this video? https://www.youtube.com/shorts/B0gDDdNvB3c"),
    ]

    TOOLS = {
        "perform_google_search": perform_google_search,
        "perform_image_search": perform_image_search,
        "get_youtube_video_info": get_youtube_video_info,
    }

    llm_with_tools = llm_gpt4omini_factual.bind_tools([tool for tool in TOOLS.values()], strict=True)

    # with tracing_v2_enabled():
    # Let the agent self loop up to 3 times
    for i in range(3):
        ai_message = await llm_with_tools.ainvoke(messages)
        messages.append(ai_message)
        if ai_message.tool_calls:
            for tool_call in ai_message.tool_calls:
                tool: Tool = TOOLS[tool_call["name"]]
                print(f"Calling tool {tool_call['name']} with args {tool_call['args']}")
                tool_message: ToolMessage = await tool.ainvoke(tool_call)
                messages.append(tool_message)
                print(f"-> {tool_message.content[:512]}")
        else:
            break

    # Output response
    pprint(messages)
    response = ai_message.content if ai_message.content.strip() else "Unable to answer within iteration count."
    print(f"\n\nResponse:\n{response}")


asyncio.run(main())
