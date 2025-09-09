from fastapi import APIRouter, Depends, HTTPException, status as http_status, Query, Path
from sqlalchemy.orm import Session
from typing import Optional, List
from uuid import UUID
from dependencies.dependencies import (
    get_db, get_current_user, get_current_sub_admin_user,
    DatabaseSession, CurrentUser, CurrentSubAdminUser
)
from services.module_service import ModuleService
from schemas.module import (
    ModuleCreate, ModuleUpdate, ModuleResponse, ModuleListFilter,
    ModuleBulkCreate, ModuleStatusUpdate, BidModulesResponse
)
from schemas.common import SuccessResponse, PaginatedResponse
from models.models import UserRole, ModuleStatus
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Dependency injection
def get_module_service() -> ModuleService:
    return ModuleService()


@router.post("/", response_model=ModuleResponse, status_code=http_status.HTTP_201_CREATED)
async def create_module(
    module_data: ModuleCreate,
    current_user: CurrentSubAdminUser,
    db: DatabaseSession,
    module_service: ModuleService = Depends(get_module_service)
):
    """
    Create a new project module for a bid (Sub-Admin and Admin only).
    
    Business Rules:
    - Bid must be won
    - User must have access to the bid's team
    - Cannot create modules if receivables already exist for the bid
    """
    return module_service.create_module(
        db, module_data, current_user.id,
        current_user.role, current_user.team_id
    )


@router.post("/single", response_model=ModuleResponse, status_code=http_status.HTTP_201_CREATED)
async def create_single_module(
    module_data: ModuleCreate,
    current_user: CurrentSubAdminUser,
    db: DatabaseSession,
    module_service: ModuleService = Depends(get_module_service)
):
    """
    Create a single module for a bid - Single Module Workflow (Sub-Admin and Admin only).
    
    This endpoint is specifically for the "Single Module" workflow where:
    1. User creates ONE module for the entire bid
    2. Later creates ONE receivable for that module
    
    Business Rules:
    - Bid must be won
    - User must have access to the bid's team
    - Cannot create modules if receivables already exist for the bid
    - No other modules should exist for this bid (enforced in service)
    """
    return module_service.create_single_module(
        db, module_data, current_user.id,
        current_user.role, current_user.team_id
    )


@router.post("/bulk", response_model=List[ModuleResponse], status_code=http_status.HTTP_201_CREATED)
async def create_bulk_modules(
    bulk_data: ModuleBulkCreate,
    current_user: CurrentSubAdminUser,
    db: DatabaseSession,
    module_service: ModuleService = Depends(get_module_service)
):
    """
    Create multiple modules for a bid (Sub-Admin and Admin only).
    
    This is for module-based workflow where multiple modules are created at once.
    """
    return module_service.create_bulk_modules(
        db, bulk_data, current_user.id,
        current_user.role, current_user.team_id
    )


@router.get("/", response_model=PaginatedResponse[ModuleResponse])
async def get_modules(
    current_user: CurrentUser,
    db: DatabaseSession,
    bid_id: Optional[str] = Query(None, description="Filter by bid ID"),
    status: Optional[ModuleStatus] = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Number of records to return"),
    sort: str = Query("-created_at", description="Sort field and direction"),
    module_service: ModuleService = Depends(get_module_service)
):
    """
    Get modules with filtering and pagination.
    
    Access control:
    - Admin: Can see all modules
    - Sub-Admin: Can see modules for their team's bids
    - Member: Cannot access this endpoint
    """
    if current_user.role == UserRole.MEMBER:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )

    # Validate bid_id if provided
    bid_uuid = None
    if bid_id:
        try:
            bid_uuid = UUID(bid_id)
        except ValueError:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="Invalid bid ID format"
            )
    
    filters = ModuleListFilter(
        bid_id=bid_uuid,
        status=status
    )
    
    return module_service.get_modules(
        db, filters, current_user.id, current_user.role, 
        skip, limit, sort, current_user.team_id
    )


