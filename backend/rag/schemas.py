"""
Shared type definitions for the RAG pipeline.
"""

from typing import Literal

try:
    from typing import TypedDict
except ImportError:
    from typing_extensions import TypedDict


class ImageChunkMetadata(TypedDict):
    chunk_type: Literal["image_description"]
    source_image_key: str     # storage path: documents/{user_id}/{filename}
    media_type: str           # image/jpeg, image/png, etc.
    original_filename: str    # for Phase 2 prompt context
    vision_model: str         # model that generated this — enables re-indexing queries
    description_length: int   # quick quality signal without re-fetching text
