import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Request
router = APIRouter()
logger = logging.getLogger(__name__)
from dependencies import limiter , get_current_user, db, performance_monitor, trigger_project_deletion_workflow, trigger_project_prompts_workflow

from api.models import ProjectPromptRequest


# ...existing code...
async def calculate_project_statistics(user_id: str, project_id: str) -> dict:
    """Calculate statistics for a project."""
    prompt_count = await db["prompts"].count_documents({"user_id": user_id, "project_id": project_id})
    # Add more stats as needed
    return {
        "total_prompts": prompt_count,
    }


@router.get("/{project_id}")
@limiter.limit("20/minute")
async def get_project_details(
    project_id: str,
    request: Request,
    include_prompts: bool = Query(False, description="Include project prompts"),
    user: dict = Depends(get_current_user)
):
    """Get detailed information about a specific project (Mongo-only)."""
    user_id = user['uid']
    logger.info(f"Project details request from user: {user_id} for project: {project_id}")

    async with performance_monitor("get_project_details"):
        try:
            # cache_key = f"project:details:{user_id}:{project_id}:v1"
            # if include_prompts:
            #     cache_key += ":prompts"
            # cached_result = await cache_get(cache_key)
            # if cached_result:
            #     logger.info(f"Project details cache hit for: {project_id}")
            #     data = json.loads(cached_result)
            #     return APIResponse(data=data.get("data", data), message="OK (cache)")

            project_data = await db["projects"].find_one({"user_id": user_id, "id": project_id})
            if not project_data:
                raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

            await db["projects"].update_one(
                {"user_id": user_id, "id": project_id},
                {"$set": {"last_accessed": datetime.utcnow()}}
            )

            stats = await calculate_project_statistics(user_id, project_id)
            project_data['statistics'] = stats

            project_prompts = []
            if include_prompts:
                cursor = db["prompts"].find({"user_id": user_id, "project_id": project_id}).sort("created_at", DESCENDING)
                async for p in cursor:
                    project_prompts.append({
                        'id': str(p.get('_id', '')),
                        'title': p.get('title', 'Untitled'),
                        'description': (p.get('description', '')[:200] + '...') if len(p.get('description', '')) > 200 else p.get('description', ''),
                        'category': p.get('category', 'general'),
                        'tags': p.get('tags', []),
                        'uses': p.get('uses', 0),
                        'starred': p.get('starred', False),
                        'is_public': p.get('is_public', False),
                        'created_at': p.get('created_at'),
                        'updated_at': p.get('updated_at')
                    })

            response_data = {
                "status": "success",
                "message": f"Project '{project_data['name']}' details retrieved",
                "data": {
                    "project": {
                        **project_data,
                        'created_at': project_data.get('created_at').isoformat() if project_data.get('created_at') else None,
                        'updated_at': project_data.get('updated_at').isoformat() if project_data.get('updated_at') else None,
                        'last_accessed': (datetime.utcnow().isoformat())
                    },
                    "prompts": project_prompts if include_prompts else None,
                    "metadata": {
                        "prompts_included": include_prompts,
                        "total_prompts": len(project_prompts) if include_prompts else stats.get('total_prompts', 0),
                        "can_edit": True,
                        "can_delete": stats.get('total_prompts', 0) == 0
                    },
                    "ui_config": {
                        "available_actions": ["edit", "archive", "duplicate", "export"],
                        "sharing_enabled": project_data.get('is_public', False),
                        "collaboration_features": ["comments", "version_history"]
                    }
                },
                "performance": {
                    "query_time": "fast",
                    "cache_hit": False,
                    "database_queries": 2 if include_prompts else 1
                }
            }

            # No cache set (Mongo-only, no cache layer)
            return response_data

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get project details for {project_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve project details")

@router.delete("/{project_id}")
@limiter.limit("5/minute")
async def delete_project(
    project_id: str,
    request: Request,
    force: bool = Query(False, description="Force delete even if project has prompts"),
    user: dict = Depends(get_current_user)
):
    """Delete a project and optionally handle associated prompts (Mongo-only)."""
    user_id = user['uid']
    logger.info(f"Project deletion request from user: {user_id} for project: {project_id} (force={force})")

    async with performance_monitor("delete_project"):
        try:
            project_data = await db["projects"].find_one({"user_id": user_id, "id": project_id})
            if not project_data:
                raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

            prompt_count = await db["prompts"].count_documents({"user_id": user_id, "project_id": project_id})
            if prompt_count and not force:
                raise HTTPException(
                    status_code=409,
                    detail="Project contains prompts. Use 'force=true' to delete or move prompts to another project first."
                )

            if force and prompt_count:
                await db["prompts"].update_many(
                    {"user_id": user_id, "project_id": project_id},
                    {"$unset": {"project_id": ""}, "$set": {"updated_at": datetime.utcnow()}}
                )
                logger.info(f"Removed project association from {prompt_count} prompts")

            await db["projects"].delete_one({"user_id": user_id, "id": project_id})

            # No cache delete (Mongo-only, no cache layer)

            try:
                await trigger_project_deletion_workflow({
                    'user_id': user_id,
                    'project_id': project_id,
                    'project_name': project_data.get('name'),
                    'prompts_affected': prompt_count if force else 0,
                    'force_deleted': force
                })
            except Exception as workflow_error:
                logger.warning(f"Project deletion workflow failed: {workflow_error}")

            return {
                "status": "success",
                "message": f"Project '{project_data['name']}' deleted successfully",
                "data": {
                    "deleted_project_id": project_id,
                    "prompts_affected": prompt_count if force else 0,
                    "force_deleted": force
                },
                "performance": {
                    "operation_time": "medium",
                    "workflows_triggered": 1
                }
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to delete project {project_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to delete project")


@router.get("/{project_id}/prompts")
@limiter.limit("25/minute")
async def get_project_prompts(
    project_id: str,
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("updated_at", description="Sort field: created_at, updated_at, title, uses"),
    sort_order: str = Query("desc", description="Sort order: asc, desc"),
    user: dict = Depends(get_current_user)
):
    """Get prompts in a project with pagination & sorting (Mongo-only)."""
    user_id = user['uid']
    logger.info(f"Project prompts request from user: {user_id} for project: {project_id}")

    async with performance_monitor("get_project_prompts"):
        try:
            # Verify project ownership
            exists = await db["projects"].find_one({"user_id": user_id, "id": project_id})
            if not exists:
                raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

            cache_key = f"project:prompts:{user_id}:{project_id}:page:{page}:limit:{limit}:sort:{sort_by}:{sort_order}:v1"
            # cached = await cache_get(cache_key)
            # if cached:
            #     logger.info(f"Project prompts cache hit for: {project_id}")
            #     data = json.loads(cached)
            #     return APIResponse(data=data.get("data", data), message="OK (cache)")

            valid_sort_fields = ['created_at', 'updated_at', 'title', 'uses']
            if sort_by not in valid_sort_fields:
                sort_by = 'updated_at'
            direction = DESCENDING if sort_order == 'desc' else ASCENDING

            base_query = {"user_id": user_id, "project_id": project_id}
            total_prompts = await db["prompts"].count_documents(base_query)

            cursor = (
                db["prompts"]
                .find(base_query)
                .sort(sort_by, direction)
                .skip((page - 1) * limit)
                .limit(limit)
            )

            prompts = []
            async for prompt_doc in cursor:
                prompts.append({
                    'id': str(prompt_doc.get('_id', '')),
                    'title': prompt_doc.get('title', 'Untitled'),
                    'description': (prompt_doc.get('description', '')[:200] + '...') if len(prompt_doc.get('description', '')) > 200 else prompt_doc.get('description', ''),
                    'category': prompt_doc.get('category', 'general'),
                    'tags': prompt_doc.get('tags', []),
                    'uses': prompt_doc.get('uses', 0),
                    'starred': prompt_doc.get('starred', False),
                    'is_public': prompt_doc.get('is_public', False),
                    'created_at': prompt_doc.get('created_at').isoformat() if isinstance(prompt_doc.get('created_at'), datetime) else None,
                    'updated_at': prompt_doc.get('updated_at').isoformat() if isinstance(prompt_doc.get('updated_at'), datetime) else None,
                    'project_order': prompt_doc.get('project_order', 0),
                    'last_used': prompt_doc.get('last_used')
                })

            total_pages = (total_prompts + limit - 1) // limit
            has_next = page < total_pages
            has_previous = page > 1

            response = {
                "status": "success",
                "message": f"Retrieved {len(prompts)} prompts from project",
                "data": {
                    "prompts": prompts,
                    "pagination": {
                        "current_page": page,
                        "total_pages": total_pages,
                        "total_items": total_prompts,
                        "items_per_page": limit,
                        "has_next": has_next,
                        "has_previous": has_previous,
                        "next_page": page + 1 if has_next else None,
                        "previous_page": page - 1 if has_previous else None
                    },
                    "sorting": {
                        "sort_by": sort_by,
                        "sort_order": sort_order,
                        "available_sorts": valid_sort_fields
                    },
                    "project_info": {
                        "id": project_id,
                        "name": exists.get('name', 'Unknown Project')
                    }
                },
                "performance": {
                    "query_time": "fast",
                    "cache_hit": False,
                    "total_prompts_scanned": total_prompts
                }
            }

            # No cache set (Mongo-only, no cache layer)
            return response

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get project prompts for {project_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve project prompts")

@router.post("/{project_id}/prompts")
@limiter.limit("15/minute")
async def manage_project_prompts(
    project_id: str,
    request_body: ProjectPromptRequest,
    request: Request,
    user: dict = Depends(get_current_user)
):
    """
    Add, remove, or reorder prompts in a project. (Mongo-only)
    """
    user_id = user['uid']
    logger.info(f"Project prompt management request from user: {user_id} for project: {project_id}, action: {request_body.action}")

    async with performance_monitor("manage_project_prompts"):
        try:
            # Verify project exists & ownership
            project_data = await db["projects"].find_one({"user_id": user_id, "id": project_id})
            if not project_data:
                raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

            # Validate prompts belong to user
            if request_body.action in ['add', 'remove', 'reorder']:
                # Fetch all prompts by ids for this user
                # Accept both ObjectId and string 'id'
                or_clauses = []
                object_ids = []
                str_ids = []
                for pid in request_body.prompt_ids:
                    try:
                        object_ids.append(ObjectId(pid))
                    except Exception:
                        str_ids.append(pid)
                if object_ids:
                    or_clauses.append({"_id": {"$in": object_ids}, "user_id": user_id})
                if str_ids:
                    or_clauses.append({"id": {"$in": str_ids}, "user_id": user_id})

                if not or_clauses:
                    raise HTTPException(status_code=400, detail="No valid prompt_ids provided")

                cursor = db["prompts"].find({"$or": or_clauses})
                found_ids = set()
                prompt_docs = []
                async for d in cursor:
                    pid = str(d.get("_id")) if d.get("_id") else d.get("id")
                    found_ids.add(pid)
                    prompt_docs.append(d)

                missing = [pid for pid in request_body.prompt_ids if pid not in found_ids]
                if missing:
                    raise HTTPException(status_code=404, detail=f"Prompt(s) not found: {missing}")

            ops = []
            affected_prompts = []

            if request_body.action == 'add':
                for pid in request_body.prompt_ids:
                    q = {"user_id": user_id}
                    try:
                        q["_id"] = ObjectId(pid)
                    except Exception:
                        q["id"] = pid
                    ops.append(UpdateOne(q, {"$set": {
                        "project_id": project_id,
                        "updated_at": datetime.utcnow(),
                        "project_order": (request_body.order_positions or {}).get(pid, 0)
                    }}))
                    affected_prompts.append(pid)
                message = f"Added {len(request_body.prompt_ids)} prompts to project"

            elif request_body.action == 'remove':
                for pid in request_body.prompt_ids:
                    q = {"user_id": user_id}
                    try:
                        q["_id"] = ObjectId(pid)
                    except Exception:
                        q["id"] = pid
                    ops.append(UpdateOne(q, {"$unset": {"project_id": "", "project_order": ""}, "$set": {
                        "updated_at": datetime.utcnow()
                    }}))
                    affected_prompts.append(pid)
                message = f"Removed {len(request_body.prompt_ids)} prompts from project"

            elif request_body.action == 'reorder':
                if not request_body.order_positions:
                    raise HTTPException(status_code=400, detail="Order positions required for reorder action")
                for pid in request_body.prompt_ids:
                    if pid in request_body.order_positions:
                        q = {"user_id": user_id}
                        try:
                            q["_id"] = ObjectId(pid)
                        except Exception:
                            q["id"] = pid
                        ops.append(UpdateOne(q, {"$set": {
                            "project_order": request_body.order_positions[pid],
                            "updated_at": datetime.utcnow()
                        }}))
                        affected_prompts.append(pid)
                message = f"Reordered {len(affected_prompts)} prompts in project"

            else:
                raise HTTPException(status_code=400, detail=f"Invalid action: {request_body.action}. Supported: add, remove, reorder")

            if ops:
                await db["prompts"].bulk_write(ops, ordered=False)

            # Update project metadata (prompt_count)
            current_prompt_count = await db["prompts"].count_documents({"user_id": user_id, "project_id": project_id})
            await db["projects"].update_one(
                {"user_id": user_id, "id": project_id},
                {"$set": {"prompt_count": current_prompt_count, "updated_at": datetime.utcnow()}}
            )

            # Invalidate caches (best-effort)
            # No cache delete (Mongo-only, no cache layer)

            # Workflow hook (non-blocking)
            try:
                await trigger_project_prompts_workflow({
                    'user_id': user_id,
                    'project_id': project_id,
                    'project_name': project_data.get('name'),
                    'action': request_body.action,
                    'affected_prompts': affected_prompts,
                    'new_prompt_count': current_prompt_count
                })
            except Exception as workflow_error:
                logger.warning(f"Project prompts workflow failed: {workflow_error}")

            return {
                "status": "success",
                "message": message,
                "data": {
                    "project_id": project_id,
                    "action": request_body.action,
                    "affected_prompts": affected_prompts,
                    "new_prompt_count": current_prompt_count,
                    "order_positions": request_body.order_positions if request_body.action == 'reorder' else None
                },
                "performance": {
                    "operation_time": "medium",
                    "batch_operations": len(affected_prompts),
                    "workflows_triggered": 1
                }
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to manage project prompts for {project_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to manage project prompts")

