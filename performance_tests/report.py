"""Сбор результатов тестов и запись отчёта (reports/performance_report.md и .json)."""
import atexit
import json
from datetime import datetime
from pathlib import Path

REPORT_DIR = Path(__file__).resolve().parent / "reports"
_rows = []
_registered = False


def record(test_name, **metrics):
    """Запоминает метрики теста (вызывается из тестов)."""
    global _registered
    _rows.append({"test": test_name, **metrics})
    if not _registered:
        atexit.register(write_reports)
        _registered = True


def _fmt(value):
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def render_markdown():
    lines = ["# Отчёт Performance Testing — SaudaGo Online Shop", "",
             f"Дата: {datetime.now():%Y-%m-%d %H:%M:%S}", "",
             "| Тест | Метрики |", "|---|---|"]
    for row in _rows:
        metrics = ", ".join(f"{k}={_fmt(v)}" for k, v in row.items() if k != "test")
        lines.append(f"| {row['test']} | {metrics} |")
    lines += ["", "Время указано в секундах. p95 — 95% запросов были быстрее этого значения."]
    return "\n".join(lines)


def write_reports():
    if not _rows:
        return
    try:
        REPORT_DIR.mkdir(exist_ok=True)
        (REPORT_DIR / "performance_report.md").write_text(render_markdown(), encoding="utf-8")
        (REPORT_DIR / "performance_report.json").write_text(
            json.dumps(_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass
