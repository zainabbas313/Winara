from pydantic import BaseModel, validator, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from models.models import ModuleStatus


class ModuleBase(BaseModel):
    """Base module schema with common fields."""
    module_name: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    module_amount: Decimal = Field(..., gt=0)
    order_sequence: int = Field(default=1, ge=1)


class ModuleCreate(ModuleBase):
    """Schema for creating a new module."""
    bid_id: UUID

    @validator('module_name')
    def validate_module_name(cls, v):
        if not v or not v.strip():
            raise ValueError('Module name cannot be empty')
        return v.strip()

    @validator('module_amount')
    def validate_module_amount(cls, v):
        if v <= 0:
            raise ValueError('Module amount must be greater than 0')
        return v


class ModuleBulkCreate(BaseModel):
    """Schema for creating multiple modules for a bid."""
    bid_id: UUID
    modules: List[ModuleBase]

    @validator('modules')
    def validate_modules(cls, v):
        if not v or len(v) == 0:
            raise ValueError('At least one module is required')
        
        # Check for duplicate order sequences
        sequences = [module.order_sequence for module in v]
        if len(sequences) != len(set(sequences)):
            raise ValueError('Order sequences must be unique')
        
        return v


class ModuleUpdate(BaseModel):
    """Schema for updating a module."""
    module_name: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    module_amount: Optional[Decimal] = Field(None, gt=0)
    order_sequence: Optional[int] = Field(None, ge=1)
    status: Optional[ModuleStatus] = None

    @validator('module_name')
    def validate_module_name(cls, v):
        if v is not None and (not v or not v.strip()):
            raise ValueError('Module name cannot be empty')
        return v.strip() if v else v

    @validator('module_amount')
    def validate_module_amount(cls, v):
        if v is not None and v <= 0:
            raise ValueError('Module amount must be greater than 0')
        return v


class ModuleStatusUpdate(BaseModel):
    """Schema for updating module status."""
    status: ModuleStatus

    @validator('status')
    def validate_status_transition(cls, v):
        # You can add business logic here for valid status transitions
        return v


class ModuleResponse(ModuleBase):
    """Response schema for module data."""
    id: UUID
    bid_id: UUID
    status: ModuleStatus
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    # Related data
    bid_title: Optional[str] = None  # From bid
    has_receivable: bool = False  # Whether receivable exists for this module
    receivable_id: Optional[UUID] = None  # ID of associated receivable if exists

    class Config:
        from_attributes = True


class ModuleSummary(BaseModel):
    """Summary schema for dashboard and lists."""
    id: UUID
    module_name: str
    module_amount: Decimal
    status: ModuleStatus
    order_sequence: int
    has_receivable: bool

    class Config:
        from_attributes = True


class ModuleListFilter(BaseModel):
    """Filters for module listing."""
    bid_id: Optional[UUID] = None
    status: Optional[ModuleStatus] = None
    has_receivable: Optional[bool] = None


class BidModulesResponse(BaseModel):
    """Response for bid with its modules."""
    bid_id: UUID
    job_title: str
    client_name: str
    total_modules: int
    total_amount: Decimal
    modules: List[ModuleResponse]
    has_receivables: bool  # Whether any module has receivables
    can_create_modules: bool  # Whether new modules can be created
    can_delete_modules: bool  # Whether modules can be deleted

    class Config:
        from_attributes = True


class ModuleStats(BaseModel):
    """Statistics schema for modules."""
    total_modules: int
    total_amount: Decimal
    by_status: List[dict]
    avg_module_amount: Optional[Decimal]
    modules_with_receivables: int
    modules_without_receivables: int


class BidStatusCheck(BaseModel):
    """Response for checking bid status before module operations."""
    bid_id: UUID
    job_title: str
    has_modules: bool
    module_count: int
    has_receivables: bool
    receivable_count: int
    can_create_modules: bool
    can_delete_modules: bool
    message: str
    recommendations: List[str]

    class Config:
        from_attributes = True