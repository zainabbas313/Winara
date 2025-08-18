from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func
from decimal import Decimal
from .base_repository import BaseRepository
from models.models import Team, TeamGoal, User, Bid, BidStatus, UserRole, UserStatus
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

    def get_team_members_count(self, db: Session, team_id: UUID) -> int:
        """Get count of active team members."""
        try:
            return db.query(User).filter(
                and_(
                    User.team_id == team_id,
                    User.is_active == True,
                    User.status == UserStatus.ACTIVE
                )
            ).count()
        except Exception as e:
            logger.error(f"Error getting team members count for {team_id}: {e}")
            return 0


    def get_team_members_detailed(self, db: Session, team_id: UUID) -> List[User]:
        """Get detailed team members with their statistics."""
        try:
            return db.query(User).options(
                joinedload(User.vertical_assignments),
                joinedload(User.bids)
            ).filter(
                User.team_id == team_id
            ).order_by(User.created_at.desc()).all()
        except Exception as e:
            logger.error(f"Error getting detailed team members for {team_id}: {e}")
            return []


    def validate_team_capacity(self, db: Session, team_id: UUID, additional_users: int = 1) -> bool:
        """Validate if team can accommodate additional users."""
        try:
            current_count = self.get_team_members_count(db, team_id)
            # You can set a maximum team size limit here
            MAX_TEAM_SIZE = 50  # Example limit
            
            return (current_count + additional_users) <= MAX_TEAM_SIZE
        except Exception as e:
            logger.error(f"Error validating team capacity for {team_id}: {e}")
            return False


    def get_available_users_for_team(self, db: Session, limit: int = 100) -> List[User]:
        """Get users who are not assigned to any team and can be added."""
        try:
            return db.query(User).filter(
                and_(
                    User.team_id.is_(None),
                    User.is_active == True,
                    User.status == UserStatus.ACTIVE,
                    User.role == UserRole.MEMBER  # Only members can be easily assigned
                )
            ).limit(limit).all()
        except Exception as e:
            logger.error(f"Error getting available users for team assignment: {e}")
            return []


    def get_team_member_statistics(self, db: Session, team_id: UUID) -> Dict[str, Any]:
        """Get comprehensive team member statistics."""
        try:
            # Get basic member info
            members = db.query(User).filter(User.team_id == team_id).all()
            
            if not members:
                return {
                    'total_members': 0,
                    'active_members': 0,
                    'member_roles': {},
                    'member_performance': {}
                }
            
            # Calculate statistics
            total_members = len(members)
            active_members = len([m for m in members if m.is_active and m.status == UserStatus.ACTIVE])
            
            # Role distribution
            role_distribution = {}
            for member in members:
                role = member.role.value
                role_distribution[role] = role_distribution.get(role, 0) + 1
            
            # Get performance data from bids
            member_performance = {}
            for member in members:
                member_bids = db.query(Bid).filter(Bid.member_id == member.id).all()
                won_bids = [b for b in member_bids if b.status == BidStatus.WON]
                
                member_performance[str(member.id)] = {
                    'username': member.username,
                    'total_bids': len(member_bids),
                    'won_bids': len(won_bids),
                    'win_rate': (len(won_bids) / len(member_bids) * 100) if member_bids else 0,
                    'last_activity': member.last_activity.isoformat() if member.last_activity else None
                }
            
            return {
                'total_members': total_members,
                'active_members': active_members,
                'member_roles': role_distribution,
                'member_performance': member_performance
            }
            
        except Exception as e:
            logger.error(f"Error getting team member statistics for {team_id}: {e}")
            return {}


    def update_team_member_statistics(self, db: Session, team_id: UUID) -> None:
        """Update statistics for all team members."""
        try:
            members = db.query(User).filter(User.team_id == team_id).all()
            
            for member in members:
                # Update member statistics from their vertical assignments
                member_stats = db.query(
                    func.count(Bid.id).label('total_bids'),
                    func.count(func.nullif(Bid.status != BidStatus.WON, True)).label('wins'),
                    func.sum(Bid.connects_used + Bid.boost_connects_used).label('total_connects'),
                    func.sum(Bid.total_cost).label('total_cost')
                ).filter(Bid.member_id == member.id).first()
                
                # Update user vertical assignments with these stats
                for assignment in member.vertical_assignments:
                    vertical_bids = db.query(Bid).filter(
                        and_(
                            Bid.member_id == member.id,
                            Bid.vertical_id == assignment.vertical_id
                        )
                    ).all()
                    
                    assignment.total_bids = len(vertical_bids)
                    assignment.connect_used = sum(
                        (b.connects_used or 0) + (b.boost_connects_used or 0) 
                        for b in vertical_bids
                    )
                    
                    won_bids = [b for b in vertical_bids if b.status == BidStatus.WON]
                    if vertical_bids:
                        assignment.success_rate = Decimal(len(won_bids)) / Decimal(len(vertical_bids))
                    else:
                        assignment.success_rate = Decimal('0')
            
            db.commit()
            
        except Exception as e:
            logger.error(f"Error updating team member statistics for {team_id}: {e}")
            db.rollback()

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
        
    def get_user_team_history(self, db: Session, user_id: UUID, limit: int = 20) -> List[Dict[str, Any]]:
        """Get team assignment history for a specific user."""
        try:
            # This would typically query an audit log or team history table
            # For now, we'll check if the user has any team-related audit logs
            from models.models import AuditLog, AuditAction
            
            history_logs = db.query(AuditLog).filter(
                and_(
                    AuditLog.entity_id == user_id,
                    AuditLog.entity_type.in_(['user_team', 'user']),
                    AuditLog.action.in_([AuditAction.ASSIGN_VERTICAL, AuditAction.REMOVE_VERTICAL, AuditAction.UPDATE])
                )
            ).order_by(AuditLog.timestamp.desc()).limit(limit).all()
            
            history = []
            for log in history_logs:
                history_entry = {
                    'id': str(log.id),
                    'user_id': str(user_id),
                    'action': log.action.value,
                    'timestamp': log.timestamp.isoformat() if log.timestamp else None,
                    'changed_by': str(log.user_id) if log.user_id else None,
                    'description': log.description
                }
                
                # Extract team information from log values
                if log.new_values and 'team_id' in log.new_values:
                    history_entry['team_id'] = log.new_values['team_id']
                    history_entry['team_name'] = log.new_values.get('team_name', 'Unknown')
                    history_entry['action_type'] = 'team_assigned'
                elif log.old_values and 'team_id' in log.old_values:
                    history_entry['team_id'] = log.old_values['team_id']
                    history_entry['team_name'] = log.old_values.get('team_name', 'Unknown')
                    history_entry['action_type'] = 'team_removed'
                
                history.append(history_entry)
            
            return history
            
        except Exception as e:
            logger.error(f"Error getting user team history for {user_id}: {e}")
            return []

    def get_team_assignment_conflicts(self, db: Session, user_ids: List[UUID], team_id: UUID) -> List[Dict[str, Any]]:
        """Check for conflicts when assigning users to a team."""
        try:
            conflicts = []
            
            # Check if target team exists
            team = self.get_by_id(db, team_id)
            if not team:
                conflicts.append({
                    'type': 'team_not_found',
                    'message': f'Target team {team_id} not found',
                    'severity': 'error'
                })
                return conflicts
            
            # Check each user
            for user_id in user_ids:
                user = db.query(User).filter(User.id == user_id).first()
                
                if not user:
                    conflicts.append({
                        'type': 'user_not_found',
                        'user_id': str(user_id),
                        'message': f'User {user_id} not found',
                        'severity': 'error'
                    })
                    continue
                
                # Check if user is active
                if not user.is_active or user.status != UserStatus.ACTIVE:
                    conflicts.append({
                        'type': 'user_inactive',
                        'user_id': str(user_id),
                        'username': user.username,
                        'message': f'User {user.username} is not active',
                        'severity': 'error'
                    })
                
                # Check if user is already in a team
                if user.team_id:
                    if user.team_id == team_id:
                        conflicts.append({
                            'type': 'user_already_in_team',
                            'user_id': str(user_id),
                            'username': user.username,
                            'message': f'User {user.username} is already in this team',
                            'severity': 'warning'
                        })
                    else:
                        current_team = self.get_by_id(db, user.team_id)
                        conflicts.append({
                            'type': 'user_in_different_team',
                            'user_id': str(user_id),
                            'username': user.username,
                            'current_team_id': str(user.team_id),
                            'current_team_name': current_team.name if current_team else 'Unknown',
                            'message': f'User {user.username} is already in team: {current_team.name if current_team else "Unknown"}',
                            'severity': 'error'
                        })
                
                # Check if user role is suitable
                if user.role == UserRole.SUB_ADMIN:
                    # Check if sub-admin is already managing this team
                    if team.sub_admin_id == user_id:
                        conflicts.append({
                            'type': 'user_is_team_admin',
                            'user_id': str(user_id),
                            'username': user.username,
                            'message': f'User {user.username} is already the sub-admin of this team',
                            'severity': 'info'
                        })
                    else:
                        # Check if sub-admin is managing another team
                        other_team = self.get_by_sub_admin(db, user_id)
                        if other_team:
                            conflicts.append({
                                'type': 'sub_admin_managing_other_team',
                                'user_id': str(user_id),
                                'username': user.username,
                                'managing_team_id': str(other_team.id),
                                'managing_team_name': other_team.name,
                                'message': f'Sub-admin {user.username} is already managing team: {other_team.name}',
                                'severity': 'error'
                            })
            
            # Check team capacity
            current_members = self.get_team_members_count(db, team_id)
            new_members_count = len([uid for uid in user_ids if not any(
                c.get('user_id') == str(uid) and c['type'] in ['user_already_in_team', 'user_in_different_team']
                for c in conflicts
            )])
            
            if not self.validate_team_capacity(db, team_id, new_members_count):
                conflicts.append({
                    'type': 'team_capacity_exceeded',
                    'message': f'Adding {new_members_count} users would exceed team capacity. Current: {current_members}',
                    'severity': 'error'
                })
            
            return conflicts
            
        except Exception as e:
            logger.error(f"Error checking team assignment conflicts: {e}")
            return [{
                'type': 'system_error',
                'message': 'Error checking assignment conflicts',
                'severity': 'error'
            }]

    def validate_team_member_removal(self, db: Session, team_id: UUID, user_id: UUID) -> Dict[str, Any]:
        """Validate if a team member can be safely removed."""
        try:
            validation_result = {
                'can_remove': True,
                'warnings': [],
                'blocking_issues': []
            }
            
            # Check if team exists
            team = self.get_by_id(db, team_id)
            if not team:
                validation_result['can_remove'] = False
                validation_result['blocking_issues'].append('Team not found')
                return validation_result
            
            # Check if user exists and is in the team
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                validation_result['can_remove'] = False
                validation_result['blocking_issues'].append('User not found')
                return validation_result
            
            if user.team_id != team_id:
                validation_result['can_remove'] = False
                validation_result['blocking_issues'].append('User is not a member of this team')
                return validation_result
            
            # Check if user is the sub-admin
            if user.role == UserRole.SUB_ADMIN and team.sub_admin_id == user_id:
                validation_result['can_remove'] = False
                validation_result['blocking_issues'].append(
                    'Cannot remove sub-admin. Please assign a new sub-admin first.'
                )
                return validation_result
            
            # Check for active bids or ongoing work
            from models.models import Bid, BidStatus
            active_bids = db.query(Bid).filter(
                and_(
                    Bid.member_id == user_id,
                    Bid.status.in_([BidStatus.NOT_VIEWED, BidStatus.VIEWED, BidStatus.RESPONDED])  # Active statuses
                )
            ).count()
            
            if active_bids > 0:
                validation_result['warnings'].append(
                    f'User has {active_bids} active bids that may be affected'
                )
            
            # Check if user has recent activity
            from datetime import datetime, timedelta
            recent_activity_threshold = datetime.utcnow() - timedelta(days=7)
            
            if user.last_activity and user.last_activity > recent_activity_threshold:
                validation_result['warnings'].append(
                    'User has been active recently. Consider notifying them before removal.'
                )
            
            # Check team size after removal
            current_members = self.get_team_members_count(db, team_id)
            if current_members <= 1:
                validation_result['warnings'].append(
                    'Removing this user will leave the team with very few or no members'
                )
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Error validating team member removal: {e}")
            return {
                'can_remove': False,
                'warnings': [],
                'blocking_issues': ['System error during validation']
            }

    def get_team_capacity_info(self, db: Session, team_id: UUID) -> Dict[str, Any]:
        """Get team capacity information including current size and limits."""
        try:
            team = self.get_by_id(db, team_id)
            if not team:
                return {
                    'team_exists': False,
                    'error': 'Team not found'
                }
            
            current_members = self.get_team_members_count(db, team_id)
            
            # Get detailed member breakdown
            members = db.query(User).filter(User.team_id == team_id).all()
            
            role_breakdown = {}
            status_breakdown = {}
            
            for member in members:
                # Role breakdown
                role = member.role.value
                role_breakdown[role] = role_breakdown.get(role, 0) + 1
                
                # Status breakdown
                if member.is_active and member.status == UserStatus.ACTIVE:
                    status = 'active'
                else:
                    status = 'inactive'
                status_breakdown[status] = status_breakdown.get(status, 0) + 1
            
            # Business rules for capacity (can be customized)
            MAX_TEAM_SIZE = 50  # You can make this configurable
            RECOMMENDED_SIZE = 20
            
            capacity_status = 'normal'
            if current_members >= MAX_TEAM_SIZE:
                capacity_status = 'full'
            elif current_members >= RECOMMENDED_SIZE:
                capacity_status = 'near_capacity'
            elif current_members <= 2:
                capacity_status = 'understaffed'
            
            return {
                'team_exists': True,
                'team_id': str(team_id),
                'team_name': team.name,
                'current_members': current_members,
                'max_capacity': MAX_TEAM_SIZE,
                'recommended_size': RECOMMENDED_SIZE,
                'available_slots': max(0, MAX_TEAM_SIZE - current_members),
                'capacity_status': capacity_status,
                'capacity_percentage': round((current_members / MAX_TEAM_SIZE) * 100, 1),
                'role_breakdown': role_breakdown,
                'status_breakdown': status_breakdown,
                'can_add_members': current_members < MAX_TEAM_SIZE,
                'recommendations': self._get_capacity_recommendations(current_members, MAX_TEAM_SIZE, RECOMMENDED_SIZE)
            }
            
        except Exception as e:
            logger.error(f"Error getting team capacity info for {team_id}: {e}")
            return {
                'team_exists': False,
                'error': 'System error retrieving capacity information'
            }

    def archive_team_membership_change(self, db: Session, team_id: UUID, user_id: UUID, 
                                     action: str, changed_by_id: UUID, 
                                     metadata: Optional[Dict[str, Any]] = None) -> None:
        """Archive a team membership change for audit purposes."""
        try:
            # Get team and user information for the archive
            team = self.get_by_id(db, team_id)
            user = db.query(User).filter(User.id == user_id).first()
            
            if not team or not user:
                logger.warning(f"Cannot archive membership change: team or user not found")
                return
            
            # Prepare audit data
            audit_data = {
                'team_id': str(team_id),
                'team_name': team.name,
                'user_id': str(user_id),
                'username': user.username,
                'user_email': user.email,
                'user_role': user.role.value,
                'action': action,
                'changed_by': str(changed_by_id),
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Add metadata if provided
            if metadata:
                audit_data.update(metadata)
            
            # Create audit log entry using the existing audit repository pattern
            # Note: You should use self.audit_repo if it's available in TeamRepository
            # For now, creating directly:
            from models.models import AuditLog, AuditAction
            
            # Map action to audit action enum
            action_mapping = {
                'added': AuditAction.ASSIGN_VERTICAL,
                'removed': AuditAction.REMOVE_VERTICAL,
                'role_changed': AuditAction.UPDATE
            }
            
            audit_action = action_mapping.get(action, AuditAction.UPDATE)
            
            # Create audit log
            audit_log = AuditLog(
                action=audit_action,
                entity_type='team_membership',
                entity_id=user_id,
                user_id=changed_by_id,  # Using user_id instead of performed_by_id
                description=f"Team membership {action}: {user.username} {'added to' if action == 'added' else 'removed from' if action == 'removed' else 'role changed in'} {team.name}",
                new_values=audit_data if action == 'added' else None,
                old_values=audit_data if action == 'removed' else None
            )
            
            db.add(audit_log)
            db.commit()
            
            logger.info(f"Archived team membership change: {action} for user {user.username} in team {team.name}")
            
        except Exception as e:
            logger.error(f"Error archiving team membership change: {e}")
            db.rollback()

    def _get_capacity_recommendations(self, current: int, max_size: int, recommended: int) -> List[str]:
        """Get capacity-based recommendations."""
        recommendations = []
        
        if current == 0:
            recommendations.append("Team has no members. Consider adding team members to start operations.")
        elif current < 3:
            recommendations.append("Team is understaffed. Consider adding more members for better productivity.")
        elif current > recommended:
            recommendations.append(f"Team size exceeds recommended size of {recommended}. Consider team optimization.")
        elif current >= max_size * 0.9:
            recommendations.append("Team is near capacity. Plan for team expansion or workload distribution.")
        
        if current < recommended:
            recommendations.append(f"Consider adding {recommended - current} more members to reach recommended size.")
        
        return recommendations