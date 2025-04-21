import json
from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QProgressBar, QFrame, 
    QGridLayout, QLineEdit, QDialog, QTabWidget,
    QCheckBox, QFileDialog, QComboBox, QMenu, QMessageBox, QGroupBox,
    QSystemTrayIcon
)
from PySide6.QtCore import Qt, QSize, QTimer, QPoint
from PySide6.QtGui import (
    QPixmap, QPalette, QBrush, QFont, QIcon, 
    QPainter, QLinearGradient, QColor, QAction
)
from src.api.server_api import ServerAPI
from src.api.auth_api import AuthResult
import asyncio
import sys
from src.ui.login_dialog import LoginDialog
from src.utils.game_launcher import GameLauncher
import platform
import humanize

# Константы
CARD_SPACING = 15
CARD_MARGINS = (15, 10, 15, 10)
DEFAULT_ICON_SIZE = QSize(20, 20)
PLAY_BUTTON_SIZE = QSize(200, 50)
SETTINGS_BUTTON_SIZE = QSize(40, 40)
PROGRESS_BAR_HEIGHT = 4

# Цвета
COLOR_PRIMARY = "#FFB100"
COLOR_SUCCESS = "#2ecc71"
COLOR_BACKGROUND = "rgba(0, 0, 0, 0.7)"

# Размеры
MAIN_NEWS_IMAGE_HEIGHT = 200
SMALL_NEWS_IMAGE_HEIGHT = 100
SETTINGS_DIALOG_WIDTH = 600

