
# api/models.py - The Single Source of Truth for all Pydantic Models

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
# --- Analytics & Exports (restored) ---
class ExportRequest(BaseModel):
    export_type: str
    format: str = "csv"
    date_range: Optional[str] = "30d"
    start_date: Optional[Any] = None
    end_date: Optional[Any] = None
    filters: Optional[Dict[str, Any]] = None
    sort_by: Optional[str] = "created_at"
    sort_order: str = "desc"
    limit: Optional[int] = None
    include_columns: Optional[List[str]] = None
    exclude_columns: Optional[List[str]] = None

class AnalyticsJobRequest(BaseModel):
    job_type: str
    parameters: Dict[str, Any]
    job_name: Optional[str] = None
    priority: int = 10
    notification_email: Optional[str] = None
    retention_days: int = 7
# --- Core Response Model ---
class APIResponse(BaseModel):
    status: str = "success"
    data: Optional[Any] = None
    message: Optional[str] = None
class KillSwitchRequest(BaseModel):
    analysisType: str  # 'code' | 'file' | 'url' | 'prompt'
    code: str
    filename: Optional[str] = None

# --- Prompt Management ---
class SavePromptRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=100, description="Prompt title")
    body: str = Field(..., min_length=1, description="Prompt content")
    role: str = Field(..., min_length=1, max_length=100, description="Prompt role")
    category: Optional[str] = Field(default="general", description="Prompt category")
    tags: Optional[List[str]] = Field(default_factory=list, description="Prompt tags")
    is_public: Optional[bool] = Field(default=False, description="Public visibility")
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "Email Assistant",
                "body": "You are a helpful assistant. Write a {type} email about {topic}.",
                "role": "assistant",
                "category": "business",
                "tags": ["email", "business"],
                "is_public": False
            }
        }

class UpdatePromptRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=100)
    body: str = Field(..., min_length=1)
    role: Optional[str] = Field(None, min_length=1, max_length=100)

class TestDriveByIdRequest(BaseModel):
    prompt_id: str
    inputs: Dict[str, Any] = {}

# --- AI Features ---
class RemixRequest(BaseModel):
    prompt_body: str = Field(..., min_length=1, description="Text to remix")
    style: Optional[str] = Field(default="professional", description="Writing style")
    target_audience: Optional[str] = Field(default="general", description="Target audience")
    enhancement_level: Optional[str] = Field(default="medium", description="Enhancement level")
    
    class Config:
        json_schema_extra = {
            "example": {
                "prompt_body": "Write an email about project updates",
                "style": "professional",
                "target_audience": "team members",
                "enhancement_level": "medium"
            }
        }

class FusionRequest(BaseModel):
    prompt_a: str
    prompt_b: str

class AnalyzeRequest(BaseModel):
    content: str = Field(..., alias="code") # Alias for compatibility
    content_type: str = Field(..., alias="analysisType")
    filename: Optional[str] = None

class ArchitectRequest(BaseModel):
    description: str
    tech_stack: List[str] = Field(..., alias="techStack")
    architecture_style: str = Field(..., alias="architectureStyle")

# --- Marketplace & Ratings ---
class MarketplaceListingRequest(BaseModel):
    prompt_id: str
    price_credits: int
    description: str
    tags: List[str] = []

class MarketplacePurchaseRequest(BaseModel):
    listing_id: str

class PromptRatingRequest(BaseModel):
    prompt_id: str
    rating: int = Field(..., ge=1, le=5)
    review_title: Optional[str] = Field(None, max_length=100)
    review_content: Optional[str] = None
    pros: List[str] = []
    cons: List[str] = []
    would_recommend: bool = True

# --- User Management ---
class PreferencesModel(BaseModel):
    theme: Optional[str] = None
    notifications: Optional[bool] = None

# --- Packaging ---
class PackageCreateRequest(BaseModel):
    marketplace_ready: bool = False
    sales_copy: Optional[str] = None
    tags: Optional[List[str]] = []
    price_usd: Optional[float] = None
    sales_title: Optional[str] = None

class PackageManagementRequest(BaseModel):
    action: str
    package_ids: List[str]
    new_price: Optional[float] = None
    bulk_tags: Optional[List[str]] = None

# --- Partnerships ---
class PartnershipApplicationRequest(BaseModel):
    business_type: str
    use_case: str
    expected_monthly_volume: int
    company_name: Optional[str] = None
    website_url: Optional[str] = None
    portfolio_urls: Optional[List[str]] = None

class PartnerDashboardRequest(BaseModel):
    timeframe: Optional[str] = "30d"
    include_analytics: Optional[bool] = True
    include_revenue: Optional[bool] = True
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class PartnerRevenueRequest(BaseModel):
    action: str
    payout_amount: Optional[float] = None
    payment_method: Optional[Dict[str, Any]] = None
    statement_period: Optional[str] = None

# --- Projects ---
class ProjectCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None

class ProjectUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class ProjectPromptRequest(BaseModel):
    action: str
    prompt_ids: List[str]
    order_positions: Optional[Dict[str, int]] = None


# --- Upgrade API Models (for v2/upgrade endpoint) ---
from pydantic import ConfigDict

class UpgradeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=16000)
    mode: str = "free"
    client: str = "unknown"
    intent: str = "unknown"
    meta: Optional[dict] = None
    explain: Optional[bool] = False
    model_config = ConfigDict(populate_by_name=True)

class UpgradeResponse(BaseModel):
    upgraded: str
    matched_pipeline: str
    engine_version: str
    plan: Optional[List[str]] = None
    diffs: Optional[str] = None
    fidelity_score: Optional[float] = None
    matched_entries: Optional[List[str]] = None
    message: Optional[str] = None

# Pydantic v2: finalize models for forward refs
UpgradeRequest.model_rebuild()
UpgradeResponse.model_rebuild()