@router.get("/bid/{bid_id}", response_model=BidModulesResponse)
async def get_bid_modules(
    bid_id: str,
    current_user: CurrentUser,
    db: DatabaseSession,
    module_service: ModuleService = Depends(get_module_service)
):
    """
    Get all modules for a specific bid.
    
    Access control:
    - Admin: Can see any bid's modules
    - Sub-Admin: Can see modules for their team's bids
    - Member: Cannot access this endpoint
    """
    if current_user.role == UserRole.MEMBER:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    try:
        bid_uuid = UUID(bid_id)
        return module_service.get_bid_modules(
            db, bid_uuid, current_user.id, current_user.role, current_user.team_id
        )
    except ValueError:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Invalid bid ID format"
        )


@router.get("/{module_id}", response_model=ModuleResponse)
async def get_module(
    module_id: str,
    current_user: CurrentUser,
    db: DatabaseSession,
    module_service: ModuleService = Depends(get_module_service)
):
    """
    Get module by ID.
    
    Access control:
    - Admin: Can see any module
    - Sub-Admin: Can see modules for their team's bids
    - Member: Cannot access this endpoint
    """
    if current_user.role == UserRole.MEMBER:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    try:
        module_uuid = UUID(module_id)
        module = module_service.get_module(
            db, module_uuid, current_user.id,
            current_user.role, current_user.team_id
        )
        
        if not module:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Module not found"
            )
        
        return module
    except ValueError:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Invalid module ID format"
        )


@router.put("/{module_id}", response_model=ModuleResponse)
async def update_module(
    module_id: str,
    module_data: ModuleUpdate,
    current_user: CurrentSubAdminUser,
    db: DatabaseSession,
    module_service: ModuleService = Depends(get_module_service)
):
    """
    Update module (Sub-Admin and Admin only).
    """
    try:
        module_uuid = UUID(module_id)
        module = module_service.update_module(
            db, module_uuid, module_data,
            current_user.id, current_user.role, current_user.team_id
        )
        
        if not module:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Module not found"
            )
        
        return module
    except ValueError:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Invalid module ID format"
        )


@router.patch("/{module_id}/status", response_model=ModuleResponse)
async def update_module_status(
    module_id: str,
    status_data: ModuleStatusUpdate,
    current_user: CurrentSubAdminUser,
    db: DatabaseSession,
    module_service: ModuleService = Depends(get_module_service)
):
    """
    Update module status (Sub-Admin and Admin only).
    """
    try:
        module_uuid = UUID(module_id)
        module = module_service.update_module_status(
            db, module_uuid, status_data,
            current_user.id, current_user.role, current_user.team_id
        )
        
        if not module:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Module not found"
            )
        
        return module
    except ValueError:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Invalid module ID format"
        )


@router.delete("/{module_id}", response_model=SuccessResponse)
async def delete_module(
    module_id: str,
    current_user: CurrentSubAdminUser,
    db: DatabaseSession,
    module_service: ModuleService = Depends(get_module_service)
):
    """
    Delete module (Sub-Admin and Admin only).
    
    Business Rule: Can only delete if no receivables exist for this module.
    """
    try:
        module_uuid = UUID(module_id)
        return module_service.delete_module(
            db, module_uuid, current_user.id,
            current_user.role, current_user.team_id
        )
    except ValueError:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Invalid module ID format"
        )


@router.post("/bid/{bid_id}/check", response_model=dict)
async def check_bid_modules_status(
    bid_id: str,
    current_user: CurrentUser,
    db: DatabaseSession,
    module_service: ModuleService = Depends(get_module_service)
):
    """
    Check if bid has existing modules or receivables.
    
    Returns information about existing modules and receivables to guide user workflow.
    """
    if current_user.role == UserRole.MEMBER:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    try:
        bid_uuid = UUID(bid_id)
        return module_service.check_bid_status(
            db, bid_uuid, current_user.id, current_user.role, current_user.team_id
        )
    except ValueError:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Invalid bid ID format"
        )