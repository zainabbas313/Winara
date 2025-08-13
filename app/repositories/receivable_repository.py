from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, desc
from decimal import Decimal
from .base_repository import BaseRepository
from models.models import Receivable, ReceivableStatus, Bid, Team
from schemas.receivable import ReceivableCreate, ReceivableUpdate, ReceivableListFilter
from schemas.common import PaginatedResponse
from interface.Irepositories.receivable_repository import IReceivableRepository
from utils.helpers import is_overdue_payment, calculate_overdue_days
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

    def get_by_id(self, db: Session, receivable_id: UUID) -> Optional[Receivable]:
        """Get receivable by ID with related data."""
        try:
            return db.query(Receivable).options(
                joinedload(Receivable.bid),
                joinedload(Receivable.team),
                joinedload(Receivable.created_by)
            ).filter(Receivable.id == receivable_id).first()
        except Exception as e:
            logger.error(f"Error getting receivable {receivable_id}: {e}")
            return None

    def get_by_bid(self, db: Session, bid_id: UUID) -> Optional[Receivable]:
        """Get receivable by bid ID."""
        try:
            return db.query(Receivable).filter(Receivable.bid_id == bid_id).first()
        except Exception as e:
            logger.error(f"Error getting receivable by bid {bid_id}: {e}")
            return None

    def get_all(self, db: Session, filters: ReceivableListFilter, skip: int = 0, 
                limit: int = 20, sort_by: str = "-created_at") -> PaginatedResponse:
        """Get all receivables with filters and pagination."""
        try:
            query = db.query(Receivable).options(
                joinedload(Receivable.bid),
                joinedload(Receivable.team)
            )
            
            # Apply filters
            query = self._apply_receivable_filters(query, filters)
            
            # Apply sorting
            query = self._apply_sorting(query, sort_by)
            
            # Get total count
            total_count = query.count()
            
            # Apply pagination
            items = query.offset(skip).limit(limit).all()
            
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
            return PaginatedResponse(items=[], next_cursor=None, count=0)

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
            db.commit()
            db.refresh(receivable)
            
            return receivable
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
            query = db.query(Receivable).filter(
                and_(
                    Receivable.expected_payment_date < today,
                    Receivable.status.in_([ReceivableStatus.PENDING, ReceivableStatus.PARTIAL])
                )
            )
            
            if team_id:
                query = query.filter(Receivable.team_id == team_id)
            
            return query.all()
        except Exception as e:
            logger.error(f"Error getting overdue receivables: {e}")
            return []

    def get_statistics(self, db: Session, team_id: Optional[UUID] = None) -> Dict[str, Any]:
        """Get receivable statistics."""
        try:
            query = db.query(Receivable)
            if team_id:
                query = query.filter(Receivable.team_id == team_id)
            
            # Get basic counts and totals
            stats = db.query(
                func.count(Receivable.id).label('total_receivables'),
                func.sum(Receivable.contract_value).label('total_value'),
                func.sum(
                    func.case(
                        (Receivable.status == ReceivableStatus.PAID, Receivable.payment_amount),
                        else_=0
                    )
                ).label('paid_value'),
                func.sum(
                    func.case(
                        (Receivable.status.in_([ReceivableStatus.PENDING, ReceivableStatus.PARTIAL]), 
                         Receivable.contract_value),
                        else_=0
                    )
                ).label('pending_value')
            )
            
            if team_id:
                stats = stats.filter(Receivable.team_id == team_id)
            
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
            
            return {
                'total_receivables': result.total_receivables or 0,
                'total_value': result.total_value or Decimal('0'),
                'paid_value': result.paid_value or Decimal('0'),
                'pending_value': result.pending_value or Decimal('0'),
                'overdue_value': overdue_stats.overdue_value or Decimal('0'),
                'overdue_count': overdue_stats.overdue_count or 0,
                'avg_payment_days': Decimal(str(avg_payment_days)) if avg_payment_days else None
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
            
            query = db.query(Receivable).filter(
                and_(
                    Receivable.expected_payment_date >= start_date,
                    Receivable.expected_payment_date <= end_date
                )
            )
            
            if team_id:
                query = query.filter(Receivable.team_id == team_id)
            
            # Get summary statistics
            summary = query.with_entities(
                func.count(Receivable.id).label('count'),
                func.sum(Receivable.contract_value).label('expected_value'),
                func.sum(
                    func.case(
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
                    func.case(
                        (Receivable.status == ReceivableStatus.PAID, 1),
                        else_=None
                    )
                ).label('paid_count'),
                func.sum(
                    func.case(
                        (Receivable.status == ReceivableStatus.PAID, Receivable.payment_amount),
                        else_=0
                    )
                ).label('paid_value')
            ).filter(Receivable.expected_payment_date >= start_date)
            
            if team_id:
                query = query.filter(Receivable.team_id == team_id)
            
            results = query.group_by(func.date(Receivable.expected_payment_date)).all()
            
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
                Receivable.client_name,
                func.count(Receivable.id).label('total_receivables'),
                func.sum(Receivable.contract_value).label('total_value'),
                func.sum(
                    func.case(
                        (Receivable.status == ReceivableStatus.PAID, Receivable.payment_amount),
                        else_=0
                    )
                ).label('paid_value'),
                func.count(
                    func.case(
                        (Receivable.status == ReceivableStatus.OVERDUE, 1),
                        else_=None
                    )
                ).label('overdue_count')
            )
            
            if team_id:
                query = query.filter(Receivable.team_id == team_id)
            
            results = query.group_by(Receivable.client_name).order_by(
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
            ).filter(
                and_(
                    Receivable.expected_payment_date >= start_date,
                    Receivable.expected_payment_date <= end_date,
                    Receivable.status.in_([ReceivableStatus.PENDING, ReceivableStatus.PARTIAL])
                )
            )
            
            if team_id:
                query = query.filter(Receivable.team_id == team_id)
            
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

    def _apply_receivable_filters(self, query, filters: ReceivableListFilter):
        """Apply receivable-specific filters to query."""
        if filters.team_id:
            query = query.filter(Receivable.team_id == filters.team_id)
        
        if filters.status:
            query = query.filter(Receivable.status == filters.status)
        
        if filters.date_from:
            query = query.filter(Receivable.expected_payment_date >= filters.date_from)
        
        if filters.date_to:
            query = query.filter(Receivable.expected_payment_date <= filters.date_to)
        
        if filters.client_name:
            search_term = f"%{filters.client_name}%"
            query = query.filter(Receivable.client_name.ilike(search_term))
        
        return query