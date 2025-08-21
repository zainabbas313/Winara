import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))  # Must be first

from datetime import datetime, timezone
import bcrypt
from sqlalchemy.orm import Session
from database.database import SessionLocal, engine
from models.models import User, UserRole, UserStatus

from sqlalchemy.ext.declarative import declarative_base
Base = declarative_base()

Base.metadata.create_all(bind=engine)

db: Session = SessionLocal()

email = "zain@winara.com"
username = "zain"
password = "123qwe!@#QWE"
hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

existing_admin = db.query(User).filter(User.email == email).first()

if not existing_admin:
    # Create new admin
    admin_user = User(
        email=email,
        username=username,
        hashed_password=hashed_password,
        first_name="Zain",
        last_name="Abbas",
        role=UserRole.ADMIN,  # Must match DB enum exactly
        status=UserStatus.ACTIVE,
        is_active=True,
        is_verified=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)
    print(f"✅ Admin user created with ID: {admin_user.id}")
else:
    # Update existing admin
    existing_admin.username = username
    existing_admin.hashed_password = hashed_password
    existing_admin.first_name = "Zain"
    existing_admin.last_name = "Abbas"
    existing_admin.role = UserRole.ADMIN
    existing_admin.status = UserStatus.ACTIVE
    existing_admin.is_active = True
    existing_admin.is_verified = True
    existing_admin.updated_at = datetime.now(timezone.utc)

    db.commit()
    print(f"🔄 Admin user updated with ID: {existing_admin.id}")

db.close()
