import subprocess
import sys

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from media import MediaInfo, format_time, get_current_media


class MediaWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Media Player")
        self.setMinimumWidth(320)
        self._current_track: tuple[str, str] | None = None

        self.artwork = QLabel("Thumbnail unavailable")
        self.artwork.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.artwork.setFixedSize(320, 180)

        self.title = QLabel("Waiting for media...")
        self.title.setWordWrap(True)
        self.artist = QLabel()
        self.position = QLabel()
        self.status = QLabel()

        layout = QVBoxLayout(self)
        layout.addWidget(self.artwork, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title)
        layout.addWidget(self.artist)
        layout.addWidget(self.position)
        layout.addWidget(self.status)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_media)
        self.timer.start(1000)
        self.refresh_media()

    def refresh_media(self) -> None:
        try:
            _, media = get_current_media()
        except FileNotFoundError:
            self.clear_media()
            self.status.setText("playerctl is not installed or is not on PATH.")
            return
        except subprocess.CalledProcessError:
            self.clear_media()
            return
        except subprocess.TimeoutExpired:
            self.status.setText("Timed out while reading the current media.")
            return
        except ValueError as error:
            self.status.setText(f"Could not read media metadata: {error}")
            return

        self.show_media(media)

    def show_media(self, media: MediaInfo) -> None:
        self.title.setText(media.title or "Unknown title")
        self.artist.setText(media.artist)
        self.position.setText(
            f"{format_time(media.position_seconds)} / "
            f"{format_time(media.duration_seconds)}"
        )
        self.status.clear()

        track = (media.track_id, media.art_url)
        if track != self._current_track:
            self._current_track = track
            local_path = QUrl(media.art_url).toLocalFile()
            pixmap = QPixmap(local_path) if local_path else QPixmap()
            if pixmap.isNull():
                self.artwork.setPixmap(QPixmap())
                self.artwork.setText("Thumbnail unavailable")
            else:
                self.artwork.setText("")
                self.artwork.setPixmap(
                    pixmap.scaled(
                        self.artwork.size(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )

    def clear_media(self) -> None:
        self.title.setText("No media player found.")
        self.artist.clear()
        self.position.clear()
        self.status.clear()
        self.artwork.setPixmap(QPixmap())
        self.artwork.setText("Thumbnail unavailable")
        self._current_track = None


app = QApplication(sys.argv)
window = MediaWindow()
window.show()
sys.exit(app.exec())
