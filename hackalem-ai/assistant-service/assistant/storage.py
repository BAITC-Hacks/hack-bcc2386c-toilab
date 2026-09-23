import asyncio
import time
from dataclasses import dataclass,field
from typing import Protocol
from .models import Action

@dataclass
class Session:
    history:list=field(default_factory=list)
    pending:Action|None=None
    pending_at:float=0
    touched:float=field(default_factory=time.monotonic)
    lock:asyncio.Lock=field(default_factory=asyncio.Lock)

class SessionRepository(Protocol):
    def get(self,session_id:str)->Session: ...

class MemorySessions:
    def __init__(self,ttl=3600,max_sessions=5000):
        self.sessions={};self.ttl=ttl;self.max_sessions=max_sessions
    def get(self,session_id):
        now=time.monotonic()
        for key in list(self.sessions):
            value=self.sessions[key]
            if now-value.touched>self.ttl and not value.lock.locked():
                del self.sessions[key]
        if session_id not in self.sessions:
            if len(self.sessions)>=self.max_sessions:
                raise RuntimeError("Session capacity reached")
            self.sessions[session_id]=Session()
        value=self.sessions[session_id];value.touched=now
        return value
