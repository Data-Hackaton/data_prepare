"""Read source frame counts with ffprobe; run in the data-prepare container."""
import csv
import json
import subprocess
from pathlib import Path

root = Path("/data")
rows = list(csv.DictReader((root / "labels.csv").open(encoding="utf-8")))
result = []
for row in rows:
    file = root / "videos" / (row["video"] + ".mov")
    command = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
               "stream=nb_frames,width,height,r_frame_rate,avg_frame_rate,duration", "-of", "json", str(file)]
    stream = json.loads(subprocess.check_output(command))["streams"][0]
    if not str(stream.get("nb_frames", "")).isdigit():
        command = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
                   "-show_entries", "stream=nb_read_frames", "-of", "json", str(file)]
        stream["nb_frames"] = json.loads(subprocess.check_output(command))["streams"][0]["nb_read_frames"]
    result.append({**row, **stream, "frame_count": int(stream["nb_frames"]), "frame_step": 1})
report = {"videos": len(result), "frames": sum(v["frame_count"] for v in result),
          "unique_frames": sum(v["frame_count"] for v in result if not v["duplicate_of"]),
          "selection": "all original video frames, step=1", "items": result}
(root / "video_frame_manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({k: v for k, v in report.items() if k != "items"}), flush=True)
