"""Azure AI Search indexer and skillset setup.

Creates or updates the data source, skillset, and indexer for processing
documents. Includes skills for document extraction, text chunking, embeddings,
image verbalization, and document-level security group lookup.
"""

import logging
import os
import time

from azure.search.documents.indexes.models import (
    AzureOpenAIEmbeddingSkill,
    ChatCompletionSkill,
    DocumentExtractionSkill,
    FieldMapping,
    IndexingSchedule,
    IndexProjectionMode,
    InputFieldMappingEntry,
    OutputFieldMappingEntry,
    SearchIndexer,
    SearchIndexerDataContainer,
    SearchIndexerDataSourceConnection,
    SearchIndexerIndexProjection,
    SearchIndexerIndexProjectionSelector,
    SearchIndexerIndexProjectionsParameters,
    SearchIndexerSkillset,
    ShaperSkill,
    SplitSkill,
    WebApiSkill,
)

from raglib.clients import (
    get_project_names,
    get_search_index_client,
    get_search_indexer_client,
    load_env_vars,
)
from raglib.config import config
from raglib.log import configure_logging
from raglib.prompts.markdown_loader import markdown_loader

logger = logging.getLogger(__name__)

configure_logging()
prompt_verbalisation_image = markdown_loader("prompt_verbalisation_image")

load_env_vars()
index_name, semantic_config_name = get_project_names()
data_source_name = f"{index_name}-datasource"
skillset_name = f"{index_name}-skillset"
indexer_name = f"{index_name}-indexer"

index_client = get_search_index_client()
indexer_client = get_search_indexer_client()

container = SearchIndexerDataContainer(name=os.getenv("DOCUMENTS_FILESYSTEM_NAME"))
data_source_connection = SearchIndexerDataSourceConnection(
    name=data_source_name,
    type="adlsgen2",
    connection_string=os.getenv("STORAGE_CONNECTION_STRING"),
    container=container,
)
data_source = indexer_client.create_or_update_data_source_connection(
    data_source_connection
)

logger.info("%s created or updated", data_source_name)

skill_document_extraction = DocumentExtractionSkill(
    name="document-extraction-skill",
    description="Document extraction skill to extract text and images from documents",
    context="/document",
    parsing_mode="default",
    data_to_extract="contentAndMetadata",
    configuration={
        "imageAction": "generateNormalizedImages",
        "normalizedImageMaxWidth": 2000,
        "normalizedImageMaxHeight": 2000,
    },
    inputs=[InputFieldMappingEntry(name="file_data", source="/document/file_data")],
    outputs=[
        OutputFieldMappingEntry(name="content", target_name="extracted_content"),
        OutputFieldMappingEntry(
            name="normalized_images", target_name="normalized_images"
        ),
    ],
)

skill_split = SplitSkill(
    name="split-skill",
    description="Split skill to chunk documents",
    text_split_mode="pages",
    context="/document",
    maximum_page_length=config.chunk_size,
    page_overlap_length=config.chunk_overlap,
    inputs=[InputFieldMappingEntry(name="text", source="/document/extracted_content")],
    outputs=[OutputFieldMappingEntry(name="textItems", target_name="pages")],
)

skill_text_embedding = AzureOpenAIEmbeddingSkill(
    name="text-embedding-skill",
    description="Embedding skill for text",
    context="/document/pages/*",
    inputs=[InputFieldMappingEntry(name="text", source="/document/pages/*")],
    outputs=[OutputFieldMappingEntry(name="embedding", target_name="text_vector")],
    resource_url=os.getenv("AZURE_FOUNDRY_ENDPOINT"),
    model_name=config.embedding_deployed_model,
    deployment_name=config.embedding_deployed_model,
    dimensions=config.embedding_dimensions,
)

skill_genai_prompt = ChatCompletionSkill(
    name="genAI-prompt-skill",
    description="GenAI Prompt skill for image verbalization",
    uri=f"{os.getenv('AZURE_FOUNDRY_ENDPOINT')}/openai/deployments/{config.large_deployed_model}/chat/completions?api-version={os.getenv('AZURE_FOUNDRY_API_VERSION')}",
    context="/document/normalized_images/*",
    inputs=[
        InputFieldMappingEntry(name="systemMessage", source=prompt_verbalisation_image),
        InputFieldMappingEntry(
            name="userMessage", source="='Please describe this image.'"
        ),
        InputFieldMappingEntry(
            name="image", source="/document/normalized_images/*/data"
        ),
    ],
    outputs=[OutputFieldMappingEntry(name="response", target_name="verbalizedImage")],
)

skill_verbalized_embedding = AzureOpenAIEmbeddingSkill(
    name="verbalized-image-embedding-skill",
    description="Embedding skill for verbalized images",
    context="/document/normalized_images/*",
    inputs=[
        InputFieldMappingEntry(
            name="text", source="/document/normalized_images/*/verbalizedImage"
        )
    ],
    outputs=[
        OutputFieldMappingEntry(name="embedding", target_name="verbalizedImage_vector")
    ],
    resource_url=os.getenv("AZURE_FOUNDRY_ENDPOINT"),
    model_name=config.embedding_deployed_model,
    deployment_name=config.embedding_deployed_model,
    dimensions=config.embedding_dimensions,
)

