import json
from pathlib import Path

from .schemas import GenerationTask


class HistoryStore:
    def __init__(self, path: Path, limit: int = 200) -> None:
        self.path = path
        self.limit = limit

    def list(self) -> list[GenerationTask]:
        if not self.path.exists():
            return []
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return [GenerationTask.model_validate(item) for item in data]

    def upsert(self, task: GenerationTask) -> None:
        items = [item for item in self.list() if item.id != task.id]
        items.insert(0, task)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(
            json.dumps(
                [item.model_dump() for item in items[: self.limit]],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        temp.replace(self.path)
