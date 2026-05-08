#!/usr/bin/env python3
"""CLI tool for managing properties in the crypto real estate SQLite database."""

import argparse
import sqlite3
import sys
import os
import urllib.request
import urllib.error
import json
from typing import Optional, Any

DB_PATH = "/var/www/crypto_realestate/data/properties.db"

# ANSI color codes
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def supports_color() -> bool:
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def colorize(text: str, color: str) -> str:
    if supports_color():
        return f"{color}{text}{RESET}"
    return text


def check_db() -> bool:
    if not os.path.exists(DB_PATH):
        print(
            colorize(
                f"Error: Database not found at {DB_PATH}\n"
                "Ensure the crypto real estate application has been set up and the DB initialized.",
                RED,
            )
        )
        return False
    return True


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def fmt_row(values: list[str], widths: list[int]) -> str:
    return "  ".join(str(v).ljust(w) for v, w in zip(values, widths))


def fmt_table(headers: list[str], rows: list[list[Any]]) -> str:
    all_rows = [headers] + [[str(c) for c in row] for row in rows]
    widths = [max(len(str(r[i])) for r in all_rows) for i in range(len(headers))]
    sep = "  ".join("-" * w for w in widths)
    lines = [
        colorize(fmt_row(headers, widths), BOLD),
        sep,
    ]
    for row in rows:
        lines.append(fmt_row([str(c) for c in row], widths))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------

def cmd_list(args: argparse.Namespace) -> None:
    if not check_db():
        sys.exit(1)
    try:
        conn = get_connection()
        query = """
            SELECT p.id, p.title, p.location, p.price_xmr, p.price_usd,
                   p.status, p.created_at,
                   c.slug AS category_slug
            FROM properties p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE 1=1
        """
        params: list[Any] = []
        if args.category:
            query += " AND c.slug = ?"
            params.append(args.category)
        if args.status:
            query += " AND p.status = ?"
            params.append(args.status)
        query += " ORDER BY p.id"

        cur = conn.execute(query, params)
        rows = cur.fetchall()
        conn.close()

        if not rows:
            print(colorize("No properties found.", YELLOW))
            return

        table_rows = [
            [
                r["id"],
                r["title"][:40],
                (r["location"] or "")[:30],
                f"{r['price_xmr']:.4f}",
                f"{r['price_usd']:.2f}" if r["price_usd"] is not None else "N/A",
                r["status"] or "",
                (r["created_at"] or "")[:10],
            ]
            for r in rows
        ]
        headers = ["ID", "Title", "Location", "Price XMR", "Price USD", "Status", "Created"]
        print(fmt_table(headers, table_rows))
        print(colorize(f"\n{len(rows)} propert{'y' if len(rows) == 1 else 'ies'} found.", CYAN))
    except sqlite3.Error as e:
        print(colorize(f"Database error: {e}", RED))
        sys.exit(1)


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------

