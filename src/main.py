import sys
from pathlib import Path
import threading
import asyncio

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.ui.main_window import MainWindow
from PySide6.QtWidgets import QApplication

def run_async_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Явно устанавливаем стиль Fusion
    window = MainWindow()
    
    # Запускаем event loop в отдельном потоке
    thread = threading.Thread(target=run_async_loop, args=(window.loop,), daemon=True)
    thread.start()
    
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 