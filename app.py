import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QSignalBlocker, QPoint, QRectF, Qt, QTimer, QUrl
from PySide6.QtGui import (
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPixmap,
    QResizeEvent,
)
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


class DragArea(QWidget):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._drag_offset: QPoint | None = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.window().pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)


class MediaWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Media Player")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(850, 479)
        self._current_track: tuple[str, str] | None = None
        self._current_player = ""
        self._artwork_pixmap = QPixmap()

        frame_path = Path(__file__).resolve().parent / "assets" / "media_player_background.png"
        self._frame_pixmap = QPixmap(str(frame_path))
        if self._frame_pixmap.isNull():
            raise FileNotFoundError(f"Could not load player background: {frame_path}")

        self.background = QLabel(self)
        self.background.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.background.setStyleSheet("background: transparent;")
        self.background.lower()

        self.drag_area = DragArea(self)
        drag_layout = QHBoxLayout(self.drag_area)
        drag_layout.setContentsMargins(0, 4, 8, 0)
        drag_layout.addStretch(1)
        self.close_button = QPushButton("×")
        self.close_button.setFixedSize(34, 34)
        self.close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_button.setStyleSheet(
            """
            QPushButton {
                color: white;
                background: rgba(90, 40, 65, 150);
                border: 1px solid rgba(255, 255, 255, 150);
                border-radius: 17px;
                font-size: 22px;
            }
            QPushButton:hover { background: rgba(90, 40, 65, 220); }
            """
        )
        self.close_button.clicked.connect(self.close)
        drag_layout.addWidget(self.close_button)

        self.artwork = QLabel(self)
        self.artwork.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.artwork.setStyleSheet("background: transparent; color: #ffffff;")

        self.details = QWidget(self)
        self.details.setStyleSheet("background: transparent;")
        details_layout = QVBoxLayout(self.details)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(12)

        self.title = QLabel("Waiting for media...")
        self.title.setWordWrap(True)
        self.title.setStyleSheet(
            "font-size: 22px; font-weight: bold; color: white; background: transparent;"
        )
        self.artist = QLabel()
        self.artist.setStyleSheet(
            "font-size: 16px; color: white; background: transparent;"
        )
        self.position = QLabel()
        self.position.setStyleSheet(
            "font-size: 14px; color: white; background: transparent;"
        )
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color: white; background: transparent;")
        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setStyleSheet(
            """
            QSlider::groove:horizontal {
                height: 5px;
                background: rgba(255, 255, 255, 100);
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: white;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                width: 14px;
                margin: -5px 0;
                border-radius: 7px;
                background: white;
            }
            """
        )
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
        details_layout.addWidget(self.title)
        details_layout.addWidget(self.artist)
        details_layout.addStretch(1)
        details_layout.addWidget(self.position)
        details_layout.addWidget(self.seek_slider)
        details_layout.addLayout(controls)
        details_layout.addWidget(self.status)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_media)
        self.timer.start(1000)
        self.resize(1022, 576)
        self.update_frame_layout()
        self.refresh_media()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.update_frame_layout()

    def update_frame_layout(self) -> None:
        width = self.width()
        height = self.height()
        self.drag_area.setGeometry(40, 0, max(0, width - 80), 48)
        self.drag_area.raise_()
        self.background.setGeometry(0, 0, width, height)
        self.background.lower()
        self.background.setPixmap(
            self._frame_pixmap.scaled(
                width,
                height,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        self.artwork.setGeometry(
            round(width * 0.0396),
            round(height * 0.0885),
            round(width * 0.4666),
            round(height * 0.8086),
        )
        self.details.setGeometry(
            round(width * 0.535),
            round(height * 0.17),
            round(width * 0.425),
            round(height * 0.66),
        )
        self.update_artwork()

    def update_artwork(self) -> None:
        if self._artwork_pixmap.isNull():
            return

        size = self.artwork.size()
        scaled = self._artwork_pixmap.scaled(
            size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        left = (scaled.width() - size.width()) // 2
        top = (scaled.height() - size.height()) // 2
        cropped = scaled.copy(left, top, size.width(), size.height())
        rounded = QPixmap(size)
        rounded.fill(Qt.GlobalColor.transparent)

        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        radius = min(size.width(), size.height()) * 0.055
        clip_path = QPainterPath()
        clip_path.addRoundedRect(QRectF(0, 0, size.width(), size.height()), radius, radius)
        painter.setClipPath(clip_path)
        painter.drawPixmap(0, 0, cropped)
        painter.end()
        self.artwork.setPixmap(rounded)

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
            self._artwork_pixmap = QPixmap(local_path) if local_path else QPixmap()
            if self._artwork_pixmap.isNull():
                self.artwork.setPixmap(QPixmap())
                self.artwork.setText("Thumbnail unavailable")
            else:
                self.artwork.setText("")
                self.update_artwork()

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
        self._artwork_pixmap = QPixmap()
        self.artwork.setPixmap(QPixmap())
        self.artwork.setText("Thumbnail unavailable")
        self._current_track = None
        self.play_button.setEnabled(False)
        self.pause_button.setEnabled(False)


app = QApplication(sys.argv)
window = MediaWindow()
window.show()
sys.exit(app.exec())
