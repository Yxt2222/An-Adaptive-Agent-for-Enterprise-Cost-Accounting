# app/agentic/orchestration/trace.py
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List

@dataclass
class TraceEvent:
    ts: str
    type: str
    payload: Dict[str, Any]

class TraceRecorder:
    def __init__(self):
        self.events: List[TraceEvent] = []

    def emit(self, type_: str, **payload):
        '''
        Record a trace event.
        param:
        type_: str - The type of the event.
        payload: Dict[str, Any] - Additional data for the event.
        '''
        self.events.append(TraceEvent(ts=datetime.now().isoformat(), type=type_, payload=payload))

    def dump(self):
        '''
        Print all recorded trace events.
        '''
        for e in self.events:
            print(f"[{e.ts}] {e.type}: {e.payload}")
