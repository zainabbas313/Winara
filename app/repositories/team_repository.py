from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func
from decimal import Decimal
from .base_repository import BaseRepository
from models.models import Team, TeamGoal, User, Bid, BidStatus
from schemas.team import TeamCreate, TeamUpdate, TeamListFilter, TeamGoalCreate, TeamGoalUpdate
from schemas.common import PaginatedResponse
from interface.Irepositories.team_repository import ITeamRepository
from utils.sort_values import _apply_sorting
import logging

logger = logging.getLogger(__name__)


class TeamRepository(BaseRepository[Team], ITeamRepository):
    def __init__(self):
        super().__init__(Team)

    def create(self, db: Session, team_data: TeamCreate, created_by_id: UUID) -> Team:
        """Create a new team."""
        try:
            team_dict = team_data.dict()
            team_dict['created_by_id'] = created_by_id
            return super().create(db, **team_dict)
        except Exception as e:
            logger.error(f"Error creating team: {e}")
            raise

    def get_by_id(self, db: Session, team_id: UUID) -> Optional[Team]:
        """Get team by ID with related data."""
        try:
            return db.query(Team).options(
                joinedload(Team.sub_admin),
                joinedload(Team.created_by),
                joinedload(Team.members)
            ).filter(Team.id == team_id).first()
        except Exception as e:
            logger.error(f"Error getting team {team_id}: {e}")
            return None

    def get_by_name(self, db: Session, name: str) -> Optional[Team]:
        """Get team by name."""
        try:
            return db.query(Team).filter(Team.name == name).first()
        except Exception as e:
            logger.error(f"Error getting team by name {name}: {e}")
            return None

    def get_all(self, db: Session, filters: TeamListFilter, skip: int = 0, 
                limit: int = 20, sort_by: str = "-created_at") -> PaginatedResponse:
        """Get all teams with filters and pagination."""
        try:
            query = db.query(Team).options(
                joinedload(Team.sub_admin),
                joinedload(Team.created_by)
            )
            
            # Apply filters
            if filters.status:
                query = query.filter(Team.status == filters.status)
            
            if filters.sub_admin_id:
                query = query.filter(Team.sub_admin_id == filters.sub_admin_id)
            
            if filters.q:
                search_term = f"%{filters.q}%"
                query = query.filter(
                    or_(
                        Team.name.ilike(search_term),
                        Team.description.ilike(search_term)
                    )
                )
            
            # Apply sorting
            query = _apply_sorting(query, sort_by, Team)
            
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
            logger.error(f"Error getting teams: {e}")
            return PaginatedResponse(items=[], next_cursor=None, count=0)

    def get_by_sub_admin(self, db: Session, sub_admin_id: UUID) -> Optional[Team]:
        """Get team managed by sub-admin."""
        try:
            return db.query(Team).filter(Team.sub_admin_id == sub_admin_id).first()
        except Exception as e:
            logger.error(f"Error getting team by sub-admin {sub_admin_id}: {e}")
            return None

    def update(self, db: Session, team_id: UUID, team_data: TeamUpdate) -> Optional[Team]:
        """Update team."""
        try:
            team = self.get_by_id(db, team_id)
            if not team:
                return None
            
            update_data = team_data.dict(exclude_unset=True)
            return super().update(db, team, **update_data)
        except Exception as e:
            logger.error(f"Error updating team {team_id}: {e}")
            return None

    def delete(self, db: Session, team_id: UUID) -> bool:
        """Delete team."""
        try:
            # First check if team has members
            member_count = db.query(User).filter(User.team_id == team_id).count()
            if member_count > 0:
                logger.warning(f"Cannot delete team {team_id}: has {member_count} members")
                return False
            
            # Delete team goals first
            db.query(TeamGoal).filter(TeamGoal.team_id == team_id).delete()
            
            # Then delete team
            return super().delete(db, team_id)
        except Exception as e:
            logger.error(f"Error deleting team {team_id}: {e}")
            return False

    def update_statistics(self, db: Session, team_id: UUID) -> None:
        """Update team statistics (total_earn, total_connect_used, total_bids)."""
        try:
            team = self.get_by_id(db, team_id)
            if not team:
                return
            
            # Calculate statistics from bids
            bid_stats = db.query(
                func.count(Bid.id).label('total_bids'),
                func.sum(Bid.connects_used + Bid.boost_connects_used).label('total_connects'),
                func.sum(Bid.total_cost).label('total_cost')
            ).filter(Bid.team_id == team_id).first()
            
            # Calculate total earnings from won bids
            # This would typically come from receivables or project completion data
            # For now, we'll estimate based on bid values
            won_bids = db.query(Bid).filter(
                and_(
                    Bid.team_id == team_id,
                    Bid.status == BidStatus.WON
                )
            ).all()
            
            total_earn = Decimal('0')
            for bid in won_bids:
                if bid.budget_type.value == 'fixed' and bid.budget_min:
                    total_earn += bid.budget_min
                elif bid.budget_type.value == 'hourly' and bid.hourly_rate and bid.estimated_hours:
                    total_earn += bid.hourly_rate * bid.estimated_hours
            
            # Update team statistics
            team.total_bids = bid_stats.total_bids or 0
            team.total_connect_used = bid_stats.total_connects or 0
            team.total_earn = total_earn
            
            db.commit()
            
        except Exception as e:
            logger.error(f"Error updating team statistics for {team_id}: {e}")
            db.rollback()

    def get_team_statistics(self, db: Session, team_id: UUID) -> Dict[str, Any]:
        """Get team statistics."""
        try:
            team = self.get_by_id(db, team_id)
            if not team:
                return {}
            
            # Get bid statistics
            bid_stats = db.query(
                func.count(Bid.id).label('total_bids'),
                func.count(func.nullif(Bid.status != BidStatus.WON, True)).label('wins'),
                func.sum(Bid.connects_used + Bid.boost_connects_used).label('total_connects'),
                func.sum(Bid.total_cost).label('total_cost')
            ).filter(Bid.team_id == team_id).first()
            
            # Get member count
            member_count = db.query(User).filter(
                and_(
                    User.team_id == team_id,
                    User.is_active == True
                )
            ).count()
            
            # Calculate win rate
            total_bids = bid_stats.total_bids or 0
            wins = bid_stats.wins or 0
            win_rate = Decimal(wins) / Decimal(total_bids) * 100 if total_bids > 0 else Decimal('0')
            
            return {
                'team_id': team_id,
                'team_name': team.name,
                'member_count': member_count,
                'total_bids': total_bids,
                'wins': wins,
                'win_rate': win_rate,
                'total_connects_used': bid_stats.total_connects or 0,
                'total_cost': bid_stats.total_cost or Decimal('0'),
                'total_earn': team.total_earn or Decimal('0')
            }
            
        except Exception as e:
            logger.error(f"Error getting team statistics for {team_id}: {e}")
            return {}

    def get_team_performance(self, db: Session, team_id: UUID, 
                            days: int = 30) -> Dict[str, Any]:
        """Get team performance metrics."""
        try:
            from datetime import timedelta
            start_date = datetime.utcnow() - timedelta(days=days)
            
            # Get performance data for the specified period
            performance_data = db.query(
                func.date(Bid.submitted_at).label('date'),
                func.count(Bid.id).label('daily_bids'),
                func.count(func.nullif(Bid.status != BidStatus.WON, True)).label('daily_wins')
            ).filter(
                and_(
                    Bid.team_id == team_id,
                    Bid.submitted_at >= start_date
                )
            ).group_by(func.date(Bid.submitted_at)).all()
            
            # Calculate averages
            if performance_data:
                avg_daily_bids = sum(p.daily_bids for p in performance_data) / len(performance_data)
                avg_daily_wins = sum(p.daily_wins for p in performance_data) / len(performance_data)
                avg_win_rate = (avg_daily_wins / avg_daily_bids * 100) if avg_daily_bids > 0 else 0
            else:
                avg_daily_bids = avg_daily_wins = avg_win_rate = 0
            
            return {
                'team_id': team_id,
                'period_days': days,
                'avg_daily_bids': round(avg_daily_bids, 2),
                'avg_daily_wins': round(avg_daily_wins, 2),
                'avg_win_rate': round(avg_win_rate, 2),
                'performance_trend': [
                    {
                        'date': p.date.isoformat(),
                        'bids': p.daily_bids,
                        'wins': p.daily_wins,
                        'win_rate': (p.daily_wins / p.daily_bids * 100) if p.daily_bids > 0 else 0
                    }
                    for p in performance_data
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting team performance for {team_id}: {e}")
            return {}

    # Team Goals
    def create_goal(self, db: Session, team_id: UUID, goal_data: TeamGoalCreate, 
                   created_by_id: UUID) -> TeamGoal:
        """Create team goal."""
        try:
            goal_dict = goal_data.dict()
            goal_dict.update({
                'team_id': team_id,
                'created_by_id': created_by_id
            })
            
            goal = TeamGoal(**goal_dict)
            db.add(goal)
            db.commit()
            db.refresh(goal)
            return goal
            
        except Exception as e:
            logger.error(f"Error creating team goal: {e}")
            db.rollback()
            raise

    def get_goals(self, db: Session, team_id: UUID) -> List[TeamGoal]:
        """Get team goals."""
        try:
            return db.query(TeamGoal).filter(
                TeamGoal.team_id == team_id
            ).order_by(TeamGoal.created_at.desc()).all()
        except Exception as e:
            logger.error(f"Error getting goals for team {team_id}: {e}")
            return []

    def get_goal_by_id(self, db: Session, goal_id: UUID) -> Optional[TeamGoal]:
        """Get team goal by ID."""
        try:
            return db.query(TeamGoal).filter(TeamGoal.id == goal_id).first()
        except Exception as e:
            logger.error(f"Error getting goal {goal_id}: {e}")
            return None

    def update_goal(self, db: Session, goal_id: UUID, goal_data: TeamGoalUpdate) -> Optional[TeamGoal]:
        """Update team goal."""
        try:
            goal = self.get_goal_by_id(db, goal_id)
            if not goal:
                return None
            
            update_data = goal_data.dict(exclude_unset=True)
            for field, value in update_data.items():
                if hasattr(goal, field):
                    setattr(goal, field, value)
            
            db.commit()
            db.refresh(goal)
            return goal
            
        except Exception as e:
            logger.error(f"Error updating goal {goal_id}: {e}")
            db.rollback()
            return None

    def delete_goal(self, db: Session, goal_id: UUID) -> bool:
        """Delete team goal."""
        try:
            goal = self.get_goal_by_id(db, goal_id)
            if goal:
                db.delete(goal)
                db.commit()
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting goal {goal_id}: {e}")
            db.rollback()
            return False

    def update_goal_progress(self, db: Session, team_id: UUID) -> None:
        """Update progress for all active team goals."""
        try:
            active_goals = db.query(TeamGoal).filter(
                and_(
                    TeamGoal.team_id == team_id,
                    TeamGoal.is_active == True,
                    TeamGoal.period_end >= datetime.utcnow().date()
                )
            ).all()
            
            for goal in active_goals:
                # Calculate current progress based on goal type
                current_value = self._calculate_goal_progress(db, goal)
                
                goal.current_value = current_value
                goal.is_achieved = current_value >= goal.target_value
            
            db.commit()
            
        except Exception as e:
            logger.error(f"Error updating goal progress for team {team_id}: {e}")
            db.rollback()

    def get_active_goals(self, db: Session, team_id: UUID) -> List[TeamGoal]:
        """Get active team goals."""
        try:
            return db.query(TeamGoal).filter(
                and_(
                    TeamGoal.team_id == team_id,
                    TeamGoal.is_active == True,
                    TeamGoal.period_end >= datetime.utcnow().date()
                )
            ).all()
        except Exception as e:
            logger.error(f"Error getting active goals for team {team_id}: {e}")
            return []

    def _calculate_goal_progress(self, db: Session, goal: TeamGoal) -> Decimal:
        """Calculate current progress for a goal."""
        try:
            if goal.goal_type == 'bids':
                # Count bids in the goal period
                count = db.query(func.count(Bid.id)).filter(
                    and_(
                        Bid.team_id == goal.team_id,
                        Bid.submitted_at >= goal.period_start,
                        Bid.submitted_at <= goal.period_end
                    )
                ).scalar()
                return Decimal(count or 0)
            
            elif goal.goal_type == 'wins':
                # Count won bids in the goal period
                count = db.query(func.count(Bid.id)).filter(
                    and_(
                        Bid.team_id == goal.team_id,
                        Bid.status == BidStatus.WON,
                        Bid.submitted_at >= goal.period_start,
                        Bid.submitted_at <= goal.period_end
                    )
                ).scalar()
                return Decimal(count or 0)
            
            elif goal.goal_type == 'revenue':
                # Calculate revenue from won bids (estimated)
                won_bids = db.query(Bid).filter(
                    and_(
                        Bid.team_id == goal.team_id,
                        Bid.status == BidStatus.WON,
                        Bid.submitted_at >= goal.period_start,
                        Bid.submitted_at <= goal.period_end
                    )
                ).all()
                
                total_revenue = Decimal('0')
                for bid in won_bids:
                    if bid.budget_type.value == 'fixed' and bid.budget_min:
                        total_revenue += bid.budget_min
                    elif bid.budget_type.value == 'hourly' and bid.hourly_rate and bid.estimated_hours:
                        total_revenue += bid.hourly_rate * bid.estimated_hours
                
                return total_revenue
            
            elif goal.goal_type == 'win_rate':
                # Calculate win rate percentage
                total_bids = db.query(func.count(Bid.id)).filter(
                    and_(
                        Bid.team_id == goal.team_id,
                        Bid.submitted_at >= goal.period_start,
                        Bid.submitted_at <= goal.period_end
                    )
                ).scalar()
                
                wins = db.query(func.count(Bid.id)).filter(
                    and_(
                        Bid.team_id == goal.team_id,
                        Bid.status == BidStatus.WON,
                        Bid.submitted_at >= goal.period_start,
                        Bid.submitted_at <= goal.period_end
                    )
                ).scalar()
                
                if total_bids and total_bids > 0:
                    return Decimal(wins) / Decimal(total_bids) * 100
                else:
                    return Decimal('0')
            
            return Decimal('0')
            
        except Exception as e:
            logger.error(f"Error calculating goal progress: {e}")
            return Decimal('0')