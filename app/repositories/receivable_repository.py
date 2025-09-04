from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, desc, case
from decimal import Decimal
from .base_repository import BaseRepository
from models.models import Receivable, ReceivableStatus, Bid, Team, ProjectModule, BidStatus, PaymentType, ModuleStatus
from schemas.receivable import ReceivableCreate, ReceivableUpdate, ReceivableListFilter, ProjectModuleCreate
from schemas.common import PaginatedResponse
from interface.Irepositories.receivable_repository import IReceivableRepository
from utils.receivables_sort_values import _apply_sorting_generic, _apply_receivable_filters
import logging

logger = logging.getLogger(__name__)


class ReceivableRepository(BaseRepository[Receivable], IReceivableRepository):
    def __init__(self):
        super().__init__(Receivable)

    def create(self, db: Session, receivable_data: ReceivableCreate, created_by_id: UUID) -> Receivable:
        """Create a new receivable."""
        try:
            receivable_dict = receivable_data.dict()
            receivable_dict['created_by_id'] = created_by_id
            return super().create(db, **receivable_dict)
        except Exception as e:
            logger.error(f"Error creating receivable: {e}")
            raise

    def create_module(self, db: Session, bid_id: UUID, module_data: ProjectModuleCreate) -> ProjectModule:
        """Create a new project module."""
        try:
            module_dict = module_data.dict()
            module_dict['bid_id'] = bid_id
            
            module = ProjectModule(**module_dict)
            db.add(module)
            db.commit()
            db.refresh(module)
            return module
        except Exception as e:
            logger.error(f"Error creating module: {e}")
            db.rollback()
            raise

    def create_bulk_modules_and_receivables(self, db: Session, bid_id: UUID, modules_data: List[ProjectModuleCreate], 
                                          created_by_id: UUID, currency: str = "USD") -> List[Receivable]:
        """Create multiple modules and their corresponding receivables."""
        try:
            receivables = []
            
            # First, update bid to indicate it has modules
            bid = db.query(Bid).filter(Bid.id == bid_id).first()
            if bid:
                bid.has_modules = True
                db.commit()
            
            for module_data in modules_data:
                # Create module
                module = self.create_module(db, bid_id, module_data)
                
                # Create receivable for this module
                receivable_data = ReceivableCreate(
                    bid_id=bid_id,
                    module_id=module.id,
                    contract_value=module_data.module_amount,
                    expected_payment_date=module_data.expected_payment_date if hasattr(module_data, 'expected_payment_date') else date.today() + timedelta(days=30),
                    payment_type=PaymentType.MODULE_BASED,
                    currency=currency
                )
                
                receivable = self.create(db, receivable_data, created_by_id)
                receivables.append(receivable)
            
            return receivables
        except Exception as e:
            logger.error(f"Error creating bulk modules and receivables: {e}")
            db.rollback()
            raise

    def get_by_id(self, db: Session, receivable_id: UUID) -> Optional[Receivable]:
        """Get receivable by ID with related data."""
        try:
            receivable = db.query(Receivable).options(
                joinedload(Receivable.bid),
                joinedload(Receivable.module),
                joinedload(Receivable.created_by)
            ).filter(Receivable.id == receivable_id).first()
            
            if receivable:
                receivable = self._enrich_receivable_with_derived_fields(receivable)
            
            return receivable
        except Exception as e:
            logger.error(f"Error getting receivable {receivable_id}: {e}")
            return None

    def get_by_bid(self, db: Session, bid_id: UUID) -> List[Receivable]:
        """Get all receivables for a bid."""
        try:
            receivables = db.query(Receivable).options(
                joinedload(Receivable.bid),
                joinedload(Receivable.module),
                joinedload(Receivable.created_by)
            ).filter(Receivable.bid_id == bid_id).all()
            
            return self._enrich_receivables_with_derived_fields(receivables)
        except Exception as e:
            logger.error(f"Error getting receivables by bid {bid_id}: {e}")
            return []

    def get_by_module(self, db: Session, module_id: UUID) -> Optional[Receivable]:
        """Get receivable by module ID."""
        try:
            receivable = db.query(Receivable).options(
                joinedload(Receivable.bid),
                joinedload(Receivable.module),
                joinedload(Receivable.created_by)
            ).filter(Receivable.module_id == module_id).first()
            
            if receivable:
                receivable = self._enrich_receivable_with_derived_fields(receivable)
            
            return receivable
        except Exception as e:
            logger.error(f"Error getting receivable by module {module_id}: {e}")
            return None

    def _calculate_derived_fields(self, receivable: Receivable) -> Dict[str, Any]:
        """Calculate derived fields for receivable."""
        today = date.today()
        expected_date = receivable.expected_payment_date
        
        # Calculate is_overdue
        is_overdue = expected_date < today and receivable.status in [
            ReceivableStatus.PENDING, ReceivableStatus.PARTIAL
        ]
        
        # Calculate days_overdue (positive if overdue, 0 if not)
        days_overdue = max(0, (today - expected_date).days) if expected_date < today else 0
        
        # Calculate days_until_due (positive if future, negative if past)
        days_until_due = (expected_date - today).days
        
        # Calculate payment_delay (only if paid and we have actual payment date)
        payment_delay = None
        if (receivable.status == ReceivableStatus.PAID and 
            receivable.actual_payment_date and 
            receivable.expected_payment_date):
            payment_delay = (receivable.actual_payment_date - receivable.expected_payment_date).days
        
        return {
            "is_overdue": is_overdue,
            "days_overdue": days_overdue,
            "days_until_due": days_until_due,
            "payment_delay": payment_delay
        }

    def _enrich_receivable_with_derived_fields(self, receivable: Receivable) -> Receivable:
        """Add derived fields to receivable object."""
        derived_data = self._calculate_derived_fields(receivable)
        
        # Add derived as a dynamic attribute
        from types import SimpleNamespace
        receivable.derived = SimpleNamespace(**derived_data)
        
        return receivable

    def _enrich_receivables_with_derived_fields(self, receivables: List[Receivable]) -> List[Receivable]:
        """Add derived fields to list of receivables."""
        return [self._enrich_receivable_with_derived_fields(r) for r in receivables]

    def get_all(self, db: Session, filters: ReceivableListFilter, skip: int = 0, 
                limit: int = 20, sort_by: str = "-created_at") -> PaginatedResponse:
        """Get all receivables with filters and pagination."""
        try:
            query = db.query(Receivable).options(
                joinedload(Receivable.bid),
                joinedload(Receivable.module),
                joinedload(Receivable.created_by)
            )
            
            # Apply filters
            query = self._apply_receivable_filters(query, filters)
            
            # Get total count before pagination
            total_count = query.count()
            
            # Apply sorting using the utility function
            query = _apply_sorting_generic(query, sort_by, Receivable)
            
            # Apply pagination
            items = query.offset(skip).limit(limit).all()
            
            # Enrich items with derived fields
            items = self._enrich_receivables_with_derived_fields(items)
            
            # Build next cursor if needed
            next_cursor = None
            if len(items) == limit and skip + limit < total_count:
                next_cursor = f"offset:{skip + limit}"
            
            return PaginatedResponse(
                items=items,
                next_cursor=next_cursor,
                count=len(items)
            )
        except Exception as e:
            logger.error(f"Error getting receivables: {e}")
            return PaginatedResponse(
                items=[], 
                next_cursor=None, 
                count=0
            )

    def _apply_receivable_filters(self, query, filters: ReceivableListFilter):
        """Apply filters to receivable query."""
        if filters.team_id:
            query = query.join(Receivable.bid).filter(Bid.team_id == filters.team_id)
        
        if filters.status:
            query = query.filter(Receivable.status == filters.status)
        
        if filters.payment_type:
            query = query.filter(Receivable.payment_type == filters.payment_type)
        
        if filters.date_from:
            query = query.filter(Receivable.expected_payment_date >= filters.date_from)
        
        if filters.date_to:
            query = query.filter(Receivable.expected_payment_date <= filters.date_to)
        
        if filters.client_name:
            query = query.join(Receivable.bid).filter(
                Bid.client_name.ilike(f"%{filters.client_name}%")
            )
        
        if filters.module_id:
            query = query.filter(Receivable.module_id == filters.module_id)
        
        return query

    def get_by_team(self, db: Session, team_id: UUID, filters: ReceivableListFilter,
                   skip: int = 0, limit: int = 20) -> PaginatedResponse:
        """Get receivables by team with filters."""
        filters.team_id = team_id
        return self.get_all(db, filters, skip, limit)

    def get_by_status(self, db: Session, status: ReceivableStatus, 
                     skip: int = 0, limit: int = 20) -> PaginatedResponse:
        """Get receivables by status."""
        filters = ReceivableListFilter(status=status)
        return self.get_all(db, filters, skip, limit)

    def update(self, db: Session, receivable_id: UUID, receivable_data: ReceivableUpdate) -> Optional[Receivable]:
        """Update receivable."""
        try:
            receivable = self.get_by_id(db, receivable_id)
            if not receivable:
                return None
            
            update_data = receivable_data.dict(exclude_unset=True)
            return super().update(db, receivable, **update_data)
        except Exception as e:
            logger.error(f"Error updating receivable {receivable_id}: {e}")
            return None

    def update_status(self, db: Session, receivable_id: UUID, status: ReceivableStatus) -> Optional[Receivable]:
        """Update receivable status."""
        try:
            receivable = self.get_by_id(db, receivable_id)
            if not receivable:
                return None
            
            receivable.status = status
            
            # Also update module status if it's a module-based payment
            if receivable.module:
                if status == ReceivableStatus.PAID:
                    receivable.module.status = ModuleStatus.PAID
                elif status == ReceivableStatus.PARTIAL:
                    receivable.module.status = ModuleStatus.IN_PROGRESS
            
            db.commit()
            db.refresh(receivable)
            
            return self._enrich_receivable_with_derived_fields(receivable)
        except Exception as e:
            logger.error(f"Error updating receivable status {receivable_id}: {e}")
            db.rollback()
            return None

    def delete(self, db: Session, receivable_id: UUID) -> bool:
        """Delete receivable."""
        return super().delete(db, receivable_id)

    def get_overdue(self, db: Session, team_id: Optional[UUID] = None) -> List[Receivable]:
        """Get overdue receivables."""
        try:
            today = date.today()
            query = db.query(Receivable).options(
                joinedload(Receivable.bid),
                joinedload(Receivable.module),
                joinedload(Receivable.created_by)
            ).filter(
                and_(
                    Receivable.expected_payment_date < today,
                    Receivable.status.in_([ReceivableStatus.PENDING, ReceivableStatus.PARTIAL])
                )
            )
            
            if team_id:
                query = query.join(Receivable.bid).filter(Bid.team_id == team_id)
            
            receivables = query.all()
            return self._enrich_receivables_with_derived_fields(receivables)
        except Exception as e:
            logger.error(f"Error getting overdue receivables: {e}")
            return []

    def get_statistics(self, db: Session, team_id: Optional[UUID] = None) -> Dict[str, Any]:
        """Get receivable statistics."""
        try:
            query = db.query(Receivable).join(Receivable.bid)
            if team_id:
                query = query.filter(Bid.team_id == team_id)
            
            # Get basic counts and totals
            stats = db.query(
                func.count(Receivable.id).label('total_receivables'),
                func.sum(Receivable.contract_value).label('total_value'),
                func.sum(
                    case(
                        (Receivable.status == ReceivableStatus.PAID, Receivable.payment_amount),
                        else_=0
                    )
                ).label('paid_value'),
                func.sum(
                    case(
                        (Receivable.status == ReceivableStatus.PENDING, Receivable.contract_value),
                        else_=0
                    )
                ).label('pending_value'),
                func.sum(
                    case(
                        (Receivable.status == ReceivableStatus.PARTIAL, Receivable.contract_value),
                        else_=0
                    )
                ).label('partial_value')
            ).select_from(Receivable).join(Bid)
            
            if team_id:
                stats = stats.filter(Bid.team_id == team_id)
            
            result = stats.first()
            
            # Get overdue statistics
            overdue_query = query.filter(
                and_(
                    Receivable.expected_payment_date < date.today(),
                    Receivable.status.in_([ReceivableStatus.PENDING, ReceivableStatus.PARTIAL])
                )
            )
            
            overdue_stats = overdue_query.with_entities(
                func.count(Receivable.id).label('overdue_count'),
                func.sum(Receivable.contract_value).label('overdue_value')
            ).first()
            
            # Get status breakdown
            status_breakdown = query.with_entities(
                Receivable.status,
                func.count(Receivable.id).label('count'),
                func.sum(Receivable.contract_value).label('value')
            ).group_by(Receivable.status).all()
            
            # Get payment type breakdown
            payment_type_breakdown = query.with_entities(
                Receivable.payment_type,
                func.count(Receivable.id).label('count'),
                func.sum(Receivable.contract_value).label('value')
            ).group_by(Receivable.payment_type).all()
            
            # Get currency breakdown
            currency_breakdown = query.with_entities(
                Receivable.currency,
                func.count(Receivable.id).label('count'),
                func.sum(Receivable.contract_value).label('value')
            ).group_by(Receivable.currency).all()
            
            # Get current month and next month values
            today = date.today()
            current_month_start = date(today.year, today.month, 1)
            if today.month == 12:
                next_month_start = date(today.year + 1, 1, 1)
                next_month_end = date(today.year + 1, 2, 1) - timedelta(days=1)
            else:
                next_month_start = date(today.year, today.month + 1, 1)
                if today.month == 11:
                    next_month_end = date(today.year + 1, 1, 1) - timedelta(days=1)
                else:
                    next_month_end = date(today.year, today.month + 2, 1) - timedelta(days=1)
            
            current_month_query = query.filter(
                and_(
                    Receivable.expected_payment_date >= current_month_start,
                    Receivable.expected_payment_date < next_month_start
                )
            )
            current_month_value = current_month_query.with_entities(
                func.sum(Receivable.contract_value)
            ).scalar() or Decimal('0')
            
            next_month_query = query.filter(
                and_(
                    Receivable.expected_payment_date >= next_month_start,
                    Receivable.expected_payment_date <= next_month_end
                )
            )
            next_month_value = next_month_query.with_entities(
                func.sum(Receivable.contract_value)
            ).scalar() or Decimal('0')
            
            # Calculate average payment days for paid receivables
            paid_receivables = query.filter(
                and_(
                    Receivable.status == ReceivableStatus.PAID,
                    Receivable.actual_payment_date.isnot(None)
                )
            ).all()
            
            payment_days = []
            for receivable in paid_receivables:
                if receivable.actual_payment_date and receivable.expected_payment_date:
                    days = (receivable.actual_payment_date - receivable.expected_payment_date).days
                    payment_days.append(days)
            
            avg_payment_days = None
            if payment_days:
                avg_payment_days = sum(payment_days) / len(payment_days)
            
            # Calculate collection rate
            total_value = result.total_value or Decimal('0')
            paid_value = result.paid_value or Decimal('0')
            collection_rate = (paid_value / total_value * 100) if total_value > 0 else Decimal('0')

            return {
                'total_receivables': result.total_receivables or 0,
                'total_value': result.total_value or Decimal('0'),
                'paid_value': result.paid_value or Decimal('0'),
                'pending_value': result.pending_value or Decimal('0'),
                'partial_value': result.partial_value or Decimal('0'),
                'overdue_value': overdue_stats.overdue_value or Decimal('0'),
                'overdue_count': overdue_stats.overdue_count or 0,
                'avg_payment_days': Decimal(str(avg_payment_days)) if avg_payment_days else None,
                'collection_rate': collection_rate,
                'by_status': [
                    {
                        'status': breakdown.status.value,
                        'count': breakdown.count,
                        'value': breakdown.value or Decimal('0')
                    }
                    for breakdown in status_breakdown
                ],
                'by_payment_type': [
                    {
                        'payment_type': breakdown.payment_type.value,
                        'count': breakdown.count,
                        'value': breakdown.value or Decimal('0')
                    }
                    for breakdown in payment_type_breakdown
                ],
                'by_currency': [
                    {
                        'currency': breakdown.currency,
                        'count': breakdown.count,
                        'value': breakdown.value or Decimal('0')
                    }
                    for breakdown in currency_breakdown
                ],
                'current_month_value': current_month_value,
                'next_month_value': next_month_value
            }
            
        except Exception as e:
            logger.error(f"Error getting receivable statistics: {e}")
            return {}

    def get_team_statistics(self, db: Session, team_id: UUID) -> Dict[str, Any]:
        """Get team receivable statistics."""
        return self.get_statistics(db, team_id)

    def get_monthly_summary(self, db: Session, year: int, month: int, 
                       team_id: Optional[UUID] = None) -> Dict[str, Any]:
        """Get monthly receivables summary."""
        try:
            # Create date range for the month
            start_date = date(year, month, 1)
            if month == 12:
                end_date = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = date(year, month + 1, 1) - timedelta(days=1)
            
            query = db.query(Receivable).join(Receivable.bid).filter(
                and_(
                    Receivable.expected_payment_date >= start_date,
                    Receivable.expected_payment_date <= end_date
                )
            )
            
            if team_id:
                query = query.filter(Bid.team_id == team_id)
            
            # Get summary statistics
            summary = query.with_entities(
                func.count(Receivable.id).label('count'),
                func.sum(Receivable.contract_value).label('expected_value'),
                func.sum(
                    case(
                        (Receivable.status == ReceivableStatus.PAID, Receivable.payment_amount),
                        else_=0
                    )
                ).label('actual_received')
            ).first()
            
            # Get status breakdown
            status_breakdown = query.with_entities(
                Receivable.status,
                func.count(Receivable.id).label('count'),
                func.sum(Receivable.contract_value).label('value')
            ).group_by(Receivable.status).all()
            
            return {
                'year': year,
                'month': month,
                'total_receivables': summary.count or 0,
                'expected_value': summary.expected_value or Decimal('0'),
                'actual_received': summary.actual_received or Decimal('0'),
                'status_breakdown': [
                    {
                        'status': breakdown.status.value,
                        'count': breakdown.count,
                        'value': breakdown.value or Decimal('0')
                    }
                    for breakdown in status_breakdown
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting monthly summary: {e}")
            return {}
        
    def mark_overdue(self, db: Session) -> int:
        """Mark overdue receivables and return count."""
        try:
            today = date.today()
            updated_count = db.query(Receivable).filter(
                and_(
                    Receivable.expected_payment_date < today,
                    Receivable.status.in_([ReceivableStatus.PENDING, ReceivableStatus.PARTIAL])
                )
            ).update({"status": ReceivableStatus.OVERDUE})
            
            db.commit()
            return updated_count
            
        except Exception as e:
            logger.error(f"Error marking overdue receivables: {e}")
            db.rollback()
            return 0

    def get_payment_trends(self, db: Session, team_id: Optional[UUID] = None,
                        days: int = 90) -> List[Dict[str, Any]]:
        """Get payment trends over time."""
        try:
            start_date = date.today() - timedelta(days=days)
            
            query = db.query(
                func.date(Receivable.expected_payment_date).label('date'),
                func.count(Receivable.id).label('expected_count'),
                func.sum(Receivable.contract_value).label('expected_value'),
                func.count(
                    case(
                        (Receivable.status == ReceivableStatus.PAID, 1),
                        else_=None
                    )
                ).label('paid_count'),
                func.sum(
                    case(
                        (Receivable.status == ReceivableStatus.PAID, Receivable.payment_amount),
                        else_=0
                    )
                ).label('paid_value')
            ).select_from(Receivable).join(Bid).filter(
                Receivable.expected_payment_date >= start_date
            )
            
            if team_id:
                query = query.filter(Bid.team_id == team_id)
            
            results = query.group_by(func.date(Receivable.expected_payment_date)).order_by(
                func.date(Receivable.expected_payment_date)
            ).all()
            
            # Create running total for cash flow projection
            cash_flow = []
            running_total = Decimal('0')
            
            for result in results:
                running_total += result.expected_amount or Decimal('0')
                cash_flow.append({
                    'date': result.date.isoformat(),
                    'daily_amount': float(result.expected_amount or 0),
                    'cumulative_amount': float(running_total)
                })
            
            return cash_flow
            
        except Exception as e:
            logger.error(f"Error calculating cash flow: {e}")
            result = query.group_by(func.date(Receivable.expected_payment_date)).all()
            
            return [
                {
                    'date': result.date.isoformat(),
                    'expected_count': result.expected_count,
                    'expected_value': float(result.expected_value or 0),
                    'paid_count': result.paid_count,
                    'paid_value': float(result.paid_value or 0),
                    'payment_rate': (result.paid_count / result.expected_count * 100) if result.expected_count > 0 else 0
                }
                for result in results
            ]
            
        except Exception as e:
            logger.error(f"Error getting payment trends: {e}")
            return []

    def get_client_summary(self, db: Session, team_id: Optional[UUID] = None) -> List[Dict[str, Any]]:
        """Get summary by client."""
        try:
            query = db.query(
                Bid.client_name,
                func.count(Receivable.id).label('total_receivables'),
                func.sum(Receivable.contract_value).label('total_value'),
                func.sum(
                    case(
                        (Receivable.status == ReceivableStatus.PAID, Receivable.payment_amount),
                        else_=0
                    )
                ).label('paid_value'),
                func.count(
                    case(
                        (Receivable.status == ReceivableStatus.OVERDUE, 1),
                        else_=None
                    )
                ).label('overdue_count')
            ).select_from(Receivable).join(Bid)
            
            if team_id:
                query = query.filter(Bid.team_id == team_id)
            
            results = query.group_by(Bid.client_name).order_by(
                desc(func.sum(Receivable.contract_value))
            ).all()
            
            return [
                {
                    'client_name': result.client_name,
                    'total_receivables': result.total_receivables,
                    'total_value': float(result.total_value or 0),
                    'paid_value': float(result.paid_value or 0),
                    'overdue_count': result.overdue_count,
                    'payment_rate': (result.paid_value / result.total_value * 100) if result.total_value > 0 else 0
                }
                for result in results
            ]
            
        except Exception as e:
            logger.error(f"Error getting client summary: {e}")
            return []
        
    def calculate_cash_flow(self, db: Session, team_id: Optional[UUID] = None,
                        days_ahead: int = 90) -> List[Dict[str, Any]]:
        """Calculate projected cash flow."""
        try:
            start_date = date.today()
            end_date = start_date + timedelta(days=days_ahead)
            
            query = db.query(
                func.date(Receivable.expected_payment_date).label('date'),
                func.sum(Receivable.contract_value).label('expected_amount')
            ).select_from(Receivable).join(Bid).filter(
                and_(
                    Receivable.expected_payment_date >= start_date,
                    Receivable.expected_payment_date <= end_date,
                    Receivable.status.in_([ReceivableStatus.PENDING, ReceivableStatus.PARTIAL])
                )
            )
            
            if team_id:
                query = query.filter(Bid.team_id == team_id)
            
            results = query.group_by(func.date(Receivable.expected_payment_date)).order_by(
                func.date(Receivable.expected_payment_date)
            ).all()
            
            # Create running total for cash flow projection
            cash_flow = []
            running_total = Decimal('0')
            
            for result in results:
                running_total += result.expected_amount or Decimal('0')
                cash_flow.append({
                    'date': result.date.isoformat(),
                    'daily_amount': float(result.expected_amount or 0),
                    'cumulative_amount': float(running_total)
                })
            
            return cash_flow
            
        except Exception as e:
            logger.error(f"Error calculating cash flow: {e}")
            return []
    
