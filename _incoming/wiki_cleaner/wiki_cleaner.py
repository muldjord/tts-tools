import xml.etree.ElementTree as ET
import re

INPUT_FILE = "dawiki-latest-pages-articles.xml"
OUTPUT_FILE = "clean_paragraphs.txt"

# --- Cleaning functions ---

def remove_templates(text):
    return re.sub(r"\{\{.*?\}\}", "", text, flags=re.DOTALL)

def remove_refs(text):
    text = re.sub(r"<ref.*?>.*?</ref>", "", text, flags=re.DOTALL)
    return re.sub(r"<ref.*?/>", "", text)

def remove_tables(text):
    return re.sub(r"\{\|.*?\|\}", "", text, flags=re.DOTALL)

def remove_files(text):
    return re.sub(r"\[\[(File|Image):.*?\]\]", "", text, flags=re.DOTALL | re.IGNORECASE)

def simplify_links(text):
    # [[link|text]] → text
    text = re.sub(r"\[\[.*?\|(.*?)\]\]", r"\1", text)
    # [[link]] → link
    text = re.sub(r"\[\[(.*?)\]\]", r"\1", text)
    return text

def remove_headings(text):
    return re.sub(r"^=+.*?=+$", "", text, flags=re.MULTILINE)

def remove_lists(text):
    return re.sub(r"^[\*\#;:].*$", "", text, flags=re.MULTILINE)

def remove_html(text):
    return re.sub(r"<.*?>", "", text)

def clean_text(text):
    text = remove_templates(text)
    text = remove_refs(text)
    text = remove_tables(text)
    text = remove_files(text)
    text = simplify_links(text)
    text = remove_headings(text)
    text = remove_lists(text)
    text = remove_html(text)

    # Normalize whitespace
    text = re.sub(r"\n\s*\n", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)

    return text.strip()

# --- XML parsing ---

def extract_text():
    context = ET.iterparse(INPUT_FILE, events=("end",))
    with open(OUTPUT_FILE, "w", encoding="utf-8") as out:

        for event, elem in context:
            if elem.tag.endswith("page"):
                title = elem.find("./{*}title")
                ns = elem.find("./{*}ns")
                revision = elem.find("./{*}revision")
                text_elem = revision.find("./{*}text") if revision is not None else None

                # Only namespace 0 = actual articles
                if ns is not None and ns.text != "0":
                    elem.clear()
                    continue

                if text_elem is not None and text_elem.text:
                    raw_text = text_elem.text

                    # Skip redirects
                    if raw_text.strip().lower().startswith("#redirect"):
                        elem.clear()
                        continue

                    cleaned = clean_text(raw_text)

                    # Keep only "real paragraphs" (long-ish lines)
                    paragraphs = [
                        p.strip()
                        for p in cleaned.split("\n\n")
                        if len(p.strip()) > 200  # tweak threshold as needed
                    ]

                    if paragraphs:
                        out.write("\n\n".join(paragraphs) + "\n\n")

                elem.clear()

if __name__ == "__main__":
    extract_text()
