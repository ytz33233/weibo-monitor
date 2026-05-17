from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional
import json


@dataclass
class SentimentRecord:
    platform: str
    keyword: str
    record_id: str
    title: str
    content: str
    author: str
    author_id: str
    likes: int
    comments: int
    shares: int
    collects: int
    created_at: Optional[datetime] = None
    collected_at: datetime = field(default_factory=datetime.now)
    raw_data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["created_at"] = self.created_at.isoformat() if self.created_at else None
        d["collected_at"] = self.collected_at.isoformat() if self.collected_at else None
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "SentimentRecord":
        d = d.copy()
        if isinstance(d.get("created_at"), str) and d["created_at"]:
            d["created_at"] = datetime.fromisoformat(d["created_at"])
        if isinstance(d.get("collected_at"), str) and d["collected_at"]:
            d["collected_at"] = datetime.fromisoformat(d["collected_at"])
        if isinstance(d.get("raw_data"), str):
            d["raw_data"] = json.loads(d["raw_data"])
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