class Card(QFrame):
    """Базовый класс для карточек"""
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        if title:
            title_label = QLabel(title)
            title_label.setProperty("class", "title")
            self.layout.addWidget(title_label)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Кэшируем часто используемые виджеты
        self._cached_widgets = {}
        
        # Загружаем стили
        self._load_styles()
        
        # Создаем event loop для асинхронных операций
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        # Инициализация API клиента
        self.server_api = ServerAPI()
        
        # Таймер для обновления статуса
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_server_status)
        self.status_timer.start(30000)  # Обновляем каждые 30 секунд
        
        # Настройки
        self.settings_file = Path("config/settings.json")
        self.default_settings = {
            "game": {
                "path": "",
                "realmlist": "logon.server.com",
                "launch_options": ""
            },
            "graphics": {
                "resolution": "1920x1080",
                "quality": "Высокое",
                "windowed": False
            },
            "auth": {
                "username": None,
                "account_id": None,
                "auto_login": False
            }
        }
        
        self.settings = self.load_settings()
        self.game_launcher = GameLauncher(self.settings, self)
        self.current_user = None
        
        # Подключаем сигналы GameLauncher
        self.game_launcher.signals.client_missing.connect(self.show_download_buttons)
        self.game_launcher.signals.download_progress.connect(self.update_download_progress)
        self.game_launcher.signals.download_error.connect(self.on_download_error)
        
        # Проверяем сохраненные данные авторизации
        auth = self.settings.get('auth', {})
        if auth.get('username') and auth.get('account_id'):
            self.current_user = AuthResult(
                success=True,
                message="Сессия восстановлена",
                username=auth['username'],
                account_id=auth['account_id']
            )
            # Обновляем данные в GameLauncher
            self.game_launcher.set_account_info(
                auth['username'],
                auth['account_id']
            )

        # Создаем UI
        self.setWindowTitle("WoW 3.3.5 Launcher")
        self.setMinimumSize(1200, 800)
        
        # Фоновое изображение
        self.background = QPixmap("assets/images/background.jpg")
        self.updateBackground()
        
        # Главный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Главный layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(40, 30, 40, 30)
        
        # Компоненты
        main_layout.addWidget(self.create_header())
        main_layout.addWidget(self.create_status_cards())
        main_layout.addWidget(self.create_content())
        
        # Создаем футер
        footer = QWidget()
        footer.setObjectName("footer")
        self.footer_layout = QHBoxLayout(footer)
        self.footer_layout.setContentsMargins(20, 10, 20, 10)
        self.footer_layout.setSpacing(10)
        self.footer_layout.setAlignment(Qt.AlignLeft)  # Выравнивание влево
        
        # Настраиваем кнопку игры
        self.setup_game_button()
        
        # Добавляем растягивающийся спейсер после кнопки
        self.footer_layout.addStretch()
        
        main_layout.addWidget(footer)
        
        # Первоначальное получение статуса
        self.update_server_status()
        
        # Обновляем UI если есть сохраненная сессия
        if self.current_user:
            self.update_ui_after_login()

        # Инициализация трей-иконки
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon("assets/images/wow-logo.png"))
        self.tray_icon.setToolTip("WoW 3.3.5 Launcher")  # Подсказка при наведении
        
        # Создаем меню для трей-иконки
        self.tray_menu = QMenu()
        
        # Добавляем пункты меню
        play_action = QAction("Играть", self)
        play_action.triggered.connect(self.launch_game_from_tray)
        self.tray_menu.addAction(play_action)
        
        restore_action = QAction("Восстановить", self)
        restore_action.triggered.connect(self.show_normal)
        self.tray_menu.addAction(restore_action)
        
        exit_action = QAction("Выйти", self)
        exit_action.triggered.connect(self.close)
        self.tray_menu.addAction(exit_action)
        
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.show()  # Показываем иконку сразу

    def _load_styles(self):
        """Загрузка стилей"""
        try:
            with open("assets/styles/main.qss", "r") as f:
                self.setStyleSheet(f.read())
        except Exception as e:
            self.logger.error(f"Error loading styles: {e}")

    def _get_widget(self, name: str):
        """Получение кэшированного виджета"""
        if name not in self._cached_widgets:
            self._cached_widgets[name] = self.findChild(QWidget, name)
        return self._cached_widgets[name]

    def create_content(self):
        content = Card("НОВОСТИ")
        content.setMinimumHeight(400)
        
        # Создаем grid layout для новостей
        grid = QGridLayout()
        grid.setSpacing(15)
        content.layout.addLayout(grid)
        
        # Главная новость (большая карточка слева)
        main_news = self.create_news_card(
            "Открытие нового сезона",
            "Встречайте новый сезон арены с обновленной системой рейтинга и наградами!",
            "main_news.jpg",
            is_main=True
        )
        grid.addWidget(main_news, 0, 0, 2, 2)  # Занимает 2x2 ячейки
        
        # Дополнительные новости (справа)
        news_items = [
            {
                "title": "Обновление 3.3.5a",
                "text": "Список изменений и улучшений в новой версии...",
                "image": "update_news.jpg",
                "tag": "ОБНОВЛЕНИЕ"
            },
            {
                "title": "Турнир на арене",
                "text": "Регистрация на турнир начинается через...",
                "image": "arena_news.jpg",
                "tag": "СОБЫТИЕ"
            },
            {
                "title": "Новые предметы",
                "text": "В магазине появились новые предметы...",
                "image": "items_news.jpg",
                "tag": "МАГАЗИН"
            }
        ]
        
        for i, news in enumerate(news_items):
            card = self.create_news_card(
                news["title"],
                news["text"],
                news["image"],
                tag=news["tag"]
            )
            grid.addWidget(card, i, 2)  # Добавляем справа
        
        return content

    def create_header(self):
        """Создает шапку с логотипом и навигацией"""
        header = QWidget()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Логотип
        logo = QLabel()
        logo_pixmap = QPixmap("assets/images/wow-logo.png")
        logo.setPixmap(logo_pixmap.scaled(150, 50, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        layout.addWidget(logo)
        
        # Навигация
        nav = QHBoxLayout()
        nav.setSpacing(20)
        
        # Добавляем растягивающийся элемент слева
        nav.addStretch()
        
        # Кнопки навигации
        news_btn = self.create_nav_button("Новости", "assets/images/news-icon.svg")
        ranking_btn = self.create_nav_button("Рейтинг", "assets/images/ranking-icon.svg")
        shop_btn = self.create_nav_button("Магазин", "assets/images/shop-icon.svg")
        
        nav.addWidget(news_btn)
        nav.addWidget(ranking_btn)
        nav.addWidget(shop_btn)
        
        # Кнопка логина/аккаунта
        self.account_btn = QPushButton("Войти")
        self.account_btn.setProperty("class", "login-button")
        self.account_btn.clicked.connect(self.show_login_dialog)
        nav.addWidget(self.account_btn)
        
        # Кнопка настроек
        settings_btn = QPushButton()
        settings_btn.setIcon(QIcon("assets/images/settings.svg"))
        settings_btn.setIconSize(DEFAULT_ICON_SIZE)
        settings_btn.setProperty("class", "icon-button")
        settings_btn.clicked.connect(self.show_settings)
        nav.addWidget(settings_btn)
        
        layout.addLayout(nav)
        return header
    
    def create_status_cards(self):
        """Создает карточки статуса сервера, онлайна и версии."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setSpacing(CARD_SPACING)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Статус сервера
        status_card = Card()
        status_card.setObjectName("status_card")
        status_card.setProperty("class", "base-card status-card status-card-green")
        
        status_layout = QVBoxLayout()
        status_layout.setSpacing(5)
        status_layout.setContentsMargins(*CARD_MARGINS)
        
        title = self.create_label("СТАТУС СЕРВЕРА", "title")
        self.status_label = self.create_label("Онлайн", "status-value-online")
        self.realm_name = self.create_label("REALM NAME", "subtitle")
        
        status_layout.addWidget(title)
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.realm_name)
        status_card.layout.addLayout(status_layout)
        
        # Онлайн
        online_card = Card()
        online_card.setProperty("class", "status-card status-card-blue")
        
        online_layout = QVBoxLayout()
        online_layout.setSpacing(5)
        online_layout.setContentsMargins(*CARD_MARGINS)
        
        online_title = self.create_label("ИГРОКОВ ОНЛАЙН", "title")
        
        self.online_count = self.create_label("1500", "value")
        
        self.online_trend = self.create_label("↑ +125 за час", "trend-up")
        
        online_layout.addWidget(online_title)
        online_layout.addWidget(self.online_count)
        online_layout.addWidget(self.online_trend)
        online_card.layout.addLayout(online_layout)
        
        # Версия
        version_card = Card()
        version_card.setProperty("class", "status-card status-card-purple")
        
        version_layout = QVBoxLayout()
        version_layout.setSpacing(5)
        version_layout.setContentsMargins(*CARD_MARGINS)
        
        version_title = self.create_label("ВЕРСИЯ", "title")
        
        version_number = self.create_label("3.3.5a", "value")
        
        build_number = self.create_label("12340", "subtitle")
        
        version_layout.addWidget(version_title)
        version_layout.addWidget(version_number)
        version_layout.addWidget(build_number)
        version_card.layout.addLayout(version_layout)
        
        # Добавляем карточки в layout
        layout.addWidget(status_card)
        layout.addWidget(online_card)
        layout.addWidget(version_card)
        layout.addStretch()
        
        return widget
    
    def create_news_section(self):
        """Создает секцию новостей"""
        news_widget = QWidget()
        layout = QVBoxLayout(news_widget)
        layout.setSpacing(20)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Заголовок секции
        title = QLabel("Новости")
        title.setProperty("class", "section-title")
        layout.addWidget(title)
        
        # Сетка новостей
        news_grid = QGridLayout()
        news_grid.setSpacing(20)
        
        # Главная новость
        main_news = self.create_news_card(
            "Обновление 3.3.5a",
            "Установлен патч 3.3.5a...",
            "assets/images/news/main_news.jpg",
            True
        )
        news_grid.addWidget(main_news, 0, 0, 1, 2)
        
        # Дополнительные новости
        news1 = self.create_news_card(
            "Открытие арены",
            "Новый сезон арены...",
            "assets/images/news/arena_news.jpg"
        )
        news_grid.addWidget(news1, 1, 0)
        
        news2 = self.create_news_card(
            "Новые предметы",
            "Добавлены новые предметы...",
            "assets/images/news/items_news.jpg"
        )
        news_grid.addWidget(news2, 1, 1)
        
        layout.addLayout(news_grid)
        return news_widget
    
    def create_news_card(self, title, text, image_path, tag=None, is_main=False):
        card = QFrame()
        card.setProperty("class", "news-card")
        
        layout = QVBoxLayout(card)
        layout.setSpacing(10)
        
        # Изображение новости
        image_label = QLabel()
        image_label.setProperty("class", "news-image")
        pixmap = QPixmap(f"assets/images/news/{image_path}")
        
        # Проверяем, загрузилось ли изображение
        if pixmap.isNull():
            # Создаем заглушку с градиентом
            if is_main:
                pixmap = QPixmap(400, 200)
            else:
                pixmap = QPixmap(200, 100)
            pixmap.fill(Qt.transparent)
            
            # Можно добавить градиент или цвет заглушки
            painter = QPainter(pixmap)
            gradient = QLinearGradient(0, 0, pixmap.width(), 0)
            gradient.setColorAt(0, QColor("#2c3e50"))
            gradient.setColorAt(1, QColor("#3498db"))
            painter.fillRect(pixmap.rect(), gradient)
            painter.end()
        
        # Устанавливаем размер и масштабируем изображение
        if is_main:
            image_label.setFixedHeight(200)
        else:
            image_label.setFixedHeight(100)
        
        scaled_pixmap = pixmap.scaled(
            image_label.width() if image_label.width() > 0 else pixmap.width(),
            image_label.height(),
            Qt.KeepAspectRatioByExpanding,
            Qt.SmoothTransformation
        )
        
        image_label.setPixmap(scaled_pixmap)
        layout.addWidget(image_label)  # Добавляем изображение в layout
        
        # Тег (если есть)
        if tag:
            tag_label = QLabel(tag)
            tag_label.setProperty("class", "news-tag")
            # Даем тегу возможность подстроиться под содержимое
            tag_label.adjustSize()
            # Добавляем небольшой отступ для текста внутри тега
            tag_label.setContentsMargins(8, 2, 8, 2)
            layout.addWidget(tag_label)
        
        # Заголовок
        title_label = QLabel(title)
        title_label.setProperty("class", "news-title")
        if is_main:
            title_label.setProperty("main", "true")
        layout.addWidget(title_label)  # Добавляем заголовок в layout
        
        # Текст
        text_label = QLabel(text)
        text_label.setWordWrap(True)
        text_label.setProperty("class", "news-text")
        layout.addWidget(text_label)  # Добавляем текст в layout
        
        # Кнопка "Подробнее"
        if is_main:
            more_btn = QPushButton("Подробнее →")
            more_btn.setProperty("class", "more-button")
            layout.addWidget(more_btn)
        
        layout.addStretch()
        return card
    
    def create_footer(self):
        # Этот метод больше не нужен, так как футер создается в __init__
        pass
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.updateBackground()
    
    def updateBackground(self):
        # Получаем размеры окна
        window_size = self.size()
        
        # Масштабируем изображение, чтобы оно покрывало всё окно
        scaled_bg = self.background.scaled(
            window_size.width() + 50,  # Добавляем небольшой запас по ширине
            window_size.height() + 50,  # и высоте, чтобы избежать пустых краёв
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation
        )
        
        # Если изображение больше окна, обрезаем его по центру
        if scaled_bg.width() > window_size.width() or scaled_bg.height() > window_size.height():
            x = (scaled_bg.width() - window_size.width()) // 2
            y = (scaled_bg.height() - window_size.height()) // 2
            scaled_bg = scaled_bg.copy(
                x, y, 
                window_size.width(), 
                window_size.height()
            )
        
        # Устанавливаем фон
        palette = self.palette()
        palette.setBrush(QPalette.Window, QBrush(scaled_bg))
        self.setPalette(palette)
    
    def pulse_play_button(self):
        self.play_button.setProperty("class", "play-button-pulse")
    
    def load_settings(self):
        """Загружает настройки из файла"""
        if self.settings_file.exists():
            try:
                with open(self.settings_file, "r") as f:
                    return json.load(f)
            except:
                return self.default_settings.copy()
        return self.default_settings.copy()
    
    def save_settings(self):
        """Сохраняет настройки в файл"""
        self.settings_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.settings_file, "w") as f:
            json.dump(self.settings, f, indent=4)
    
    def get_setting(self, category, key):
        """Получает значение настройки по категории и ключу"""
        return self.settings.get(category, {}).get(key, self.default_settings[category][key])
    
    def set_setting(self, category, key, value):
        """Устанавливает значение настройки"""
        if category not in self.settings:
            self.settings[category] = {}
        self.settings[category][key] = value
        self.save_settings()
    
    def show_settings(self):
        """Показывает окно настроек"""
        dialog = SettingsDialog(self)
        dialog.exec()

    def create_label(self, text, class_name, additional_props=None):
        """Создает стилизованный QLabel с заданным классом.
        
        Args:
            text (str): Текст метки
            class_name (str): Имя класса для стилей
            additional_props (dict, optional): Дополнительные свойства
            
        Returns:
            QLabel: Созданная метка
        """
        label = QLabel(text)
        label.setProperty("class", class_name)
        if additional_props:
            for key, value in additional_props.items():
                label.setProperty(key, value)
        return label

    def update_server_status(self):
        """Обновляет информацию о статусе сервера"""
        async def get_status():
            status = await self.server_api.get_server_status()
            if status:
                # Обновляем UI в главном потоке
                online = status.auth_online and status.world_online
                
                # Определяем текст статуса
                if online:
                    status_text = "Онлайн"
                elif not status.auth_online and not status.world_online:
                    status_text = "Оффлайн"
                elif not status.auth_online:
                    status_text = "Auth Оффлайн"
                else:
                    status_text = "World Оффлайн"
                
                # Обновляем текст и стиль статуса
                self.status_label.setText(status_text)
                self.status_label.setProperty(
                    "class", 
                    "status-value-online" if online else "status-value-offline"
                )
                self.status_label.style().unpolish(self.status_label)
                self.status_label.style().polish(self.status_label)
                
                # Обновляем стиль карточки статуса
                status_card = self.findChild(Card, "status_card")
                if status_card:
                    new_class = f"base-card status-card {'status-card-green' if online else 'status-card-red'}"
                    print(f"Setting card class to: {new_class}")  # Отладочный вывод
                    status_card.setProperty("class", new_class)
                    status_card.style().unpolish(status_card)
                    status_card.style().polish(status_card)
                    status_card.update()  # Принудительно обновляем виджет
                
                self.realm_name.setText(status.realm_name)
                self.online_count.setText(str(status.players_online))
                
                # Обновляем тренд
                self.online_trend.setText(f"↑ {status.players_online} из {status.max_players}")
            else:
                self.status_label.setText("Недоступен")
                self.status_label.setProperty("class", "status-value-offline")
                self.status_label.style().unpolish(self.status_label)
                self.status_label.style().polish(self.status_label)
                
                # Обновляем стиль карточки на красный
                status_card = self.findChild(Card, "status_card")
                if status_card:
                    status_card.setProperty("class", "base-card status-card status-card-red")
                    status_card.style().unpolish(status_card)
                    status_card.style().polish(status_card)
        
        # Запускаем асинхронную задачу в нашем event loop
        future = asyncio.run_coroutine_threadsafe(get_status(), self.loop)
        future.add_done_callback(lambda f: self.handle_status_update_error(f))

    def handle_status_update_error(self, future):
        """Обрабатывает ошибки при обновлении статуса"""
        try:
            future.result()
        except Exception as e:
            print(f"Error updating server status: {e}")

    def show_login(self):
        """Показывает диалог авторизации"""
        dialog = LoginDialog(self)
        if dialog.exec_():
            # Успешная авторизация
            self.current_user = dialog.auth_result
            self.update_ui_after_login()
    
    def update_ui_after_login(self):
        """Обновляет UI после успешной авторизации"""
        self.game_button.setEnabled(True)
        self.update_account_info()
        
    def update_account_info(self):
        """Обновляет информацию об аккаунте в UI"""
        if self.current_user:
            # Обновляем кнопку аккаунта
            self.account_btn.setText(self.current_user.username)
            self.account_btn.setProperty("class", "account-button")
            
            # Обновляем стили
            self.account_btn.style().unpolish(self.account_btn)
            self.account_btn.style().polish(self.account_btn)
            
            # Обновляем меню аккаунта
            self.create_account_menu()
    
    def create_account_menu(self):
        """Создает меню аккаунта"""
        menu = QMenu(self)
        menu.setProperty("class", "account-menu")
        
        if self.current_user:
            # Добавляем информацию об аккаунте
            account_info = QAction(f"Аккаунт: {self.current_user.username}", self)
            account_info.setEnabled(False)
            menu.addAction(account_info)
            
            menu.addSeparator()
            
            # Кнопка выхода
            logout = QAction("Выйти", self)
            logout.triggered.connect(self.logout)
            menu.addAction(logout)
        else:
            # Кнопка входа
            login = QAction("Войти", self)
            login.triggered.connect(self.show_login)
            menu.addAction(login)
        
        return menu

    def logout(self):
        """Выход из аккаунта"""
        # Очищаем данные авторизации
        self.settings['auth']['username'] = None
        self.settings['auth']['account_id'] = None
        self.settings['auth']['auto_login'] = False
        self.settings['auth']['saved_password'] = ""
        
        # Сохраняем настройки
        self.save_settings()
        
        # Обновляем UI
        self.account_btn.setText("Войти")
        self.account_btn.setMenu(None)
        self.play_button.setEnabled(False)
        self.current_user = None
        
        # Очищаем данные в GameLauncher
        self.game_launcher.set_account_info(None, None)

    def show_login_dialog(self):
        """Показывает диалог авторизации"""
        if not self.current_user:  # Если пользователь не авторизован
            dialog = LoginDialog(self)
            if dialog.exec_():
                # Успешная авторизация
                self.current_user = dialog.auth_result
                self.update_ui_after_login()
        else:  # Если пользователь уже авторизован
            self.show_account_menu()

    def show_account_menu(self):
        """Показывает меню аккаунта"""
        menu = QMenu(self)
        menu.setProperty("class", "account-menu")
        
        # Добавляем информацию об аккаунте
        account_info = QAction(f"Аккаунт: {self.current_user.username}", menu)
        account_info.setEnabled(False)
        menu.addAction(account_info)
        
        menu.addSeparator()
        
        # Добавляем действия
        logout = QAction("Выйти", menu)
        logout.triggered.connect(self.logout)
        menu.addAction(logout)
        
        # Показываем меню под кнопкой
        menu.exec_(self.account_btn.mapToGlobal(
            QPoint(0, self.account_btn.height())
        ))

    def create_nav_button(self, text: str, icon_path: str) -> QPushButton:
        """Создает навигационную кнопку"""
        btn = QPushButton(text)
        btn.setIcon(QIcon(icon_path))
        btn.setIconSize(DEFAULT_ICON_SIZE)
        btn.setProperty("class", "nav-button")
        return btn

    def launch_game(self):
        """Обработчик нажатия кнопки запуска"""
        if not self.game_launcher.validate_game_path(self.settings.get('game', {}).get('path', '')):
            QMessageBox.warning(
                self,
                "Ошибка",
                "Неверный путь к игре. Проверьте настройки."
            )
            return
        
        # Если пользователь авторизован, добавляем параметры для автологина
        if self.current_user:
            self.game_launcher.set_account_info(
                self.current_user.username,
                self.current_user.account_id
            )
        
        if self.game_launcher.launch_game():
            # Сворачиваем лаунчер при запуске игры
            self.showMinimized()
        else:
            QMessageBox.critical(
                self,
                "Ошибка",
                "Не удалось запустить игру. Проверьте настройки и файлы игры."
            )

    def show_download_buttons(self):
        """Показывает кнопки для скачивания клиента"""
        self.play_button.hide()
        
        # Создаем кнопки в футере
        self.download_button = QPushButton("Скачать клиент")
        self.download_button.setObjectName("download-button")
        self.download_button.clicked.connect(self.start_download)
        
        self.select_folder_button = QPushButton("Выбрать папку")
        self.select_folder_button.setObjectName("select-folder-button")
        self.select_folder_button.clicked.connect(self.select_game_folder)
        
        # Добавляем в футер
        self.footer_layout.insertWidget(1, self.download_button)
        self.footer_layout.insertWidget(2, self.select_folder_button)
        
    def show_download_progress(self):
        """Показывает прогресс загрузки"""
        self.game_button.setEnabled(False)
        self.game_button.setText("Загрузка...")
        self.game_button.setProperty("state", "downloading")
        
        # Создаем и добавляем прогресс-бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("download-progress")
        self.progress_bar.setFixedHeight(40)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.footer_layout.insertWidget(1, self.progress_bar)
        
        # Обновляем стили
        self.game_button.style().unpolish(self.game_button)
        self.game_button.style().polish(self.game_button)

    def update_download_progress(self, progress: float, status: str, speed: float):
        """Обновляет прогресс загрузки"""
        if hasattr(self, 'progress_bar'):
            self.progress_bar.setValue(int(progress))
            speed_str = humanize.naturalsize(speed, binary=True) + "/s"
            self.progress_bar.setFormat(f"{status} - {speed_str}")

    def on_download_error(self, error_msg: str):
        """Обработчик ошибки загрузки"""
        self.hide_download_progress()
        QMessageBox.critical(self, "Ошибка загрузки", error_msg)

    def setup_game_button(self):
        """Настройка основной кнопки игры/загрузки"""
        self.game_button = QPushButton()
        self.game_button.setObjectName("game-button")
        
        # Обновляем состояние кнопки
        self.update_game_button_state()
        
        # Добавляем в футер
        self.footer_layout.addWidget(self.game_button)

    def on_tray_icon_activated(self, reason):
        """Обработчик кликов по трей-иконке"""
        if reason == QSystemTrayIcon.Trigger:  # Обычный клик
            self.show_normal()

    def launch_game_from_tray(self):
        """Запускает игру из трея"""
        if not self.game_launcher.validate_game_path(self.settings.get('game', {}).get('path', '')):
            self.show_normal()
            QMessageBox.warning(
                self,
                "Ошибка", 
                "Неверный путь к игре. Проверьте настройки."
            )
            return
            
        if self.current_user:
            self.game_launcher.set_account_info(
                self.current_user.username,
                self.current_user.account_id
            )
            
        if self.game_launcher.launch_game():
            self.hide()
            self.tray_icon.show()

    def update_game_button_state(self):
        """Обновляет состояние кнопки в зависимости от наличия клиента"""
        # Безопасно отключаем старые подключения
        try:
            if self.game_button.receivers(self.game_button.clicked) > 0:
                self.game_button.clicked.disconnect()
        except (TypeError, RuntimeError):
            pass  # Игнорируем ошибки отключения
            
        if not self.settings['game']['path']:
            # Нет выбранной папки
            self.game_button.setText("Выбрать папку")
            self.game_button.setProperty("state", "select")
            self.game_button.clicked.connect(self.select_game_folder)
            
        elif not self.game_launcher.validate_game_path(self.settings['game']['path']):
            # Папка выбрана, но клиент не найден
            self.game_button.setText("Скачать клиент")
            self.game_button.setProperty("state", "download")
            self.game_button.clicked.connect(self.start_download)
            
        else:
            # Клиент найден
            self.game_button.setText("Играть")
            self.game_button.setProperty("state", "play")
            self.game_button.clicked.connect(self.launch_game)

        # Обновляем стили
        self.game_button.style().unpolish(self.game_button)
        self.game_button.style().polish(self.game_button)

    def start_download(self):
        """Запускает загрузку клиента"""
        try:
            self.game_launcher._download_client()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))
            
    def select_game_folder(self):
        """Открывает диалог выбора папки с игрой"""
        path = QFileDialog.getExistingDirectory(
            self,
            "Выберите папку с игрой"
        )
        if path:
            self.settings['game']['path'] = path
            self.save_settings()
            # Проверяем новый путь и обновляем состояние кнопки
            self.game_launcher.validate_game_path(path)
            self.update_game_button_state()
            
    def launch_game(self):
        """Запускает игру"""
        if self.game_launcher.launch_game():
            self.hide()  # Скрываем окно
            self.tray_icon.show()  # Показываем иконку в трее

    def on_login_success(self, result: AuthResult):
        """Обработчик успешной авторизации"""
        self.current_user = result
        self.settings['auth']['username'] = result.username
        self.settings['auth']['account_id'] = result.account_id
        self.save_settings()

    def start_game_monitoring(self):
        """Запускает мониторинг процесса игры"""
        self.game_monitor_timer = QTimer()
        self.game_monitor_timer.timeout.connect(self.check_game_running)
        self.game_monitor_timer.start(5000)  # Проверяем каждые 5 секунд

    def check_game_running(self):
        """Проверяет, запущена ли игра"""
        if not self.game_launcher.is_game_running():
            self.game_monitor_timer.stop()
            self.tray_icon.hide()  # Скрываем иконку
            self.showNormal()  # Восстанавливаем окно

    def show_normal(self):
        """Восстанавливает окно из трея"""
        self.showNormal()
        self.activateWindow()

class SettingsDialog(QDialog):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.settings = main_window.settings.copy()
        self.game_launcher = main_window.game_launcher
        self.setup_ui()
    
    def browse_directory(self, line_edit, title):
        """Открывает диалог выбора папки"""
        path = QFileDialog.getExistingDirectory(self, title)
        if path:
            line_edit.setText(path)
            # Проверяем наличие клиента если это путь к игре
            if line_edit.objectName() == "game_path":
                if not self.game_launcher.validate_game_path(path):
                    QMessageBox.warning(
                        self,
                        "Клиент не найден",
                        "В указанной папке не найден клиент WoW. "
                        "После сохранения настроек вам будет предложено скачать его."
                    )
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Создаем вкладки
        tabs = QTabWidget()
        tabs.addTab(self.create_game_tab(), "Игра")
        tabs.addTab(self.create_graphics_tab(), "Графика")
        tabs.addTab(self.create_addons_tab(), "Аддоны")
        
        layout.addWidget(tabs)
        
        # Кнопки
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.setSpacing(10)
        
        save_btn = QPushButton("Сохранить")
        save_btn.setObjectName("save_button")
        save_btn.setProperty("class", "save-button")
        save_btn.setFixedHeight(40)
        
        cancel_btn = QPushButton("Отмена")
        cancel_btn.setObjectName("cancel_button")
        cancel_btn.setProperty("class", "cancel-button")
        cancel_btn.setFixedHeight(40)
        
        buttons.addWidget(cancel_btn)
        buttons.addWidget(save_btn)
        
        layout.addLayout(buttons)
        
        # Подключаем сигналы
        save_btn.clicked.connect(self.save_settings)
        cancel_btn.clicked.connect(self.reject)
    
    def create_game_tab(self):
        tab = QWidget()
        tab.setObjectName("game_tab")  # Добавляем id для поиска
        layout = QVBoxLayout(tab)
        
        # Группа настроек для Linux
        if platform.system().lower() == 'linux':
            linux_group = QGroupBox("Настройки для Linux")
            linux_layout = QVBoxLayout(linux_group)
            
            # Выбор эмулятора
            runner_label = QLabel("Эмулятор:")
            runner_combo = QComboBox()
            runner_combo.setObjectName("runner_combo")  # Добавляем id для поиска
            runner_combo.setProperty("class", "settings-combobox")
            runner_combo.addItems(["wine", "lutris", "proton", "portproton"])
            runner_combo.setCurrentText(self.settings.get('game', {}).get('runner', 'wine'))
            
            # WINEPREFIX
            prefix_label = QLabel("WINEPREFIX:")
            prefix_input = QLineEdit()
            prefix_input.setObjectName("prefix_input")  # Добавляем id для поиска
            prefix_input.setProperty("class", "settings-input")
            prefix_input.setText(self.settings.get('game', {}).get('wineprefix', ''))
            
            # Кнопка выбора WINEPREFIX
            prefix_browse = QPushButton("Обзор")
            prefix_browse.setProperty("class", "browse-button")
            prefix_browse.clicked.connect(lambda: self.browse_directory(prefix_input, "Выберите WINEPREFIX"))
            
            prefix_layout = QHBoxLayout()
            prefix_layout.addWidget(prefix_input)
            prefix_layout.addWidget(prefix_browse)
            
            linux_layout.addWidget(runner_label)
            linux_layout.addWidget(runner_combo)
            linux_layout.addWidget(prefix_label)
            linux_layout.addLayout(prefix_layout)
            
            layout.addWidget(linux_group)
        
        # Путь к игре
        path_label = QLabel("Путь к игре:")
        path_input = QLineEdit()
        path_input.setObjectName("game_path")  # Добавляем id для поиска
        path_input.setProperty("class", "settings-input")
        path_input.setText(self.settings.get('game', {}).get('path', ''))
        
        # Кнопка выбора пути
        path_browse = QPushButton("Обзор")
        path_browse.setProperty("class", "browse-button")
        path_browse.clicked.connect(lambda: self.browse_directory(path_input, "Выберите папку с игрой"))
        
        path_layout = QHBoxLayout()
        path_layout.addWidget(path_input)
        path_layout.addWidget(path_browse)
        
        # Реалм-лист
        realmlist_label = QLabel("Реалм-лист:")
        realmlist_input = QLineEdit()
        realmlist_input.setObjectName("realmlist_input")  # Добавляем id для поиска
        realmlist_input.setProperty("class", "settings-input")
        realmlist_input.setText(self.settings.get('game', {}).get('realmlist', 'logon.server.com'))
        
        # Параметры запуска
        launch_label = QLabel("Параметры запуска:")
        launch_input = QLineEdit()
        launch_input.setObjectName("launch_options")  # Добавляем id для поиска
        launch_input.setProperty("class", "settings-input")
        launch_input.setText(self.settings.get('game', {}).get('launch_options', ''))
        
        layout.addWidget(path_label)
        layout.addLayout(path_layout)
        layout.addWidget(realmlist_label)
        layout.addWidget(realmlist_input)
        layout.addWidget(launch_label)
        layout.addWidget(launch_input)
        
        return tab
    
    def create_graphics_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Разрешение экрана
        self.resolution = QComboBox()
        self.resolution.addItems(["1920x1080", "1600x900", "1366x768"])
        self.resolution.setProperty("class", "settings-combobox")
        layout.addWidget(QLabel("Разрешение:"))
        layout.addWidget(self.resolution)
        
        # Качество графики
        self.graphics = QComboBox()
        self.graphics.addItems(["Низкое", "Среднее", "Высокое", "Ультра"])
        self.graphics.setProperty("class", "settings-combobox")
        layout.addWidget(QLabel("Качество графики:"))
        layout.addWidget(self.graphics)
        
        # Оконный режим
        self.windowed = QCheckBox("Оконный режим")
        self.windowed.setProperty("class", "settings-checkbox")
        layout.addWidget(self.windowed)
        
        layout.addStretch()
        return tab
    
    def create_addons_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(QLabel("Список аддонов появится в следующем обновлении"))
        layout.addStretch()
        return tab
    
    def create_path_selector(self, label_text, button_text, line_edit):
        layout = QHBoxLayout()
        
        layout.addWidget(label_text)
        layout.addWidget(line_edit)
        
        browse_btn = QPushButton(button_text)
        browse_btn.setProperty("class", "browse-button")
        browse_btn.clicked.connect(lambda: self.browse_path(line_edit))
        layout.addWidget(browse_btn)
        
        return layout
    
    def browse_path(self, line_edit):
        path = QFileDialog.getExistingDirectory(self, "Выберите папку")
        if path:
            line_edit.setText(path) 

    def save_settings(self):
        """Сохраняет настройки"""
        try:
            # Получаем значения из вкладки Игра
            game_tab = self.findChild(QWidget, "game_tab")
            
            # Путь к игре
            game_path = game_tab.findChild(QLineEdit, "game_path").text()
            old_path = self.settings['game'].get('path', '')
            self.settings['game']['path'] = game_path
            
            # Если путь изменился, проверяем наличие клиента
            if game_path != old_path:
                if not self.game_launcher.validate_game_path(game_path):
                    if QMessageBox.question(
                        self,
                        "Клиент не найден",
                        "В указанной папке не найден клиент WoW. Хотите скачать его?",
                        QMessageBox.Yes | QMessageBox.No
                    ) == QMessageBox.Yes:
                        self.accept()  # Закрываем настройки
                        self.main_window.show_download_buttons()
                        return
            
            # Реалм-лист
            realmlist = game_tab.findChild(QLineEdit, "realmlist_input").text()
            old_realmlist = self.settings['game'].get('realmlist', '')
            self.settings['game']['realmlist'] = realmlist
            
            # Если изменился реалм-лист или путь к игре, обновляем файл
            if (realmlist != old_realmlist or game_path != old_path) and game_path:
                if not self.game_launcher.update_realmlist(game_path, realmlist):
                    raise Exception("Не удалось обновить realmlist.wtf")
            
            # Параметры запуска
            launch_options = game_tab.findChild(QLineEdit, "launch_options").text()
            self.settings['game']['launch_options'] = launch_options
            
            # Настройки Linux
            if platform.system().lower() == 'linux':
                runner = game_tab.findChild(QComboBox, "runner_combo").currentText()
                wineprefix = game_tab.findChild(QLineEdit, "prefix_input").text()
                
                self.settings['game']['runner'] = runner
                self.settings['game']['wineprefix'] = wineprefix
            
            # Сохраняем настройки
            self.main_window.settings = self.settings
            self.main_window.save_settings()
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить настройки: {str(e)}")
