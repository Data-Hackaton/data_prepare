"""Record every decoded source-frame timestamp using ffprobe, preserving VFR timing."""
import concurrent.futures
import json
import subprocess
from pathlib import Path

DATA = Path('/data')


def probe(item):
    name = item['video']
    result = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'frame=best_effort_timestamp_time', '-of', 'json',
        str(DATA / 'videos' / f'{name}.mov')], check=True, capture_output=True, text=True)
    frames = json.loads(result.stdout)['frames']
    times = [float(frame['best_effort_timestamp_time']) for frame in frames]
    if len(times) != item['frame_count'] or times != sorted(times):
        raise ValueError(f'Invalid frame timestamps: {name}')
    (DATA / 'frame_times' / f'{name}.json').write_text(json.dumps(times), encoding='utf-8')
    print(json.dumps({'video': name, 'frames': len(times), 'last_pts': times[-1]}), flush=True)
    return name, times


if __name__ == '__main__':
    manifest = json.loads((DATA / 'video_frame_manifest.json').read_text(encoding='utf-8'))
    (DATA / 'frame_times').mkdir(exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        results = dict(executor.map(probe, [item for item in manifest['items'] if not item['duplicate_of']]))
    for item in manifest['items']:
        if item['duplicate_of']:
            (DATA / 'frame_times' / f"{item['video']}.json").write_text(json.dumps(results[item['duplicate_of']]), encoding='utf-8')
