"""Staging area models."""

from enum import Enum

from pydantic import BaseModel, Field


class StagingType(str, Enum):
    """Supported staging area types."""

    S3 = "s3"
    ADLS = "adls"
    GCS = "gcs"
    INTERNAL = "internal"


class StagingArea(BaseModel):
    """A preconfigured staging area."""

    id: str
    name: str = Field(..., min_length=1)
    type: StagingType
    path: str = Field(..., description="Display path (read-only)")
    available: bool = True
    description: str = ""

    @property
    def type_icon(self) -> str:
        """Return icon/emoji for staging type."""
        icons = {
            StagingType.S3: "S3",
            StagingType.ADLS: "ADLS",
            StagingType.GCS: "GCS",
            StagingType.INTERNAL: "@",
        }
        return icons.get(self.type, "?")

    @property
    def type_display(self) -> str:
        """Human-readable type name."""
        names = {
            StagingType.S3: "AWS S3",
            StagingType.ADLS: "Azure Data Lake",
            StagingType.GCS: "Google Cloud Storage",
            StagingType.INTERNAL: "Snowflake Internal Stage",
        }
        return names.get(self.type, self.type.value)
