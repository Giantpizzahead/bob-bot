"""
I think this is pretty much the same impl as that markdown API site.

See scraping_test.txt for website scraping test results.
"""

import asyncio
from urllib.parse import urljoin, urlparse

import mdformat
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from markdownify import MarkdownConverter
from playwright.async_api import TimeoutError

from bobbot.utils import (
    close_playwright_browser,
    get_playwright_browser,
    get_playwright_page,
)

load_dotenv()


# Create shorthand method for conversion
def md(soup, **options):
    return MarkdownConverter(**options).convert_soup(soup)


def build_metadata(soup: BeautifulSoup, url: str) -> dict:
    """Build metadata from BeautifulSoup output."""
    # https://python.langchain.com/v0.2/api_reference/_modules/langchain_community/document_loaders/web_base.html
    metadata = {"source": url}
    if title := soup.find("title"):
        metadata["title"] = title.get_text()
    if description := soup.find("meta", attrs={"name": "description"}):
        metadata["description"] = description.get("content", "No description found.")
    if html := soup.find("html"):
        metadata["language"] = html.get("lang", "No language found.")
    return metadata


async def scrape_website(do_cleaning=True, include_links=False):
    url = "https://www.youtube.com/watch?v=Mdnace-jyNg&t=969s"

    # Get the page's raw HTML content
    browser = await get_playwright_browser()
    context = await browser.new_context()
    page = await get_playwright_page(context)
    try:
        await page.goto(url, timeout=4000)
        await page.wait_for_timeout(3000)
    except TimeoutError:
        print("timed out, but will keep going")
    content = await page.content()
    soup = BeautifulSoup(content, "html.parser")
    metadata = build_metadata(soup, url)
    print(f"HTML length {len(str(soup))} before cleaning.")

    if do_cleaning:
        # Remove unwanted elements
        for tag in soup(["header", "footer", "nav", "aside", "style", "script", "svg"]):
            tag.decompose()  # Completely removes the tag from the tree

        if include_links:
            # Fix links with absolute URLs
            base_parsed = urlparse(url)
            for a_tag in soup.find_all("a"):
                try:
                    href = a_tag["href"]
                    absolute_url = urljoin(url, href)
                    absolute_parsed = urlparse(absolute_url)
                    # Check if the link is a self-link (same domain and path, optional fragment)
                    is_self_link = (
                        absolute_parsed.scheme == base_parsed.scheme
                        and absolute_parsed.netloc == base_parsed.netloc
                        and absolute_parsed.path == base_parsed.path
                        and absolute_parsed.query == base_parsed.query
                    )
                    if is_self_link:
                        a_tag.replace_with(f"{a_tag.get_text()} ")
                    else:
                        a_tag["href"] = absolute_url
                except Exception as e:
                    # print(type(e), e, a_tag.get_text())
                    a_tag.replace_with(f"{a_tag.get_text()} ")
                    continue
            for img_tag in soup.find_all("img"):
                try:
                    img_tag["src"] = urljoin(url, img_tag["src"])
                except Exception:
                    img_tag.decompose()
                    continue
        else:
            # Remove links by replacing with text
            for a_tag in soup.find_all("a"):
                a_tag.replace_with(f"{a_tag.get_text()} ")  # Space to handle non-text links

            # Remove images, replacing with <p> tags or removing them
            for img_tag in soup.find_all("img"):
                try:
                    alt_text = img_tag["alt"]
                    if not alt_text:
                        img_tag.decompose()
                        continue
                    new_tag = soup.new_tag("p")
                    new_tag.string = alt_text
                    img_tag.replace_with(new_tag)
                except Exception:
                    img_tag.decompose()
                    continue
    print(f"HTML length {len(str(soup))}.")

    # Convert to markdown
    raw_markdown = MarkdownConverter().convert_soup(soup)
    markdown = mdformat.text(raw_markdown)
    print(f"Markdown length {len(markdown)}.")
    # Save to file
    with open("out.md", "w") as f:
        f.write(markdown)
    print(metadata)
    await close_playwright_browser()


asyncio.run(scrape_website())
