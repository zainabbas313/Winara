from fastapi import APIRouter, Depends, HTTPException, status as http_status, Query, status
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import date
from uuid import UUID
from dependencies.dependencies import (
    get_db, get_current_user, get_current_sub_admin_user,
    DatabaseSession, CurrentUser, CurrentSubAdminUser
)
from services.receivable_service import ReceivableService
from schemas.receivable import (
    ReceivableCreate, ReceivableUpdate, ReceivableResponse, ReceivableListFilter,
    ReceivableStatusUpdate, ReceivableStats, ReceivableSummary, BulkReceivableCreate,
    BidReceivableResponse, ProjectModuleCreate
)
from schemas.common import SuccessResponse, PaginatedResponse
from models.models import UserRole, ReceivableStatus, PaymentType
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Dependency injection
def get_receivable_service() -> ReceivableService:
    return ReceivableService()


@router.post("/", response_model=ReceivableResponse, status_code=status.HTTP_201_CREATED)
async def create_receivable(
    receivable_data: ReceivableCreate,
    current_user: CurrentSubAdminUser,
    db: DatabaseSession,
    receivable_service: ReceivableService = Depends(get_receivable_service)
):
    """
    Create a new receivable (Sub-Admin and Admin only).
    
    - **bid_id**: ID of the won bid
    - **module_id**: ID of the module (for module-based payments)
    - **contract_value**: Value of the contract/module
    - **expected_payment_date**: Expected payment date
    - **payment_type**: SINGLE or MODULE_BASED
    - **currency**: Currency code (default USD)
    """
    return receivable_service.create_receivable(
        db, receivable_data, current_user.id,
        current_user.role, current_user.team_id
    )


@router.post("/bulk", response_model=List[ReceivableResponse], status_code=status.HTTP_201_CREATED)
async def create_bulk_receivables(
    bulk_data: BulkReceivableCreate,
    current_user: CurrentSubAdminUser,
    db: DatabaseSession,
    receivable_service: ReceivableService = Depends(get_receivable_service)
):
    """
    Create receivables for all modules of a bid (Sub-Admin and Admin only).
    
    This endpoint:
    1. Creates all modules for the bid
    2. Creates a receivable for each module
    3. Returns all created receivables
    """
    return receivable_service.create_bulk_receivables(
        db, bulk_data, current_user.id,
        current_user.role, current_user.team_id
    )


@router.get("/", response_model=PaginatedResponse[ReceivableResponse])
async def get_receivables(
    current_user: CurrentUser,
    db: DatabaseSession,
    team_id: Optional[str] = Query(None, description="Filter by team ID"),
    status: Optional[ReceivableStatus] = Query(None, description="Filter by status"),
    payment_type: Optional[PaymentType] = Query(None, description="Filter by payment type"),
    date_from: Optional[date] = Query(None, description="Filter from this date"),
    date_to: Optional[date] = Query(None, description="Filter until this date"),
    client_name: Optional[str] = Query(None, description="Search by client name"),
    module_id: Optional[str] = Query(None, description="Filter by module ID"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Number of records to return"),
    sort: str = Query("-created_at", description="Sort field and direction"),
    receivable_service: ReceivableService = Depends(get_receivable_service)
):
    """
    Get receivables with filtering and pagination.
    
    Access control:
    - Admin: Can see all receivables
    - Sub-Admin: Can see receivables for their team
    - Member: Cannot access this endpoint
    """
    if current_user.role == UserRole.MEMBER:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )

    # Validate team_id if provided
    team_uuid = None
    if team_id:
        try:
            team_uuid = UUID(team_id)
        except ValueError:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="Invalid team ID format"
            )
    
    # Validate module_id if provided
    module_uuid = None
    if module_id:
        try:
            module_uuid = UUID(module_id)
        except ValueError:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="Invalid module ID format"
            )
    
    filters = ReceivableListFilter(
        team_id=team_uuid,
        status=status,
        payment_type=payment_type,
        date_from=date_from,
        date_to=date_to,
        client_name=client_name,
        module_id=module_uuid
    )
    
    return receivable_service.get_receivables(
        db, filters, current_user.id, current_user.role, 
        skip, limit, sort, current_user.team_id
    )


