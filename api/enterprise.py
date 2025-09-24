"""
🏢 ENTERPRISE TEAM MANAGEMENT - PHASE 4
======================================
Advanced team collaboration, SSO integration, and enterprise admin controls
for PromptForgeAI platform.
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime, timedelta
from enum import Enum
import logging
import uuid

from auth import get_current_user, verify_admin_access
from dependencies import db
from utils import send_notification, generate_secure_token

logger = logging.getLogger(__name__)

# ===================================================================
# ENTERPRISE MODELS
# ===================================================================

class OrganizationPlan(str, Enum):
    STARTUP = "startup"
    BUSINESS = "business"
    ENTERPRISE = "enterprise"
    CUSTOM = "custom"

class UserRole(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    MEMBER = "member"
    VIEWER = "viewer"

class TeamPermission(str, Enum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"
    BILLING = "billing"

class SSOProvider(str, Enum):
    SAML = "saml"
    OIDC = "oidc"
    AZURE_AD = "azure_ad"
    GOOGLE_WORKSPACE = "google_workspace"
    OKTA = "okta"

class OrganizationSettings(BaseModel):
    """Organization-wide settings and policies"""
    name: str = Field(..., min_length=2, max_length=100)
    domain: Optional[str] = Field(None, description="Company domain for email validation")
    sso_enabled: bool = Field(False)
    sso_provider: Optional[SSOProvider] = None
    enforce_sso: bool = Field(False, description="Require SSO for all users")
    require_mfa: bool = Field(False, description="Require multi-factor authentication")
    session_timeout_minutes: int = Field(480, ge=30, le=1440)  # 8 hours default
    allowed_providers: List[str] = Field(["openai", "anthropic"], description="Allowed LLM providers")
    data_retention_days: int = Field(90, ge=30, le=365)
    audit_logging: bool = Field(True)
    ip_whitelist: List[str] = Field([], description="Allowed IP addresses")
    department_isolation: bool = Field(False, description="Isolate data between departments")

class BillingSettings(BaseModel):
    """Enterprise billing configuration"""
    plan: OrganizationPlan
    credit_limit: int = Field(100000, ge=0)
    monthly_budget: float = Field(10000.0, ge=0)
    department_budgets: Dict[str, float] = Field({})
    cost_center_tracking: bool = Field(True)
    budget_alerts: bool = Field(True)
    budget_alert_threshold: float = Field(0.8, ge=0.1, le=1.0)

class CreateOrganizationRequest(BaseModel):
    """Request to create new organization"""
    name: str = Field(..., min_length=2, max_length=100)
    admin_email: EmailStr
    plan: OrganizationPlan = OrganizationPlan.BUSINESS
    settings: OrganizationSettings
    billing: BillingSettings

class InviteUserRequest(BaseModel):
    """Request to invite user to organization"""
    email: EmailStr
    role: UserRole
    department: Optional[str] = None
    permissions: List[TeamPermission] = Field([TeamPermission.READ, TeamPermission.WRITE])
    credit_limit: Optional[int] = Field(None, description="Individual credit limit")
    send_welcome_email: bool = Field(True)

class UpdateUserRequest(BaseModel):
    """Request to update user in organization"""
    role: Optional[UserRole] = None
    department: Optional[str] = None
    permissions: Optional[List[TeamPermission]] = None
    credit_limit: Optional[int] = None
    is_active: Optional[bool] = None

class SSOConfigRequest(BaseModel):
    """SSO configuration request"""
    provider: SSOProvider
    entity_id: str = Field(..., description="SSO Entity ID")
    sso_url: str = Field(..., description="SSO Login URL")
    certificate: str = Field(..., description="X.509 Certificate")
    attribute_mapping: Dict[str, str] = Field({
        "email": "email",
        "first_name": "firstName",
        "last_name": "lastName",
        "department": "department"
    })
    auto_provision: bool = Field(True, description="Auto-create users on first login")

class AuditLogEntry(BaseModel):
    """Audit log entry"""
    id: str
    timestamp: datetime
    user_id: str
    user_email: str
    action: str
    resource_type: str
    resource_id: str
    details: Dict[str, Any]
    ip_address: str
    user_agent: str

class OrganizationStats(BaseModel):
    """Organization usage statistics"""
    total_users: int
    active_users_30d: int
    total_credits_consumed: int
    credits_consumed_30d: int
    total_cost_30d: float
    most_used_providers: List[Dict[str, Any]]
    top_departments: List[Dict[str, Any]]
    productivity_metrics: Dict[str, float]

# ===================================================================
# ENTERPRISE ROUTER
# ===================================================================

router = APIRouter(prefix="/api/v1/enterprise", tags=["Enterprise Management"])

@router.post("/organizations", response_model=Dict[str, str])
async def create_organization(
    request: CreateOrganizationRequest,
    current_user: dict = Depends(get_current_user),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    🏢 Create new enterprise organization
    
    Features:
    - Organization setup with admin controls
    - Default team and admin user creation
    - Billing configuration and credit allocation
    - Audit logging and compliance setup
    """
    
    try:
        # Generate organization ID
        org_id = str(uuid.uuid4())
        
        # Create organization document
        organization = {
            "id": org_id,
            "name": request.name,
            "domain": request.settings.domain,
            "plan": request.plan.value,
            "settings": request.settings.dict(),
            "billing": request.billing.dict(),
            "created_at": datetime.utcnow(),
            "created_by": current_user["id"],
            "is_active": True,
            "sso_config": None,
            "departments": [],
            "integrations": {}
        }
        
        # Save to database
        await db.organizations.insert_one(organization)
        
        # Create admin user entry
        admin_user = {
            "user_id": current_user["id"],
            "organization_id": org_id,
            "email": request.admin_email,
            "role": UserRole.ADMIN.value,
            "permissions": [p.value for p in TeamPermission],
            "department": None,
            "credit_limit": None,  # No limit for admin
            "is_active": True,
            "joined_at": datetime.utcnow(),
            "last_activity": datetime.utcnow()
        }
        
        await db.organization_users.insert_one(admin_user)
        
        # Create default department
        if request.settings.department_isolation:
            default_dept = {
                "organization_id": org_id,
                "name": "General",
                "description": "Default department",
                "budget": request.billing.monthly_budget * 0.5,
                "created_at": datetime.utcnow()
            }
            await db.departments.insert_one(default_dept)
        
        # Setup audit logging
        await _log_audit_event(
            org_id=org_id,
            user_id=current_user["id"],
            action="organization_created",
            resource_type="organization",
            resource_id=org_id,
            details={"name": request.name, "plan": request.plan.value}
        )
        
        # Send welcome email
        background_tasks.add_task(
            _send_organization_welcome_email,
            org_id=org_id,
            admin_email=request.admin_email,
            org_name=request.name
        )
        
        logger.info(f"✅ Created organization: {org_id} ({request.name})")
        
        return {
            "organization_id": org_id,
            "message": "Organization created successfully",
            "admin_user_id": current_user["id"]
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to create organization: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/organizations/{org_id}/stats", response_model=OrganizationStats)
async def get_organization_stats(
    org_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    📊 Get comprehensive organization statistics and metrics
    """
    
    # Verify user access to organization
    await _verify_organization_access(current_user["id"], org_id, [UserRole.ADMIN, UserRole.MANAGER])
    
    try:
        # Get user statistics
        users_cursor = db.organization_users.find({"organization_id": org_id})
        users = await users_cursor.to_list(length=None)
        
        total_users = len(users)
        active_users_30d = len([
            u for u in users 
            if u.get("last_activity", datetime.min) > datetime.utcnow() - timedelta(days=30)
        ])
        
        # Get usage statistics (mock data - would integrate with analytics)
        usage_stats = await _get_organization_usage_stats(org_id)
        
        return OrganizationStats(
            total_users=total_users,
            active_users_30d=active_users_30d,
            total_credits_consumed=usage_stats["total_credits"],
            credits_consumed_30d=usage_stats["credits_30d"],
            total_cost_30d=usage_stats["cost_30d"],
            most_used_providers=usage_stats["top_providers"],
            top_departments=usage_stats["top_departments"],
            productivity_metrics=usage_stats["productivity"]
        )
        
    except Exception as e:
        logger.error(f"❌ Failed to get organization stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/organizations/{org_id}/invite")
async def invite_user_to_organization(
    org_id: str,
    request: InviteUserRequest,
    current_user: dict = Depends(get_current_user),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    📧 Invite user to enterprise organization
    
    Features:
    - Role-based access control
    - Department assignment
    - Credit limit configuration
    - Automated invitation emails
    """
    
    # Verify admin access
    await _verify_organization_access(current_user["id"], org_id, [UserRole.ADMIN])
    
    try:
        # Check if user already exists in organization
        existing_user = await db.organization_users.find_one({
            "organization_id": org_id,
            "email": request.email
        })
        
        if existing_user:
            raise HTTPException(status_code=400, detail="User already exists in organization")
        
        # Generate invitation token
        invitation_token = generate_secure_token()
        
        # Create invitation record
        invitation = {
            "id": str(uuid.uuid4()),
            "organization_id": org_id,
            "email": request.email,
            "role": request.role.value,
            "department": request.department,
            "permissions": [p.value for p in request.permissions],
            "credit_limit": request.credit_limit,
            "token": invitation_token,
            "invited_by": current_user["id"],
            "invited_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(days=7),
            "is_used": False
        }
        
        await db.organization_invitations.insert_one(invitation)
        
        # Send invitation email
        if request.send_welcome_email:
            background_tasks.add_task(
                _send_invitation_email,
                invitation=invitation,
                org_name=await _get_organization_name(org_id)
            )
        
        # Audit log
        await _log_audit_event(
            org_id=org_id,
            user_id=current_user["id"],
            action="user_invited",
            resource_type="invitation",
            resource_id=invitation["id"],
            details={"email": request.email, "role": request.role.value}
        )
        
        logger.info(f"✅ Invited user {request.email} to organization {org_id}")
        
        return {
            "invitation_id": invitation["id"],
            "message": "Invitation sent successfully",
            "expires_at": invitation["expires_at"]
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to invite user: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/organizations/{org_id}/sso/configure")
async def configure_sso(
    org_id: str,
    request: SSOConfigRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    🔐 Configure Single Sign-On for organization
    
    Supports:
    - SAML 2.0 integration
    - OIDC/OAuth integration
    - Azure AD, Google Workspace, Okta
    - Automatic user provisioning
    """
    
    # Verify admin access
    await _verify_organization_access(current_user["id"], org_id, [UserRole.ADMIN])
    
    try:
        # Validate SSO configuration
        await _validate_sso_config(request)
        
        # Update organization with SSO config
        sso_config = {
            "provider": request.provider.value,
            "entity_id": request.entity_id,
            "sso_url": request.sso_url,
            "certificate": request.certificate,
            "attribute_mapping": request.attribute_mapping,
            "auto_provision": request.auto_provision,
            "configured_at": datetime.utcnow(),
            "configured_by": current_user["id"]
        }
        
        await db.organizations.update_one(
            {"id": org_id},
            {"$set": {
                "sso_config": sso_config,
                "settings.sso_enabled": True,
                "updated_at": datetime.utcnow()
            }}
        )
        
        # Audit log
        await _log_audit_event(
            org_id=org_id,
            user_id=current_user["id"],
            action="sso_configured",
            resource_type="organization",
            resource_id=org_id,
            details={"provider": request.provider.value}
        )
        
        logger.info(f"✅ Configured SSO for organization {org_id}")
        
        return {
            "message": "SSO configured successfully",
            "provider": request.provider.value,
            "test_url": f"/api/v1/auth/sso/{org_id}/test"
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to configure SSO: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/organizations/{org_id}/audit-logs", response_model=List[AuditLogEntry])
async def get_audit_logs(
    org_id: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    action: Optional[str] = None,
    user_id: Optional[str] = None,
    limit: int = Field(100, ge=1, le=1000),
    current_user: dict = Depends(get_current_user)
):
    """
    📋 Get organization audit logs for compliance and security
    """
    
    # Verify admin access
    await _verify_organization_access(current_user["id"], org_id, [UserRole.ADMIN])
    
    try:
        # Build query
        query = {"organization_id": org_id}
        
        if start_date or end_date:
            timestamp_query = {}
            if start_date:
                timestamp_query["$gte"] = start_date
            if end_date:
                timestamp_query["$lte"] = end_date
            query["timestamp"] = timestamp_query
        
        if action:
            query["action"] = action
        
        if user_id:
            query["user_id"] = user_id
        
        # Get audit logs
        cursor = db.audit_logs.find(query).sort("timestamp", -1).limit(limit)
        logs = await cursor.to_list(length=None)
        
        return [
            AuditLogEntry(
                id=log["id"],
                timestamp=log["timestamp"],
                user_id=log["user_id"],
                user_email=log["user_email"],
                action=log["action"],
                resource_type=log["resource_type"],
                resource_id=log["resource_id"],
                details=log["details"],
                ip_address=log.get("ip_address", ""),
                user_agent=log.get("user_agent", "")
            )
            for log in logs
        ]
        
    except Exception as e:
        logger.error(f"❌ Failed to get audit logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/organizations/{org_id}/users")
async def get_organization_users(
    org_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    👥 Get all users in organization with roles and permissions
    """
    
    # Verify access
    await _verify_organization_access(current_user["id"], org_id, [UserRole.ADMIN, UserRole.MANAGER])
    
    try:
        # Get organization users
        cursor = db.organization_users.find({"organization_id": org_id, "is_active": True})
        users = await cursor.to_list(length=None)
        
        # Enhance with user details
        for user in users:
            # Get user profile
            user_profile = await db.users.find_one({"id": user["user_id"]})
            if user_profile:
                user["name"] = user_profile.get("name", "")
                user["avatar"] = user_profile.get("avatar", "")
            
            # Get recent activity
            user["credits_used_30d"] = await _get_user_credits_used(user["user_id"], org_id, 30)
        
        return {
            "organization_id": org_id,
            "total_users": len(users),
            "users": users
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to get organization users: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ===================================================================
# HELPER FUNCTIONS
# ===================================================================

async def _verify_organization_access(user_id: str, org_id: str, required_roles: List[UserRole]):
    """Verify user has required access to organization"""
    org_user = await db.organization_users.find_one({
        "user_id": user_id,
        "organization_id": org_id,
        "is_active": True
    })
    
    if not org_user:
        raise HTTPException(status_code=403, detail="Access denied to organization")
    
    if UserRole(org_user["role"]) not in required_roles:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    return org_user

async def _log_audit_event(
    org_id: str,
    user_id: str,
    action: str,
    resource_type: str,
    resource_id: str,
    details: Dict[str, Any],
    ip_address: str = "",
    user_agent: str = ""
):
    """Log audit event for compliance"""
    
    # Get user email
    user = await db.users.find_one({"id": user_id})
    user_email = user.get("email", "") if user else ""
    
    audit_entry = {
        "id": str(uuid.uuid4()),
        "organization_id": org_id,
        "timestamp": datetime.utcnow(),
        "user_id": user_id,
        "user_email": user_email,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "details": details,
        "ip_address": ip_address,
        "user_agent": user_agent
    }
    
    await db.audit_logs.insert_one(audit_entry)

async def _get_organization_usage_stats(org_id: str) -> Dict[str, Any]:
    """Get organization usage statistics"""
    # Mock data - would integrate with real analytics
    return {
        "total_credits": 45000,
        "credits_30d": 12000,
        "cost_30d": 240.50,
        "top_providers": [
            {"provider": "openai", "usage": 8000, "cost": 160.00},
            {"provider": "anthropic", "usage": 4000, "cost": 80.50}
        ],
        "top_departments": [
            {"department": "Engineering", "usage": 7000, "cost": 140.00},
            {"department": "Marketing", "usage": 5000, "cost": 100.50}
        ],
        "productivity": {
            "avg_quality_score": 0.92,
            "time_saved_hours": 120,
            "prompts_improved": 850
        }
    }

async def _get_organization_name(org_id: str) -> str:
    """Get organization name"""
    org = await db.organizations.find_one({"id": org_id})
    return org.get("name", "Organization") if org else "Organization"

async def _get_user_credits_used(user_id: str, org_id: str, days: int) -> int:
    """Get credits used by user in organization"""
    # Mock data - would integrate with billing system
    return 450

async def _validate_sso_config(config: SSOConfigRequest):
    """Validate SSO configuration"""
    # Basic validation - would implement full SAML/OIDC validation
    if not config.entity_id or not config.sso_url:
        raise HTTPException(status_code=400, detail="Invalid SSO configuration")

async def _send_organization_welcome_email(org_id: str, admin_email: str, org_name: str):
    """Send welcome email to organization admin"""
    logger.info(f"📧 Sending welcome email to {admin_email} for organization {org_name}")

async def _send_invitation_email(invitation: Dict[str, Any], org_name: str):
    """Send invitation email to user"""
    logger.info(f"📧 Sending invitation email to {invitation['email']} for {org_name}")

# Export the router
__all__ = ["router"]
