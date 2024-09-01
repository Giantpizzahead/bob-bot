"""Fit BM25 values to a custom corpus and store them to a json file.

Source: https://python.langchain.com/v0.2/docs/integrations/retrievers/pinecone_hybrid_search/
"""

import nltk
from pinecone_text.sparse import BM25Encoder

nltk.download("punkt_tab")

# use default tf-idf values
bm25_encoder = BM25Encoder().default()

# fitting to custom corpus
corpus = ["foo", "bar", "world", "hello"]

# fit tf-idf values on your corpus
bm25_encoder.fit(corpus)

# store the values to a json file
bm25_encoder.dump("bm25_values.json")

# load to your BM25Encoder object
bm25_encoder = BM25Encoder().load("bm25_values.json")
