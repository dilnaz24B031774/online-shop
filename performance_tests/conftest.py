"""Печатает таблицу метрик в конце запуска pytest (для unittest не нужен)."""


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    try:
        from performance_tests import report
        if report._rows:
            terminalreporter.write_sep("=", "Performance metrics (секунды)")
            for line in report.render_markdown().splitlines()[4:-2]:
                terminalreporter.write_line(line)
            terminalreporter.write_line("Полный отчёт: performance_tests/reports/performance_report.md")
    except Exception:       # отчёт — бонус, он не должен ломать запуск тестов
        pass
