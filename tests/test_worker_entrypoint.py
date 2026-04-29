from app.config.settings import Settings


def test_worker_entrypoint_can_build_worker(tmp_path):
    from app.workers.run_worker import build_worker

    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'worker.db'}",
        redis_url="",
        max_task_retries=2,
        session_lock_ttl_seconds=9,
    )

    worker = build_worker(settings)

    assert worker.max_retries == 2
    assert worker.session_lock_ttl_seconds == 9
    assert worker.queue is not None


def test_worker_entrypoint_main_smoke(monkeypatch):
    from app.workers import run_worker

    events: dict[str, bool] = {"run_loop": False, "stop": False}

    class FakeWorker:
        def run_loop(self):
            events["run_loop"] = True
            raise KeyboardInterrupt

        def stop(self):
            events["stop"] = True

    monkeypatch.setattr(run_worker, "build_worker", lambda settings: FakeWorker())
    run_worker.main()

    assert events["run_loop"] is True
    assert events["stop"] is True
