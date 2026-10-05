import subprocess
from dataclasses import dataclass


@dataclass
class MediaInfo:
    title: str
    artist: str
    art_url: str
    track_id: str
    duration_seconds: float
    position_seconds: float


def get_current_media() -> tuple[str, MediaInfo]:
    metadata = subprocess.run(
        ["playerctl", "metadata"],
        check=True,
        capture_output=True,
        text=True,
        timeout=2,
    )
    position = subprocess.run(
        ["playerctl", "position"],
        check=True,
        capture_output=True,
        text=True,
        timeout=2,
    )

    fields: dict[str, str] = {}
    for line in metadata.stdout.splitlines():
        parts = line.split(maxsplit=2)
        if len(parts) == 3:
            fields[parts[1]] = parts[2].strip()

    duration_microseconds = int(fields.get("mpris:length", "0"))
    media = MediaInfo(
        title=fields.get("xesam:title", ""),
        artist=fields.get("xesam:artist", ""),
        art_url=fields.get("mpris:artUrl", ""),
        track_id=fields.get("mpris:trackid", ""),
        duration_seconds=duration_microseconds / 1_000_000,
        position_seconds=float(position.stdout.strip()),
    )
    return metadata.stdout, media


def format_time(seconds: float) -> str:
    total_seconds = max(0, int(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
