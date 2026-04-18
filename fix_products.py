#!/usr/bin/env python3
"""
fix_products.py — Product Order Form Fixer & Payment Page Generator
====================================================================

Scans every site directory under /var/www/ (configurable via --root), locates
index.html or index.php, detects EVERY <form action="payment.php"> block that
contains <select> elements named "item", "amount", and "price", extracts the
real product name / quantity tiers / price tiers from the surrounding page
context, and rewrites every form with those accurate values.

It also generates a modern two-phase payment.php for each site:
  Phase 1 — Product grid: one card per product (image, name, desc, price,
             per-product qty input, subtotal, "Order Now" button).
  Phase 2 — Checkout: order summary, region/shipping selectors, broken-down
             total, live crypto prices (CoinGecko), wallet QR, copy button,
             payment status, contact info, and a "Back to Products" button.
URL params payment.php?item=X&price=Y&amount=Z jump straight to Phase 2.

Requirements:
    pip install beautifulsoup4

Usage:
    python fix_products.py [--root /var/www] [--config path/to/config.json]
                           [--dry-run]

Python 3.6+ compatible (uses .format(), no f-strings, no list[dict] hints).
"""

from __future__ import print_function

import argparse
import datetime
import html as html_module
import json
import os
import re
import shutil
import sys
from urllib.parse import quote as url_quote

try:
    from bs4 import BeautifulSoup, NavigableString, Tag
except ImportError:
    sys.exit(
        "ERROR: beautifulsoup4 is not installed.\n"
        "       Run:  pip install beautifulsoup4"
    )

# ---------------------------------------------------------------------------
# DEFAULT CONFIGURATION (used when no config.json is found)
# ---------------------------------------------------------------------------

DEFAULT_CONFIG = {
    "monero_wallet_address": "YOUR_MONERO_WALLET_ADDRESS_HERE",
    "website_root": ".",
    "site_url": "http://yoursite.onion",
    "contact_wickr": "",
    "contact_email": "",
    "continent_pricing": {
        "north_america": 1.0,
        "europe": 1.2,
        "south_america": 1.5,
        "asia": 1.8,
        "africa": 2.0,
        "oceania": 1.6,
        "antarctica": 2.0,
    },
    "shipping_methods": {
        "domestic_standard": 5.00,
        "domestic_express": 10.00,
        "international_standard": 15.00,
        "international_priority": 25.00,
        "international_express": 40.00,
    },
}

# ---------------------------------------------------------------------------
# MODULE-LEVEL CONSTANTS (magic numbers extracted for maintainability)
# ---------------------------------------------------------------------------

# Minimum number of characters for a text block to qualify as a product
# description (shorter strings are likely nav labels or single words).
_MIN_DESCRIPTION_LEN = 20

# Maximum number of characters to retain for a product description snippet.
_MAX_DESCRIPTION_LEN = 200

# Maximum character length of a quantity option string.  Strings longer than
# this are assumed to be descriptive paragraphs rather than tier labels
# (e.g. "100-piece bulk pack" is fine; a full product paragraph is not).
_MAX_QTY_TEXT_LEN = 80

# ---------------------------------------------------------------------------
# REGEX PATTERNS
# ---------------------------------------------------------------------------

# Detects placeholder item/product-name values such as:
#   "Product name", "Product name here", "Product" (alone), "Item" (alone),
#   "Item 1", "your product here", "name here"
# Deliberately does NOT flag "Product 1", "Product 42", etc. — a
# "Product N" heading is treated as a legitimate product name.
_RE_ITEM_PLACEHOLDER = re.compile(
    r"^\s*("
    r"product name(\s+here)?"    # "Product name" / "Product name here"
    r"|product"                  # bare "Product" with nothing after it
    r"|item \d+"                 # "Item 1", "Item 2", …
    r"|item"                     # bare "Item"
    r"|your product(\s+here)?"   # "Your product" / "Your product here"
    r"|name here"                # "Name here"
    r")\s*$",
    re.IGNORECASE,
)

# Detects placeholder quantity values such as:
#   "quantity 1", "qty 2", "amount 3"
_RE_AMOUNT_PLACEHOLDER = re.compile(
    r"^\s*(quantity|qty|amount)\s+\d+\s*$",
    re.IGNORECASE,
)

# Detects placeholder price values such as:
#   "price 1", "€price 2", "$price 3"
_RE_PRICE_PLACEHOLDER = re.compile(
    r"^\s*[€$£₿¥₹]?\s*(price)\s*\d+\s*$",
    re.IGNORECASE,
)

# Recognises a price value anywhere in a string (with optional currency prefix)
_RE_PRICE_VALUE = re.compile(
    r"([€$£₿¥₹]|XMR|BTC|USD|EUR|GBP)?\s*(\d{1,6}(?:[.,]\d{1,3})*)"
    r"(?:\s*([€$£₿¥₹]|XMR|BTC|USD|EUR|GBP))?",
    re.IGNORECASE,
)

# Recognises "quantity — price" pair within a single text line, e.g.
#   "100g - €5.00", "5 units: $12.50", "1 piece for €3"
_RE_QTY_PRICE_LINE = re.compile(
    r"(.+?)\s*[-:–—\/for]+\s*([€$£₿¥₹]?\s*\d+(?:[.,]\d+)*(?:\s*(?:XMR|BTC|USD|EUR|GBP))?)",
    re.IGNORECASE,
)

# Table header text that should be skipped as data rows
_TABLE_HEADER_WORDS = frozenset(
    ["qty", "quantity", "amount", "price", "cost", "total", "unit", "#"]
)

# ---------------------------------------------------------------------------
# UTILITY HELPERS
# ---------------------------------------------------------------------------


