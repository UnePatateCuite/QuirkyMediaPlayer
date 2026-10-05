import subprocess
import sys

from PySide6.QtCore import QSignalBlocker, Qt, QTimer, QUrl
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from media import (
    MediaInfo,
    control_player,
    format_time,
    get_current_media,
    seek_player,
)


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
        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 0)
        self.seek_slider.setTracking(True)
        self.seek_slider.setEnabled(False)
        self.seek_slider.sliderMoved.connect(self.show_seek_preview)
        self.seek_slider.sliderReleased.connect(self.seek_to_slider)
        self.seek_slider.valueChanged.connect(self.on_seek_value_changed)

        self.seek_timer = QTimer(self)
        self.seek_timer.setSingleShot(True)
        self.seek_timer.setInterval(300)
        self.seek_timer.timeout.connect(self.seek_to_slider)

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
        layout.addWidget(self.seek_slider)
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
        duration = max(0, int(media.duration_seconds))
        self.seek_slider.setEnabled(duration > 0)
        with QSignalBlocker(self.seek_slider):
            self.seek_slider.setMaximum(duration)
            if not self.seek_slider.isSliderDown() and not self.seek_timer.isActive():
                self.seek_slider.setValue(
                    min(int(media.position_seconds), duration)
                )
        if not self.seek_slider.isSliderDown():
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

    def show_seek_preview(self, position_seconds: int) -> None:
        self.position.setText(
            f"{format_time(position_seconds)} / "
            f"{format_time(self.seek_slider.maximum())}"
        )

    def on_seek_value_changed(self, position_seconds: int) -> None:
        if not self.seek_slider.isSliderDown():
            self.show_seek_preview(position_seconds)
            self.seek_timer.start()

    def seek_to_slider(self) -> None:
        if not self._current_player or not self.seek_slider.isEnabled():
            return

        self.seek_timer.stop()
        try:
            seek_player(self._current_player, self.seek_slider.value())
        except FileNotFoundError:
            self.status.setText("playerctl is not installed or is not on PATH.")
        except subprocess.CalledProcessError as error:
            message = error.stderr.strip() or "Could not seek in the current media."
            self.status.setText(message)
        except subprocess.TimeoutExpired:
            self.status.setText("Timed out while seeking in the current media.")

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
        self.seek_timer.stop()
        self.seek_slider.setEnabled(False)
        with QSignalBlocker(self.seek_slider):
            self.seek_slider.setRange(0, 0)
        self.artwork.setPixmap(QPixmap())
        self.artwork.setText("Thumbnail unavailable")
        self._current_track = None
        self.play_button.setEnabled(False)
        self.pause_button.setEnabled(False)


app = QApplication(sys.argv)
window = MediaWindow()
window.show()
sys.exit(app.exec())
