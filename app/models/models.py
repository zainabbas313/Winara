from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, ForeignKey, Enum, DECIMAL, Date, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from database.database import Base


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    SUB_ADMIN = "sub_admin"
    MEMBER = "member"


class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class BudgetType(str, enum.Enum):
    FIXED = "fixed"
    HOURLY = "hourly"


class BidStatus(str, enum.Enum):
    NOT_VIEWED = "not_viewed"
    VIEWED = "viewed"
    DECLINED = "declined"
    RESPONDED = "responded"
    CLOSED = "closed"
    WON = "won"


class ReceivableStatus(str, enum.Enum):
    PENDING = "pending"
    PARTIAL = "partial"
    PAID = "paid"
    OVERDUE = "overdue"


class SessionStatus(str, enum.Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    INVALIDATED = "invalidated"
    SUSPICIOUS = "suspicious"


class NotificationType(str, enum.Enum):
    EMAIL = "email"
    IN_APP = "in_app"
    PUSH = "push"


class AuditAction(str, enum.Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    ASSIGN_VERTICAL = "assign_vertical"
    REMOVE_VERTICAL = "remove_vertical"
    STATUS_CHANGE = "status_change"


class SecurityEventType(str, enum.Enum):
    LOGIN_INITIATED = "login_initiated"
    LOGIN_COMPLETED = "login_completed"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    SESSION_EXPIRED = "session_expired"
    PASSWORD_CHANGED = "password_changed"
    PASSWORD_RESET_INITIATED = "password_reset_initiated"
    PASSWORD_RESET_COMPLETED = "password_reset_completed"
    PASSWORD_RESET_FAILED = "password_reset_failed"
    ACCOUNT_LOCKED = "account_locked"
    ACCOUNT_UNLOCKED = "account_unlocked"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    UNAUTHORIZED_ACCESS = "unauthorized_access"


class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    phone = Column(String(20))
    bio = Column(Text)
    linkedin_profile_url = Column(String(500))
    timezone = Column(String(50), default="UTC+05:00")
    role = Column(Enum(UserRole), nullable=False)
    status = Column(Enum(UserStatus), default=UserStatus.ACTIVE)
    team_id = Column(
        UUID(as_uuid=True),
        ForeignKey("teams.id", use_alter=True, name="fk_user_team_id"),
        nullable=True
    )
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    is_locked = Column(Boolean, default=False)
    last_login = Column(DateTime(timezone=True))
    last_activity = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    team = relationship("Team", back_populates="members", foreign_keys=[team_id], post_update=True)
    created_teams = relationship("Team", foreign_keys="Team.created_by_id", back_populates="created_by")
    bids = relationship("Bid", back_populates="member")
    vertical_assignments = relationship("UserVertical", back_populates="user")
    sessions = relationship("UserSession", back_populates="user")
    notifications = relationship("Notification", back_populates="user")
    audit_logs = relationship("AuditLog", back_populates="user")


class Team(Base):
    __tablename__ = "teams"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    sub_admin_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", use_alter=True, name="fk_team_sub_admin_id"),
        nullable=True
    )
    status = Column(Enum(UserStatus), default=UserStatus.ACTIVE)
    total_earn = Column(DECIMAL(12, 2), default=0)
    total_connect_used = Column(Integer, default=0)
    total_bids = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", use_alter=True, name="fk_team_created_by_id"),
        nullable=True
    )
    
    # Relationships
    sub_admin = relationship("User", foreign_keys=[sub_admin_id], post_update=True)
    created_by = relationship("User", foreign_keys=[created_by_id], back_populates="created_teams", post_update=True)
    members = relationship("User", foreign_keys="User.team_id", back_populates="team")
    bids = relationship("Bid", back_populates="team")
    receivables = relationship("Receivable", back_populates="team")
    goals = relationship("TeamGoal", back_populates="team")


class TeamGoal(Base):
    __tablename__ = "team_goals"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False)
    goal_name = Column(String(200), nullable=False)
    goal_type = Column(String(50), nullable=False)
    target_value = Column(DECIMAL(12, 2), nullable=False)
    current_value = Column(DECIMAL(12, 2), default=0)
    unit = Column(String(20), nullable=False)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    is_active = Column(Boolean, default=True)
    is_achieved = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    # Relationships
    team = relationship("Team", back_populates="goals")
    created_by = relationship("User")


class Vertical(Base):
    __tablename__ = "verticals"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    slug = Column(String(200), nullable=False, unique=True, index=True)
    description = Column(Text)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("verticals.id"))
    level = Column(Integer, default=0)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    requires_approval = Column(Boolean, default=False)
    total_earn = Column(DECIMAL(12, 2), default=0)
    connect_used = Column(Integer, default=0)
    total_bids = Column(Integer, default=0)
    avg_project_value = Column(DECIMAL(12, 2))
    competition_level = Column(Integer, default=1)  # 1-10 scale
    success_rate = Column(DECIMAL(5, 4))  # Percentage as decimal
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    # Relationships
    parent = relationship("Vertical", remote_side=[id])
    children = relationship("Vertical", cascade="all, delete-orphan")
    created_by = relationship("User")
    user_assignments = relationship("UserVertical", back_populates="vertical")
    bids = relationship("Bid", back_populates="vertical")


