import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))  # Must be first

from datetime import datetime, timezone
import bcrypt
from sqlalchemy.orm import Session
from database.database import SessionLocal, Base, engine
from models.models import User, UserRole, UserStatus

Base.metadata.create_all(bind=engine)

db: Session = SessionLocal()

email = "zain@winara.com"
username = "zain"
password = "123qwe!@#QWE"
hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

existing_admin = db.query(User).filter(User.email == email).first()
if not existing_admin:
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
    print("⚠️ Admin already exists.")

db.close()