@router.get("/bid/{bid_id}", response_model=BidReceivableResponse)
async def get_bid_receivables(
    bid_id: str,
    current_user: CurrentUser,
    db: DatabaseSession,
    receivable_service: ReceivableService = Depends(get_receivable_service)
):
    """
    Get all receivables for a specific bid.
    
    Access control:
    - Admin: Can see any bid's receivables
    - Sub-Admin: Can see receivables for their team's bids
    - Member: Cannot access this endpoint
    """
    if current_user.role == UserRole.MEMBER:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    try:
        bid_uuid = UUID(bid_id)
        return receivable_service.get_bid_receivables(
            db, bid_uuid, current_user.id, current_user.role, current_user.team_id
        )
    except ValueError:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Invalid bid ID format"
        )


@router.get("/{receivable_id}", response_model=ReceivableResponse)
async def get_receivable(
    receivable_id: str,
    current_user: CurrentUser,
    db: DatabaseSession,
    receivable_service: ReceivableService = Depends(get_receivable_service)
):
    """
    Get receivable by ID.
    
    Access control:
    - Admin: Can see any receivable
    - Sub-Admin: Can see receivables for their team
    - Member: Cannot access this endpoint
    """
    if current_user.role == UserRole.MEMBER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    try:
        receivable_uuid = UUID(receivable_id)
        receivable = receivable_service.get_receivable(
            db, receivable_uuid, current_user.id,
            current_user.role, current_user.team_id
        )
        
        if not receivable:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Receivable not found"
            )
        
        return receivable
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid receivable ID format"
        )


@router.put("/{receivable_id}", response_model=ReceivableResponse)
async def update_receivable(
    receivable_id: str,
    receivable_data: ReceivableUpdate,
    current_user: CurrentSubAdminUser,
    db: DatabaseSession,
    receivable_service: ReceivableService = Depends(get_receivable_service)
):
    """
    Update receivable (Sub-Admin and Admin only).
    """
    try:
        receivable_uuid = UUID(receivable_id)
        receivable = receivable_service.update_receivable(
            db, receivable_uuid, receivable_data,
            current_user.id, current_user.role, current_user.team_id
        )
        
        if not receivable:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Receivable not found"
            )
        
        return receivable
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid receivable ID format"
        )


@router.patch("/{receivable_id}/status", response_model=ReceivableResponse)
async def update_receivable_status(
    receivable_id: str,
    status_data: ReceivableStatusUpdate,
    current_user: CurrentSubAdminUser,
    db: DatabaseSession,
    receivable_service: ReceivableService = Depends(get_receivable_service)
):
    """
    Update receivable status (Sub-Admin and Admin only).
    
    Available status transitions:
    - pending → partial/paid/overdue
    - partial → paid/overdue
    - overdue → paid/partial
    """
    try:
        receivable_uuid = UUID(receivable_id)
        receivable = receivable_service.update_receivable_status(
            db, receivable_uuid, status_data,
            current_user.id, current_user.role, current_user.team_id
        )
        
        if not receivable:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Receivable not found"
            )
        
        return receivable
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid receivable ID format"
        )


@router.delete("/{receivable_id}", response_model=SuccessResponse)
async def delete_receivable(
    receivable_id: str,
    current_user: CurrentSubAdminUser,
    db: DatabaseSession,
    receivable_service: ReceivableService = Depends(get_receivable_service)
):
    """
    Delete receivable (Sub-Admin and Admin only).
    """
    try:
        receivable_uuid = UUID(receivable_id)
        return receivable_service.delete_receivable(
            db, receivable_uuid, current_user.id,
            current_user.role, current_user.team_id
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid receivable ID format"
        )


