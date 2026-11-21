"""Staff page "Резервные копии": only for the administrator (superuser)."""
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_safe

from . import backups


def _admin_only(request):
    if not request.user.is_superuser:
        raise PermissionDenied


@require_http_methods(["GET", "POST"])
def backup_list(request):
    _admin_only(request)
    if request.method == "POST":
        try:
            path = backups.create_backup()
            messages.success(request, f"Копия сохранена: {path.name}")
        except RuntimeError as e:
            messages.error(request, f"Не получилось сделать копию: {e}")
        return redirect("staff_backups")
    files = [{"name": p.name, "kb": round(p.stat().st_size / 1024), "kind": "PostgreSQL (pg_dump)" if p.suffix == ".sql" else "JSON (данные Django)"}
             for p in backups.list_backups()]
    return render(request, "shop/staff_backups.html", {
        "files": files, "keep": backups.KEEP, "active_section": "backups",
        "pg_dump": backups.find_tool("pg_dump") if backups.is_postgres() else None,
    })


@require_safe
def backup_download(request, name):
    _admin_only(request)
    path = backups.get_backup(name)
    if not path:
        raise Http404
    return FileResponse(open(path, "rb"), as_attachment=True, filename=path.name)
