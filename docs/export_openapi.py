# scripts/export_openapi.py
import json
from pathlib import Path

from main import app  # main.py가 루트에 있으니 이게 제일 단순함


OUT = Path("docs/openapi.json")  # Mintlify가 읽을 위치로 맞춰

def main():
    spec = app.openapi()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()