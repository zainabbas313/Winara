from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, desc, case
from decimal import Decimal
from .base_repository import BaseRepository
from models.models import Receivable, ReceivableStatus, Bid, Team, ProjectModule, BidStatus, PaymentType, ModuleStatus
from schemas.receivable import ReceivableCreate, ReceivableUpdate, ReceivableListFilter
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
            # Ensure payment_type is MODULE_BASED for new workflow
            receivable_dict['payment_type'] = PaymentType.MODULE_BASED
            return super().create(db, **receivable_dict)
        except Exception as e:
            logger.error(f"Error creating receivable: {e}")
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
            ).filter(Receivable.bid_id == bid_id).order_by(
                # Order by module sequence if module exists
                case(
                    (Receivable.module_id.isnot(None), ProjectModule.order_sequence),
                    else_=Receivable.created_at
                )
            ).outerjoin(ProjectModule, Receivable.module_id == ProjectModule.id).all()
            
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

    def get_by_team(self, db: Session, team_id: UUID, filters: ReceivableListFilter = None,
                   skip: int = 0, limit: int = 20, sort_by: str = "-created_at") -> PaginatedResponse:
        """Get receivables by team with filters."""
        if not filters:
            filters = ReceivableListFilter()
        filters.team_id = team_id
        return self.get_all(db, filters, skip, limit, sort_by)

    def get_modules_without_receivables(self, db: Session, team_id: Optional[UUID] = None) -> List[ProjectModule]:
        """Get modules that don't have receivables yet."""
        try:
            # Start with modules that belong to won bids
            query = db.query(ProjectModule).join(
                Bid, ProjectModule.bid_id == Bid.id
            ).filter(
                Bid.status == BidStatus.WON
            ).outerjoin(
                Receivable, ProjectModule.id == Receivable.module_id
            ).filter(
                Receivable.id.is_(None)  # No receivable exists
            ).options(
                joinedload(ProjectModule.bid)
            )
            
            # Apply team filter if specified
            if team_id:
                query = query.filter(Bid.team_id == team_id)
            
            return query.order_by(
                Bid.created_at.desc(),
                ProjectModule.order_sequence
            ).all()
            
        except Exception as e:
            logger.error(f"Error getting modules without receivables: {e}")
            return []

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
            query = _apply_receivable_filters(query, filters)
            
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
            
            # If status is being updated to PAID, also update the module status
            if update_data.get('status') == ReceivableStatus.PAID and receivable.module:
                receivable.module.status = ModuleStatus.PAID
                db.commit()
            
            return super().update(db, receivable, **update_data)
        except Exception as e:
            logger.error(f"Error updating receivable {receivable_id}: {e}")
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
            
            receivables = query.order_by(Receivable.expected_payment_date).all()
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
            stats = query.with_entities(
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
            ).first()
            
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
            
            # Get modules statistics
            modules_query = db.query(ProjectModule).join(Bid)
            if team_id:
                modules_query = modules_query.filter(Bid.team_id == team_id)
            
            modules_with_receivables = modules_query.join(
                Receivable, ProjectModule.id == Receivable.module_id
            ).count()
            
            total_modules = modules_query.count()
            modules_without_receivables = total_modules - modules_with_receivables
            
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
            total_value = stats.total_value or Decimal('0')
            paid_value = stats.paid_value or Decimal('0')
            collection_rate = (paid_value / total_value * 100) if total_value > 0 else Decimal('0')

            return {
                'total_receivables': stats.total_receivables or 0,
                'total_value': stats.total_value or Decimal('0'),
                'paid_value': stats.paid_value or Decimal('0'),
                'pending_value': stats.pending_value or Decimal('0'),
                'partial_value': stats.partial_value or Decimal('0'),
                'overdue_value': overdue_stats.overdue_value or Decimal('0'),
                'overdue_count': overdue_stats.overdue_count or 0,
                'avg_payment_days': Decimal(str(avg_payment_days)) if avg_payment_days else None,
                'collection_rate': collection_rate,
                'modules_with_receivables': modules_with_receivables,
                'modules_without_receivables': modules_without_receivables,
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