# Module management endpoints
@router.post("/modules/", response_model=List[ReceivableResponse], status_code=status.HTTP_201_CREATED)
async def create_modules_with_receivables(
    bid_id: UUID,
    modules: List[ProjectModuleCreate],
    current_user: CurrentSubAdminUser,
    db: DatabaseSession,
    receivable_service: ReceivableService = Depends(get_receivable_service)
):
    """
    Create modules and their corresponding receivables for a bid.
    """
    bulk_data = BulkReceivableCreate(bid_id=bid_id, modules=modules)
    return receivable_service.create_bulk_receivables(
        db, bulk_data, current_user.id,
        current_user.role, current_user.team_id
    )


# Status and filtering endpoints
@router.get("/status/overdue", response_model=List[ReceivableResponse])
async def get_overdue_receivables(
    current_user: CurrentUser,
    db: DatabaseSession,
    receivable_service: ReceivableService = Depends(get_receivable_service)
):
    """
    Get overdue receivables.
    
    Access control:
    - Admin: Can see all overdue receivables
    - Sub-Admin: Can see overdue receivables for their team
    - Member: Cannot access this endpoint
    """
    if current_user.role == UserRole.MEMBER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    team_id = current_user.team_id if current_user.role == UserRole.SUB_ADMIN else None
    return receivable_service.get_overdue_receivables(db, team_id)


@router.get("/analytics/statistics", response_model=ReceivableStats)
async def get_receivable_statistics(
    current_user: CurrentUser,
    db: DatabaseSession,
    team_id: Optional[str] = Query(None, description="Filter by team ID"),
    receivable_service: ReceivableService = Depends(get_receivable_service)
):
    """
    Get receivable statistics.
    
    Returns:
    - Total receivables count
    - Total contract value
    - Paid value
    - Pending value
    - Overdue value and count
    - Average payment days
    - Breakdown by payment type
    """
    if current_user.role == UserRole.MEMBER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    try:
        team_uuid = UUID(team_id) if team_id else None
        
        # Validate access
        if current_user.role == UserRole.SUB_ADMIN:
            if team_uuid and team_uuid != current_user.team_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Can only access your own team statistics"
                )
            team_uuid = current_user.team_id
        
        return receivable_service.get_statistics(db, team_uuid)
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid team ID format"
        )


# Analytics and reporting endpoints (keeping existing ones)
@router.get("/analytics/monthly-summary")
async def get_monthly_receivables_summary(
    current_user: CurrentUser,
    db: DatabaseSession,
    year: int = Query(..., ge=2020, le=2030, description="Year"),
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    team_id: Optional[str] = Query(None, description="Filter by team ID"),
    receivable_service: ReceivableService = Depends(get_receivable_service)
):
    """Get monthly receivables summary."""
    if current_user.role == UserRole.MEMBER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    try:
        team_uuid = UUID(team_id) if team_id else None
        
        if current_user.role == UserRole.SUB_ADMIN:
            if team_uuid and team_uuid != current_user.team_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Can only access your own team data"
                )
            team_uuid = current_user.team_id
        
        return receivable_service.get_monthly_summary(db, year, month, team_uuid)
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid team ID format"
        )


@router.get("/analytics/payment-trends")
async def get_payment_trends(
    current_user: CurrentUser,
    db: DatabaseSession,
    days: int = Query(90, ge=1, le=365, description="Number of days for trend analysis"),
    team_id: Optional[str] = Query(None, description="Filter by team ID"),
    receivable_service: ReceivableService = Depends(get_receivable_service)
):
    """Get payment trends over specified period."""
    if current_user.role == UserRole.MEMBER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    try:
        team_uuid = UUID(team_id) if team_id else None
        
        if current_user.role == UserRole.SUB_ADMIN:
            if team_uuid and team_uuid != current_user.team_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Can only access your own team data"
                )
            team_uuid = current_user.team_id
        
        return receivable_service.get_payment_trends(db, team_uuid, days)
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid team ID format"
        )


