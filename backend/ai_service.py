from collections import defaultdict
from io import BytesIO
import json
import re
import unicodedata

import numpy as np
import requests
from PIL import Image, ImageOps

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "llama3.2"
def _prepare_quote_image(image_bytes: bytes) -> np.ndarray:
    """Decode an uploaded image into the BGR array expected by RapidOCR."""
    try:
        with Image.open(BytesIO(image_bytes)) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.thumbnail((1800, 1800), Image.Resampling.LANCZOS)
            return np.asarray(image)[:, :, ::-1].copy()
    except (OSError, ValueError) as error:
        raise ValueError("The image could not be read. Upload a clear PNG or JPG image.") from error


def _normalize_ocr_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def _group_ocr_rows(result):
    raw_texts = getattr(result, "txts", None)
    raw_boxes = getattr(result, "boxes", None)
    texts = list(raw_texts) if raw_texts is not None else []
    boxes = list(raw_boxes) if raw_boxes is not None else []
    if not texts:
        return []

    entries = []
    for index, text in enumerate(texts):
        if not str(text).strip():
            continue
        if index < len(boxes) and boxes[index] is not None:
            box = np.asarray(boxes[index], dtype=float)
            top, bottom = float(box[:, 1].min()), float(box[:, 1].max())
            left = float(box[:, 0].min())
            center_y, height = (top + bottom) / 2, max(1.0, bottom - top)
        else:
            center_y, height, left = float(index * 20), 16.0, float(index)
        entries.append((center_y, height, left, str(text).strip()))

    if not entries:
        return []
    entries.sort(key=lambda entry: (entry[0], entry[2]))
    typical_height = float(np.median([entry[1] for entry in entries]))
    row_tolerance = max(8.0, typical_height * 0.7)
    rows = []
    for center_y, _height, _left, text in entries:
        if not rows or center_y - rows[-1]["center"] > row_tolerance:
            rows.append({"center": center_y, "entries": [(center_y, _left, text)]})
        else:
            row = rows[-1]
            row["entries"].append((center_y, _left, text))
            row["center"] = sum(item[0] for item in row["entries"]) / len(row["entries"])
    return [
        " ".join(item[2] for item in sorted(row["entries"], key=lambda item: item[1]))
        for row in rows
    ]


def _find_catalog_matches(row_text: str, available_products):
    normalized_row = _normalize_ocr_text(row_text)
    row_tokens = list(re.finditer(r"[a-z0-9]+", normalized_row))
    matches = []
    for product in available_products:
        normalized_product = _normalize_ocr_text(product)
        if not normalized_product:
            continue
        phrase = re.search(rf"(?<![a-z0-9]){re.escape(normalized_product)}(?![a-z0-9])", normalized_row)
        if phrase:
            matches.append((str(product), phrase.start(), phrase.end()))
            continue

        product_tokens = normalized_product.split()
        if not product_tokens:
            continue
        # Allow small OCR mistakes while avoiding broad one-word matches.
        if len(product_tokens) == 1 and len(product_tokens[0]) < 5:
            continue
        best = None
        from difflib import SequenceMatcher
        for start in range(len(row_tokens)):
            for count in range(max(1, len(product_tokens) - 1), len(product_tokens) + 2):
                end = start + count
                if end > len(row_tokens):
                    continue
                candidate = " ".join(token.group() for token in row_tokens[start:end])
                score = SequenceMatcher(None, normalized_product, candidate).ratio()
                if score >= 0.88 and (best is None or score > best[0]):
                    best = (score, row_tokens[start].start(), row_tokens[end - 1].end())
        if best:
            matches.append((str(product), best[1], best[2]))
    # Prefer the most specific catalogue name if names overlap.
    matches.sort(key=lambda item: item[2] - item[1], reverse=True)
    selected = []
    for match in matches:
        if any(match[1] < other[2] and other[1] < match[2] for other in selected):
            continue
        selected.append(match)
    return sorted(selected, key=lambda item: item[1])


