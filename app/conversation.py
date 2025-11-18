"""
Conversation history management using SQLModel ORM
"""
from sqlmodel import Field, Session, SQLModel, create_engine, select
from datetime import datetime
from typing import Optional, List, Dict
from pathlib import Path

# Database path
DB_PATH = Path(__file__).parent.parent / "tmp" / "conversations.db"
DB_URL = f"sqlite:///{DB_PATH}"


class Conversation(SQLModel, table=True):
    """
    Conversation message model.
    Stores individual messages in a conversation thread.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str = Field(index=True)
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Create engine and tables
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
engine = create_engine(DB_URL, echo=False)


def init_db():
    """Initialize the database and create tables"""
    SQLModel.metadata.create_all(engine)


def save_message(session_id: str, role: str, content: str):
    """
    Save a message to conversation history.
    
    Args:
        session_id: Unique identifier for the conversation session
        role: 'user' or 'assistant'
        content: The message content
    """
    with Session(engine) as session:
        message = Conversation(
            session_id=session_id,
            role=role,
            content=content
        )
        session.add(message)
        session.commit()


def get_conversation(session_id: str, limit: int = 20) -> List[Dict[str, str]]:
    """
    Get conversation history for a session.
    
    Args:
        session_id: The conversation session to retrieve
        limit: Maximum number of messages to return (most recent)
    
    Returns:
        List of messages in format: [{"role": "user", "content": "..."}]
        Ordered from oldest to newest.
    """
    with Session(engine) as session:
        statement = (
            select(Conversation)
            .where(Conversation.session_id == session_id)
            .order_by(Conversation.timestamp.desc())
            .limit(limit)
        )
        results = session.exec(statement).all()
        
        # Reverse so oldest comes first
        return [
            {"role": msg.role, "content": msg.content}
            for msg in reversed(results)
        ]


def clear_conversation(session_id: str):
    """
    Delete all messages for a specific session.
    
    Args:
        session_id: The conversation session to clear
    """
    with Session(engine) as session:
        statement = select(Conversation).where(
            Conversation.session_id == session_id
        )
        messages = session.exec(statement).all()
        for msg in messages:
            session.delete(msg)
        session.commit()


def clear_all_conversations():
    """Delete all conversation history from the database"""
    with Session(engine) as session:
        statement = select(Conversation)
        messages = session.exec(statement).all()
        for msg in messages:
            session.delete(msg)
        session.commit()


# Initialize database on module import
init_db()
