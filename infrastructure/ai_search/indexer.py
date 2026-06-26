"""Azure AI Search indexer and skillset setup.

Creates or updates the data source, skillset, and indexer for processing
documents. Includes skills for document extraction, text chunking, embeddings,
image verbalization, and document-level security group lookup.
"""

import os
import time

from azure.search.documents.indexes.models import (
    AzureOpenAIEmbeddingSkill,
    ChatCompletionSkill,
    DocumentExtractionSkill,
    FieldMapping,
    FieldMappingFunction,
    IndexingSchedule,
    IndexProjectionMode,
    InputFieldMappingEntry,
    NativeBlobSoftDeleteDeletionDetectionPolicy,
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

from raglib.config import (
    get_search_index_client,
    get_search_indexer_client,
    get_project_names,
    load_env_vars,
)
from raglib.log import log_message
from raglib.prompts.markdown_loader import markdown_loader

prompt_verbalisation_image = markdown_loader("prompt_verbalisation_image")

load_env_vars()
index_name, semantic_config_name = get_project_names()
data_source_name = f"{index_name}-datasource"
skillset_name = f"{index_name}-skillset"
indexer_name = f"{index_name}-indexer"

index_client = get_search_index_client()
indexer_client = get_search_indexer_client()

log_enabled = True
print_log_enabled = True
log_tag = "setup_indexer"
start_timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

container = SearchIndexerDataContainer(
    name=os.getenv("BLOB_CONTAINER_NAME_DOCUMENTS")
)
data_source_connection = SearchIndexerDataSourceConnection(
    name=data_source_name,
    type="azureblob",
    connection_string=os.getenv("BLOB_CONNECTION_STRING"),
    container=container,
    data_deletion_detection_policy=NativeBlobSoftDeleteDeletionDetectionPolicy()
)
data_source = indexer_client.create_or_update_data_source_connection(data_source_connection)

properties = {
    'tag': log_tag,
    'start_timestamp': start_timestamp,
    'end_timestamp': time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
}
log_message(
    should_log=log_enabled,
    print_message=print_log_enabled,
    message=f"{data_source_name} created or updated",
    level=20,
    additional_properties=properties
)

skill_document_extraction = DocumentExtractionSkill(
    name="document-extraction-skill",
    description="Document extraction skill to extract text and images from documents",
    context="/document",
    parsing_mode="default",
    data_to_extract="contentAndMetadata",
    configuration={
        "imageAction": "generateNormalizedImages",
        "normalizedImageMaxWidth": 2000,
        "normalizedImageMaxHeight": 2000
    },
    inputs=[
        InputFieldMappingEntry(name="file_data", source="/document/file_data")
    ],
    outputs=[
        OutputFieldMappingEntry(name="content", target_name="extracted_content"),
        OutputFieldMappingEntry(name="normalized_images", target_name="normalized_images")
    ]
)

skill_split = SplitSkill(
    name="split-skill",
    description="Split skill to chunk documents",
    text_split_mode="pages",
    context="/document",
    maximum_page_length=int(os.getenv('PARAMETER_CHUNK_SIZE', '1000')),
    page_overlap_length=int(os.getenv('PARAMETER_CHUNK_OVERLAP', '100')),
    inputs=[
        InputFieldMappingEntry(name="text", source="/document/extracted_content")
    ],
    outputs=[
        OutputFieldMappingEntry(name="textItems", target_name="pages")
    ]
)

skill_text_embedding = AzureOpenAIEmbeddingSkill(
    name="text-embedding-skill",
    description="Embedding skill for text",
    context="/document/pages/*",
    inputs=[
        InputFieldMappingEntry(name="text", source="/document/pages/*")
    ],
    outputs=[
        OutputFieldMappingEntry(name="embedding", target_name="text_vector")
    ],
    resource_url=os.getenv("AZURE_FOUNDRY_ENDPOINT"),
    model_name=os.getenv("AZURE_FOUNDRY_EMBEDDING_DEPLOYED_MODEL"),
    deployment_name=os.getenv("AZURE_FOUNDRY_EMBEDDING_DEPLOYED_MODEL"),
    dimensions=int(os.getenv("AZURE_FOUNDRY_EMBEDDING_DIMENSIONS", "3072"))
)

skill_genai_prompt = ChatCompletionSkill(
    name="genAI-prompt-skill",
    description="GenAI Prompt skill for image verbalization",
    uri=f'{os.getenv("AZURE_FOUNDRY_ENDPOINT")}/openai/deployments/{os.getenv("AZURE_FOUNDRY_LARGE_DEPLOYED_MODEL")}/chat/completions?api-version={os.getenv("AZURE_FOUNDRY_API_VERSION")}',
    context="/document/normalized_images/*",
    inputs=[
        InputFieldMappingEntry(name="systemMessage", source=prompt_verbalisation_image),
        InputFieldMappingEntry(name="userMessage", source="='Please describe this image.'"),
        InputFieldMappingEntry(name="image", source="/document/normalized_images/*/data")
    ],
    outputs=[
        OutputFieldMappingEntry(name="response", target_name="verbalizedImage")
    ]
)

skill_verbalized_embedding = AzureOpenAIEmbeddingSkill(
    name="verbalized-image-embedding-skill",
    description="Embedding skill for verbalized images",
    context="/document/normalized_images/*",
    inputs=[
        InputFieldMappingEntry(name="text", source="/document/normalized_images/*/verbalizedImage")
    ],
    outputs=[
        OutputFieldMappingEntry(name="embedding", target_name="verbalizedImage_vector")
    ],
    resource_url=os.getenv("AZURE_FOUNDRY_ENDPOINT"),
    model_name=os.getenv("AZURE_FOUNDRY_EMBEDDING_DEPLOYED_MODEL"),
    deployment_name=os.getenv("AZURE_FOUNDRY_EMBEDDING_DEPLOYED_MODEL"),
    dimensions=int(os.getenv("AZURE_FOUNDRY_EMBEDDING_DIMENSIONS", "3072"))
)

skill_shaper = ShaperSkill(
    name="shaper-skill",
    description="Shaper skill to reshape the data to fit the index schema",
    context="/document/normalized_images/*",
    inputs=[
        InputFieldMappingEntry(name="normalized_images", source="/document/normalized_images/*"),
        InputFieldMappingEntry(name="imagePath", source="='{{imageProjectionContainer}}/'+$(/document/normalized_images/*/imagePath)"),
        InputFieldMappingEntry(
            name="location_metadata",
            source_context="/document/normalized_images/*",
            inputs=[
                InputFieldMappingEntry(name="page_number", source="/document/normalized_images/*/pageNumber"),
                InputFieldMappingEntry(name="bounding_polygons", source="/document/normalized_images/*/boundingPolygon")
            ]
        )
    ],
    outputs=[
        OutputFieldMappingEntry(name="output", target_name="new_normalized_images")
    ]
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
        InputFieldMappingEntry(name="document_name", source="/document/metadata_storage_name")
    ],
    outputs=[
        OutputFieldMappingEntry(name="security_groups", target_name="security_groups_array")
    ]
)

