🚀 PromptForge.ai API
 7.0.0-production-ready 
OAS 3.1
/openapi.json
PromptForge.ai API with Firebase Authentication


Authorize
Debug


GET
/api/v1/debug/auth-headers
Debug Auth Headers



POST
/api/v1/debug/test-auth
Test Auth With Mock


Prompts


GET
/api/v1/prompts/prompts/arsenal
Get User Arsenal



POST
/api/v1/prompts/prompts/
Create New Prompt



POST
/api/v1/prompts/prompts/test-drive-by-id
Test Drive Prompt By Id



GET
/api/v1/prompts/prompts/{prompt_id}
Get Prompt Details



DELETE
/api/v1/prompts/prompts/{prompt_id}
Delete Prompt



PUT
/api/v1/prompts/prompts/{prompt_id}
Update Prompt



GET
/api/v1/prompts/prompts/public
Get Public Prompts



GET
/api/v1/prompts/prompts/{prompt_id}/versions
Get Prompt Versions



POST
/api/v1/prompts/prompts/bulk-action
Bulk Prompt Action


AI Features


POST
/api/v1/ai/remix-prompt
Remix Prompt



POST
/api/v1/ai/architect-prompt
Architect Prompt



POST
/api/v1/ai/fuse-prompts
Fuse Prompts



POST
/api/v1/ai/generate-enhanced-prompt
Generate Enhanced Prompt



POST
/api/v1/ai/analyze-prompt
Analyze Prompt


marketplace


GET
/api/v1/marketplace/search
Search Marketplace



GET
/api/v1/marketplace/my-listings
Get My Marketplace Listings



GET
/api/v1/marketplace/{id}
Get Public Prompt Details



POST
/api/v1/marketplace/list-prompt
List Prompt In Marketplace



GET
/api/v1/marketplace/listings
Get Marketplace Listings



GET
/api/v1/marketplace/preview/{prompt_id}
Preview Marketplace Item



POST
/api/v1/marketplace/rate
Rate Marketplace Prompt



GET
/api/v1/marketplace/{prompt_id}/reviews
List Marketplace Reviews



GET
/api/v1/marketplace/{prompt_id}/analytics
Get Marketplace Prompt Analytics


users


PUT
/api/v1/users/me/profile
Update Profile



POST
/api/v1/users/auth/complete
Auth Complete



GET
/api/v1/users/me
Get Me



GET
/api/v1/users/credits
Get User Credits



PUT
/api/v1/users/profile
Update User Profile



GET
/api/v1/users/export-data
Export User Data



DELETE
/api/v1/users/account
Delete User Account



GET
/api/v1/users/preferences
Get User Preferences



PUT
/api/v1/users/preferences
Update User Preferences



GET
/api/v1/users/stats
Get User Stats



GET
/api/v1/users/me/usage
Get My Usage



POST
/api/v1/users/usage/track
Track Usage Event


Users


PUT
/api/v1/users/me/profile
Update Profile



POST
/api/v1/users/auth/complete
Auth Complete



GET
/api/v1/users/me
Get Me



GET
/api/v1/users/credits
Get User Credits



PUT
/api/v1/users/profile
Update User Profile



GET
/api/v1/users/export-data
Export User Data



DELETE
/api/v1/users/account
Delete User Account



GET
/api/v1/users/preferences
Get User Preferences



PUT
/api/v1/users/preferences
Update User Preferences



GET
/api/v1/users/stats
Get User Stats



GET
/api/v1/users/me/usage
Get My Usage



POST
/api/v1/users/usage/track
Track Usage Event


Packaging


POST
/api/v1/packaging/{prompt_id}/package
Package Prompt For Marketplace



GET
/api/v1/packaging/
List User Packages



POST
/api/v1/packaging/manage-bulk
Manage Packages Bulk



GET
/api/v1/packaging/analytics
Get Package Analytics


Partnerships


POST
/api/v1/partnerships/request
Request Partnership Enhanced



POST
/api/v1/partnerships/revenue
Manage Partner Revenue



GET
/api/v1/partnerships/dashboard
Get Partner Dashboard


Analytics


POST
/api/v1/analytics/events
Log Analytics Events



POST
/api/v1/analytics/performance
Log Performance Metrics



