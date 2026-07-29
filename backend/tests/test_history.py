from pathlib import Path

from app.history import HistoryStore
from app.schemas import GenerationRequest, GenerationTask


def test_history_persists_after_store_recreation(tmp_path: Path) -> None:
    path = tmp_path / "history.json"
    task = GenerationTask(
        id="1",
        status="completed",
        progress=100,
        request=GenerationRequest(prompt="fox", checkpoint="a.safetensors"),
        outputs=["fox.png"],
    )

    HistoryStore(path).upsert(task)

    assert HistoryStore(path).list()[0] == task
