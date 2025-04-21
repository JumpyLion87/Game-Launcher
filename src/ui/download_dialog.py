from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QProgressBar, 
    QLabel, QPushButton, QWidget, QHBoxLayout
)
from PySide6.QtCore import Qt, Signal, QObject
from pathlib import Path
import humanize

class DownloadSignals(QObject):
    progress = Signal(float, str, float)  # прогресс, состояние, скорость
    finished = Signal()
    error = Signal(str)

class DownloadDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.signals = DownloadSignals()
        self.setup_ui()
        
        # Подключаем сигналы
        self.signals.progress.connect(self.update_progress)
        self.signals.finished.connect(self.on_finished)
        self.signals.error.connect(self.on_error)
        
    def setup_ui(self):
        self.setWindowTitle("Загрузка клиента")
        self.setFixedSize(400, 200)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Заголовок
        self.status_label = QLabel("Подготовка к загрузке...")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)
        
        # Прогресс бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)
        
        # Информация о загрузке
        info_widget = QWidget()
        info_layout = QHBoxLayout(info_widget)
        
        self.speed_label = QLabel("Скорость: 0 MB/s")
        self.time_label = QLabel("Осталось: --:--")
        
        info_layout.addWidget(self.speed_label)
        info_layout.addWidget(self.time_label)
        
        layout.addWidget(info_widget)
        
        # Кнопки
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        
        self.pause_button = QPushButton("Пауза")
        self.pause_button.clicked.connect(self.toggle_pause)
        
        self.cancel_button = QPushButton("Отмена")
        self.cancel_button.clicked.connect(self.cancel_download)
        
        button_layout.addWidget(self.pause_button)
        button_layout.addWidget(self.cancel_button)
        
        layout.addWidget(button_widget)
        
    def update_progress(self, progress: float, state: str, speed: float):
        """Обновляет информацию о прогрессе"""
        self.progress_bar.setValue(int(progress))
        self.status_label.setText(state)
        
        # Обновляем скорость
        speed_str = humanize.naturalsize(speed, binary=True) + "/s"
        self.speed_label.setText(f"Скорость: {speed_str}")
        
        # Расчет оставшегося времени
        if speed > 0:
            remaining = (100 - progress) / (progress / self.start_time)
            time_str = humanize.naturaltime(remaining)
            self.time_label.setText(f"Осталось: {time_str}")
            
    def toggle_pause(self):
        """Пауза/продолжение загрузки"""
        if self.pause_button.text() == "Пауза":
            self.pause_button.setText("Продолжить")
            # TODO: Реализовать паузу
        else:
            self.pause_button.setText("Пауза")
            # TODO: Реализовать продолжение
            
    def cancel_download(self):
        """Отмена загрузки"""
        # TODO: Реализовать отмену
        self.reject()
        
    def on_finished(self):
        """Обработчик завершения загрузки"""
        self.status_label.setText("Загрузка завершена")
        self.accept()
        
    def on_error(self, message: str):
        """Обработчик ошибки"""
        self.status_label.setText(f"Ошибка: {message}")
        self.reject() 