from engine.stability_patch import install


class DummyEngine:
    def __init__(self):
        self.diagnostics = {"rejections": {}}

    def now(self):
        from datetime import datetime, timezone
        return datetime.now(timezone.utc)

    def _write_diagnostics(self):
        self.written = True

    def _market_snapshot(self):
        return {"source": "test"}

    def run_cycle(self):
        raise RuntimeError("temporary market-data failure")


def test_runtime_failure_does_not_escape_worker_boundary():
    install(DummyEngine)
    engine = DummyEngine()
    assert engine.run_cycle() == []
    assert engine.diagnostics["runtime_error"] == "RuntimeError: temporary market-data failure"
    assert engine.diagnostics["rejections"]["runtime"] == engine.diagnostics["runtime_error"]
    assert getattr(engine, "written", False) is True
