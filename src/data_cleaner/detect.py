"""Guess what each column holds, from its header and its values.

Kinds: email, phone, date, number, name, category, id, text. `id` and `text` are only
trimmed; every other kind gets its own rule. The user can override any guess.
"""

from __future__ import annotations

import re

from . import rules

KINDS = ("email", "phone", "date", "number", "name", "category", "id", "text")

HINTS = {
    "email": {"email", "e-mail", "mail", "correo", "emails"},
    "phone": {"phone", "tel", "telefono", "celular", "cel", "movil", "mobile", "whatsapp",
              "cell", "telephone", "fono"},
    "date": {"date", "fecha", "created", "updated", "birth", "birthday", "nacimiento",
             "registro", "dob", "since", "desde", "joined", "signup"},
    "id": {"id", "code", "codigo", "sku", "nit", "cedula", "documento", "document", "zip",
           "postal", "rut", "rfc", "dni", "ref", "reference", "referencia", "invoice", "factura",
           "order", "pedido", "ticket"},
    "number": {"amount", "price", "total", "valor", "monto", "precio", "cost", "costo",
               "salary", "salario", "qty", "quantity", "cantidad", "balance", "saldo",
               "importe", "revenue", "ingresos", "subtotal", "discount", "descuento", "units",
               "unidades"},
    "name": {"name", "nombre", "nombres", "apellido", "apellidos", "first", "last",
             "fullname", "contact", "contacto", "surname"},
    "category": {"city", "ciudad", "country", "pais", "state", "estado", "status", "category",
                 "categoria", "segment", "segmento", "source", "fuente", "department",
                 "departamento", "plan", "tipo", "type", "gender", "genero", "region",
                 "channel", "canal", "stage", "etapa", "product", "producto", "seller",
                 "vendedor"},
}  # fmt: skip
ORDER = ("email", "phone", "date", "id", "number", "name", "category")

_PHONE_SHAPE = re.compile(r"^\+?[\d\s().-]{7,20}(?:\s*(?:ext\.?|x)\s*\d+)?$", re.IGNORECASE)


def _tokens(header: str) -> set[str]:
    return set(re.split(r"[^a-z0-9]+|(?<=[a-z])(?=[0-9])", rules.plain(header))) - {""}


def _share(values: list[str], test) -> float:
    return sum(1 for v in values if test(v)) / len(values) if values else 0.0


def _is_number(v: str) -> bool:
    return rules.parse_number(v, ",") is not None or rules.parse_number(v, ".") is not None


def detect_kind(header: str, values: list[str]) -> str:
    filled = [rules.squeeze(v) for v in values if v.strip() and not rules.is_empty_token(v)]
    tokens = _tokens(header)
    sample = filled[:2000]

    tests = {
        "email": lambda v: "@" in v,
        "phone": lambda v: bool(_PHONE_SHAPE.match(v)),
        "date": lambda v: rules.parse_date(v, "DMY") or rules.parse_date(v, "MDY"),
        "number": _is_number,
    }

    if sample and _share(sample, tests["email"]) >= 0.8:  # unmistakable, whatever the header
        return "email"
    for kind in ORDER:  # header hint confirmed by at least half the values
        if tokens & HINTS[kind]:
            if kind in tests and sample and _share(sample, tests[kind]) < 0.5:
                continue
            return kind

    if not sample:
        return "text"
    if _share(sample, tests["email"]) >= 0.8:
        return "email"
    if _share(sample, tests["date"]) >= 0.8 and not all(v.isdigit() for v in sample):
        return "date"
    if _share(sample, _is_number) >= 0.9:
        return "number"
    distinct = {rules.plain(v) for v in sample}
    if len(distinct) <= 30 and len(distinct) <= 0.3 * len(sample) and len(sample) >= 10:
        return "category"
    return "text"


def detect_date_order(values: list[str], default: str) -> str:
    """'DMY' or 'MDY' from values whose day can only be one position (e.g. 25/03 or 03/25)."""
    dmy = mdy = 0
    for v in values:
        parts = rules.numeric_date_parts(v)
        if parts:
            a, b = parts
            dmy += a > 12 >= b
            mdy += b > 12 >= a
    if dmy and not mdy:
        return "DMY"
    if mdy and not dmy:
        return "MDY"
    return default


def detect_decimal(values: list[str], default: str) -> str:
    comma = dot = 0
    for v in values:
        s = rules.strip_currency(v)
        comma += bool(rules.COMMA_DECIMAL.match(s))
        dot += bool(rules.DOT_DECIMAL.match(s))
    if comma > dot:
        return ","
    if dot > comma:
        return "."
    return default
