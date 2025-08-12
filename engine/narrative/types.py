from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, List

@dataclass(eq=False)
class Choice:
    id: str
    text: str
    goto: Optional[str] = None  # Fully-qualified "namespace.key" or None (WIP)
    
@dataclass(eq=False)
class Node:
    fqid: str                   # Fully-qualified id: "<namespace>.<key>"
    namespace: str
    key: str
    say: str                    # Original multiline block
    choices: List[Choice] = field(default_factory=list)
    
@dataclass
class Story:
    nodes: Dict[str, Node]      # FQID -> None
    start: str                  # FQID
    
