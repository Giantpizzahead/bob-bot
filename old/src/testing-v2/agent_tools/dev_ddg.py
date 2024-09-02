"""Main runner for the bot."""

import json
from pprint import pprint

from langchain_community.tools import DuckDuckGoSearchResults

search = DuckDuckGoSearchResults()
res = search.invoke("League champs")
pprint(type(res))
pprint(search.invoke("League champs"))