skill_shaper = ShaperSkill(
    name="shaper-skill",
    description="Shaper skill to reshape the data to fit the index schema",
    context="/document/normalized_images/*",
    inputs=[
        InputFieldMappingEntry(
            name="normalized_images", source="/document/normalized_images/*"
        ),
        InputFieldMappingEntry(
            name="imagePath",
            source="='{{imageProjectionContainer}}/'+$(/document/normalized_images/*/imagePath)",
        ),
    ],
    outputs=[
        OutputFieldMappingEntry(name="output", target_name="new_normalized_images")
    ],
)

skill_security_groups = WebApiSkill(
    name="security-groups-skill",
    description="Look up security groups for document from external service",
    context="/document",
    uri=os.getenv("AZURE_FUNCTION_SECURITY_GROUPS_URL"),
    http_method="POST",
    auth_resource_id=os.getenv("AZURE_FUNCTION_AUTH_RESOURCE_ID"),
    timeout="PT10S",
    batch_size=1,
    inputs=[
        InputFieldMappingEntry(
            name="document_name", source="/document/metadata_storage_name"
        )
    ],
    outputs=[
        OutputFieldMappingEntry(
            name="security_groups", target_name="security_groups_array"
        )
    ],
)

skills = [
    skill_document_extraction,
    skill_split,
    skill_text_embedding,
    skill_genai_prompt,
    skill_verbalized_embedding,
    skill_shaper,
    skill_security_groups,
]

index_projections = SearchIndexerIndexProjection(
    selectors=[
        SearchIndexerIndexProjectionSelector(
            target_index_name=index_name,
            parent_key_field_name="text_document_id",
            source_context="/document/pages/*",
            mappings=[
                InputFieldMappingEntry(
                    name="content_embedding", source="/document/pages/*/text_vector"
                ),
                InputFieldMappingEntry(name="content_text", source="/document/pages/*"),
                InputFieldMappingEntry(
                    name="document_title", source="/document/document_title"
                ),
                InputFieldMappingEntry(
                    name="document_date", source="/document/metadata_creation_date"
                ),
                InputFieldMappingEntry(
                    name="security_groups", source="/document/security_groups_array"
                ),
            ],
        ),
        SearchIndexerIndexProjectionSelector(
            target_index_name=index_name,
            parent_key_field_name="image_document_id",
            source_context="/document/normalized_images/*",
            mappings=[
                InputFieldMappingEntry(
                    name="content_text",
                    source="/document/normalized_images/*/verbalizedImage",
                ),
                InputFieldMappingEntry(
                    name="content_embedding",
                    source="/document/normalized_images/*/verbalizedImage_vector",
                ),
                InputFieldMappingEntry(
                    name="document_title", source="/document/document_title"
                ),
                InputFieldMappingEntry(
                    name="document_date", source="/document/metadata_creation_date"
                ),
                InputFieldMappingEntry(
                    name="content_path",
                    source="/document/normalized_images/*/new_normalized_images/imagePath",
                ),
                InputFieldMappingEntry(
                    name="security_groups", source="/document/security_groups_array"
                ),
            ],
        ),
    ],
    parameters=SearchIndexerIndexProjectionsParameters(
        projection_mode=IndexProjectionMode.SKIP_INDEXING_PARENT_DOCUMENTS
    ),
)

skillset = SearchIndexerSkillset(
    name=skillset_name,
    description="Skillset to chunk documents and generating embeddings",
    skills=skills,
    index_projection=index_projections,
)
indexer_client.create_or_update_skillset(skillset)

logger.info("%s created or updated", skillset.name)

indexer_parameters = {
    "configuration": {
        "allowSkillsetToReadFileData": True,  # to enable image handleing in skillset
        # Enable private skillset execution with:
        # "executionEnvironment": "private"
    }
}
schedule_indexer = IndexingSchedule(interval="P1D")
indexer = SearchIndexer(
    name=indexer_name,
    description="Indexer to index documents and generate embeddings",
    skillset_name=skillset_name,
    target_index_name=index_name,
    data_source_name=data_source_name,
    field_mappings=[
        FieldMapping(
            source_field_name="metadata_storage_name",
            target_field_name="document_title",
        ),
        FieldMapping(
            source_field_name="metadata_creation_date",
            target_field_name="document_date",
        ),
    ],
    parameters=indexer_parameters,
    schedule=schedule_indexer,
)
indexer_result = indexer_client.create_or_update_indexer(indexer)

logger.info("%s created or updated", indexer_name)

# run indexer and poll for document count to confirm indexing has started
RUN_INDEXER = True
INDEXER_RETRY_COUNT = 10
INDEXER_RETRY_INTERVAL = 2

document_count = 0
if RUN_INDEXER:
    indexer_client.run_indexer(indexer_name)
    while document_count == 0 and INDEXER_RETRY_COUNT > 0:
        time.sleep(INDEXER_RETRY_INTERVAL)
        document_count = index_client.get_search_client(index_name).get_document_count()
        updated_log_message = (
            "Documents have started loading into the index. "
            f"Current count: {document_count}."
        )
        INDEXER_RETRY_COUNT -= 1

    logger.info(updated_log_message)