class UserVertical(Base):
    __tablename__ = "user_verticals"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    vertical_id = Column(UUID(as_uuid=True), ForeignKey("verticals.id"), nullable=False)
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())
    assigned_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    is_active = Column(Boolean, default=True)
    total_earn = Column(DECIMAL(12, 2), default=0)
    connect_used = Column(Integer, default=0)
    total_bids = Column(Integer, default=0)
    success_rate = Column(DECIMAL(5, 4))
    notes = Column(Text)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="vertical_assignments")
    vertical = relationship("Vertical", back_populates="user_assignments")
    assigned_by = relationship("User", foreign_keys=[assigned_by_id])
    
    __table_args__ = (Index('ix_user_vertical_unique', 'user_id', 'vertical_id', unique=True),)


class Bid(Base):
    __tablename__ = "bids"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_title = Column(String(500), nullable=False)
    job_url = Column(String(1000))
    job_description = Column(Text)
    client_name = Column(String(200))
    vertical_id = Column(UUID(as_uuid=True), ForeignKey("verticals.id"), nullable=False)
    member_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False)
    budget_type = Column(Enum(BudgetType), nullable=False)
    budget_min = Column(DECIMAL(12, 2))
    budget_max = Column(DECIMAL(12, 2))
    hourly_rate = Column(DECIMAL(8, 2))
    estimated_hours = Column(Integer, default=0)
    connects_used = Column(Integer, default=1)
    boost_connects_used = Column(Integer, default=0)
    connect_cost = Column(DECIMAL(8, 4))
    total_cost = Column(DECIMAL(10, 4))
    status = Column(Enum(BidStatus), default=BidStatus.NOT_VIEWED)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())
    last_status_change = Column(DateTime(timezone=True), server_default=func.now())
    proposal_text = Column(Text)
    cover_letter = Column(Text)
    is_featured = Column(Boolean, default=False)
    competition_level = Column(Integer, default=1)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    vertical = relationship("Vertical", back_populates="bids")
    member = relationship("User", back_populates="bids")
    team = relationship("Team", back_populates="bids")
    receivable = relationship("Receivable", back_populates="bid", uselist=False)


class Receivable(Base):
    __tablename__ = "receivables"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bid_id = Column(UUID(as_uuid=True), ForeignKey("bids.id"), nullable=False)
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False)
    client_name = Column(String(200), nullable=False)
    project_title = Column(String(500), nullable=False)
    contract_value = Column(DECIMAL(12, 2), nullable=False)
    expected_payment_date = Column(Date, nullable=False)
    actual_payment_date = Column(Date)
    payment_amount = Column(DECIMAL(12, 2))
    status = Column(Enum(ReceivableStatus), default=ReceivableStatus.PENDING)
    currency = Column(String(3), default="USD")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    # Relationships
    bid = relationship("Bid", back_populates="receivable")
    team = relationship("Team", back_populates="receivables")
    created_by = relationship("User")


class UserSession(Base):
    __tablename__ = "user_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    refresh_token = Column(String(500), nullable=False, unique=True)
    status = Column(Enum(SessionStatus), default=SessionStatus.ACTIVE)
    ip_address = Column(String(45))
    user_agent = Column(Text)
    os = Column(String(100))
    browser = Column(String(100))
    browser_version = Column(String(50))
    device_type = Column(String(20))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_activity = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="sessions")


class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    type = Column(Enum(NotificationType), nullable=False)
    title = Column(String(500), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    is_sent = Column(Boolean, default=False)
    priority = Column(Integer, default=1)  # 1-5 scale
    entity_type = Column(String(100))
    entity_id = Column(UUID(as_uuid=True))
    sent_at = Column(DateTime(timezone=True))
    read_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="notifications")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    action = Column(Enum(AuditAction), nullable=False)
    entity_type = Column(String(100))
    entity_id = Column(UUID(as_uuid=True))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    session_id = Column(UUID(as_uuid=True))
    ip_address = Column(String(45))
    user_agent = Column(Text)
    description = Column(Text)
    old_values = Column(JSONB)
    new_values = Column(JSONB)
    risk_level = Column(Integer, default=1)  # 1-5 scale
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")


class SecurityEvent(Base):
    __tablename__ = "security_events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(Enum(SecurityEventType), nullable=False)
    severity = Column(Integer, default=1)  # 1-5 scale
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    session_id = Column(UUID(as_uuid=True))
    ip_address = Column(String(45))
    user_agent = Column(Text)
    description = Column(Text, nullable=False)
    additional_data = Column(JSONB)
    is_resolved = Column(Boolean, default=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User")