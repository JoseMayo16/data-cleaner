"""Generate the two messy sample files used by the demo and the tests.

Every person, email and phone number is invented. The mess is the kind real exports have:
inconsistent case and spacing, mixed date and number formats, typos in email domains,
placeholder values like "N/A", spelling variants of the same city, and duplicate rows.

    python scripts/make_samples.py
"""

from __future__ import annotations

import csv
import io
import random
from datetime import date, datetime, timedelta
from pathlib import Path

from openpyxl import Workbook

ROOT = Path(__file__).resolve().parents[1]
OUT = [ROOT / "samples", ROOT / "site" / "samples"]

FIRST = [
    "María",
    "José",
    "Juan",
    "Ana",
    "Luis",
    "Carolina",
    "Andrés",
    "Valentina",
    "Camilo",
    "Daniela",
    "Santiago",
    "Laura",
    "Felipe",
    "Sofía",
    "Mateo",
    "Natalia",
    "Sebastián",
    "Isabella",
    "Julián",
    "Paula",
    "Diego",
    "Mariana",
    "Tomás",
    "Gabriela",
]
LAST = [
    "García",
    "Rodríguez",
    "Martínez",
    "López",
    "Gómez",
    "Restrepo",
    "Zapata",
    "Ospina",
    "Cardona",
    "Henao",
    "Vélez",
    "Jaramillo",
    "Arango",
    "Muñoz",
    "Ríos",
    "de la Cruz",
    "Castaño",
    "Giraldo",
    "Duque",
    "Mejía",
]
CITIES = {
    "Medellín": ["Medellín", "medellin", "MEDELLIN", "Medellin "],
    "Bogotá": ["Bogotá", "bogota", "Bogota", " BOGOTÁ"],
    "Cali": ["Cali", "cali", "CALI"],
    "Barranquilla": ["Barranquilla", "barranquilla"],
    "Envigado": ["Envigado", "envigado"],
}
DOMAINS = ["gmail.com", "hotmail.com", "outlook.com", "yahoo.com", "empresa.example"]
TYPOS = {
    "gmail.com": ["gmial.com", "gmail.con"],
    "hotmail.com": ["hotmial.com"],
    "outlook.com": ["outlok.com"],
    "yahoo.com": ["yaho.com"],
}
MONTHS_ES = [
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
]
EMPTY = ["", "N/A", "-", "null", "sin dato"]


def ascii_lower(text: str) -> str:
    table = str.maketrans("áéíóúñ", "aeioun")
    return text.lower().translate(table).replace(" ", "")


def messy_name(rng, first, last):
    name = f"{first} {last}"
    return rng.choice(
        [name, name.upper(), name.lower(), f"  {name}", name.replace(" ", "  "), name, name, name]
    )


def messy_email(rng, first, last, n):
    domain = rng.choice(DOMAINS)
    local = f"{ascii_lower(first)}.{ascii_lower(last)}{n % 7 or ''}"
    roll = rng.random()
    if roll < 0.1 and domain in TYPOS:
        domain = rng.choice(TYPOS[domain])
    email = f"{local}@{domain}"
    if roll > 0.93:
        return rng.choice([email.replace("@", " at "), f"{local}@", f"{local}.{domain}"])
    return rng.choice([email, email, email.upper(), f" {email} ", f"mailto:{email}", email])


def messy_phone(rng):
    n = f"3{rng.randint(0, 2)}{rng.randint(0, 9)}{rng.randint(1000000, 9999999)}"
    roll = rng.random()
    if roll < 0.04:
        return n[:5]
    return rng.choice(
        [
            n,
            f"{n[:3]} {n[3:6]} {n[6:]}",
            f"({n[:3]}) {n[3:6]}-{n[6:]}",
            f"+57 {n}",
            f"57{n}",
            f"+57 {n[:3]} {n[3:]}",
            f"{n[:3]}-{n[3:]}",
        ]
    )


def messy_date_es(rng, d: date):
    return rng.choice(
        [
            d.strftime("%d/%m/%Y"),
            d.isoformat(),
            d.strftime("%d-%m-%Y"),
            f"{d.day} de {MONTHS_ES[d.month - 1]} de {d.year}",
            d.strftime("%d/%m/%y"),
            d.strftime("%d/%m/%Y"),
        ]
    )


def messy_cop(rng, value: int):
    dotted = f"{value:,}".replace(",", ".")
    return rng.choice([f"$ {dotted}", str(value), f"{dotted},00", f"COP {dotted}", dotted])