GET
/api/v1/analytics/dashboard
Get Analytics Dashboard



POST
/api/v1/analytics/exports/prompts
Export Prompts Data



POST
/api/v1/analytics/exports/analytics
Export Analytics Data



POST
/api/v1/analytics/jobs/analytics
Create Analytics Job



GET
/api/v1/analytics/jobs/analytics/{job_id}/status
Get Analytics Job Status


Projects


GET
/api/v1/projects/{project_id}
Get Project Details



DELETE
/api/v1/projects/{project_id}
Delete Project



GET
/api/v1/projects/{project_id}/prompts
Get Project Prompts



POST
/api/v1/projects/{project_id}/prompts
Manage Project Prompts


Notifications


PUT
/api/v1/notifications/{notification_id}/read
Mark Notification Read



POST
/api/v1/notifications/mark-all-read
Mark All Notifications Read


billing


GET
/api/v1/billing/tiers
Get Billing Tiers



GET
/api/v1/billing/me/entitlements
Get Me Entitlements


Payments


POST
/api/v1/payments/initiate-payment
Initiate Payment


webhooks


GET
/api/v1/payments/webhooks/health
Health



POST
/api/v1/payments/webhooks/payments/webhooks/paddle
Paddle Webhook



POST
/api/v1/payments/webhooks/payments/webhooks/razorpay
Razorpay Webhook


health


GET
/api/v1/payments/webhooks/health
Health


search


GET
/api/v1/search/users
Search Users



GET
/api/v1/search/
Global Search


Prompt Engine


POST
/api/v1/prompt/prompt/quick_upgrade
Quick Mode: Upgrade prompt (extension, low-latency)



POST
/api/v1/prompt/prompt/upgrade
Full Mode: Upgrade prompt (deep pipeline, Pro)


Brain Engine


POST
/api/v1/prompt/prompt/quick_upgrade
Quick Mode: Upgrade prompt (extension, low-latency)



POST
/api/v1/prompt/prompt/upgrade
Full Mode: Upgrade prompt (deep pipeline, Pro)


Demon Engine


POST
/api/v1/demon/route
Route



POST
/api/v1/demon/v2/upgrade
Upgrade V2


Prompt Vault


GET
/api/v1/vault/vault/arsenal
Get Arsenal



GET
/api/v1/vault/vault/search
Search Prompts



POST
/api/v1/vault/vault/{prompt_id}/test-drive
Test Drive Prompt



POST
/api/v1/vault/vault/save
Save Prompt



GET
/api/v1/vault/vault/list
List Prompts



GET
/api/v1/vault/vault/{prompt_id}/versions
Get Prompt Versions



DELETE
/api/v1/vault/vault/delete/{prompt_id}
Delete Prompt


Ideas


POST
/api/v1/ideas/generate
Generate Ideas


Admin


GET
/api/v1/admin/diagnostics
Diagnostics


Monitoring


GET
/api/v1/monitoring/health
Health Check



GET
/api/v1/monitoring/health/detailed
Detailed Health Check



GET
/api/v1/monitoring/metrics
Get Metrics



GET
/api/v1/monitoring/trace/{request_id}
Get Request Trace



GET
/api/v1/monitoring/circuit-breakers
Get Circuit Breaker Status



POST
/api/v1/monitoring/circuit-breakers/{breaker_name}/reset
Reset Circuit Breaker


Credit Management


GET
/api/v1/credits/dashboard
Get Credit Dashboard



GET
/api/v1/credits/usage/history
Get Usage History



GET
/api/v1/credits/analytics/routes
Get Route Analytics



GET
/api/v1/credits/predictions/usage
Predict Usage



GET
/api/v1/credits/admin/overview
Admin Credit Overview


Performance


GET
/api/v1/performance/performance/dashboard
Get Performance Dashboard



GET
/api/v1/performance/performance/slow-queries
Get Slow Queries



GET
/api/v1/performance/performance/cache-stats
Get Cache Statistics



POST
/api/v1/performance/performance/optimize
Trigger Optimization



DELETE
/api/v1/performance/performance/cache
Clear Cache



GET
/api/v1/performance/performance/health
Performance Health Check


Prompt Intelligence


POST
/api/v1/intelligence/analyze
Analyze Prompt



