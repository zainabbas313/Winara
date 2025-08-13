
from models.models import Team, User
from sqlalchemy import asc, desc
from models.models import User 
from fastapi import HTTPException


def _apply_sorting(query, sort_by: str, instance):
    """Apply sorting to a query using the User table."""
    sort_field, direction = parse_sort_parameter(sort_by)

    # Whitelist allowed sort fields from User model
    if instance == User:
        allowed_fields = {
            "created_at": User.created_at,
            "updated_at": User.updated_at,
            "email": User.email,
            "first_name": User.first_name,
            "last_name": User.last_name,
            "status": User.status,
            "role": User.role
        }
    if instance == Team:
        allowed_fields = {
            "created_at": Team.created_at,
            "updated_at": Team.updated_at,
            "name": Team.name,
            "status": Team.status
        }


    column = allowed_fields.get(sort_field)
    if column is None:
        raise HTTPException(status_code=400, detail=f"Invalid sort field: {sort_field}")

    return query.order_by(desc(column) if direction == 'desc' else asc(column))

def parse_sort_parameter(sort_by: str):
    """
    Parse sort string like '-created_at' or 'email' into (field_name, direction).
    direction is 'asc' or 'desc'.
    """
    if not sort_by:
        return "created_at", "desc"  # default
    sort_by = sort_by.strip()
    if sort_by.startswith("-"):
        return sort_by[1:], "desc"
    elif sort_by.startswith("+"):
        return sort_by[1:], "asc"
    else:
        return sort_by, "asc"

