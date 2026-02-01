"""
Asynchronous Messaging System for Tooeybot

Provides email-like asynchronous communication between the agent and user.
Messages are persisted, typed, and auditable.

Key features:
- Message types (question, answer, clarification, instruction, status, completion)
- Persistent storage in JSONL format
- Thread support for conversation context
- Read/unread tracking
- Task association
"""

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any


class MessageType(Enum):
    """Types of messages in the system."""
    QUESTION = "question"           # Agent asking user for input
    ANSWER = "answer"               # User answering agent's question
    CLARIFICATION = "clarification" # Request for more detail
    INSTRUCTION = "instruction"     # User giving new instructions
    STATUS = "status"               # Agent reporting status
    COMPLETION = "completion"       # Agent reporting task completion
    ALERT = "alert"                 # Agent raising an issue
    ACKNOWLEDGMENT = "ack"          # Simple acknowledgment


class MessageSender(Enum):
    """Who sent the message."""
    AGENT = "agent"
    USER = "user"


class MessagePriority(Enum):
    """Message priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class Message:
    """A single message in the system."""
    id: str
    sender: MessageSender
    message_type: MessageType
    subject: str
    body: str
    timestamp: str
    task_id: Optional[str] = None
    thread_id: Optional[str] = None
    reply_to: Optional[str] = None
    priority: MessagePriority = MessagePriority.NORMAL
    read: bool = False
    context: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "sender": self.sender.value,
            "message_type": self.message_type.value,
            "subject": self.subject,
            "body": self.body,
            "timestamp": self.timestamp,
            "task_id": self.task_id,
            "thread_id": self.thread_id,
            "reply_to": self.reply_to,
            "priority": self.priority.value,
            "read": self.read,
            "context": self.context,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            sender=MessageSender(data["sender"]),
            message_type=MessageType(data["message_type"]),
            subject=data["subject"],
            body=data["body"],
            timestamp=data["timestamp"],
            task_id=data.get("task_id"),
            thread_id=data.get("thread_id"),
            reply_to=data.get("reply_to"),
            priority=MessagePriority(data.get("priority", "normal")),
            read=data.get("read", False),
            context=data.get("context", {}),
        )


@dataclass
class Thread:
    """A conversation thread."""
    id: str
    subject: str
    task_id: Optional[str]
    created_at: str
    updated_at: str
    status: str  # "open", "waiting_user", "waiting_agent", "closed"
    message_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "subject": self.subject,
            "task_id": self.task_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status,
            "message_count": self.message_count,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Thread":
        return cls(
            id=data["id"],
            subject=data["subject"],
            task_id=data.get("task_id"),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            status=data["status"],
            message_count=data.get("message_count", 0),
        )


class MessageManager:
    """Manages the messaging system."""
    
    def __init__(self, agent_home: Path):
        self.agent_home = agent_home
        self.messages_dir = agent_home / "messages"
        self.messages_dir.mkdir(parents=True, exist_ok=True)
        
        self.messages_file = self.messages_dir / "messages.jsonl"
        self.threads_file = self.messages_dir / "threads.json"
        
        # Initialize files if needed
        if not self.messages_file.exists():
            self.messages_file.touch()
        if not self.threads_file.exists():
            self.threads_file.write_text("{}")
    
    def _generate_id(self) -> str:
        """Generate a unique message ID."""
        return f"msg-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
    
    def _generate_thread_id(self) -> str:
        """Generate a unique thread ID."""
        return f"thread-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
    
    def _now(self) -> str:
        """Get current timestamp."""
        return datetime.now(timezone.utc).isoformat()
    
    def _load_threads(self) -> Dict[str, Thread]:
        """Load all threads."""
        try:
            data = json.loads(self.threads_file.read_text() or "{}")
            return {k: Thread.from_dict(v) for k, v in data.items()}
        except Exception:
            return {}
    
    def _save_threads(self, threads: Dict[str, Thread]) -> None:
        """Save all threads."""
        data = {k: v.to_dict() for k, v in threads.items()}
        self.threads_file.write_text(json.dumps(data, indent=2))
    
    def _append_message(self, message: Message) -> None:
        """Append a message to the log."""
        with open(self.messages_file, "a") as f:
            json.dump(message.to_dict(), f)
            f.write("\n")
    
    def _load_all_messages(self) -> List[Message]:
        """Load all messages."""
        messages = []
        if self.messages_file.exists():
            with open(self.messages_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            messages.append(Message.from_dict(json.loads(line)))
                        except Exception:
                            pass
        return messages
    
    def _rewrite_messages(self, messages: List[Message]) -> None:
        """Rewrite all messages (for updates like marking read)."""
        with open(self.messages_file, "w") as f:
            for msg in messages:
                json.dump(msg.to_dict(), f)
                f.write("\n")
    
    def send_agent_message(
        self,
        message_type: MessageType,
        subject: str,
        body: str,
        task_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        reply_to: Optional[str] = None,
        priority: MessagePriority = MessagePriority.NORMAL,
        context: Optional[Dict[str, Any]] = None,
    ) -> Message:
        """
        Send a message from the agent to the user.
        
        If no thread_id is provided and this is a question, creates a new thread.
        """
        now = self._now()
        threads = self._load_threads()
        
        # Create new thread if needed
        if not thread_id and message_type == MessageType.QUESTION:
            thread_id = self._generate_thread_id()
            threads[thread_id] = Thread(
                id=thread_id,
                subject=subject,
                task_id=task_id,
                created_at=now,
                updated_at=now,
                status="waiting_user",
                message_count=0,
            )
        
        message = Message(
            id=self._generate_id(),
            sender=MessageSender.AGENT,
            message_type=message_type,
            subject=subject,
            body=body,
            timestamp=now,
            task_id=task_id,
            thread_id=thread_id,
            reply_to=reply_to,
            priority=priority,
            read=False,
            context=context or {},
        )
        
        # Update thread
        if thread_id and thread_id in threads:
            threads[thread_id].updated_at = now
            threads[thread_id].message_count += 1
            if message_type == MessageType.QUESTION:
                threads[thread_id].status = "waiting_user"
        
        self._append_message(message)
        self._save_threads(threads)
        
        return message
    
    def send_user_message(
        self,
        message_type: MessageType,
        subject: str,
        body: str,
        task_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        reply_to: Optional[str] = None,
    ) -> Message:
        """
        Send a message from the user to the agent.
        """
        now = self._now()
        threads = self._load_threads()
        
        # Create new thread for new instructions
        if not thread_id and message_type == MessageType.INSTRUCTION:
            thread_id = self._generate_thread_id()
            threads[thread_id] = Thread(
                id=thread_id,
                subject=subject,
                task_id=task_id,
                created_at=now,
                updated_at=now,
                status="waiting_agent",
                message_count=0,
            )
        
        message = Message(
            id=self._generate_id(),
            sender=MessageSender.USER,
            message_type=message_type,
            subject=subject,
            body=body,
            timestamp=now,
            task_id=task_id,
            thread_id=thread_id,
            reply_to=reply_to,
            priority=MessagePriority.NORMAL,
            read=False,
            context={},
        )
        
        # Update thread
        if thread_id and thread_id in threads:
            threads[thread_id].updated_at = now
            threads[thread_id].message_count += 1
            threads[thread_id].status = "waiting_agent"
        
        self._append_message(message)
        self._save_threads(threads)
        
        return message
    
    def get_unread_for_user(self) -> List[Message]:
        """Get unread messages for the user (from agent)."""
        messages = self._load_all_messages()
        return [
            m for m in messages
            if m.sender == MessageSender.AGENT and not m.read
        ]
    
    def get_unread_for_agent(self) -> List[Message]:
        """Get unread messages for the agent (from user)."""
        messages = self._load_all_messages()
        return [
            m for m in messages
            if m.sender == MessageSender.USER and not m.read
        ]
    
    def get_thread_messages(self, thread_id: str) -> List[Message]:
        """Get all messages in a thread, ordered by timestamp."""
        messages = self._load_all_messages()
        thread_msgs = [m for m in messages if m.thread_id == thread_id]
        return sorted(thread_msgs, key=lambda m: m.timestamp)
    
    def get_all_threads(self) -> List[Thread]:
        """Get all threads, newest first."""
        threads = self._load_threads()
        return sorted(threads.values(), key=lambda t: t.updated_at, reverse=True)
    
    def get_open_threads(self) -> List[Thread]:
        """Get threads that are not closed."""
        threads = self._load_threads()
        return [t for t in threads.values() if t.status != "closed"]
    
    def get_threads_waiting_user(self) -> List[Thread]:
        """Get threads waiting for user response."""
        threads = self._load_threads()
        return [t for t in threads.values() if t.status == "waiting_user"]
    
    def get_threads_waiting_agent(self) -> List[Thread]:
        """Get threads waiting for agent processing."""
        threads = self._load_threads()
        return [t for t in threads.values() if t.status == "waiting_agent"]
    
    def mark_read(self, message_id: str) -> None:
        """Mark a message as read."""
        messages = self._load_all_messages()
        for msg in messages:
            if msg.id == message_id:
                msg.read = True
                break
        self._rewrite_messages(messages)
    
    def mark_thread_read(self, thread_id: str, for_user: bool = True) -> None:
        """Mark all messages in a thread as read."""
        messages = self._load_all_messages()
        sender_to_mark = MessageSender.AGENT if for_user else MessageSender.USER
        for msg in messages:
            if msg.thread_id == thread_id and msg.sender == sender_to_mark:
                msg.read = True
        self._rewrite_messages(messages)
    
    def close_thread(self, thread_id: str) -> None:
        """Close a thread."""
        threads = self._load_threads()
        if thread_id in threads:
            threads[thread_id].status = "closed"
            threads[thread_id].updated_at = self._now()
            self._save_threads(threads)
    
    def get_pending_questions(self) -> List[Message]:
        """Get unanswered questions from agent."""
        messages = self._load_all_messages()
        
        # Find questions
        questions = [
            m for m in messages
            if m.sender == MessageSender.AGENT
            and m.message_type == MessageType.QUESTION
        ]
        
        # Find which have been answered
        answered_ids = set()
        for m in messages:
            if m.sender == MessageSender.USER and m.reply_to:
                answered_ids.add(m.reply_to)
        
        return [q for q in questions if q.id not in answered_ids]
    
    def has_pending_user_messages(self) -> bool:
        """Check if there are unread messages from user for agent."""
        return len(self.get_unread_for_agent()) > 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get messaging statistics."""
        messages = self._load_all_messages()
        threads = self._load_threads()
        
        return {
            "total_messages": len(messages),
            "total_threads": len(threads),
            "unread_for_user": len([m for m in messages if m.sender == MessageSender.AGENT and not m.read]),
            "unread_for_agent": len([m for m in messages if m.sender == MessageSender.USER and not m.read]),
            "waiting_user": len([t for t in threads.values() if t.status == "waiting_user"]),
            "waiting_agent": len([t for t in threads.values() if t.status == "waiting_agent"]),
            "open_threads": len([t for t in threads.values() if t.status != "closed"]),
        }