@router.get("/analytics/client-summary")
async def get_client_summary(
    current_user: CurrentUser,
    db: DatabaseSession,
    team_id: Optional[str] = Query(None, description="Filter by team ID"),
    receivable_service: ReceivableService = Depends(get_receivable_service)
):
    """Get summary statistics by client."""
    if current_user.role == UserRole.MEMBER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    try:
        team_uuid = UUID(team_id) if team_id else None
        
        if current_user.role == UserRole.SUB_ADMIN:
            if team_uuid and team_uuid != current_user.team_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Can only access your own team data"
                )
            team_uuid = current_user.team_id
        
        return receivable_service.get_client_summary(db, team_uuid)
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid team ID format"
        )


@router.get("/analytics/cash-flow")
async def get_cash_flow_projection(
    current_user: CurrentUser,
    db: DatabaseSession,
    days_ahead: int = Query(90, ge=1, le=365, description="Days ahead for projection"),
    team_id: Optional[str] = Query(None, description="Filter by team ID"),
    receivable_service: ReceivableService = Depends(get_receivable_service)
):
    """Get projected cash flow based on expected payment dates."""
    if current_user.role == UserRole.MEMBER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    try:
        team_uuid = UUID(team_id) if team_id else None
        
        if current_user.role == UserRole.SUB_ADMIN:
            if team_uuid and team_uuid != current_user.team_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Can only access your own team data"
                )
            team_uuid = current_user.team_id
        
        return receivable_service.calculate_cash_flow(db, team_uuid, days_ahead)
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid team ID format"
        )


# Utility endpoints
@router.post("/actions/mark-overdue")
async def mark_overdue_receivables(
    current_user: CurrentSubAdminUser,
    db: DatabaseSession,
    receivable_service: ReceivableService = Depends(get_receivable_service)
):
    """
    Mark overdue receivables (Sub-Admin and Admin only).
    
    Updates status of receivables past their expected payment date.
    """
    count = receivable_service.mark_overdue_receivables(db)
    return {"marked_overdue": count, "message": f"Marked {count} receivables as overdue"}


@router.get("/receivables/summary")
async def get_receivables_dashboard_summary(
    current_user: CurrentUser,
    db: DatabaseSession,
    receivable_service: ReceivableService = Depends(get_receivable_service)
):
    """
    Get receivables summary for dashboard display.
    
    Returns summary based on user role:
    - Admin: System-wide summary
    - Sub-Admin: Team summary
    - Member: Cannot access
    """
    if current_user.role == UserRole.MEMBER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    team_id = current_user.team_id if current_user.role == UserRole.SUB_ADMIN else None
    
    # Get statistics
    stats = receivable_service.get_statistics(db, team_id)
    
    # Get overdue receivables
    overdue = receivable_service.get_overdue_receivables(db, team_id)
    
    # Get recent receivables
    recent_filters = ReceivableListFilter(team_id=team_id)
    recent_result = receivable_service.get_receivables(
        db, recent_filters, current_user.id, current_user.role, 
        0, 5, "-created_at", current_user.team_id
    )
    
    return {
        "statistics": stats,
        "overdue_count": len(overdue),
        "overdue_receivables": [
            ReceivableSummary(
                id=r.id,
                client_name=r.client_name,
                project_title=r.project_title,
                contract_value=r.contract_value,
                status=r.status,
                expected_payment_date=r.expected_payment_date,
                is_overdue=r.derived.is_overdue,
                payment_type=r.payment_type,
                module_name=r.module.module_name if r.module else None
            ) for r in overdue[:5]  # Top 5 overdue
        ],
        "recent_receivables": [
            ReceivableSummary(
                id=r.id,
                client_name=r.client_name,
                project_title=r.project_title,
                contract_value=r.contract_value,
                status=r.status,
                expected_payment_date=r.expected_payment_date,
                is_overdue=r.derived.is_overdue,
                payment_type=r.payment_type,
                module_name=r.module.module_name if r.module else None
            ) for r in recent_result.items
        ]
    }