def cmd_add(args: argparse.Namespace) -> None:
    if not check_db():
        sys.exit(1)
    try:
        conn = get_connection()
        category_id: Optional[int] = None
        if args.category:
            row = conn.execute(
                "SELECT id FROM categories WHERE slug = ?", (args.category,)
            ).fetchone()
            if row is None:
                print(colorize(f"Category '{args.category}' not found.", RED))
                conn.close()
                sys.exit(1)
            category_id = row["id"]

        conn.execute(
            """
            INSERT INTO properties
                (title, description, location, price_xmr, price_usd,
                 bedrooms, bathrooms, sqft, image_url, category_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                args.title,
                args.description,
                args.location,
                args.price_xmr,
                args.price_usd,
                args.bedrooms,
                args.bathrooms,
                args.sqft,
                args.image_url,
                category_id,
                args.status,
            ),
        )
        conn.commit()
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()
        print(colorize(f"Property added with ID {new_id}.", GREEN))
    except sqlite3.Error as e:
        print(colorize(f"Database error: {e}", RED))
        sys.exit(1)


# ---------------------------------------------------------------------------
# remove
# ---------------------------------------------------------------------------

def cmd_remove(args: argparse.Namespace) -> None:
    if not check_db():
        sys.exit(1)
    try:
        conn = get_connection()
        row = conn.execute(
            "SELECT id, title FROM properties WHERE id = ?", (args.id,)
        ).fetchone()
        if row is None:
            print(colorize(f"Property with ID {args.id} not found.", RED))
            conn.close()
            sys.exit(1)

        print(f"About to remove: [{row['id']}] {row['title']}")
        answer = input("Are you sure? (yes/no): ").strip().lower()
        if answer not in ("yes", "y"):
            print(colorize("Aborted.", YELLOW))
            conn.close()
            return

        conn.execute("DELETE FROM properties WHERE id = ?", (args.id,))
        conn.commit()
        conn.close()
        print(colorize(f"Property {args.id} removed.", GREEN))
    except sqlite3.Error as e:
        print(colorize(f"Database error: {e}", RED))
        sys.exit(1)


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------

def cmd_update(args: argparse.Namespace) -> None:
    if not check_db():
        sys.exit(1)

    updatable = {
        "title": args.title,
        "description": args.description,
        "location": args.location,
        "price_xmr": args.price_xmr,
        "price_usd": args.price_usd,
        "bedrooms": args.bedrooms,
        "bathrooms": args.bathrooms,
        "sqft": args.sqft,
        "image_url": args.image_url,
        "status": args.status,
    }
    fields = {k: v for k, v in updatable.items() if v is not None}

    if args.category is not None:
        fields["_category"] = args.category

    if not fields:
        print(colorize("No fields to update. Provide at least one option.", YELLOW))
        sys.exit(1)

    try:
        conn = get_connection()
        row = conn.execute(
            "SELECT id FROM properties WHERE id = ?", (args.id,)
        ).fetchone()
        if row is None:
            print(colorize(f"Property with ID {args.id} not found.", RED))
            conn.close()
            sys.exit(1)

        if "_category" in fields:
            slug = fields.pop("_category")
            cat = conn.execute(
                "SELECT id FROM categories WHERE slug = ?", (slug,)
            ).fetchone()
            if cat is None:
                print(colorize(f"Category '{slug}' not found.", RED))
                conn.close()
                sys.exit(1)
            fields["category_id"] = cat["id"]

        set_clause = ", ".join(f"{col} = ?" for col in fields)
        values = list(fields.values()) + [args.id]
        conn.execute(f"UPDATE properties SET {set_clause} WHERE id = ?", values)
        conn.commit()
        conn.close()
        print(colorize(f"Property {args.id} updated ({', '.join(fields)}).", GREEN))
    except sqlite3.Error as e:
        print(colorize(f"Database error: {e}", RED))
        sys.exit(1)


# ---------------------------------------------------------------------------
# update-prices
# ---------------------------------------------------------------------------

def fetch_xmr_usd_rate() -> float:
    url = "https://api.coingecko.com/api/v3/simple/price?ids=monero&vs_currencies=usd"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        return float(data["monero"]["usd"])
    except (urllib.error.URLError, KeyError, ValueError) as e:
        print(colorize(f"Failed to fetch XMR/USD rate: {e}", RED))
        sys.exit(1)


def cmd_update_prices(_args: argparse.Namespace) -> None:
    if not check_db():
        sys.exit(1)

    rate = fetch_xmr_usd_rate()
    print(colorize(f"Current XMR/USD rate: ${rate:,.2f}", CYAN))

    try:
        conn = get_connection()
        rows = conn.execute(
            "SELECT id, title, price_xmr, price_usd FROM properties WHERE status = 'active'"
        ).fetchall()

        if not rows:
            print(colorize("No active properties found.", YELLOW))
            conn.close()
            return

        headers = ["ID", "Title", "Old USD", "New USD", "Change"]
        table_rows = []
        for r in rows:
            new_usd = round(r["price_xmr"] * rate, 2)
            old_usd = r["price_usd"] if r["price_usd"] is not None else 0.0
            diff = new_usd - old_usd
            sign = "+" if diff >= 0 else ""
            table_rows.append([
                r["id"],
                r["title"][:40],
                f"{old_usd:.2f}",
                f"{new_usd:.2f}",
                f"{sign}{diff:.2f}",
            ])
            conn.execute(
                "UPDATE properties SET price_usd = ? WHERE id = ?",
                (new_usd, r["id"]),
            )

        conn.commit()
        conn.close()
        print(fmt_table(headers, table_rows))
        print(colorize(f"\nUpdated {len(rows)} propert{'y' if len(rows) == 1 else 'ies'}.", GREEN))
    except sqlite3.Error as e:
        print(colorize(f"Database error: {e}", RED))
        sys.exit(1)


# ---------------------------------------------------------------------------
# show
# ---------------------------------------------------------------------------

def cmd_show(args: argparse.Namespace) -> None:
    if not check_db():
        sys.exit(1)
    try:
        conn = get_connection()
        row = conn.execute(
            """
            SELECT p.*, c.name AS category_name, c.slug AS category_slug
            FROM properties p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE p.id = ?
            """,
            (args.id,),
        ).fetchone()
        conn.close()

        if row is None:
            print(colorize(f"Property with ID {args.id} not found.", RED))
            sys.exit(1)

        label_w = 16
        print(colorize(f"\n{'='*60}", CYAN))
        print(colorize(f"  Property #{row['id']}: {row['title']}", BOLD))
        print(colorize(f"{'='*60}", CYAN))
        fields = [
            ("Description", row["description"]),
            ("Location", row["location"]),
            ("Price (XMR)", f"{row['price_xmr']:.4f} XMR"),
            ("Price (USD)", f"${row['price_usd']:.2f}" if row["price_usd"] is not None else "N/A"),
            ("Bedrooms", row["bedrooms"]),
            ("Bathrooms", row["bathrooms"]),
            ("Sqft", row["sqft"]),
            ("Category", f"{row['category_name']} ({row['category_slug']})" if row["category_name"] else "N/A"),
            ("Status", row["status"]),
            ("Image URL", row["image_url"] or "N/A"),
            ("Created", row["created_at"]),
            ("Updated", row["updated_at"] if "updated_at" in row.keys() else "N/A"),
        ]
        for label, value in fields:
            print(f"  {colorize(label.ljust(label_w), YELLOW)}{value}")
        print(colorize(f"{'='*60}\n", CYAN))
    except sqlite3.Error as e:
        print(colorize(f"Database error: {e}", RED))
        sys.exit(1)


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def cmd_stats(_args: argparse.Namespace) -> None:
    if not check_db():
        sys.exit(1)
    try:
        conn = get_connection()

        status_rows = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM properties GROUP BY status ORDER BY status"
        ).fetchall()

        category_rows = conn.execute(
            """
            SELECT COALESCE(c.name, 'Uncategorized') AS category,
                   COUNT(*) AS cnt
            FROM properties p
            LEFT JOIN categories c ON p.category_id = c.id
            GROUP BY c.id, c.name
            ORDER BY cnt DESC
            """
        ).fetchall()

        totals = conn.execute(
            "SELECT SUM(price_xmr) AS total_xmr, SUM(price_usd) AS total_usd FROM properties"
        ).fetchone()
        conn.close()

        print(colorize("\n=== Properties by Status ===", BOLD))
        if status_rows:
            print(fmt_table(["Status", "Count"], [[r["status"] or "N/A", r["cnt"]] for r in status_rows]))
        else:
            print("  No data.")

        print(colorize("\n=== Properties by Category ===", BOLD))
        if category_rows:
            print(fmt_table(["Category", "Count"], [[r["category"], r["cnt"]] for r in category_rows]))
        else:
            print("  No data.")

        print(colorize("\n=== Portfolio Totals ===", BOLD))
        total_xmr = totals["total_xmr"] or 0.0
        total_usd = totals["total_usd"] or 0.0
        print(f"  {'Total XMR:'.ljust(20)}{total_xmr:.4f} XMR")
        print(f"  {'Total USD:'.ljust(20)}${total_usd:,.2f}\n")
    except sqlite3.Error as e:
        print(colorize(f"Database error: {e}", RED))
        sys.exit(1)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="manage_properties.py",
        description="Manage properties in the crypto real estate SQLite database.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # list
    p_list = sub.add_parser("list", help="List all properties")
    p_list.add_argument("--category", help="Filter by category slug")
    p_list.add_argument("--status", choices=["active", "sold", "pending"], help="Filter by status")
    p_list.set_defaults(func=cmd_list)

    # add
    p_add = sub.add_parser("add", help="Add a new property")
    p_add.add_argument("--title", required=True)
    p_add.add_argument("--description", default="")
    p_add.add_argument("--location", default="")
    p_add.add_argument("--price-xmr", type=float, required=True, dest="price_xmr")
    p_add.add_argument("--price-usd", type=float, default=None, dest="price_usd")
    p_add.add_argument("--bedrooms", type=int, default=None)
    p_add.add_argument("--bathrooms", type=int, default=None)
    p_add.add_argument("--sqft", type=int, default=None)
    p_add.add_argument("--image-url", default=None, dest="image_url")
    p_add.add_argument("--category", default=None, help="Category slug")
    p_add.add_argument("--status", choices=["active", "sold", "pending"], default="active")
    p_add.set_defaults(func=cmd_add)

    # remove
    p_remove = sub.add_parser("remove", help="Remove a property by ID")
    p_remove.add_argument("--id", type=int, required=True)
    p_remove.set_defaults(func=cmd_remove)

    # update
    p_update = sub.add_parser("update", help="Update property fields")
    p_update.add_argument("--id", type=int, required=True)
    p_update.add_argument("--title", default=None)
    p_update.add_argument("--description", default=None)
    p_update.add_argument("--location", default=None)
    p_update.add_argument("--price-xmr", type=float, default=None, dest="price_xmr")
    p_update.add_argument("--price-usd", type=float, default=None, dest="price_usd")
    p_update.add_argument("--bedrooms", type=int, default=None)
    p_update.add_argument("--bathrooms", type=int, default=None)
    p_update.add_argument("--sqft", type=int, default=None)
    p_update.add_argument("--image-url", default=None, dest="image_url")
    p_update.add_argument("--category", default=None, help="Category slug")
    p_update.add_argument("--status", choices=["active", "sold", "pending"], default=None)
    p_update.set_defaults(func=cmd_update)

    # update-prices
    p_up = sub.add_parser("update-prices", help="Recalculate USD prices from live XMR rate")
    p_up.set_defaults(func=cmd_update_prices)

    # show
    p_show = sub.add_parser("show", help="Show full details of a property")
    p_show.add_argument("--id", type=int, required=True)
    p_show.set_defaults(func=cmd_show)

    # stats
    p_stats = sub.add_parser("stats", help="Show database statistics")
    p_stats.set_defaults(func=cmd_stats)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
