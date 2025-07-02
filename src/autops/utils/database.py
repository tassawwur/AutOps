"""
Database utilities and models for AutOps.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Generator
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    DateTime,
    JSON,
    Text,
    Boolean,
    ForeignKey,
    Index,
    desc,
    or_,
    Engine,
    text,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from contextlib import contextmanager
import structlog

from ..config import settings


# Create the base class for SQLAlchemy models
Base = declarative_base()
logger = structlog.get_logger(__name__)


class AgentExecution(Base):  # type: ignore
    """Model for tracking agent executions."""

    __tablename__ = "agent_executions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_name = Column(String(100), nullable=False, index=True)
    method_name = Column(String(100), nullable=False)
    start_time = Column(DateTime, nullable=False, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    status = Column(
        String(50), nullable=False, default="running"
    )  # running, success, error
    input_data = Column(JSON, nullable=True)
    output_data = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    record_metadata = Column(JSON, nullable=True)

    __table_args__ = (
        Index("idx_agent_executions_agent_time", "agent_name", "start_time"),
        Index("idx_agent_executions_status_time", "status", "start_time"),
    )


class Query(Base):  # type: ignore
    """Model for storing user queries and responses."""

    __tablename__ = "queries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    query_id = Column(String(100), unique=True, nullable=False, index=True)
    user_id = Column(String(100), nullable=False, index=True)
    channel_id = Column(String(100), nullable=True)
    original_query = Column(Text, nullable=False)
    parsed_intent = Column(JSON, nullable=True)
    execution_plan = Column(JSON, nullable=True)
    final_response = Column(Text, nullable=True)
    status = Column(
        String(50), nullable=False, default="processing"
    )  # processing, completed, error
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    execution_time_ms = Column(Integer, nullable=True)

    # Relationships
    agent_executions = relationship(
        "QueryAgentExecution", back_populates="query", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_queries_user_time", "user_id", "created_at"),
        Index("idx_queries_status_time", "status", "created_at"),
    )


class QueryAgentExecution(Base):  # type: ignore
    """Association table linking queries to agent executions."""

    __tablename__ = "query_agent_executions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    query_id = Column(Integer, ForeignKey("queries.id"), nullable=False)
    agent_execution_id = Column(
        Integer, ForeignKey("agent_executions.id"), nullable=False
    )
    sequence_order = Column(Integer, nullable=False)

    # Relationships
    query = relationship("Query", back_populates="agent_executions")
    agent_execution = relationship("AgentExecution")

    __table_args__ = (Index("idx_query_agent_exec_query", "query_id"),)


class ServiceMetrics(Base):  # type: ignore
    """Model for storing service metrics snapshots."""

    __tablename__ = "service_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    service_name = Column(String(200), nullable=False, index=True)
    metric_type = Column(
        String(100), nullable=False
    )  # error_rate, latency, throughput, etc.
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    value = Column(JSON, nullable=False)  # Flexible metric data
    source = Column(String(100), nullable=False)  # datadog, prometheus, etc.
    record_metadata = Column(JSON, nullable=True)

    __table_args__ = (
        Index(
            "idx_service_metrics_service_type_time",
            "service_name",
            "metric_type",
            "timestamp",
        ),
        Index("idx_service_metrics_source_time", "source", "timestamp"),
    )


class Incident(Base):  # type: ignore
    """Model for tracking incidents and their resolutions."""

    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(String(100), unique=True, nullable=False, index=True)
    external_id = Column(String(100), nullable=True)  # PagerDuty, etc.
    service_name = Column(String(200), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(
        String(50), nullable=False, default="open"
    )  # open, investigating, resolved, closed
    severity = Column(
        String(50), nullable=False, default="medium"
    )  # low, medium, high, critical
    source = Column(String(100), nullable=False)  # autops, pagerduty, manual
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    resolution_time_minutes = Column(Integer, nullable=True)
    auto_resolved = Column(Boolean, default=False)
    resolution_actions = Column(JSON, nullable=True)
    record_metadata = Column(JSON, nullable=True)

    __table_args__ = (
        Index("idx_incidents_service_status", "service_name", "status"),
        Index("idx_incidents_status_time", "status", "created_at"),
    )


class KnowledgeBase(Base):  # type: ignore
    """Model for storing knowledge base articles and solutions."""

    __tablename__ = "knowledge_base"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String(100), nullable=False, index=True)
    tags = Column(JSON, nullable=True)  # List of tags for searchability
    service_names = Column(JSON, nullable=True)  # Associated services
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_by = Column(String(100), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, default=True)
    usage_count = Column(Integer, default=0)
    effectiveness_score = Column(Integer, default=0)  # 0-100 based on feedback

    __table_args__ = (
        Index("idx_knowledge_base_category_active", "category", "is_active"),
        Index("idx_knowledge_base_updated", "updated_at"),
    )


class AuditLog(Base):  # type: ignore
    """Model for audit logging."""

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    user_id = Column(String(100), nullable=False, index=True)
    action = Column(String(200), nullable=False)
    resource_type = Column(String(100), nullable=False)
    resource_id = Column(String(200), nullable=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    success = Column(Boolean, nullable=False, default=True)

    __table_args__ = (
        Index("idx_audit_logs_user_time", "user_id", "timestamp"),
        Index("idx_audit_logs_action_time", "action", "timestamp"),
    )


class DatabaseManager:
    """Thread-safe database manager with connection pooling."""

    def __init__(self) -> None:
        self.engine: Optional[Engine] = None
        self.SessionLocal: Optional[sessionmaker[Session]] = None

    def initialize(self, database_url: str) -> None:
        """Initialize the database connection."""
        try:
            self.engine = create_engine(database_url, echo=settings.debug)

            # Create all tables
            Base.metadata.create_all(bind=self.engine)

            # Create sessionmaker
            self.SessionLocal = sessionmaker(
                autocommit=False, autoflush=False, bind=self.engine
            )

            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def health_check(self) -> Dict[str, Any]:
        """Check database connectivity."""
        try:
            if not self.engine:
                return {"status": "unhealthy", "message": "Database not initialized"}

            # Try to connect and execute a simple query
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            return {"status": "healthy", "message": "Database connection successful"}
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {"status": "unhealthy", "message": str(e)}

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Get a database session with automatic cleanup."""
        if not self.SessionLocal:
            raise RuntimeError("Database not initialized")

        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_session_direct(self) -> Session:
        """Get a database session for manual management."""
        if not self.SessionLocal:
            raise RuntimeError("Database not initialized")
        return self.SessionLocal()


