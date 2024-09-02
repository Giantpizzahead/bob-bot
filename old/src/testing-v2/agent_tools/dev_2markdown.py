"""
Test sites:

https://leagueoflegends.fandom.com/wiki/List_of_champions - Terrible, gets the cookies popup.
https://webscraper.io/test-sites/e-commerce/more - Decent but misses the big heading.
https://www.leagueoflegends.com/en-us/champions/ - Terrible. Gets basically nothing.
https://www.youtube.com/watch?v=Mdnace-jyNg&t=969s - Doesn't work at all.

The non-JS endpoint works a little bit better, but at that point we might as well just use our local solution.

Welp, looks like we're doing it locally. Yay!
"""

# You will need to get your own API key. See https://2markdown.com/login

import asyncio
import os
from pprint import pprint

import aiohttp
from dotenv import load_dotenv

load_dotenv()


async def post_request():
    url = "https://api.2markdown.com/v1/url2md"
    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": os.getenv("TWO_MARKDOWN_KEY"),  # Replace with your actual API key
    }
    payload = {"url": "https://leagueoflegends.fandom.com/wiki/List_of_champions"}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as response:
            if response.status == 200:
                data = await response.json()  # Assuming the response is in JSON format
                print(data)
            else:
                print(f"Request failed with status: {response.status}")
                print(await response.text())  # Print the error message from the server


# Run the async function
asyncio.run(post_request())
