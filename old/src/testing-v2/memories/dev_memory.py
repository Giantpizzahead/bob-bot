"""Contains long term memory management functionality."""

import asyncio
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from langchain.docstore.document import Document
from langchain_community.retrievers import PineconeHybridSearchRetriever
from pinecone import Pinecone, ServerlessSpec
from pinecone_text.hybrid import hybrid_convex_scale
from pinecone_text.sparse import BM25Encoder

from bobbot.agents.llms import openai_embeddings
from bobbot.utils import get_logger

logger = get_logger(__name__)

# Create index if it doesn't exist
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index_name = "bob-bot"
if index_name not in pc.list_indexes().names():
    pc.create_index(
        name=index_name,
        dimension=1536,  # dimensionality of dense model
        metric="dotproduct",  # sparse values supported only for dotproduct
        spec=ServerlessSpec(cloud="aws", region="us-east-1"),
    )
index = pc.Index(index_name)
bm25_encoder = BM25Encoder().default()  # Default tf-idf values
retriever = PineconeHybridSearchRetriever(embeddings=openai_embeddings, sparse_encoder=bm25_encoder, index=index)


async def add_tool_memories(texts: list[str], chain_id: str, response: str) -> None:
    """Add tool usage results to Bob's long term memory.

    Args:
        texts: The texts representing inputs/outputs of each individual tool.
        chain_id: The ID of the chain in which the tools were used.
        response: Bob's final response after using the tools.
    """
    curr_time = datetime.now(timezone.utc).timestamp()
    metadatas = []
    for _ in texts:
        metadatas.append(
            {
                "creation_time": curr_time,
                "last_retrieval_time": curr_time,
                "type": "tool",
                "chain_id": chain_id,
                "response": response,
                "version": 1,
            }
        )
    try:
        await asyncio.to_thread(retriever.add_texts, texts, metadatas=metadatas)
        logger.info("Saved tool memories for this chain.")
    except Exception as e:
        logger.error(f"Error saving tool memories: {e}")


async def add_chat_memories(texts: list[str], message_ids: list[list[int]]) -> None:
    """Add message histories to Bob's long term memory.

    Args:
        texts: The message histories.
        message_ids: The message IDs of the messages in each history.
    """
    curr_time = datetime.now(timezone.utc).timestamp()
    metadatas = []
    for _, ids in zip(texts, message_ids):
        metadatas.append(
            {
                "creation_time": curr_time,
                "last_retrieval_time": curr_time,
                "type": "chat",
                "message_ids": [str(id) for id in ids],
                "version": 1,
            }
        )
    try:
        await asyncio.to_thread(retriever.add_texts, texts, metadatas=metadatas)
        logger.info("Saved chat memories for this chain.")
    except Exception as e:
        logger.error(f"Error saving chat memories: {e}")


async def get_relevant_documents(query: str, query_filter: Optional[dict] = None) -> list[Document]:
    """Get relevant documents from Bob's long term memory using hybrid search.

    Adapted from PineconeHybridSearchRetriever's _get_relevant_documents method.
    """
    sparse_vec = retriever.sparse_encoder.encode_queries(query)
    # Convert the question into a dense vector
    dense_vec = retriever.embeddings.embed_query(query)
    # Scale alpha with hybrid_scale
    dense_vec, sparse_vec = hybrid_convex_scale(dense_vec, sparse_vec, retriever.alpha)
    sparse_vec["values"] = [float(s1) for s1 in sparse_vec["values"]]
    # Query Pinecone index
    result = await asyncio.to_thread(
        retriever.index.query,
        vector=dense_vec,
        sparse_vector=sparse_vec if sparse_vec["indices"] else None,
        top_k=retriever.top_k,
        include_metadata=True,
        namespace=retriever.namespace,
        filter=query_filter,
    )
    final_result = []
    for res in result["matches"]:
        context = res["metadata"].pop("context")
        metadata = res["metadata"]
        metadata["id"] = res["id"]
        metadata["score"] = res["score"]
        final_result.append(Document(page_content=context, metadata=res["metadata"]))
    return final_result


async def search_memories(query: str, limit: int = 4, age_limit: Optional[timedelta] = None) -> list[Document]:
    """Search Bob's long term memory for relevant, recent memories.

    Args:
        query: The query to search for.
        limit: The maximum number of memories to retrieve.
        age_limit: The maximum age of the memories to retrieve. If None, all memories are considered.

    Returns:
        The list of retrieved memories.
    """
    if age_limit is not None:
        # Calculate the threshold datetime
        threshold_time = (datetime.now(timezone.utc) - age_limit).timestamp()

        # Create a filter to retrieve memories based on recency
        query_filter = {"last_retrieval_time": {"$gte": threshold_time}}
    else:
        query_filter = None

    # Retrieve relevant documents
    retriever.top_k = limit
    results = await get_relevant_documents(query, query_filter=query_filter)

    # Update last retrieval times concurrently
    curr_time = datetime.now(timezone.utc).timestamp()
    tasks = [
        asyncio.to_thread(
            retriever.index.update, id=result.metadata["id"], set_metadata={"last_retrieval_time": curr_time}
        )
        for result in results
    ]
    await asyncio.gather(*tasks)

    print(results)
    return results


async def main():
    """Main."""
    await add_tool_memories(["input1\noutput1", "hello\nworld"], "chain1", "response1")
    await add_chat_memories(["bob: hi!\nalex: yo", "what: ?????\nidk: yeah this is weird"], [[1, 2], [3]])
    print(await search_memories("this is a query!", age_limit=timedelta(days=1)))


if __name__ == "__main__":
    asyncio.run(main())