# Global database manager instance
db_manager = DatabaseManager()


def get_db_session() -> Session:
    """Get database session (for dependency injection)."""
    return db_manager.get_session_direct()


class QueryRepository:
    """Repository for query operations."""

    @staticmethod
    def create_query(session: Session, query_data: Dict[str, Any]) -> Query:
        """Create a new query record."""
        query = Query(**query_data)
        session.add(query)
        session.flush()  # Get the ID without committing
        return query

    @staticmethod
    def get_query_by_id(session: Session, query_id: str) -> Optional[Query]:
        """Get query by ID."""
        return session.query(Query).filter(Query.query_id == query_id).first()

    @staticmethod
    def update_query_status(
        session: Session, query_id: str, status: str, **kwargs: Any
    ) -> bool:
        """Update query status and other fields."""
        query = session.query(Query).filter(Query.query_id == query_id).first()
        if query:
            query.status = status  # type: ignore
            for key, value in kwargs.items():
                if hasattr(query, key):
                    setattr(query, key, value)
            return True
        return False

    @staticmethod
    def get_recent_queries(
        session: Session, user_id: Optional[str] = None, limit: int = 50
    ) -> List[Query]:
        """Get recent queries, optionally filtered by user."""
        query = session.query(Query).order_by(desc(Query.created_at))
        if user_id:
            query = query.filter(Query.user_id == user_id)
        return query.limit(limit).all()


