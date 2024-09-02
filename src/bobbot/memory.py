"""Contains long term memory management functionality."""

import asyncio
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import nltk
from langchain.docstore.document import Document
from langchain_community.retrievers import PineconeHybridSearchRetriever
from pinecone import Pinecone, ServerlessSpec
from pinecone_text.hybrid import hybrid_convex_scale
from pinecone_text.sparse import BM25Encoder

from bobbot.agents.llms import openai_embeddings
from bobbot.utils import get_logger

PARAMS_PATH = "local/bm25_params.json"

logger = get_logger(__name__)


def create_bm25_encoder() -> "BM25Encoder":
    """Create a default BM25 model from the MS MARCO passages corpus, or restore from local cache."""
    bm25 = BM25Encoder()
    if not Path(PARAMS_PATH).exists():
        bm25 = BM25Encoder().default()  # Default tf-idf values
        print()
        bm25.dump(str(Path(PARAMS_PATH)))
    else:
        bm25.load(str(Path(PARAMS_PATH)))
    return bm25


nltk.download("punkt_tab", quiet=True)

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
bm25_encoder = create_bm25_encoder()
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
    await asyncio.to_thread(retriever.add_texts, texts, metadatas=metadatas)
    logger.info("Saved tool memories for this chain.")


async def add_chat_memory(text: str, message_ids: list[int]) -> None:
    """Add a given message history to Bob's long term memory.

    Args:
        text: The message history.
        message_ids: The message IDs of the messages in the history.
    """
    curr_time = datetime.now(timezone.utc).timestamp()
    metadatas = [
        {
            "creation_time": curr_time,
            "last_retrieval_time": curr_time,
            "type": "chat",
            "message_ids": [str(id) for id in message_ids],
            "version": 1,
        }
    ]
    await asyncio.to_thread(retriever.add_texts, [text], metadatas=metadatas)
    logger.info("Saved chat memory.")


async def delete_memory(id: str) -> bool:
    """Delete a memory from Bob's long term memory.

    Args:
        id: The ID of the memory to delete.

    Returns:
        True if the memory was deleted, False otherwise.
    """
    try:
        result = index.fetch(ids=[id])
        if len(result["vectors"]) == 0:
            logger.info(f"Memory with ID {id} does not exist.")
            return False
        index.delete(ids=[id])
    except Exception:
        logger.exception(f"Error deleting memory with ID {id}.")
        return False
    logger.info(f"Deleted memory with ID {id}.")
    return True


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
    # print(result["usage"])
    final_result = []
    for res in result["matches"]:
        context = res["metadata"].pop("context")
        metadata = res["metadata"]
        metadata["id"] = res["id"]
        metadata["score"] = res["score"]
        final_result.append(Document(page_content=context, metadata=res["metadata"]))
    return final_result


async def query_memories(
    query: str,
    limit: int = 4,
    age_limit: Optional[timedelta] = None,
    ignore_recent: bool = True,
    only_tools: bool = False,
) -> list[Document]:
    """Search Bob's long term memory for relevant, recent memories.

    Most memories should not exceed ~5000 characters in length, but this is still a lot, and is also not guaranteed.
    Truncate all memories before giving them to an LLM!

    Args:
        query: The query to search for.
        limit: The maximum number of memories to retrieve.
        age_limit: The maximum age of the memories to retrieve. If None, all memories are considered.
        ignore_recent: Whether to ignore recent memories (within 1 minute old) when retrieving.
        only_tools: Whether to only retrieve tool memories.

    Returns:
        The list of retrieved memories, sorted by relevance.
    """
    query_filter = {}
    # Threshold datetimes
    if ignore_recent:
        recent_time = (datetime.now(timezone.utc) - timedelta(minutes=1)).timestamp()
        query_filter.setdefault("creation_time", {})
        query_filter["creation_time"]["$lt"] = recent_time
    if age_limit is not None:
        old_time = (datetime.now(timezone.utc) - age_limit).timestamp()
        query_filter.setdefault("creation_time", {})
        query_filter["creation_time"]["$gt"] = old_time
    # Tool memories only
    if only_tools:
        query_filter["type"] = {"$eq": "tool"}
    # Empty filter
    if not query_filter:
        query_filter = None

    # Retrieve relevant documents
    retriever.top_k = limit
    try:
        results = await get_relevant_documents(query, query_filter=query_filter)
    except Exception:
        logger.exception("Error querying long term memory")
        return []
    logger.debug(
        f"Long term memory query with query={query}, limit={limit}, age_limit={age_limit}, ignore_recent={ignore_recent}, only_tools={only_tools} -> {[f'{doc.metadata["id"][:16]}...' for doc in results]}"  # noqa: E501
    )

    # Update last retrieval times concurrently
    curr_time = datetime.now(timezone.utc).timestamp()
    tasks = [
        asyncio.to_thread(
            retriever.index.update, id=result.metadata["id"], set_metadata={"last_retrieval_time": curr_time}
        )
        for result in results
    ]
    await asyncio.gather(*tasks)
    return results
