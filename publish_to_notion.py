import os
import sys
import yaml
import requests

# Load config
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

VAULT = config["vault_folder"]
TOKEN = config["notion_token"]
DBID = config["notion_database_id"]

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

def parse_markdown(filepath):
    with open(filepath, "r", encoding="utf8") as f:
        content = f.read()

    parts = content.split('---')
    if len(parts) < 3:
        return None, None

    metadata = yaml.safe_load(parts[1])
    body = parts[2].strip()

    # Hapus heading "## Full text OCR" jika ada
    lines = body.splitlines()
    if lines and lines[0].strip().lower().startswith("## full text ocr"):
        lines = lines[1:]
    body = "\n".join(lines).strip()

    return metadata, body

def publish_to_notion(meta, body):
    payload = {
        "parent": {"database_id": DBID},
        "properties": {
            "Judul": {
                "title": [
                    {
                        "text": {
                            "content": meta.get("title", "Untitled")
                        }
                    }
                ]
            },
            "Category": {
                "select": {
                    "name": meta.get("category", "Uncategorized")
                }
            },
            "Tags": {
                "multi_select": [{"name": t} for t in meta.get("tags", [])]
            },
            "Summary": {
                "rich_text": [
                    {
                        "text": {
                            "content": meta.get("summary", "")
                        }
                    }
                ]
            },
            "source": {
                "rich_text": [
                    {
                        "text": {
                            "content": meta.get("source", "")
                        }
                    }
                ]
            },
            "Full text OCR": {
                "rich_text": [
                    {
                        "text": {
                            "content": body[:2000]
                        }
                    }
                ]
            }
        },
        "children": [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": body[:2000]
                            }
                        }
                    ]
                }
            }
        ]
    }

    response = requests.post("https://api.notion.com/v1/pages", headers=HEADERS, json=payload)
    return response.ok, response.text

def main(filepath):
    meta, body = parse_markdown(filepath)
    if not meta:
        print(f"[SKIP] Format tidak valid: {filepath}")
        return

    if not meta.get("publish", False):
        print(f"[SKIP] publish=False: {filepath}")
        return

    print(f"[INFO] Mempublikasikan: {os.path.basename(filepath)}")
    success, response_text = publish_to_notion(meta, body)
    if success:
        print(f"[OK] {os.path.basename(filepath)} berhasil dikirim ke Notion")
        original_name = os.path.basename(filepath).replace(".processing", "")
        dst = os.path.join(VAULT.replace("template", "legal"), original_name)
        os.rename(filepath, dst)

    else:
        print(f"[FAILED] Gagal publish {os.path.basename(filepath)}. Pesan: {response_text}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        main(sys.argv[1])