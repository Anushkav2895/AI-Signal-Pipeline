"""
Canonical data schemas for the AI Signal / GraphOne intelligence pipeline.

These map 1:1 to the "Expected Schemas" section of the demo task brief.
Every record produced anywhere in the pipeline (scrapers, LLM extraction
layer, entity resolver) must validate against one of these before it is
allowed to be written to storage or to the output sheet. This is the
single source of truth for "shape of a record" in the whole codebase.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator

SCHEMA_VERSION = "1.0"


# --------------------------------------------------------------------------
# Shared sub-objects
# --------------------------------------------------------------------------

class Source(BaseModel):
    name: str = Field(..., description="Name of the source site, e.g. 'TechCrunch'")
    url: str = Field(..., description="Original source URL the record was extracted from")

    @field_validator("url")
    @classmethod
    def url_must_be_http(cls, v: str) -> str:
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError(f"source.url must be an absolute http(s) URL, got: {v}")
        return v


class RecordType(str, Enum):
    STARTUP = "STARTUP"
    PRODUCT = "PRODUCT"
    RESEARCH_PAPER = "RESEARCH_PAPER"
    JOB = "JOB"
    NEWS = "NEWS"  # not in the original table but needed for the News tab


class PricingModel(str, Enum):
    FREE = "FREE"
    FREEMIUM = "FREEMIUM"
    PAID = "PAID"
    ENTERPRISE = "ENTERPRISE"


def utcnow_iso() -> str:
    """ISO-8601 timestamp in UTC, e.g. 2026-09-11T13:45:00Z"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------
# Startup
# --------------------------------------------------------------------------

class StartupContentData(BaseModel):
    employeeCount: Optional[int] = Field(
        default=None, description="Number of employees (if available)"
    )


class StartupContent(BaseModel):
    entityName: str = Field(..., description="Canonical startup name")
    data: StartupContentData = Field(default_factory=StartupContentData)


class StartupEntity(BaseModel):
    schemaVersion: str = SCHEMA_VERSION
    recordType: RecordType = RecordType.STARTUP
    source: Source
    content: StartupContent
    collectedAt: str = Field(default_factory=utcnow_iso)


# --------------------------------------------------------------------------
# Product
# --------------------------------------------------------------------------

class ProductContent(BaseModel):
    startupName: str = Field(..., description="Canonical startup name this product belongs to")
    pricingModel: Optional[PricingModel] = None


class ProductEntity(BaseModel):
    schemaVersion: str = SCHEMA_VERSION
    recordType: RecordType = RecordType.PRODUCT
    source: Source
    content: ProductContent
    collectedAt: str = Field(default_factory=utcnow_iso)


# --------------------------------------------------------------------------
# Research Paper
# --------------------------------------------------------------------------

class ResearchPaperContent(BaseModel):
    title: str
    authors: list[str] = Field(default_factory=list)
    paper_url: str
    github_url: Optional[str] = None
    github_stars: Optional[int] = None
    published_date: str  # ISO-8601


class ResearchPaperEntity(BaseModel):
    schemaVersion: str = SCHEMA_VERSION
    recordType: RecordType = RecordType.RESEARCH_PAPER
    source: Source
    content: ResearchPaperContent
    collectedAt: str = Field(default_factory=utcnow_iso)


# --------------------------------------------------------------------------
# Job
# --------------------------------------------------------------------------

class JobContent(BaseModel):
    company: str = Field(..., description="Canonical company name")
    date: str  # ISO-8601 publication date
    is_remote: bool = False
    role_family: str = Field(..., description="e.g. 'Engineering', 'Research', 'Product'")
    title: Optional[str] = None
    job_url: Optional[str] = None


class JobEntity(BaseModel):
    schemaVersion: str = SCHEMA_VERSION
    recordType: RecordType = RecordType.JOB
    source: Source
    content: JobContent
    collectedAt: str = Field(default_factory=utcnow_iso)


# --------------------------------------------------------------------------
# News (not in the brief's table, but required for the "News" output tab)
# --------------------------------------------------------------------------

class NewsContent(BaseModel):
    title: str
    full_text: str
    published_date: str  # ISO-8601, normalized
    article_url: str


class NewsEntity(BaseModel):
    schemaVersion: str = SCHEMA_VERSION
    recordType: RecordType = RecordType.NEWS
    source: Source
    content: NewsContent
    collectedAt: str = Field(default_factory=utcnow_iso)


# --------------------------------------------------------------------------
# Entity resolution log row (for the "Entity Mapping Log" tab)
# --------------------------------------------------------------------------

class EntityMappingLogRow(BaseModel):
    raw_name: str
    canonical_name: str
    match_method: str  # e.g. "exact", "alias_table", "fuzzy:0.92", "llm"
    confidence: float
    source_url: Optional[str] = None
