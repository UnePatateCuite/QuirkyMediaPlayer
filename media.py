import subprocess
from dataclasses import dataclass


@dataclass
class MediaInfo:
    player: str
    title: str
    artist: str
    art_url: str
    track_id: str
    duration_seconds: float
    position_seconds: float


def get_current_media() -> tuple[str, MediaInfo]:
    players = subprocess.run(
        ["playerctl", "-l"],
        check=True,
        capture_output=True,
        text=True,
        timeout=2,
    )
    available_media: list[tuple[str, str, MediaInfo]] = []

    for player in players.stdout.splitlines():
        try:
            status = subprocess.run(
                ["playerctl", f"--player={player}", "status"],
                check=True,
                capture_output=True,
                text=True,
                timeout=2,
            ).stdout.strip()
            metadata = subprocess.run(
                ["playerctl", f"--player={player}", "metadata"],
                check=True,
                capture_output=True,
                text=True,
                timeout=2,
            )
            position = subprocess.run(
                ["playerctl", f"--player={player}", "position"],
                check=True,
                capture_output=True,
                text=True,
                timeout=2,
            )
        except subprocess.CalledProcessError:
            continue

        fields: dict[str, str] = {}
        for line in metadata.stdout.splitlines():
            parts = line.split(maxsplit=2)
            if len(parts) == 3:
                fields[parts[1]] = parts[2].strip()

        duration_microseconds = int(fields.get("mpris:length", "0"))
        media = MediaInfo(
            player=player,
            title=fields.get("xesam:title", ""),
            artist=fields.get("xesam:artist", ""),
            art_url=fields.get("mpris:artUrl", ""),
            track_id=fields.get("mpris:trackid", ""),
            duration_seconds=duration_microseconds / 1_000_000,
            position_seconds=float(position.stdout.strip()),
        )
        available_media.append((status, metadata.stdout, media))

    if not available_media:
        raise subprocess.CalledProcessError(
            1, ["playerctl", "-l"], stderr="No MPRIS player with metadata was found."
        )

    return next(
        (
            (metadata, media)
            for status, metadata, media in available_media
            if status == "Playing"
        ),
        (available_media[0][1], available_media[0][2]),
    )


def control_player(player: str, command: str) -> None:
    if command not in {"play", "pause"}:
        raise ValueError(f"Unsupported playback command: {command}")

    subprocess.run(
        ["playerctl", f"--player={player}", command],
        check=True,
        capture_output=True,
        text=True,
        timeout=2,
    )


def format_time(seconds: float) -> str:
    total_seconds = max(0, int(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
