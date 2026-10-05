import subprocess
import sys

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from media import MediaInfo, control_player, format_time, get_current_media


class MediaWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Media Player")
        self.setMinimumWidth(320)
        self._current_track: tuple[str, str] | None = None
        self._current_player = ""

        self.artwork = QLabel("Thumbnail unavailable")
        self.artwork.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.artwork.setFixedSize(320, 180)

        self.title = QLabel("Waiting for media...")
        self.title.setWordWrap(True)
        self.artist = QLabel()
        self.position = QLabel()
        self.status = QLabel()
        self.play_button = QPushButton("Play")
        self.pause_button = QPushButton("Pause")
        self.play_button.setEnabled(False)
        self.pause_button.setEnabled(False)
        self.play_button.clicked.connect(lambda: self.send_command("play"))
        self.pause_button.clicked.connect(lambda: self.send_command("pause"))
        controls = QHBoxLayout()
        controls.addWidget(self.play_button)
        controls.addWidget(self.pause_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.artwork, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title)
        layout.addWidget(self.artist)
        layout.addWidget(self.position)
        layout.addLayout(controls)
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
        self._current_player = media.player
        self.title.setText(media.title or "Unknown title")
        self.artist.setText(media.artist)
        self.position.setText(
            f"{format_time(media.position_seconds)} / "
            f"{format_time(media.duration_seconds)}"
        )
        self.play_button.setEnabled(True)
        self.pause_button.setEnabled(True)
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

    def send_command(self, command: str) -> None:
        if not self._current_player:
            return

        try:
            control_player(self._current_player, command)
        except FileNotFoundError:
            self.status.setText("playerctl is not installed or is not on PATH.")
        except subprocess.CalledProcessError as error:
            message = error.stderr.strip() or f"Could not {command} the current player."
            self.status.setText(message)
        except subprocess.TimeoutExpired:
            self.status.setText(f"Timed out while trying to {command} the current player.")

    def clear_media(self) -> None:
        self._current_player = ""
        self.title.setText("No media player found.")
        self.artist.clear()
        self.position.clear()
        self.status.clear()
        self.artwork.setPixmap(QPixmap())
        self.artwork.setText("Thumbnail unavailable")
        self._current_track = None
        self.play_button.setEnabled(False)
        self.pause_button.setEnabled(False)


app = QApplication(sys.argv)
window = MediaWindow()
window.show()
sys.exit(app.exec())
