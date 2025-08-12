from __future__ import annotations
import os
from typing import Dict, Any, Tuple
import yaml

from engine.narrative.types import Story, Node, Choice

def _fq(ns: str, key: str) -> str:
    return f"{ns}.{key}"

def _normalize_goto(ns: str, raw: Any) -> Any:
    """
    Accepts None, empty, or string. If string is relative (no dot), qualify it with ns.
    """
    if raw is None:
        return None
    if not isinstance(raw, str) or raw.strip() == "":
        return None
    s = raw.strip()
    return s if "." in s else _fq(ns, s)

def load_story_file(path: str) -> Story:
    """
    Loads a single YAMP file containing:
        namespace: <str>
        nodes: { <key> : {say: <str or list>, choices: [...] } }
    Returns a Story with fully-qualified node ids.
    """
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
        
    ns = str(data.get("namespace", "")).strip()
    if not ns:
        raise ValueError(f"{path}: Missing 'namespace'")
    
    raw_nodes = data.get("nodes", {})
    if not isinstance(raw_nodes, dict) or not raw_nodes:
        raise ValueError(f"{path}: 'nodes' must be a non-empty mapping")
    
    nodes: Dict[str, Node] = {}
    first_fqid: str | None = None
    
    # YAML preservers order
    for key, body in raw_nodes.items():
        if not isinstance(body, dict):
            raise ValueError(f"{path}: node '{key}' must be a mapping")
        
        # say: allow str or list[str] (join lists into a single block)
        say = body.get("say", "")
        if isinstance(say, list):
            say = "\n".join(str(s) for s in say)
        elif not isinstance(say, str):
            say = str(say or "")
            
        # choices: list of {id, text, goto?}
        choices = []
        for idx, c in enumerate(body.get("choices", []) or []):
            if not isinstance(c, dict):
                continue
            cid = str(c.get("id") or f"{key}.choice{idx}")
            text = str(c.get("text") or "")
            goto = _normalize_goto(ns, c.get("goto"))
            choices.append(Choice(id=cid, text=text, goto=goto))
            
        fqid = _fq(ns, key)
        node = Node(fqid=fqid, namespace=ns, key=key, say=say, choices=choices)
        nodes[fqid] = node
        if first_fqid is None:
            first_fqid = fqid
        
    return Story(nodes=nodes, start=first_fqid or "")
