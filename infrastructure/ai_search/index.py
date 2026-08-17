"""Azure AI Search index setup.

Creates or updates the search index with fields for text, image embeddings,
and document-level security groups. Configures vector search with HNSW
algorithm and semantic reranking.
"""

import logging
import os

from azure.search.documents.indexes.models import (
    AzureOpenAIVectorizer,
    AzureOpenAIVectorizerParameters,
    HnswAlgorithmConfiguration,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
    VectorSearch,
    VectorSearchProfile,
)

from raglib.clients import get_project_names, get_search_index_client, load_env_vars
from raglib.config import app_config
from raglib.log import configure_logging

logger = logging.getLogger(__name__)

configure_logging()
load_env_vars()

index_name, semantic_config_name = get_project_names()
index_client = get_search_index_client()

fields = [
    SearchField(
        name="content_id",
        type=SearchFieldDataType.String,
        key=True,
        analyzer_name="keyword",
        sortable=True,
        filterable=True,
        facetable=True,
    ),
    SearchField(
        name="document_title", type=SearchFieldDataType.String, searchable=True
    ),
    SearchField(
        name="document_date",
        type=SearchFieldDataType.String,
        filterable=True,
        sortable=True,
    ),
    SearchField(
        name="text_document_id",
        type=SearchFieldDataType.String,
        filterable=True,
    ),
    SearchField(
        name="image_document_id",
        type=SearchFieldDataType.String,
        filterable=True,
    ),
    SearchField(
        name="content_text",
        type=SearchFieldDataType.String,
        searchable=True,
    ),
    SearchField(
        name="content_embedding",
        type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
        vector_search_dimensions=app_config.embedding_dimensions,
        vector_search_profile_name="HnswProfile",
        searchable=True,
    ),
    SearchField(
        name="content_path",
        type=SearchFieldDataType.String,
        searchable=False,
    ),
    SearchField(
        name="security_groups",
        type=SearchFieldDataType.Collection(SearchFieldDataType.String),
        filterable=True,
        searchable=False,
    ),
]

vector_search = VectorSearch(
    profiles=[
        VectorSearchProfile(
            name="HnswProfile",
            algorithm_configuration_name="Hnsw",
            vectorizer_name="OpenAI",
        )
    ],
    algorithms=[HnswAlgorithmConfiguration(name="Hnsw")],
    vectorizers=[
        AzureOpenAIVectorizer(
            vectorizer_name="OpenAI",
            kind="azureOpenAI",
            parameters=AzureOpenAIVectorizerParameters(
                resource_url=os.getenv("AZURE_FOUNDRY_ENDPOINT"),
                model_name=app_config.embedding_deployed_model,
                deployment_name=app_config.embedding_deployed_model,
            ),
        )
    ],
)

semantic_config = SemanticConfiguration(
    name=semantic_config_name,
    prioritized_fields=SemanticPrioritizedFields(
        title_field=SemanticField(field_name="document_title"),
        content_fields=[SemanticField(field_name="content_text")],
        keywords_fields=[SemanticField(field_name="content_text")],
    ),
)
semantic_search_settings = SemanticSearch(configurations=[semantic_config])

index = SearchIndex(
    name=index_name,
    fields=fields,
    vector_search=vector_search,
    semantic_search=semantic_search_settings,
)
index_client.create_or_update_index(index)

logger.info("%s created or updated", index_name)
