# scripts/export_openapi.py
import json
from pathlib import Path

from main import app  # main.py가 루트에 있으니 이게 제일 단순함


def main():
    # docs 폴더가 루트에 있다고 가정
    out_path = Path("docs") / "openapi.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    schema = app.openapi()

    out_path.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[OK] wrote: {out_path}")


if __name__ == "__main__":
    main()
