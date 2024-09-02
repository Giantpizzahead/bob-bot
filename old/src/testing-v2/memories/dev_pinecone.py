"""Set up and use a Pinecone hybrid search index.

Source: https://python.langchain.com/v0.2/docs/integrations/retrievers/pinecone_hybrid_search/
"""

import os

from langchain_community.retrievers import PineconeHybridSearchRetriever
from pinecone import Pinecone, ServerlessSpec

from bobbot.agents.llms import openai_embeddings
from bobbot.utils import get_logger

logger = get_logger(__name__)

index_name = "bob-bot"

# initialize Pinecone client
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))

# create the index
if index_name not in pc.list_indexes().names():
    pc.create_index(
        name=index_name,
        dimension=1536,  # dimensionality of dense model
        metric="dotproduct",  # sparse values supported only for dotproduct
        spec=ServerlessSpec(cloud="aws", region="us-east-1"),
    )
index = pc.Index(index_name)

embeddings = openai_embeddings

from pinecone_text.sparse import BM25Encoder

# use default tf-idf values
bm25_encoder = BM25Encoder().default()

retriever = PineconeHybridSearchRetriever(embeddings=embeddings, sparse_encoder=bm25_encoder, index=index)

# add text (ids are hashes of the strings, so no duplicates will be added)
retriever.add_texts(["hello world", "my favorite number is 28"])

# search
result = retriever.invoke("whats my lucky lottery ticket?")
print(result)