def contacts(rng) -> list[list[str]]:
    header = [
        "Nombre",
        "Correo",
        "Teléfono",
        "Ciudad",
        "Fecha de registro",
        "Valor compra",
        "Estado",
    ]
    rows = []
    start = date(2024, 1, 1)
    for n in range(230):
        first, last = rng.choice(FIRST), f"{rng.choice(LAST)} {rng.choice(LAST)}"
        city = rng.choice(list(CITIES))
        rows.append(
            [
                messy_name(rng, first, last),
                messy_email(rng, first, last, n) if rng.random() > 0.05 else rng.choice(EMPTY),
                messy_phone(rng) if rng.random() > 0.06 else rng.choice(EMPTY),
                rng.choice(CITIES[city]),
                messy_date_es(rng, start + timedelta(days=rng.randint(0, 640))),
                messy_cop(rng, rng.randrange(45000, 4800000, 500))
                if rng.random() > 0.05
                else rng.choice(EMPTY),
                rng.choice(
                    ["Activo", "activo", "ACTIVO", "Inactivo", "inactivo", "Prospecto", "prospecto"]
                ),
            ]
        )
    for _ in range(12):  # duplicates that only differ in case or spacing
        src = list(rng.choice(rows))
        src[0] = src[0].strip().upper() if rng.random() < 0.5 else f" {src[0].strip()} "
        rows.insert(rng.randint(0, len(rows)), src)
    for _ in range(5):  # same email, different person data: a probable duplicate to review
        src = list(rng.choice(rows))
        src[3] = rng.choice(CITIES[rng.choice(list(CITIES))])
        src[6] = "Activo"
        rows.insert(rng.randint(0, len(rows)), src)
    rows.insert(40, ["", "", "", "", "", "", ""])  # a blank line in the middle of the export
    return [header, *rows]


REGIONS = {
    "West": ["West", "west", "WEST"],
    "East": ["East", "east", " East"],
    "Midwest": ["Midwest", "midwest", "Mid-west"],
    "South": ["South", "south"],
}
PRODUCTS = [
    ("Standing desk", 499),
    ("Ergonomic chair", 329.5),
    ("Monitor arm", 89.99),
    ("Desk lamp", 45),
    ("Cable kit", 19.9),
    ("Laptop stand", 59),
]
US_FIRST = [
    "Emma",
    "Liam",
    "Olivia",
    "Noah",
    "Ava",
    "Elijah",
    "Mia",
    "James",
    "Harper",
    "Lucas",
    "Evelyn",
    "Mason",
]
US_LAST = [
    "Walker",
    "Bennett",
    "Hayes",
    "Brooks",
    "Sullivan",
    "Foster",
    "Reyes",
    "Nguyen",
    "Patel",
    "Kim",
    "Ortiz",
    "Coleman",
]


def orders(rng) -> list[list]:
    header = [
        "Order ID",
        "Order Date",
        "Customer Name",
        "Email",
        "Phone",
        "Product",
        "Quantity",
        "Unit Price",
        "Region",
    ]
    rows = []
    start = datetime(2026, 1, 5)
    for n in range(140):
        d = start + timedelta(days=rng.randint(0, 270))
        first, last = rng.choice(US_FIRST), rng.choice(US_LAST)
        product, price = rng.choice(PRODUCTS)
        phone = f"{rng.randint(201, 989)}{rng.randint(200, 999)}{rng.randint(1000, 9999)}"
        rows.append(
            [
                f"SO-{10200 + n}",
                rng.choice(
                    [d, d, d.strftime("%m/%d/%Y"), d.strftime("%b %d, %Y"), d.strftime("%Y-%m-%d")]
                ),
                rng.choice(
                    [
                        f"{first} {last}",
                        f"{first} {last}".upper(),
                        f"{first.lower()} {last.lower()}",
                    ]
                ),
                rng.choice(
                    [
                        f"{first}.{last}@example.com".lower(),
                        f"{first}.{last}@Example.com",
                        f" {first[0]}{last}@example.com ".lower(),
                    ]
                ),
                rng.choice(
                    [
                        f"({phone[:3]}) {phone[3:6]}-{phone[6:]}",
                        f"{phone[:3]}.{phone[3:6]}.{phone[6:]}",
                        f"+1 {phone}",
                        phone,
                        f"1-{phone[:3]}-{phone[3:6]}-{phone[6:]}",
                    ]
                ),
                product,
                rng.choice([rng.randint(1, 12), str(rng.randint(1, 12))]),
                rng.choice([price, f"${price:,.2f}", f"{price:,.2f}", f"USD {price}"]),
                rng.choice(REGIONS[rng.choice(list(REGIONS))]),
            ]
        )
    for _ in range(6):
        rows.insert(rng.randint(0, len(rows)), list(rng.choice(rows)))
    rows[17][7] = "TBD"
    rows[52][1] = "13/31/2026"
    return [header, *rows]


def main() -> None:
    rng = random.Random(2026)
    buf = io.StringIO()
    csv.writer(buf, delimiter=";", lineterminator="\r\n").writerows(contacts(rng))
    data = buf.getvalue().encode("utf-8-sig")

    wb = Workbook()
    ws = wb.active
    ws.title = "Orders"
    for row in orders(rng):
        ws.append(row)
    for cell in ws["B"][1:]:
        if isinstance(cell.value, datetime):
            cell.number_format = "mm/dd/yyyy"
    xlsx = io.BytesIO()
    wb.save(xlsx)

    for folder in OUT:
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "crm-contacts.csv").write_bytes(data)
        (folder / "sales-orders.xlsx").write_bytes(xlsx.getvalue())
    print("crm-contacts.csv, sales-orders.xlsx")


if __name__ == "__main__":
    main()
