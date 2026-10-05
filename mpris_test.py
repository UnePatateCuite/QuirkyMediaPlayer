import subprocess
import sys

from media import format_time, get_current_media


try:
    metadata, media = get_current_media()
except FileNotFoundError:
    print("playerctl is not installed or is not on PATH.", file=sys.stderr)
    sys.exit(1)
except subprocess.CalledProcessError as error:
    message = error.stderr.strip() or "No MPRIS player with metadata was found."
    print(f"Could not read player metadata: {message}", file=sys.stderr)
    sys.exit(error.returncode)
except subprocess.TimeoutExpired:
    print("Timed out while reading the current media.", file=sys.stderr)
    sys.exit(1)
except ValueError as error:
    print(f"Could not parse player metadata: {error}", file=sys.stderr)
    sys.exit(1)

print(metadata, end="")
print(
    f"Position: {format_time(media.position_seconds)} / "
    f"{format_time(media.duration_seconds)}"
)