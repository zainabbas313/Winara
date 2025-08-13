from typing import Generic, TypeVar, Type, Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc, func, text
from sqlalchemy.exc import SQLAlchemyError
from database.database import Base
from utils.helpers import parse_sort_parameter, parse_pagination_cursor, build_pagination_cursor
from schemas.common import PaginatedResponse
import json
import logging

logger = logging.getLogger(__name__)

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType]):
        self.model = model

    def create(self, db: Session, **kwargs) -> ModelType:
        """Create a new record."""
        try:
            db_obj = self.model(**kwargs)
            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
            return db_obj
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Error creating {self.model.__name__}: {e}")
            raise

    def get_by_id(self, db: Session, id: Any) -> Optional[ModelType]:
        """Get record by ID."""
        try:
            return db.query(self.model).filter(self.model.id == id).first()
        except SQLAlchemyError as e:
            logger.error(f"Error getting {self.model.__name__} by id {id}: {e}")
            return None

    def get_multi(
        self,
        db: Session,
        skip: int = 0,
        limit: int = 20,
        filters: Optional[Dict[str, Any]] = None,
        sort_by: str = "-created_at"
    ) -> PaginatedResponse:
        """Get multiple records with pagination and filtering."""
        try:
            query = db.query(self.model)
            
            # Apply filters
            if filters:
                query = self._apply_filters(query, filters)
            
            # Apply sorting
            query = self._apply_sorting(query, sort_by)
            
            # Get total count before pagination
            total_count = query.count()
            
            # Apply pagination
            items = query.offset(skip).limit(limit).all()
            
            # Build next cursor if there are more items
            next_cursor = None
            if len(items) == limit and skip + limit < total_count:
                last_item = items[-1]
                sort_field, _ = parse_sort_parameter(sort_by)
                sort_value = getattr(last_item, sort_field, None)
                next_cursor = build_pagination_cursor(str(last_item.id), sort_field, sort_value)
            
            return PaginatedResponse(
                items=items,
                next_cursor=next_cursor,
                count=len(items)
            )
        except SQLAlchemyError as e:
            logger.error(f"Error getting multiple {self.model.__name__}: {e}")
            return PaginatedResponse(items=[], next_cursor=None, count=0)

    def update(self, db: Session, db_obj: ModelType, **kwargs) -> ModelType:
        """Update a record."""
        try:
            for field, value in kwargs.items():
                if hasattr(db_obj, field):
                    setattr(db_obj, field, value)
            
            db.commit()
            db.refresh(db_obj)
            return db_obj
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Error updating {self.model.__name__}: {e}")
            raise

    def delete(self, db: Session, id: Any) -> bool:
        """Delete a record by ID."""
        try:
            db_obj = self.get_by_id(db, id)
            if db_obj:
                db.delete(db_obj)
                db.commit()
                return True
            return False
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Error deleting {self.model.__name__} with id {id}: {e}")
            return False

    def exists(self, db: Session, id: Any) -> bool:
        """Check if record exists by ID."""
        try:
            return db.query(self.model).filter(self.model.id == id).first() is not None
        except SQLAlchemyError as e:
            logger.error(f"Error checking existence of {self.model.__name__} with id {id}: {e}")
            return False

    def count(self, db: Session, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count records with optional filters."""
        try:
            query = db.query(self.model)
            if filters:
                query = self._apply_filters(query, filters)
            return query.count()
        except SQLAlchemyError as e:
            logger.error(f"Error counting {self.model.__name__}: {e}")
            return 0

    def _apply_filters(self, query, filters: Dict[str, Any]):
        """Apply filters to query."""
        for field, value in filters.items():
            if value is None:
                continue
                
            if hasattr(self.model, field):
                column = getattr(self.model, field)
                
                if isinstance(value, list):
                    query = query.filter(column.in_(value))
                elif isinstance(value, dict):
                    # Handle range filters
                    if 'gte' in value:
                        query = query.filter(column >= value['gte'])
                    if 'lte' in value:
                        query = query.filter(column <= value['lte'])
                    if 'gt' in value:
                        query = query.filter(column > value['gt'])
                    if 'lt' in value:
                        query = query.filter(column < value['lt'])
                    if 'ne' in value:
                        query = query.filter(column != value['ne'])
                elif isinstance(value, str) and field.endswith('_search'):
                    # Handle text search
                    actual_field = field.replace('_search', '')
                    if hasattr(self.model, actual_field):
                        actual_column = getattr(self.model, actual_field)
                        query = query.filter(actual_column.ilike(f"%{value}%"))
                else:
                    query = query.filter(column == value)
        
        return query

    def _apply_sorting(self, query, sort_by: str):
        """Apply sorting to query."""
        sort_field, direction = parse_sort_parameter(sort_by)
        
        if hasattr(self.model, sort_field):
            column = getattr(self.model, sort_field)
            if direction == 'desc':
                query = query.order_by(desc(column))
            else:
                query = query.order_by(asc(column))
        
        return query

    def bulk_create(self, db: Session, objects: List[Dict[str, Any]]) -> List[ModelType]:
        """Bulk create multiple records."""
        try:
            db_objects = [self.model(**obj) for obj in objects]
            db.add_all(db_objects)
            db.commit()
            for obj in db_objects:
                db.refresh(obj)
            return db_objects
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Error bulk creating {self.model.__name__}: {e}")
            raise

    def bulk_update(self, db: Session, updates: List[Dict[str, Any]]) -> bool:
        """Bulk update multiple records."""
        try:
            db.bulk_update_mappings(self.model, updates)
            db.commit()
            return True
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Error bulk updating {self.model.__name__}: {e}")
            return False

    def get_or_create(self, db: Session, defaults: Optional[Dict[str, Any]] = None, **kwargs) -> tuple[ModelType, bool]:
        """Get existing record or create new one."""
        try:
            instance = db.query(self.model).filter_by(**kwargs).first()
            if instance:
                return instance, False
            else:
                params = dict((k, v) for k, v in kwargs.items())
                if defaults:
                    params.update(defaults)
                instance = self.create(db, **params)
                return instance, True
        except SQLAlchemyError as e:
            logger.error(f"Error in get_or_create for {self.model.__name__}: {e}")
            raise