def _read_file(path):
    """Read a text file; return empty string on error."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except Exception as exc:
        print("  WARN: Cannot read {}: {}".format(path, exc), file=sys.stderr)
        return ""


def _write_file(path, content, dry_run=False):
    """Write *content* to *path*, unless dry_run is True."""
    if dry_run:
        print("  [dry-run] Would write: {}".format(path))
        return
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
    except Exception as exc:
        print("  ERROR writing {}: {}".format(path, exc), file=sys.stderr)


def _backup_file(path, dry_run=False):
    """Create a timestamped backup of *path* if it exists."""
    if not os.path.isfile(path):
        return
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = "{}.bak.{}".format(path, ts)
    if dry_run:
        print("  [dry-run] Would backup {} -> {}".format(path, backup))
        return
    try:
        shutil.copy2(path, backup)
        print("  Backed up {} -> {}".format(
            os.path.basename(path), os.path.basename(backup)
        ))
    except Exception as exc:
        print("  WARN: Could not backup {}: {}".format(path, exc), file=sys.stderr)


def _load_config(site_dir, global_config_path=None):
    """
    Load configuration for a site.  Search order:
      1. <site_dir>/config.json
      2. global_config_path (if provided)
      3. DEFAULT_CONFIG
    """
    config = dict(DEFAULT_CONFIG)

    # Deep-copy nested dicts so mutations don't affect DEFAULT_CONFIG
    config["continent_pricing"] = dict(DEFAULT_CONFIG["continent_pricing"])
    config["shipping_methods"] = dict(DEFAULT_CONFIG["shipping_methods"])

    candidates = []
    if global_config_path and os.path.isfile(global_config_path):
        candidates.append(global_config_path)
    local = os.path.join(site_dir, "config.json")
    if os.path.isfile(local):
        candidates.append(local)

    for path in candidates:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            config.update(
                {k: v for k, v in data.items() if not k.startswith("_")}
            )
        except Exception as exc:
            print("  WARN: Could not load {}: {}".format(path, exc), file=sys.stderr)

    return config


def _find_index_file(site_dir):
    """Return the path to index.html or index.php in *site_dir*, or None."""
    for name in ("index.html", "index.php"):
        path = os.path.join(site_dir, name)
        if os.path.isfile(path):
            return path
    return None


def _find_sites(root):
    """
    Yield directories directly under *root* that contain an index file.
    Also yield *root* itself if it contains an index file.
    """
    if _find_index_file(root):
        yield root

    try:
        entries = os.listdir(root)
    except Exception as exc:
        print("WARN: Cannot list {}: {}".format(root, exc), file=sys.stderr)
        return

    for entry in sorted(entries):
        full = os.path.join(root, entry)
        if os.path.isdir(full) and not entry.startswith("."):
            if _find_index_file(full):
                yield full

# ---------------------------------------------------------------------------
# PLACEHOLDER DETECTION
# ---------------------------------------------------------------------------


def _is_item_placeholder(text):
    """Return True if the item/product option text looks like a placeholder."""
    return bool(_RE_ITEM_PLACEHOLDER.match(text.strip()))


def _are_amounts_placeholder(options):
    """Return True if ALL amount option texts look like placeholders."""
    if not options:
        return True
    return all(_RE_AMOUNT_PLACEHOLDER.match(opt.strip()) for opt in options)


def _are_prices_placeholder(options):
    """Return True if ALL price option texts look like placeholders."""
    if not options:
        return True
    return all(_RE_PRICE_PLACEHOLDER.match(opt.strip()) for opt in options)


# ---------------------------------------------------------------------------
# CURRENT OPTION EXTRACTION
# ---------------------------------------------------------------------------


def _get_select_options(select_tag):
    """Return a list of option texts from a <select> element."""
    if select_tag is None:
        return []
    return [
        opt.get_text(strip=True)
        for opt in select_tag.find_all("option")
        if opt.get_text(strip=True)
    ]


def _read_form_options(form):
    """
    Read existing option texts from the item/amount/price selects in a form.
    Returns (item_name, amount_options, price_options).
    """
    item_sel = form.find("select", attrs={"name": "item"})
    amount_sel = form.find("select", attrs={"name": "amount"})
    price_sel = form.find("select", attrs={"name": "price"})

    item_opts = _get_select_options(item_sel)
    amount_opts = _get_select_options(amount_sel)
    price_opts = _get_select_options(price_sel)

    # Product name is the first (and typically only) item option
    item_name = item_opts[0] if item_opts else ""
    return item_name, amount_opts, price_opts


# ---------------------------------------------------------------------------
# PRODUCT CONTEXT EXTRACTION — DOM TRAVERSAL
# ---------------------------------------------------------------------------


def _find_product_container(form):
    """
    Walk up the DOM from *form* to find the nearest ancestor element that
    also contains a heading tag (h1-h6) — this is considered the "product
    section" container.  Falls back to the form's direct parent.
    """
    heading_tags = {"h1", "h2", "h3", "h4", "h5", "h6"}
    # Classes that strongly hint at a product/card container
    product_class_hints = ("product", "item", "card", "listing", "entry", "shop")

    node = form.parent
    while node and getattr(node, "name", None) not in (None, "[document]", "html", "body"):
        # Found a container with a heading → use it
        if node.find(heading_tags):
            return node
        # Container with product-like CSS class
        classes = " ".join(node.get("class", [])).lower()
        if any(hint in classes for hint in product_class_hints):
            return node
        node = node.parent

    # Fallback: form's direct parent
    return form.parent


def _heading_precedes_form(heading, form):
    """
    Return True when *heading* appears before *form* in document order.

    Uses `find_next()` with an identity check so traversal stops the moment
    the form element is found — this is more efficient than materialising the
    full `find_all_next()` list and avoids capturing the loop variable inside
    a lambda (the helper function makes the intent explicit).
    """
    return bool(heading.find_next(lambda tag: tag is form))


def _find_product_name_in_container(form, container):
    """
    Find the most relevant product name (heading text) near *form* inside
    *container*.  Prefers headings that precede the form in document order.
    Returns an empty string if nothing suitable is found.

    Uses BeautifulSoup's find_all() with recursive traversal to collect
    headings in DOM order, then uses _heading_precedes_form() to identify
    the closest heading that precedes the form — no string-serialisation.
    """
    heading_tags = ["h1", "h2", "h3", "h4", "h5", "h6"]
    heading_tag_set = set(heading_tags)

    # --- Pass 1: collect all headings inside the container, in DOM order.
    # BeautifulSoup's find_all() yields elements in document (source) order.
    headings_in_container = []
    if container:
        headings_in_container = container.find_all(heading_tags)

    # --- Pass 2: keep only headings that come BEFORE the form.
    best_heading = None
    for h in headings_in_container:
        if _heading_precedes_form(h, form):
            best_heading = h  # iterate all; last winner is closest-before-form

    if best_heading:
        text = best_heading.get_text(strip=True)
        if text:
            return text

    # --- Fallback: if no heading was found strictly before the form, take any
    # heading in the container (e.g. the form is the very first child).
    for tag_name in heading_tags:
        h = container.find(tag_name) if container else None
        if h:
            text = h.get_text(strip=True)
            if text:
                return text

    # --- Last resort: walk backward through preceding siblings and ancestors
    for sibling in form.find_previous_siblings():
        if not isinstance(sibling, Tag):
            continue
        if sibling.name in heading_tag_set:
            text = sibling.get_text(strip=True)
            if text:
                return text
        # Look inside the sibling for a heading
        for tag_name in heading_tags:
            h = sibling.find(tag_name)
            if h:
                text = h.get_text(strip=True)
                if text:
                    return text

    return ""


def _extract_from_table(container):
    """
    Look for a two-column table in *container* where each row holds
    (quantity, price).  Returns (quantities, prices) or ([], []).
    """
    if container is None:
        return [], []

    table = container.find("table")
    if not table:
        return [], []

    quantities = []
    prices = []

    for row in table.find_all("tr"):
        cells = row.find_all(["td", "th"])
        if len(cells) < 2:
            continue
        qty_text = cells[0].get_text(strip=True)
        price_text = cells[-1].get_text(strip=True)

        # Skip header rows
        if qty_text.lower() in _TABLE_HEADER_WORDS:
            continue
        if price_text.lower() in _TABLE_HEADER_WORDS:
            continue
        # Skip empty cells
        if not qty_text or not price_text:
            continue

        quantities.append(qty_text)
        prices.append(price_text)

    return quantities, prices


def _extract_from_list(container):
    """
    Look for list items (<li>) in *container* that match the pattern
    "quantity — price" (separated by -, :, –, —, /, "for", etc.).
    Returns (quantities, prices) or ([], []).
    """
    if container is None:
        return [], []

    quantities = []
    prices = []

    for li in container.find_all("li"):
        text = li.get_text(strip=True)
        m = _RE_QTY_PRICE_LINE.match(text)
        if m:
            quantities.append(m.group(1).strip())
            prices.append(m.group(2).strip())

    return quantities, prices


def _extract_from_text_patterns(container):
    """
    Scan raw text nodes and paragraph text in *container* for qty-price
    patterns.  Returns (quantities, prices) or ([], []).
    """
    if container is None:
        return [], []

    quantities = []
    prices = []

    # Collect all direct-text lines from the container's text
    full_text = container.get_text(separator="\n")
    for line in full_text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = _RE_QTY_PRICE_LINE.match(line)
        if m:
            qty = m.group(1).strip()
            price = m.group(2).strip()
            # Only include if the quantity part doesn't look like a label
            if qty.lower() not in _TABLE_HEADER_WORDS and len(qty) <= _MAX_QTY_TEXT_LEN:
                quantities.append(qty)
                prices.append(price)

    # De-duplicate while preserving order
    seen = set()
    deduped_q = []
    deduped_p = []
    for q, p in zip(quantities, prices):
        key = (q.lower(), p.lower())
        if key not in seen:
            seen.add(key)
            deduped_q.append(q)
            deduped_p.append(p)

    return deduped_q, deduped_p


def _extract_qty_price_pairs(form, container):
    """
    Try all extraction strategies in order and return the first non-empty
    (quantities, prices) pair found.  Strategies:
      1. Two-column table in the product container
      2. <li> items with qty-price patterns
      3. General text-pattern scan of the container
    Returns ([], []) if nothing is found.
    """
    # Strategy 1: table
    qs, ps = _extract_from_table(container)
    if qs and ps:
        return qs, ps

    # Strategy 2: list items
    qs, ps = _extract_from_list(container)
    if qs and ps:
        return qs, ps

    # Strategy 3: text patterns
    qs, ps = _extract_from_text_patterns(container)
    if qs and ps:
        return qs, ps

    return [], []


def _get_product_context(form):
    """
    Main entry-point for per-form context extraction.

    Returns a dict with keys:
      'name'       – product name string (may be empty)
      'quantities' – list of quantity option strings (may be empty)
      'prices'     – list of price option strings, aligned with quantities

    If the existing form options already look real (non-placeholder), they
    are returned as-is so the script is idempotent.
    """
    item_name, amount_opts, price_opts = _read_form_options(form)

    # Check whether each part is already populated with real (non-placeholder) data
    name_is_real = item_name and not _is_item_placeholder(item_name)
    amounts_are_real = not _are_amounts_placeholder(amount_opts)
    prices_are_real = not _are_prices_placeholder(price_opts)

    # If everything looks real, return unchanged (idempotency)
    if name_is_real and amounts_are_real and prices_are_real:
        return {
            "name": item_name,
            "quantities": amount_opts,
            "prices": price_opts,
        }

    # Walk the DOM to find the product container (heading + content + form)
    container = _find_product_container(form)

    # Extract product name from nearest heading
    extracted_name = _find_product_name_in_container(form, container)

    # Extract qty/price pairs
    extracted_qs, extracted_ps = _extract_qty_price_pairs(form, container)

    # Align the qty and price lists (they must have the same length)
    if extracted_qs and extracted_ps:
        min_len = min(len(extracted_qs), len(extracted_ps))
        extracted_qs = extracted_qs[:min_len]
        extracted_ps = extracted_ps[:min_len]

    # Decide final values: prefer extracted when placeholder was detected
    final_name = extracted_name if (not name_is_real and extracted_name) else item_name
    final_qs = extracted_qs if (not amounts_are_real and extracted_qs) else amount_opts
    final_ps = extracted_ps if (not prices_are_real and extracted_ps) else price_opts

    # Last-resort defaults so the form always has at least one option
    if not final_name:
        final_name = "Product"
    if not final_qs:
        final_qs = ["1"]
    if not final_ps:
        final_ps = ["0.00"]

    # Ensure the two lists are the same length (trim longer one)
    min_len = min(len(final_qs), len(final_ps))
    final_qs = final_qs[:min_len]
    final_ps = final_ps[:min_len]

    return {
        "name": final_name,
        "quantities": final_qs,
        "prices": final_ps,
    }


# ---------------------------------------------------------------------------
# FORM REWRITING
# ---------------------------------------------------------------------------


def _build_select(name, options, selected_index=0):
    """
    Build a <select name="..."> HTML string with <option> tags.
    The option at *selected_index* receives selected="selected".
    All option texts are HTML-escaped.
    """
    parts = ['<select name="{name}">'.format(name=name)]
    for idx, opt in enumerate(options):
        escaped = html_module.escape(opt)
        if idx == selected_index:
            parts.append(
                '    <option selected="selected">{}</option>'.format(escaped)
            )
        else:
            parts.append("    <option>{}</option>".format(escaped))
    parts.append("  </select>")
    return "\n  ".join(parts)


def _rewrite_form(form, context):
    """
    In-place rewrite of the item/amount/price <select> elements inside
    *form* using the data in *context* (from _get_product_context).
    Returns True if any change was made.
    """
    name = context["name"]
    quantities = context["quantities"]
    prices = context["prices"]

    changed = False

    # --- item select ---
    item_sel = form.find("select", attrs={"name": "item"})
    if item_sel:
        # Build a fresh <option selected> with the product name
        # Clear existing options, then add the real one
        for opt in item_sel.find_all("option"):
            opt.decompose()
        new_opt = BeautifulSoup(
            '<option selected="selected">{}</option>'.format(
                html_module.escape(name)
            ),
            "html.parser",
        ).find("option")
        item_sel.append(new_opt)
        changed = True

    # --- amount select ---
    amount_sel = form.find("select", attrs={"name": "amount"})
    if amount_sel:
        for opt in amount_sel.find_all("option"):
            opt.decompose()
        for idx, qty in enumerate(quantities):
            tag = BeautifulSoup(
                '<option{sel}>{text}</option>'.format(
                    sel=' selected="selected"' if idx == 0 else "",
                    text=html_module.escape(qty),
                ),
                "html.parser",
            ).find("option")
            amount_sel.append(tag)
        changed = True

    # --- price select ---
    price_sel = form.find("select", attrs={"name": "price"})
    if price_sel:
        for opt in price_sel.find_all("option"):
            opt.decompose()
        for idx, price in enumerate(prices):
            tag = BeautifulSoup(
                '<option{sel}>{text}</option>'.format(
                    sel=' selected="selected"' if idx == 0 else "",
                    text=html_module.escape(price),
                ),
                "html.parser",
            ).find("option")
            price_sel.append(tag)
        changed = True

    return changed


# ---------------------------------------------------------------------------
# INDEX FILE PROCESSING
# ---------------------------------------------------------------------------


def process_index(index_path, dry_run=False):
    """
    Parse *index_path* with BeautifulSoup, find every <form action="payment.php">
    that contains <select> elements named "item", "amount", and "price", extract
    real product data from the surrounding context, and rewrite those select
    elements in-place.

    Returns:
      (new_html, products_list)
        new_html      – the updated HTML string (or original if nothing changed)
        products_list – list of dicts: {name, quantities, prices, image, description}
    """
    content = _read_file(index_path)
    if not content:
        return content, []

    # Use html.parser (stdlib) as the underlying parser for BeautifulSoup.
    # This avoids requiring lxml or html5lib; only beautifulsoup4 needs to be
    # pip-installed (as documented in the script's header).
    soup = BeautifulSoup(content, "html.parser")

    # Find every form whose action attribute is "payment.php" (case-insensitive,
    # ignoring leading/trailing whitespace)
    payment_forms = [
        f for f in soup.find_all("form")
        if (f.get("action") or "").strip().lower() == "payment.php"
    ]

    # Filter: keep only forms that have the required three selects
    target_forms = []
    for form in payment_forms:
        has_item = form.find("select", attrs={"name": "item"}) is not None
        has_amount = form.find("select", attrs={"name": "amount"}) is not None
        has_price = form.find("select", attrs={"name": "price"}) is not None
        if has_item and has_amount and has_price:
            target_forms.append(form)

    print("  Found {} payment form(s) in {}".format(
        len(target_forms), os.path.basename(index_path)
    ))

    products = []
    forms_updated = 0

    for idx, form in enumerate(target_forms):
        # Extract product context from surrounding HTML
        context = _get_product_context(form)

        # Also grab an image and description from the product container for
        # use in the generated payment.php product cards
        container = _find_product_container(form)
        image_src = ""
        description = ""
        if container:
            img = container.find("img")
            if img:
                image_src = img.get("src", "")
            # Use the first paragraph or non-heading, non-form text block as
            # description.  Skip any tag that is itself a <form> or that is
            # nested inside a <form> (e.g. labels, button text) to avoid
            # accidentally using form UI copy as the product description.
            for tag in container.find_all(["p", "div", "span"]):
                if tag.name == "form" or tag.find_parent("form"):
                    continue
                text = tag.get_text(strip=True)
                if text and len(text) > _MIN_DESCRIPTION_LEN:
                    description = text[:_MAX_DESCRIPTION_LEN]
                    break

        products.append(
            {
                "name": context["name"],
                "quantities": context["quantities"],
                "prices": context["prices"],
                "image": image_src,
                "description": description,
            }
        )

        # Rewrite the form in-place (modifies the BeautifulSoup tree)
        changed = _rewrite_form(form, context)
        if changed:
            forms_updated += 1
            print("  [{}/{}] Updated form: {}".format(
                idx + 1, len(target_forms), context["name"]
            ))

    if forms_updated == 0:
        print("  No forms needed updating.")
        return content, products

    # Serialise the modified soup back to a string.
    # BeautifulSoup preserves all non-form markup exactly.
    new_html = str(soup)
    return new_html, products


# ---------------------------------------------------------------------------
# PAYMENT.PHP GENERATION
# ---------------------------------------------------------------------------


def _continent_options_html(config):
    """Generate <option> tags for the continent selector."""
    parts = []
    for continent, mult in config.get("continent_pricing", {}).items():
        label = continent.replace("_", " ").title()
        parts.append(
            '<option value="{v}">{l} (&times;{m})</option>'.format(
                v=continent, l=label, m=mult
            )
        )
    return "\n        ".join(parts)


def _shipping_options_html(config):
    """Generate <option> tags for the shipping method selector."""
    labels = {
        "domestic_standard": "Domestic Standard",
        "domestic_express": "Domestic Express",
        "international_standard": "International Standard",
        "international_priority": "International Priority",
        "international_express": "International Express",
    }
    parts = []
    for method, cost in config.get("shipping_methods", {}).items():
        label = labels.get(method, method.replace("_", " ").title())
        parts.append(
            '<option value="{v}">{l} (+${c:.2f})</option>'.format(
                v=method, l=label, c=cost
            )
        )
    return "\n        ".join(parts)


def _product_card_html(product, card_index):
    """
    Build the HTML for one product card shown in Phase 1 (product grid).
    *card_index* is used for unique IDs when there are multiple products.
    """
    name_esc = html_module.escape(product["name"])
    desc_esc = html_module.escape(product["description"]) if product["description"] else ""
    image_src = product.get("image", "")
    quantities = product.get("quantities", ["1"])
    prices = product.get("prices", ["0.00"])

    # Build the quantity/price <option> tags for this card's selects
    qty_opts = []
    for idx, qty in enumerate(quantities):
        qty_opts.append(
            '<option value="{v}"{s}>{t}</option>'.format(
                v=html_module.escape(qty),
                s=' selected="selected"' if idx == 0 else "",
                t=html_module.escape(qty),
            )
        )

    price_opts = []
    for idx, price in enumerate(prices):
        price_opts.append(
            '<option value="{v}"{s}>{t}</option>'.format(
                v=html_module.escape(price),
                s=' selected="selected"' if idx == 0 else "",
                t=html_module.escape(price),
            )
        )

    # Use the first price as the display price
    display_price = prices[0] if prices else "0.00"

    img_html = (
        '<img class="product-img" src="{src}" alt="{alt}" '
        'onerror="this.style.display=\'none\'">'.format(
            src=html_module.escape(image_src),
            alt=name_esc,
        )
        if image_src
        else ""
    )

    card = (
        '<div class="product-card" id="card-{ci}">\n'
        "  {img}\n"
        '  <div class="card-body">\n'
        '    <h3 class="card-title">{name}</h3>\n'
        '    <p class="card-desc">{desc}</p>\n'
        '    <p class="card-price">{price}</p>\n'
        '    <div class="card-controls">\n'
        '      <label>Quantity:</label>\n'
        '      <select class="qty-select" id="qty-{ci}" onchange="updateSubtotal({ci})">\n'
        "        {qty_opts}\n"
        "      </select>\n"
        '      <select class="price-select" id="price-{ci}" onchange="updateSubtotal({ci})">\n'
        "        {price_opts}\n"
        "      </select>\n"
        "    </div>\n"
        '    <p class="card-subtotal">Subtotal: '
        '<span id="subtotal-{ci}">{price}</span></p>\n'
        '    <button class="btn-order" onclick="orderNow({ci}, {idx_json})">'
        "Order Now</button>\n"
        "  </div>\n"
        "</div>"
    ).format(
        ci=card_index,
        img=img_html,
        name=name_esc,
        desc=desc_esc,
        price=html_module.escape(display_price),
        qty_opts="\n        ".join(qty_opts),
        price_opts="\n        ".join(price_opts),
        idx_json=card_index,
    )
    return card


def _payment_page_css():
    """
    Return the inline CSS for the self-contained payment.php page.

    Extracted into its own function to keep generate_payment_php() readable.
    The CSS uses CSS custom properties (variables) for the dark-theme colour
    palette so colours can be adjusted in one place.

    Section breakdown:
      • CSS variables (root)  — colour palette, spacing, shadows
      • Reset / base          — box-sizing, body, links, headings
      • Layout                — .container, header
      • Product grid          — .products-grid, .product-card, .card-*
      • Buttons               — .btn-order, .btn-back
      • Checkout view         — #checkout-view, .step, table, form controls
      • Crypto / wallet       — .price-grid, .wallet-box, .copy-btn
      • Status / contact      — .status-box, .contact-cards, @keyframes pulse
    """
    return (
        # --- CSS variables (dark theme colour palette) ---
        "    :root{"
        "--bg:#0d0d0d;--bg2:#1a1a1a;--bg3:#222;--border:#333;"
        "--text:#e8e8e8;--muted:#a0a0a0;--accent:#ff6b35;--accent2:#ff8855;"
        "--radius:8px;--shadow:0 4px 20px rgba(0,0,0,.5);}\n"
        # --- Reset / base ---
        "    *{box-sizing:border-box;margin:0;padding:0;}\n"
        "    body{background:var(--bg);color:var(--text);"
        "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;"
        "line-height:1.6;}\n"
        "    a{color:var(--accent);text-decoration:none;}\n"
        "    a:hover{color:var(--accent2);text-decoration:underline;}\n"
        "    h1,h2,h3{color:var(--text);font-weight:600;line-height:1.3;"
        "margin-bottom:.6em;}\n"
        "    p{color:var(--muted);margin-bottom:.8em;}\n"
        # --- Layout ---
        "    .container{max-width:1200px;margin:0 auto;padding:0 20px;}\n"
        "    header{background:var(--bg2);border-bottom:1px solid var(--border);"
        "padding:1rem 0;margin-bottom:2rem;}\n"
        "    header h1{color:var(--accent);font-size:1.4rem;}\n"
        # --- Product grid ---
        "    .products-grid{display:grid;"
        "grid-template-columns:repeat(auto-fill,minmax(260px,1fr));"
        "gap:1.5rem;padding:1rem 0;}\n"
        "    .product-card{background:var(--bg3);border:1px solid var(--border);"
        "border-radius:var(--radius);overflow:hidden;display:flex;"
        "flex-direction:column;transition:border .2s,transform .2s,box-shadow .2s;}\n"
        "    .product-card:hover{border-color:var(--accent);"
        "transform:translateY(-3px);box-shadow:var(--shadow);}\n"
        "    .product-img{width:100%;aspect-ratio:4/3;object-fit:cover;"
        "background:var(--bg2);}\n"
        "    .card-body{padding:1rem;display:flex;flex-direction:column;flex:1;}\n"
        "    .card-title{font-size:1rem;font-weight:600;color:var(--text);"
        "margin-bottom:.4rem;}\n"
        "    .card-desc{font-size:.85rem;color:var(--muted);flex:1;"
        "margin-bottom:.8rem;}\n"
        "    .card-price{font-size:1.1rem;font-weight:700;color:var(--accent);"
        "margin-bottom:.6rem;}\n"
        "    .card-controls{display:flex;gap:.5rem;flex-wrap:wrap;"
        "margin-bottom:.6rem;align-items:center;}\n"
        "    .card-controls label{font-size:.8rem;color:var(--muted);}\n"
        "    .card-controls select{background:var(--bg2);border:1px solid var(--border);"
        "color:var(--text);padding:4px 8px;border-radius:4px;font-size:.85rem;}\n"
        "    .card-subtotal{font-size:.9rem;color:var(--muted);margin-bottom:.8rem;}\n"
        # --- Buttons ---
        "    .btn-order{display:block;text-align:center;background:var(--accent);"
        "color:#fff;padding:10px;border-radius:4px;font-weight:600;font-size:.9rem;"
        "border:none;cursor:pointer;transition:background .2s,transform .2s;}\n"
        "    .btn-order:hover{background:var(--accent2);transform:translateY(-1px);}\n"
        "    .btn-back{background:var(--bg2);color:var(--text);"
        "border:1px solid var(--border);padding:10px 20px;"
        "border-radius:4px;cursor:pointer;font-size:.9rem;"
        "margin-bottom:1rem;transition:background .2s;}\n"
        "    .btn-back:hover{background:var(--bg3);}\n"
        # --- Checkout view ---
        "    #checkout-view{display:none;}\n"
        "    .step{background:var(--bg3);border:1px solid var(--border);"
        "border-radius:var(--radius);padding:1.5rem;margin-bottom:1.5rem;}\n"
        "    table{width:100%;border-collapse:collapse;margin-bottom:1rem;}\n"
        "    th,td{padding:10px 14px;text-align:left;"
        "border-bottom:1px solid var(--border);font-size:.9rem;}\n"
        "    th{background:var(--bg2);color:var(--muted);font-weight:600;"
        "text-transform:uppercase;font-size:.75rem;}\n"
        "    select,input{width:100%;background:var(--bg2);"
        "border:1px solid var(--border);color:var(--text);padding:10px 14px;"
        "border-radius:4px;font-size:.95rem;outline:none;}\n"
        "    select:focus,input:focus{border-color:var(--accent);}\n"
        "    .form-group{margin-bottom:1rem;}\n"
        "    label{display:block;margin-bottom:5px;font-size:.9rem;"
        "color:var(--muted);}\n"
        "    .total-box{padding:1rem;background:var(--bg2);"
        "border-radius:4px;margin-top:.5rem;}\n"
        "    .accent{color:var(--accent);}\n"
        # --- Crypto / wallet ---
        "    .price-grid{display:grid;"
        "grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1rem;}\n"
        "    .price-box{background:var(--bg2);padding:1rem;"
        "border-radius:4px;text-align:center;}\n"
        "    .price-box .currency{font-size:.8rem;color:var(--muted);"
        "margin-bottom:.3rem;}\n"
        "    .price-box .amount{font-size:1.4rem;font-weight:700;"
        "color:var(--accent);}\n"
        "    .wallet-box{background:var(--bg2);padding:1rem;"
        "border-radius:4px;word-break:break-all;font-size:.85rem;"
        "color:var(--text);margin-bottom:1rem;}\n"
        "    .copy-btn{margin-top:.5rem;background:var(--accent);color:#fff;"
        "border:none;padding:6px 16px;border-radius:4px;cursor:pointer;"
        "font-size:.85rem;}\n"
        # --- Status / contact ---
        "    .status-box{display:flex;align-items:center;gap:1rem;padding:1rem;"
        "background:var(--bg2);border-radius:4px;}\n"
        "    .status-dot{width:12px;height:12px;border-radius:50%;"
        "background:#ff9800;flex-shrink:0;animation:pulse 2s infinite;}\n"
        "    @keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}\n"
        "    .contact-cards{display:flex;gap:1rem;flex-wrap:wrap;margin-top:1rem;}\n"
        "    .contact-card{background:var(--bg2);padding:1rem;"
        "border-radius:4px;flex:1;min-width:160px;}\n"
    )


def generate_payment_php(products, config, dry_run=False):
    """
    Build and return the complete payment.php HTML/JS string.

    The page has two phases:
      Phase 1 — #products-view: a card grid for every product.
      Phase 2 — #checkout-view: order summary, shipping, crypto prices, wallet.

    URL params ?item=X&price=Y&amount=Z skip Phase 1 and go straight to Phase 2.
    """
    wallet = config.get("monero_wallet_address", "")
    wickr = html_module.escape(config.get("contact_wickr", ""))
    email = html_module.escape(config.get("contact_email", ""))
    continent_js = json.dumps(config.get("continent_pricing", {}))
    shipping_js = json.dumps(config.get("shipping_methods", {}))
    wallet_esc = html_module.escape(wallet)
    # json.dumps produces a properly escaped JS string literal (handles
    # backslashes, quotes, control characters and Unicode safely).
    wallet_js_literal = json.dumps(wallet)   # e.g. "\"abc...xyz\""

    # Use url_quote (urllib.parse.quote) for proper percent-encoding of the
    # wallet address in the QR code API URL — html_module.escape() is not
    # appropriate for URL query parameters.
    qr_url = (
        "https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={}".format(
            url_quote(wallet, safe="")
        )
    )

    # --- Build product cards for Phase 1 ---
    card_html_parts = []
    for i, product in enumerate(products):
        card_html_parts.append(_product_card_html(product, i))
    cards_html = "\n".join(card_html_parts) if card_html_parts else (
        "<p>No products found.</p>"
    )

    # --- Embed products as JSON for use by the JS price-sync logic ---
    products_json = json.dumps(
        [
            {
                "name": p["name"],
                "quantities": p["quantities"],
                "prices": p["prices"],
                "image": p.get("image", ""),
                "description": p.get("description", ""),
            }
            for p in products
        ],
        ensure_ascii=False,
    )

    # --- Contact cards ---
    wickr_card = (
        '<div class="contact-card">'
        "<strong>Wickr</strong><br>"
        '<span class="accent">{}</span>'
        "</div>".format(wickr)
        if wickr
        else ""
    )
    email_card = (
        '<div class="contact-card">'
        "<strong>Email</strong><br>"
        '<a href="mailto:{e}">{e}</a>'
        "</div>".format(e=email)
        if email
        else ""
    )

    continent_opts = _continent_options_html(config)
    shipping_opts = _shipping_options_html(config)
    inline_css = _payment_page_css()

    page = (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="UTF-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        '  <meta name="robots" content="noindex, nofollow">\n'
        "  <title>Shop &amp; Checkout</title>\n"
        "  <style>\n"
        "{css}"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        "  <header>\n"
        "    <div class='container'>\n"
        "      <h1>&#x1F6D2; Shop</h1>\n"
        "    </div>\n"
        "  </header>\n"
        "  <main class='container'>\n"
        "\n"
        "    <!-- ===================== PHASE 1: PRODUCT GRID ===================== -->\n"
        "    <div id='products-view'>\n"
        "      <h2>Our Products</h2>\n"
        "      <div class='products-grid'>\n"
        "        {cards}\n"
        "      </div>\n"
        "    </div>\n"
        "\n"
        "    <!-- ===================== PHASE 2: CHECKOUT ===================== -->\n"
        "    <div id='checkout-view'>\n"
        "      <button class='btn-back' onclick='backToProducts()'"
        ">&larr; Back to Products</button>\n"
        "\n"
        "      <!-- Order summary -->\n"
        "      <div class='step'>\n"
        "        <h2>Order Summary</h2>\n"
        "        <table>\n"
        "          <thead><tr><th>Product</th><th>Qty</th>"
        "<th>Unit Price</th><th>Subtotal</th></tr></thead>\n"
        "          <tbody><tr>\n"
        "            <td id='co-item'>&#8212;</td>\n"
        "            <td id='co-qty'>&#8212;</td>\n"
        "            <td id='co-price'>&#8212;</td>\n"
        "            <td id='co-subtotal'>&#8212;</td>\n"
        "          </tr></tbody>\n"
        "        </table>\n"
        "      </div>\n"
        "\n"
        "      <!-- Shipping region -->\n"
        "      <div class='step'>\n"
        "        <h2>Shipping Region</h2>\n"
        "        <div class='form-group'>\n"
        "          <label for='continent-sel'>Your Region</label>\n"
        "          <select id='continent-sel' onchange='recalcTotal()'>\n"
        "            {continent_opts}\n"
        "          </select>\n"
        "        </div>\n"
        "        <div class='form-group'>\n"
        "          <label for='shipping-sel'>Shipping Method</label>\n"
        "          <select id='shipping-sel' onchange='recalcTotal()'>\n"
        "            {shipping_opts}\n"
        "          </select>\n"
        "        </div>\n"
        "        <div class='total-box'>\n"
        "          <strong>Order Total: </strong>\n"
        "          <span id='order-total' class='accent'"
        " style='font-size:1.2rem;font-weight:700'>&#8212;</span>\n"
        "        </div>\n"
        "      </div>\n"
        "\n"
        "      <!-- Live crypto prices -->\n"
        "      <div class='step'>\n"
        "        <h2>Live Crypto Prices</h2>\n"
        "        <div class='price-grid'>\n"
        "          <div class='price-box'>\n"
        "            <div class='currency'>XMR (Monero)</div>\n"
        "            <div class='amount' id='xmr-amount'>&#8230;</div>\n"
        "            <div style='font-size:.8rem;color:var(--muted)'"
        " id='xmr-usd'>Loading&hellip;</div>\n"
        "          </div>\n"
        "          <div class='price-box'>\n"
        "            <div class='currency'>BTC (Bitcoin)</div>\n"
        "            <div class='amount' id='btc-amount'>&#8230;</div>\n"
        "            <div style='font-size:.8rem;color:var(--muted)'"
        " id='btc-usd'>Loading&hellip;</div>\n"
        "          </div>\n"
        "        </div>\n"
        "        <p style='font-size:.75rem;margin-top:.5rem'>"
        "Live prices from CoinGecko. Refresh to update.</p>\n"
        "      </div>\n"
        "\n"
        "      <!-- Wallet / QR -->\n"
        "      <div class='step'>\n"
        "        <h2>Pay with Monero (XMR)</h2>\n"
        "        <p>Send the exact XMR amount shown above to this address:</p>\n"
        "        <div style='text-align:center;margin-bottom:1rem'>\n"
        "          <img src='{qr}' alt='Monero QR Code'"
        " width='200' height='200'"
        " style='border:6px solid #fff;border-radius:4px'>\n"
        "        </div>\n"
        "        <div class='wallet-box' id='wallet-addr'>{wallet_esc}</div>\n"
        "        <button class='copy-btn' onclick='copyWallet()'>Copy Address</button>\n"
        "      </div>\n"
        "\n"
        "      <!-- Payment status -->\n"
        "      <div class='step'>\n"
        "        <h2>Payment Status</h2>\n"
        "        <div class='status-box'>\n"
        "          <div class='status-dot'></div>\n"
        "          <div><strong>Waiting for Deposit</strong><br>\n"
        "            <span style='font-size:.85rem;color:var(--muted)'>"
        "Send payment to the address above. Once confirmed, contact us "
        "with your TXID and shipping details.</span>\n"
        "          </div>\n"
        "        </div>\n"
        "      </div>\n"
        "\n"
        "      <!-- Contact info -->\n"
        "      <div class='step'>\n"
        "        <h2>After Payment</h2>\n"
        "        <p>Once you have sent your payment, contact us with your "
        "transaction ID (TXID) and shipping address.</p>\n"
        "        <div class='contact-cards'>\n"
        "          {wickr_card}\n"
        "          {email_card}\n"
        "        </div>\n"
        "      </div>\n"
        "    </div><!-- /checkout-view -->\n"
        "\n"
        "  </main>\n"
        "\n"
        "  <script>\n"
        "  // All product data extracted from the site index page\n"
        "  var PRODUCTS    = {products_json};\n"
        "  var CONTINENTS  = {continent_js};\n"
        "  var SHIPPING    = {shipping_js};\n"
        "  var _xmrPrice   = null;\n"
        "  var _btcPrice   = null;\n"
        "  var _orderItem  = '';\n"
        "  var _orderQty   = 1;\n"
        "  var _orderPrice = 0;\n"
        "\n"
        "  // ---------- Phase switching ----------\n"
        "  function showCheckout(item, qty, price) {{\n"
        "    _orderItem  = item;\n"
        "    _orderQty   = parseInt(qty, 10) || 1;\n"
        "    _orderPrice = parseFloat(price) || 0;\n"
        "    document.getElementById('co-item').textContent     = item;\n"
        "    document.getElementById('co-qty').textContent      = qty;\n"
        "    document.getElementById('co-price').textContent    = price;\n"
        "    document.getElementById('co-subtotal').textContent =\n"
        "      '$' + (_orderQty * _orderPrice).toFixed(2);\n"
        "    recalcTotal();\n"
        "    document.getElementById('products-view').style.display  = 'none';\n"
        "    document.getElementById('checkout-view').style.display  = 'block';\n"
        "    window.scrollTo(0, 0);\n"
        "  }}\n"
        "\n"
        "  function backToProducts() {{\n"
        "    document.getElementById('checkout-view').style.display  = 'none';\n"
        "    document.getElementById('products-view').style.display  = 'block';\n"
        "    // Clear URL params without reloading\n"
        "    history.replaceState(null, '', window.location.pathname);\n"
        "  }}\n"
        "\n"
        "  // ---------- Price string to number helper ----------\n"
        "  // Handles both decimal conventions:\n"
        "  //   English:  '€1,234.56' (comma=thousands, dot=decimal)\n"
        "  //   European: '€1.234,56' (dot=thousands,  comma=decimal)\n"
        "  // Heuristic: if the string ends with a comma + 1-2 digits,\n"
        "  // treat that comma as the decimal separator.\n"
        "  function priceToNum(str) {{\n"
        "    var s = ('' + str).replace(/[^0-9.,]/g, '');\n"
        "    if (!s) return 0;\n"
        "    if (/,\\d{{1,2}}$/.test(s)) {{\n"
        "      s = s.replace(/\\./g, '').replace(',', '.');\n"
        "    }} else {{\n"
        "      s = s.replace(/,/g, '');\n"
        "    }}\n"
        "    return parseFloat(s) || 0;\n"
        "  }}\n"
        "\n"
        "  // ---------- Product card helpers ----------\n"
        "  function updateSubtotal(ci) {{\n"
        "    var qtySel   = document.getElementById('qty-'   + ci);\n"
        "    var priceSel = document.getElementById('price-' + ci);\n"
        "    var subEl    = document.getElementById('subtotal-' + ci);\n"
        "    if (!qtySel || !priceSel || !subEl) return;\n"
        "    var p = priceToNum(priceSel.value);\n"
        "    var q = priceToNum(qtySel.value) || 1;\n"
        "    subEl.textContent = '$' + (q * p).toFixed(2);\n"
        "  }}\n"
        "\n"
        "  function orderNow(ci) {{\n"
        "    var qtySel   = document.getElementById('qty-'   + ci);\n"
        "    var priceSel = document.getElementById('price-' + ci);\n"
        "    if (!qtySel || !priceSel) return;\n"
        "    var item  = PRODUCTS[ci] ? PRODUCTS[ci].name : 'Order';\n"
        "    var qty   = qtySel.options[qtySel.selectedIndex].text;\n"
        "    var price = priceSel.options[priceSel.selectedIndex].text;\n"
        "    // Update URL for bookmarking / direct-link support\n"
        "    history.replaceState(null, '',\n"
        "      '?item=' + encodeURIComponent(item)\n"
        "      + '&price=' + encodeURIComponent(price)\n"
        "      + '&amount=' + encodeURIComponent(qty));\n"
        "    showCheckout(item, qty, price);\n"
        "  }}\n"
        "\n"
        "  // ---------- Total recalculation ----------\n"
        "  function recalcTotal() {{\n"
        "    var cSel = document.getElementById('continent-sel');\n"
        "    var sSel = document.getElementById('shipping-sel');\n"
        "    var mult = cSel ? (CONTINENTS[cSel.value] || 1.0) : 1.0;\n"
        "    var ship = sSel ? (SHIPPING[sSel.value]   || 0)   : 0;\n"
        "    var numP = priceToNum(_orderPrice);\n"
        "    var total = (numP * mult * _orderQty) + ship;\n"
        "    var el = document.getElementById('order-total');\n"
        "    if (el) el.textContent = '$' + total.toFixed(2);\n"
        "    if (_xmrPrice) updateCryptoAmounts(total);\n"
        "  }}\n"
        "\n"
        "  // ---------- Live crypto prices ----------\n"
        "  function updateCryptoAmounts(usdTotal) {{\n"
        "    if (!usdTotal || !_xmrPrice) return;\n"
        "    document.getElementById('xmr-amount').textContent =\n"
        "      (usdTotal / _xmrPrice).toFixed(6) + ' XMR';\n"
        "    document.getElementById('xmr-usd').textContent =\n"
        "      '1 XMR ≈ $' + _xmrPrice.toFixed(2);\n"
        "    if (_btcPrice) {{\n"
        "      document.getElementById('btc-amount').textContent =\n"
        "        (usdTotal / _btcPrice).toFixed(8) + ' BTC';\n"
        "      document.getElementById('btc-usd').textContent =\n"
        "        '1 BTC ≈ $' + _btcPrice.toLocaleString();\n"
        "    }}\n"
        "  }}\n"
        "\n"
        "  fetch('https://api.coingecko.com/api/v3/simple/price'"
        "+ '?ids=monero,bitcoin&vs_currencies=usd')\n"
        "    .then(function(r){{ return r.json(); }})\n"
        "    .then(function(d){{\n"
        "      _xmrPrice = d.monero  ? d.monero.usd  : null;\n"
        "      _btcPrice = d.bitcoin ? d.bitcoin.usd : null;\n"
        "      // If checkout is visible, refresh totals with live prices\n"
        "      if (document.getElementById('checkout-view').style.display !== 'none') {{\n"
        "        var rawTotal = (document.getElementById('order-total').textContent || '')\n"
        "          .replace(/[^0-9.]/g, '');\n"
        "        var tot = parseFloat(rawTotal) || 0;\n"
        "        if (tot > 0) updateCryptoAmounts(tot);\n"
        "      }}\n"
        "    }})\n"
        "    .catch(function(){{\n"
        "      document.getElementById('xmr-usd').textContent = 'Price fetch failed.';\n"
        "    }});\n"
        "\n"
        "  // ---------- Copy wallet address ----------\n"
        "  // wallet_addr is serialised by Python's json.dumps() so it is a\n"
        "  // properly escaped JavaScript string literal (safe against injection).\n"
        "  function copyWallet() {{\n"
        # wallet_js_literal is produced by json.dumps(wallet) in Python which
        # handles all special characters (backslashes, quotes, Unicode, control
        # codes) so it is safe to interpolate directly as a JS string literal.
        "    var addr = {wallet_js_literal};\n"
        "    if (navigator.clipboard) {{\n"
        "      navigator.clipboard.writeText(addr).then(function(){{\n"
        "        var btn = document.querySelector('.copy-btn');\n"
        "        if (btn) {{ btn.textContent = 'Copied!'; }}\n"
        "        setTimeout(function(){{\n"
        "          var b = document.querySelector('.copy-btn');\n"
        "          if (b) b.textContent = 'Copy Address';\n"
        "        }}, 2000);\n"
        "      }});\n"
        "    }} else {{\n"
        "      var ta = document.createElement('textarea');\n"
        "      ta.value = addr;\n"
        "      document.body.appendChild(ta);\n"
        "      ta.select();\n"
        "      document.execCommand('copy');\n"
        "      document.body.removeChild(ta);\n"
        "    }}\n"
        "  }}\n"
        "\n"
        "  // ---------- URL param handler (direct-link / bookmark support) ----------\n"
        "  (function(){{\n"
        "    var p = new URLSearchParams(window.location.search);\n"
        "    var item  = p.get('item');\n"
        "    var price = p.get('price');\n"
        "    var qty   = p.get('amount') || p.get('qty') || '1';\n"
        "    if (item && price) {{\n"
        "      showCheckout(item, qty, price);\n"
        "    }}\n"
        "    // Initialise card subtotals\n"
        "    for (var i = 0; i < PRODUCTS.length; i++) {{\n"
        "      updateSubtotal(i);\n"
        "    }}\n"
        "  }})();\n"
        "  </script>\n"
        "</body>\n"
        "</html>"
    ).format(
        cards=cards_html,
        css=inline_css,
        continent_opts=continent_opts,
        shipping_opts=shipping_opts,
        qr=qr_url,
        wallet_esc=wallet_esc,
        wallet_js_literal=wallet_js_literal,
        wickr_card=wickr_card,
        email_card=email_card,
        products_json=products_json,
        continent_js=continent_js,
        shipping_js=shipping_js,
    )

    return page


# ---------------------------------------------------------------------------
# SITE PROCESSING
# ---------------------------------------------------------------------------


def process_site(site_dir, global_config_path=None, dry_run=False):
    """
    Process a single site directory:
      1. Load config.
      2. Find and parse the index file.
      3. Fix every payment.php form (updates the index file in-place).
      4. Back up existing payment.php.
      5. Write the new payment.php.
    """
    print("\n[Site] {}".format(site_dir))

    config = _load_config(site_dir, global_config_path)

    index_path = _find_index_file(site_dir)
    if not index_path:
        print("  SKIP: No index.html or index.php found.")
        return

    print("  Index: {}".format(os.path.basename(index_path)))

    # --- Fix all product order forms in the index file ---
    new_html, products = process_index(index_path, dry_run=dry_run)

    # Write the updated index file only when something changed
    original = _read_file(index_path)
    if new_html != original:
        print("  Writing updated index file.")
        _write_file(index_path, new_html, dry_run=dry_run)
    else:
        print("  Index file unchanged.")

    if not products:
        print("  No products extracted; skipping payment.php generation.")
        return

    print("  Extracted {} product(s): {}".format(
        len(products),
        ", ".join(p["name"] for p in products[:5])
        + (" …" if len(products) > 5 else ""),
    ))

    # --- Back up and regenerate payment.php ---
    payment_path = os.path.join(site_dir, "payment.php")
    _backup_file(payment_path, dry_run=dry_run)

    payment_page = generate_payment_php(products, config, dry_run=dry_run)
    print("  Writing payment.php ({} products).".format(len(products)))
    _write_file(payment_path, payment_page, dry_run=dry_run)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser(
        description=(
            "fix_products.py — Fix every payment.php order form in a website "
            "so it shows real product data, and regenerate payment.php with a "
            "modern two-phase checkout UI."
        )
    )
    ap.add_argument(
        "--root",
        default="/var/www",
        help="Root directory to scan for site directories (default: /var/www).",
    )
    ap.add_argument(
        "--config",
        default=None,
        metavar="PATH",
        help="Path to a global config.json used as a fallback for all sites.",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing any files.",
    )
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        sys.exit("ERROR: Root directory does not exist: {}".format(root))

    print("fix_products.py")
    print("  Root  : {}".format(root))
    print("  Config: {}".format(args.config or "(per-site only)"))
    print("  Mode  : {}".format("DRY-RUN" if args.dry_run else "LIVE"))
    print()

    sites = list(_find_sites(root))
    if not sites:
        print("No sites with an index file found under {}.".format(root))
        return

    print("Found {} site(s).".format(len(sites)))

    for site_dir in sites:
        process_site(
            site_dir,
            global_config_path=args.config,
            dry_run=args.dry_run,
        )

    print("\nDone.")


if __name__ == "__main__":
    main()
