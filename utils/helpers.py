from typing import Any, Dict
from datetime import datetime, timezone
import json

def format_datetime(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()

def sanitize_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        k: v for k, v in data.items() 
        if v is not None and v != ""
    }

def json_serializer(obj: Any) -> str:
    if isinstance(obj, datetime):
        return format_datetime(obj)
    raise TypeError(f"Type {type(obj)} not serializable")

def parse_json_safe(json_str: str) -> Dict:
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return {}