"""Mirror approved brand/video files into the self-contained GitHub Pages site.

No model calls, private workbench data, repository commits or publication.
README and site reuse the same approved media; hashes detect mirror drift.
"""
from pathlib import Path
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[1]


def main():
    mappings = {
        "assets/identity/mascot.png": "site/assets/identity/mascot.png",
        "docs/assets/readme/product-demo.mp4": "site/assets/media/product-demo.mp4",
        "docs/assets/readme/product-demo-poster.png": "site/assets/media/product-demo-poster.png",
    }
    records = []
    for source, destination in mappings.items():
        src, dst = ROOT / source, ROOT / destination
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        digest = hashlib.sha256(src.read_bytes()).hexdigest()
        assert digest == hashlib.sha256(dst.read_bytes()).hexdigest()
        records.append({"source": source, "destination": destination, "sha256": digest, "bytes": dst.stat().st_size})
    (ROOT / "site/assets/media/sources.json").write_text(
        json.dumps({"assets": records, "music": "House Two — Grigoriy Nuzhny, Mixkit track 694", "music_license": "https://mixkit.co/license/modal/musicFree/", "credits": "https://github.com/zhouke0929/wechat-visual-director/blob/main/assets/identity/PROVENANCE.txt", "selected_audio": "v18 A, BGM reduced by 2dB", "note": "Music licensed only as part of the promotional video, not as standalone music or under the project code license."}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"synced": len(records), "assets": records}, ensure_ascii=False))


if __name__ == "__main__":
    main()