def extract_quote_items_from_image(image_bytes: bytes, mime_type: str, available_products, ocr_engine=None):
    """Read product names and quantities using fast local OCR, without a vision LLM call."""
    if not image_bytes:
        raise ValueError("Choose an image before extracting products.")
    if len(image_bytes) > 10 * 1024 * 1024:
        raise ValueError("The image is too large. Please use an image under 10 MB.")
    if mime_type not in {"image/png", "image/jpeg"}:
        raise ValueError("Upload a PNG or JPG image.")
    if not available_products:
        raise ValueError("The product catalogue is empty.")

    if ocr_engine is None:
        try:
            from rapidocr import RapidOCR
        except ImportError as error:
            raise RuntimeError(
                "Image OCR is not installed. Install it with: "
                ".venv\\Scripts\\python.exe -m pip install -r requirements.txt"
            ) from error
        ocr_engine = RapidOCR()

    result = ocr_engine(_prepare_quote_image(image_bytes))
    rows = _group_ocr_rows(result)
    quantities_by_product = defaultdict(int)
    for row_text in rows:
        matches = _find_catalog_matches(row_text, available_products)
        if not matches:
            continue
        normalized_row = _normalize_ocr_text(row_text)
        number_matches = list(re.finditer(r"\d+", normalized_row))
        for product, start, end in matches:
            product_numbers = {
                int(value) for value in re.findall(r"\d+", _normalize_ocr_text(product))
            }
            candidates = [
                number for number in number_matches
                if not (number.start() >= start and number.end() <= end)
                and int(number.group()) not in product_numbers
                and int(number.group()) > 0
            ]
            quantity = min(candidates, key=lambda number: min(abs(number.start() - end), abs(start - number.end()))).group() if candidates else "1"
            quantities_by_product[product] += int(quantity)

    if not quantities_by_product:
        raise ValueError(
            "No catalogue products were found in the image. Use a sharp, upright image with "
            "the product names and quantities clearly visible."
        )
    return [
        {"product_name": name, "quantity": quantity}
        for name, quantity in quantities_by_product.items()
    ]


def extract_quote_information(message: str, available_products=None):
    if not message or not message.strip():
        raise ValueError("Customer message cannot be empty.")

    products = available_products or []
    product_catalog = (
        "\n".join(f"- {product}" for product in products)
        if products else "No product catalog was provided."
    )
    system_prompt = f"""
You are an accurate product extraction assistant.

Your task is to extract ONLY the products explicitly requested
by the customer.

Available products in the database:
{product_catalog}

STRICT RULES:
1. Understand French and English messages.
2. Extract the customer's name if explicitly mentioned.
3. Extract every product explicitly requested.
4. Extract the exact requested quantity.
5. Never invent products.
6. Never add products that the customer did not request.
7. Never replace one product with another.
8. Never automatically return Laptop or Monitor.
9. Do not use previous conversations or assumptions.
10. Product names must match the database catalog exactly whenever a catalog is provided.
11. If a requested product does not exist in the catalog, preserve its original name.
12. If quantity is not specified, use 1.
13. Each product must appear exactly once.
14. If the customer requests FC 27 and GTA 6, return FC 27 and GTA 6 only.
15. Return valid JSON only.

Required JSON format:
{{
    "customer_name": null,
    "items": [
        {{"product_name": "Exact product name", "quantity": 1}}
    ]
}}
"""
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message},
            ],
        },
        timeout=120,
    )
    response.raise_for_status()
    content = response.json()["message"]["content"]
    data = json.loads(content)
    if not isinstance(data, dict):
        raise ValueError("Invalid AI response.")
    if not isinstance(data.get("items"), list):
        raise ValueError("Invalid AI response: items must be a list.")

    cleaned_items = []
    for item in data["items"]:
        if not isinstance(item, dict):
            continue
        product_name = item.get("product_name")
        quantity = item.get("quantity", 1)
        if not isinstance(product_name, str) or not product_name.strip():
            continue
        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            continue
        if quantity > 0:
            cleaned_items.append({"product_name": product_name.strip(), "quantity": quantity})

    data["items"] = cleaned_items
    if not isinstance(data.get("customer_name"), (str, type(None))):
        data["customer_name"] = None
    return data