GET
/api/v1/intelligence/suggestions/quick
Get Quick Suggestions



GET
/api/v1/intelligence/templates/personalized
Get Personalized Templates



GET
/api/v1/intelligence/patterns/user
Get User Patterns



POST
/api/v1/intelligence/feedback
Submit Suggestion Feedback



GET
/api/v1/intelligence/analytics/intelligence
Get Intelligence Analytics


Context Intelligence


POST
/api/v1/context/analyze
Analyze Context



POST
/api/v1/context/quick-suggestions
Get Quick Context Suggestions



POST
/api/v1/context/follow-up-questions
Generate Follow Up Questions



GET
/api/v1/context/enhancement-templates
Get Enhancement Templates



GET
/api/v1/context/domain-insights
Get Domain Insights


Extension Intelligence


POST
/api/v1/extension/analyze-prompt
Analyze Extension Prompt



POST
/api/v1/extension/suggestions/contextual
Get Contextual Suggestions



POST
/api/v1/extension/enhance/selected-text
Enhance Selected Text



POST
/api/v1/extension/templates/smart
Get Smart Templates



GET
/api/v1/extension/extension/health
Extension Health Check



GET
/api/v1/extension/extension/usage-stats
Get Extension Usage Stats


Smart Workflows


GET
/api/v1/workflows/api/workflows/templates
Get Workflow Templates



POST
/api/v1/workflows/api/workflows/templates
Create Workflow Template



GET
/api/v1/workflows/api/workflows/templates/{template_id}
Get Workflow Template



POST
/api/v1/workflows/api/workflows/start
Start Workflow



GET
/api/v1/workflows/api/workflows/status/{instance_id}
Get Workflow Status



GET
/api/v1/workflows/api/workflows/results/{instance_id}
Get Workflow Results



POST
/api/v1/workflows/api/workflows/control/{instance_id}/pause
Pause Workflow



POST
/api/v1/workflows/api/workflows/control/{instance_id}/resume
Resume Workflow



POST
/api/v1/workflows/api/workflows/control/{instance_id}/cancel
Cancel Workflow



GET
/api/v1/workflows/api/workflows/my-workflows
List User Workflows



POST
/api/v1/workflows/api/workflows/quick-start/content-creation
Quick Start Content Creation



POST
/api/v1/workflows/api/workflows/quick-start/code-review
Quick Start Code Review



GET
/api/v1/workflows/api/workflows/analytics/usage
Get Workflow Analytics



GET
/api/v1/workflows/api/workflows/health
Workflow Service Health


default


GET
/
Root



GET
/health
Health



Schemas
APIResponseExpand allobject
AnalyticsJobRequestExpand allobject
ArchitectRequestExpand allobject
Body_enhance_selected_text_api_v1_extension_enhance_selected_text_postExpand allobject
Body_generate_follow_up_questions_api_v1_context_follow_up_questions_postExpand allobject
Body_get_contextual_suggestions_api_v1_extension_suggestions_contextual_postExpand allobject
Body_get_smart_templates_api_v1_extension_templates_smart_postExpand allobject
ContextAnalysisRequestExpand allobject
ContextAnalysisResponseExpand allobject
DemonRequestExpand allobject
DemonResponseExpand allobject
ExportRequestExpand allobject
ExtensionAnalysisRequestExpand allobject
FusionRequestExpand allobject
HTTPValidationErrorExpand allobject
IdeaGenerationRequestExpand allobject
KillSwitchRequestExpand allobject
MarketplaceListingRequestExpand allobject
PackageCreateRequestExpand allobject
PackageManagementRequestExpand allobject
PartnerDashboardRequestExpand allobject
PartnerRevenueRequestExpand allobject
PartnershipApplicationRequestExpand allobject
ProjectPromptRequestExpand allobject
PromptAnalysisRequestExpand allobject
PromptAnalysisResponseExpand allobject
PromptRatingRequestExpand allobject
QuickContextRequestExpand allobject
RemixRequestExpand allobject
SavePromptRequestExpand allobject
TestDriveByIdRequestExpand allobject
UpdatePromptRequestExpand allobject
UpgradeRequestExpand allobject
UpgradeResponseExpand allobject
ValidationErrorExpand allobject