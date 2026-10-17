"""Download only data files for a pinned, checksum-verified ONNX detector."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

REPO = "onnx-community/grounding-dino-tiny-ONNX"
DEST = Path(__file__).resolve().parent / "models" / "grounding-dino-tiny"
FILES = ["config.json", "preprocessor_config.json", "tokenizer.json", "tokenizer_config.json", "onnx/model_fp16.onnx"]


def main():
    with urlopen(f"https://huggingface.co/api/models/{REPO}?blobs=true", timeout=60) as response:
        metadata = json.load(response)
    revision = metadata["sha"]
    DEST.mkdir(parents=True, exist_ok=True)
    (DEST / "download_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    entries = {entry["rfilename"]: entry for entry in metadata["siblings"]}

    def download(name):
        entry = entries[name]
        target = DEST / name
        target.parent.mkdir(parents=True, exist_ok=True)
        expected = entry.get("lfs", {}).get("sha256")
        if target.exists() and (expected and hashlib.sha256(target.read_bytes()).hexdigest() == expected):
            return {"file": name, "status": "verified_existing"}
        temporary = target.with_suffix(target.suffix + ".part")
        url = f"https://huggingface.co/{REPO}/resolve/{revision}/{name}"
        digest = hashlib.sha256()
        size = 0
        with urlopen(url, timeout=90) as response, temporary.open("wb") as handle:
            while chunk := response.read(1024 * 1024):
                handle.write(chunk)
                digest.update(chunk)
                size += len(chunk)
                if name.endswith(".onnx") and size % (32 * 1024 * 1024) == 0:
                    print(json.dumps({"file": name, "downloaded_mb": size // (1024 * 1024)}), flush=True)
        if expected and digest.hexdigest() != expected:
            raise ValueError(f"Checksum mismatch: {name}")
        if entry.get("size") and size != entry["size"]:
            raise ValueError(f"Size mismatch: {name}")
        temporary.replace(target)
        return {"file": name, "bytes": size, "sha256": digest.hexdigest(), "status": "downloaded"}

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(download, FILES))
    report = {"repository": REPO, "revision": revision, "files": results}
    (DEST / "verified.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