class MetricsRepository:
    """Repository for metrics operations."""

    @staticmethod
    def store_metrics(
        session: Session,
        service_name: str,
        metric_type: str,
        value: Dict[str, Any],
        source: str,
        record_metadata: Optional[Dict[str, Any]] = None,
    ) -> ServiceMetrics:
        """Store service metrics."""
        metrics = ServiceMetrics(
            service_name=service_name,
            metric_type=metric_type,
            value=value,
            source=source,
            record_metadata=record_metadata,
        )
        session.add(metrics)
        session.flush()
        return metrics

    @staticmethod
    def get_metrics(
        session: Session,
        service_name: str,
        metric_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[ServiceMetrics]:
        """Get metrics with optional filtering."""
        query = session.query(ServiceMetrics).filter(
            ServiceMetrics.service_name == service_name
        )

        if metric_type:
            query = query.filter(ServiceMetrics.metric_type == metric_type)

        if start_time:
            query = query.filter(ServiceMetrics.timestamp >= start_time)

        if end_time:
            query = query.filter(ServiceMetrics.timestamp <= end_time)

        return query.order_by(desc(ServiceMetrics.timestamp)).all()

    @staticmethod
    def cleanup_old_metrics(session: Session, days_to_keep: int = 30) -> int:
        """Remove old metrics beyond retention period."""
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        deleted = (
            session.query(ServiceMetrics)
            .filter(ServiceMetrics.timestamp < cutoff_date)
            .delete()
        )
        return deleted


class IncidentRepository:
    """Repository for incident operations."""

    @staticmethod
    def create_incident(session: Session, incident_data: Dict[str, Any]) -> Incident:
        """Create a new incident."""
        incident = Incident(**incident_data)
        session.add(incident)
        session.flush()
        return incident

    @staticmethod
    def get_active_incidents(
        session: Session, service_name: Optional[str] = None
    ) -> List[Incident]:
        """Get active incidents, optionally filtered by service."""
        query = session.query(Incident).filter(
            or_(Incident.status == "open", Incident.status == "investigating")
        )

        if service_name:
            query = query.filter(Incident.service_name == service_name)

        return query.order_by(desc(Incident.created_at)).all()

    @staticmethod
    def resolve_incident(
        session: Session,
        incident_id: str,
        resolution_actions: Optional[Dict[str, Any]] = None,
        auto_resolved: bool = False,
    ) -> bool:
        """Mark incident as resolved."""
        incident = (
            session.query(Incident).filter(Incident.incident_id == incident_id).first()
        )

        if incident:
            incident.status = "resolved"  # type: ignore
            incident.resolved_at = datetime.now()  # type: ignore
            incident.auto_resolved = auto_resolved  # type: ignore

            if resolution_actions:
                incident.resolution_actions = resolution_actions  # type: ignore

            # Calculate resolution time
            if incident.created_at and incident.resolved_at:
                resolution_time = (
                    incident.resolved_at - incident.created_at
                ).total_seconds() / 60
                incident.resolution_time_minutes = int(resolution_time)  # type: ignore

            return True

        return False


class KnowledgeBaseRepository:
    """Repository for knowledge base operations."""

    @staticmethod
    def create_article(session: Session, article_data: Dict[str, Any]) -> KnowledgeBase:
        """Create a new knowledge base article."""
        article = KnowledgeBase(**article_data)
        session.add(article)
        session.flush()
        return article

    @staticmethod
    def search_articles(
        session: Session,
        query: str,
        category: Optional[str] = None,
        service_name: Optional[str] = None,
        limit: int = 10,
    ) -> List[KnowledgeBase]:
        """Search knowledge base articles."""
        # Simple text search - could be enhanced with full-text search
        search_query = session.query(KnowledgeBase).filter(
            KnowledgeBase.is_active == True  # noqa: E712
        )

        # Text search in title and content
        search_terms = query.lower().split()
        for term in search_terms:
            search_query = search_query.filter(
                or_(
                    KnowledgeBase.title.ilike(f"%{term}%"),
                    KnowledgeBase.content.ilike(f"%{term}%"),
                )
            )

        if category:
            search_query = search_query.filter(KnowledgeBase.category == category)

        if service_name:
            # Search in service_names JSON field
            search_query = search_query.filter(
                KnowledgeBase.service_names.contains([service_name])
            )

        return search_query.order_by(desc(KnowledgeBase.usage_count)).limit(limit).all()

    @staticmethod
    def increment_usage(session: Session, article_id: int) -> None:
        """Increment usage count for an article."""
        article = (
            session.query(KnowledgeBase).filter(KnowledgeBase.id == article_id).first()
        )
        if article:
            article.usage_count += 1  # type: ignore


def initialize_database() -> None:
    """Initialize the database."""
    db_manager.initialize(settings.get_database_url())
