"""Stage 2 shutdown lifecycle checks; no application processes are started."""
import asyncio
from pathlib import Path
from unittest.mock import Mock

from backend.app.core.config import settings
from backend.app.jobs import scheduler


def test_scheduler_waits_for_running_jobs_before_shutdown(monkeypatch):
    fake_scheduler = Mock(running=True)
    monkeypatch.setattr(scheduler, "_scheduler", fake_scheduler)

    scheduler.stop_scheduler()

    fake_scheduler.shutdown.assert_called_once_with(wait=True)
    assert scheduler._scheduler is None


def test_fastapi_lifespan_stops_jobs_and_disposes_database(monkeypatch, tmp_path):
    from backend.app import main
    from backend.app.database import session as session_module

    monkeypatch.setattr(settings, "STORAGE_PATH", str(tmp_path / "storage"))
    monkeypatch.setattr(settings, "GENERATED_IMAGES_PATH", str(tmp_path / "generated"))
    monkeypatch.setattr(settings, "TEMPLATES_PATH", str(tmp_path / "templates"))
    monkeypatch.setattr(settings, "LOGS_PATH", str(tmp_path / "logs"))
    monkeypatch.setattr(main, "init_db", Mock())
    start = Mock()
    stop = Mock()
    dispose = Mock()
    monkeypatch.setattr(scheduler, "start_scheduler", start)
    monkeypatch.setattr(scheduler, "stop_scheduler", stop)
    monkeypatch.setattr(session_module.engine, "dispose", dispose)

    async def run_lifespan():
        async with main.lifespan(None):
            pass

    asyncio.run(run_lifespan())
    start.assert_called_once()
    stop.assert_called_once()
    dispose.assert_called_once()


def test_windows_launcher_waits_then_kills_only_owned_process_trees():
    project_root = Path(__file__).resolve().parents[2]
    launcher = (project_root / "scripts" / "start.ps1").read_text(encoding="utf-8")
    assert "$BackendProc.WaitForExit(20000)" in launcher
    assert "taskkill.exe /PID $FrontendProc.Id /T /F" in launcher
    assert "taskkill.exe /PID $BackendProc.Id /T /F" in launcher


def test_scheduler_status_endpoint_is_authenticated_and_reports_live_state(client, monkeypatch):
    from backend.app.jobs import scheduler as scheduler_module

    assert client.get("/api/system/scheduler-status").status_code == 401
    client.post("/api/auth/setup", json={"username": "admin", "password": "password123456"})
    client.post("/api/auth/login", json={"username": "admin", "password": "password123456"})
    monkeypatch.setattr(scheduler_module, "get_scheduler_status", lambda: {"running": True, "jobs": []})

    response = client.get("/api/system/scheduler-status")
    assert response.status_code == 200
    assert response.json() == {"running": True, "jobs": []}
