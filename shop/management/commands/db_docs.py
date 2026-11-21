"""
Builds the database documentation straight from the Django models,
so the diagram is always the same as the real tables:

    python manage.py db_docs
      -> docs/erd.mmd           ER diagram (Mermaid; open on mermaid.live or GitHub)
      -> docs/db_tables.md      every table: columns, keys, CHECK and UNIQUE rules
"""
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import models
from django.db.models import F, Q

TYPES = {
    "AutoField": "int", "BigAutoField": "bigint", "BigIntegerField": "bigint", "IntegerField": "int",
    "PositiveIntegerField": "int", "PositiveSmallIntegerField": "smallint", "SmallIntegerField": "smallint",
    "CharField": "varchar", "EmailField": "varchar", "URLField": "varchar", "SlugField": "varchar",
    "TextField": "text", "BooleanField": "boolean", "DecimalField": "numeric", "DateTimeField": "timestamptz",
    "DateField": "date", "GenericIPAddressField": "inet", "JSONField": "jsonb", "UUIDField": "uuid",
}
OPS = {"exact": "=", "gt": ">", "gte": ">=", "lt": "<", "lte": "<=", "regex": "~", "in": "IN"}


def sql_type(field):
    if isinstance(field, (models.ForeignKey, models.OneToOneField)):
        return "bigint"
    t = TYPES.get(field.get_internal_type(), field.get_internal_type().lower())
    if t == "varchar" and field.max_length:
        return f"varchar({field.max_length})"
    if t == "numeric":
        return f"numeric({field.max_digits},{field.decimal_places})"
    return t


def value(v):
    if isinstance(v, F):
        return v.name
    if isinstance(v, str):
        return f"'{v}'"
    if isinstance(v, (list, tuple)):
        return "(" + ", ".join(value(x) for x in v) + ")"
    return str(v)


def condition(q):
    """Q(price__gt=0) -> 'price > 0' (readable, close to the SQL)."""
    parts = []
    for child in q.children:
        if isinstance(child, Q):
            parts.append("(" + condition(child) + ")")
            continue
        key, v = child
        field, _, op = key.partition("__")
        if op == "isnull":
            parts.append(f"{field} IS {'NULL' if v else 'NOT NULL'}")
        elif op == "length__gte":
            parts.append(f"length({field}) >= {v}")
        else:
            parts.append(f"{field} {OPS.get(op or 'exact', op)} {value(v)}")
    text = f" {q.connector} ".join(parts)
    return f"NOT ({text})" if q.negated else text


def our_models():
    return [m for m in apps.get_app_config("shop").get_models()]


class Command(BaseCommand):
    help = "Generate the ER diagram and the table reference from the models"

    def handle(self, *args, **opts):
        out = Path(settings.BASE_DIR) / "docs"
        out.mkdir(exist_ok=True)
        tables = {m: m._meta.db_table for m in our_models()}

        erd, rel = ["erDiagram"], []
        md = ["# Таблицы базы данных", "",
              "Файл создан командой `python manage.py db_docs` из моделей Django, поэтому совпадает с настоящими таблицами.", ""]

        for model, table in tables.items():
            uniques = {f.name for f in model._meta.fields if f.unique and not f.primary_key}
            erd.append(f"    {table.upper()} {{")
            md += [f"## {table}", "", (model.__doc__ or "").strip().split("\n")[0], "",
                   "| Колонка | Тип | Ключ | Пусто? |", "|---|---|---|---|"]
            for f in model._meta.fields:
                col = f.column
                key = "PK" if f.primary_key else "FK" if f.is_relation else "UK" if f.name in uniques else ""
                if f.is_relation and f.name in uniques:
                    key = "FK, UK"
                erd.append(f"        {sql_type(f)} {col}" + (f" {key.replace(', ', ',')}" if key else ""))
                target = f"→ {f.related_model._meta.db_table}" if f.is_relation else ""
                md.append(f"| `{col}` | {sql_type(f)} {target} | {key} | {'да' if f.null else 'нет'} |")
                if f.is_relation and f.related_model in tables or (f.is_relation and f.related_model._meta.db_table == "users"):
                    parent = f.related_model._meta.db_table.upper()
                    one = isinstance(f, models.OneToOneField)
                    left = "|o" if f.null else "||"
                    right = ("o|" if one else "o{")
                    rel.append(f'    {parent} {left}--{right} {table.upper()} : "{f.name}"')
            erd.append("    }")

            rules = []
            for c in model._meta.constraints:
                if isinstance(c, models.CheckConstraint):
                    rules.append(f"- **CHECK** `{condition(c.condition)}` — {c.name}")
                elif isinstance(c, models.UniqueConstraint):
                    cond = f" WHERE {condition(c.condition)}" if c.condition else ""
                    rules.append(f"- **UNIQUE** ({', '.join(c.fields)}){cond} — {c.name}")
            for idx in model._meta.indexes:
                rules.append(f"- **INDEX** ({', '.join(idx.fields)}) — {idx.name}")
            if rules:
                md += ["", "Правила в базе:", *rules]
            md.append("")

        (out / "erd.mmd").write_text("\n".join(erd[:1] + rel + [""] + erd[1:]) + "\n", encoding="utf-8")
        (out / "db_tables.md").write_text("\n".join(md), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"{len(tables)} tables -> docs/erd.mmd, docs/db_tables.md"))
