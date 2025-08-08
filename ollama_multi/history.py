import json
from pathlib import Path
from typing import Any, Dict, List

def load_history(path: Path) -> List[Dict[str, Any]]:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []

def save_history(path: Path, messages: List[Dict[str, Any]]) -> None:
    try:
        path.write_text(json.dumps(messages, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

def trim_history(messages: List[Dict[str, Any]], max_turns: int) -> List[Dict[str, Any]]:
    # Keep the last N messages; always keep the initial system message
    if not messages:
        return messages
    system = messages[0] if messages[0].get("role") == "system" else None
    core = messages[1:] if system else messages
    if len(core) <= max_turns:
        return messages
    trimmed = core[-max_turns:]
    return [system] + trimmed if system else trimmed