skills = [
    skill_document_extraction,
    skill_split,
    skill_text_embedding,
    skill_genai_prompt,
    skill_verbalized_embedding,
    skill_shaper,
    skill_security_groups
]

index_projections = SearchIndexerIndexProjection(
    selectors=[
        SearchIndexerIndexProjectionSelector(
            target_index_name=index_name,
            parent_key_field_name="text_document_id",
            source_context="/document/pages/*",
            mappings=[
                InputFieldMappingEntry(name="content_embedding", source="/document/pages/*/text_vector"),
                InputFieldMappingEntry(name="content_text", source="/document/pages/*"),
                InputFieldMappingEntry(name="document_title", source="/document/document_title"),
                InputFieldMappingEntry(name="document_date", source="/document/metadata_creation_date"),
                InputFieldMappingEntry(name="security_groups", source="/document/security_groups_array"),
            ]
        ),
        SearchIndexerIndexProjectionSelector(
            target_index_name=index_name,
            parent_key_field_name="image_document_id",
            source_context="/document/normalized_images/*",
            mappings=[
                InputFieldMappingEntry(name="content_text", source="/document/normalized_images/*/verbalizedImage"),
                InputFieldMappingEntry(name="content_embedding", source="/document/normalized_images/*/verbalizedImage_vector"),
                InputFieldMappingEntry(name="document_title", source="/document/document_title"),
                InputFieldMappingEntry(name="document_date", source="/document/metadata_creation_date"),
                InputFieldMappingEntry(name="content_path", source="/document/normalized_images/*/new_normalized_images/imagePath"),
                InputFieldMappingEntry(name="location_metadata", source="/document/normalized_images/*/new_normalized_images/location_metadata"),
                InputFieldMappingEntry(name="security_groups", source="/document/security_groups_array"),
            ]
        )
    ],
    parameters=SearchIndexerIndexProjectionsParameters(
        projection_mode=IndexProjectionMode.SKIP_INDEXING_PARENT_DOCUMENTS
    ),
)

skillset = SearchIndexerSkillset(
    name=skillset_name,
    description="Skillset to chunk documents and generating embeddings",
    skills=skills,
    index_projection=index_projections
)
indexer_client.create_or_update_skillset(skillset)

properties = {
    'tag': log_tag,
    'start_timestamp': start_timestamp,
    'end_timestamp': time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
}
log_message(
    should_log=log_enabled,
    print_message=print_log_enabled,
    message=f"{skillset.name} created or updated",
    level=20,
    additional_properties=properties
)

indexer_parameters = {
    "configuration": {
        "allowSkillsetToReadFileData": True
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
        FieldMapping(source_field_name="metadata_storage_name", target_field_name="document_title"),
        FieldMapping(source_field_name="metadata_creation_date", target_field_name="document_date")
    ],
    parameters=indexer_parameters,
    schedule=schedule_indexer
)
indexer_result = indexer_client.create_or_update_indexer(indexer)

properties = {
    'tag': log_tag,
    'start_timestamp': start_timestamp,
    'end_timestamp': time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
}
log_message(
    should_log=log_enabled,
    print_message=print_log_enabled,
    message=f"{indexer_name} created or updated",
    level=20,
    additional_properties=properties
)

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
        updated_log_message = f"Documents have started loading into the index. Current count: {document_count}."
        INDEXER_RETRY_COUNT -= 1

    properties = {
        'tag': log_tag,
        'start_timestamp': start_timestamp,
        'end_timestamp': time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    }
    log_message(
        should_log=log_enabled,
        print_message=print_log_enabled,
        message=updated_log_message,
        level=20,
        additional_properties=properties
    )
