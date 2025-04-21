import os
from subprocess import Popen, PIPE
from pathlib import Path
import logging
import platform
import shutil
import json
from PySide6.QtCore import QObject, Signal
from src.utils.torrent_manager import TorrentManager

class GameLauncherSignals(QObject):
    client_missing = Signal()  # Сигнал об отсутствии клиента
    download_progress = Signal(float, str, float)  # прогресс, статус, скорость
    download_error = Signal(str)  # ошибка загрузки

class GameLauncher:
    def __init__(self, settings: dict, parent=None):
        self.settings = settings
        self.parent = parent
        self.signals = GameLauncherSignals()
        self.logger = logging.getLogger('GameLauncher')
        self.platform = platform.system().lower()
        self.account_username = None
        self.account_id = None
        self.torrent_manager = None
        self.client_version = "3.3.5a"
        self.required_size = 17_179_869_184  # 16GB в байтах
        # Кэшируем пути к файлам
        self.game_path = Path(settings.get('game', {}).get('path', ''))
        self.config_path = self.game_path / 'WTF' / 'Config.wtf'
        self.realmlist_paths = [
            self.game_path / 'Data' / 'ruRU' / 'realmlist.wtf',
            self.game_path / 'Data' / 'realmlist.wtf'
        ]
        self.client_info = None
        self.torrent_path = Path("assets/client/wow-3.3.5.torrent")
        self.trackers = [
            "udp://tracker1.example.com:6969/announce",
            "udp://tracker2.example.com:6969/announce"
        ]

    def validate_game_path(self, path: str) -> bool:
        """Проверяет корректность пути к игре"""
        if not path:
            self.signals.client_missing.emit()
            return False
            
        game_path = Path(path)
        
        required_files = [
            game_path / 'Wow.exe',
            game_path / 'Data/common.MPQ',
            game_path / 'Data/common-2.MPQ'
        ]
        
        try:
            # Проверяем каждый файл
            for required_file in required_files:
                if not required_file.exists():
                    self.logger.error(f"Missing required file: {required_file}")
                    return False
            return True
        except Exception as e:
            self.logger.error(f"Error validating game path: {e}")
            return False

    def update_realmlist(self, path: str, realmlist: str) -> bool:
        """Обновляет файл realmlist.wtf"""
        try:
            # Проверяем оба возможных пути
            data_paths = [
                Path(path) / 'Data' / 'ruRU' / 'realmlist.wtf',  # Путь для русской локализации
                Path(path) / 'Data' / 'realmlist.wtf'  # Стандартный путь
            ]
            
            # Обновляем существующие файлы или создаем новые
            updated = False
            for data_path in data_paths:
                try:
                    data_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(data_path, 'w', encoding='utf-8') as f:
                        f.write(f'set realmlist {realmlist}\n')
                    updated = True
                except Exception as e:
                    self.logger.warning(f"Could not update {data_path}: {e}")
            
            return updated
        except Exception as e:
            self.logger.error(f"Error updating realmlist: {e}")
            return False

    def update_config_wtf(self, path: str) -> bool:
        """Обновляет файл Config.wtf для автологина"""
        try:
            # Получаем realmlist из настроек
            realmlist = self.settings.get('game', {}).get('realmlist', 'logon.server.com')
            
            config_path = Path(path) / 'WTF' / 'Config.wtf'
            
            # Создаем директорию WTF если её нет
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Читаем существующие настройки
            config = {}
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.startswith('SET '):
                            key, value = line[4:].strip().split(' ', 1)
                            config[key] = value.strip('"')
            
            # Обновляем настройки
            if self.account_username:
                # Настройки для автологина
                config['accountName'] = self.account_username.upper()  # Имя должно быть в верхнем регистре
                config['accountList'] = self.account_username.upper()  # Список аккаунтов
                config['lastAccountName'] = self.account_username.upper()  # Последний использованный аккаунт
                # Дополнительные настройки для списка аккаунтов
                config['portal'] = self.account_username.upper()  # Текущий аккаунт в портале
                config['lastCharacterIndex'] = "0"  # Индекс последнего персонажа
                config['realmName'] = "WoW Server"  # Имя реалма
                config['savedAccountList'] = f"{self.account_username.upper()}|{realmlist}"  # Сохраненный список
                config['lastSelectedAccount'] = self.account_username.upper()  # Последний выбранный аккаунт
            
            # Добавляем другие важные настройки если их нет
            defaults = {
                'locale': 'ruRU',
                'readTOS': '1',
                'readEULA': '1',
                'readTerminationWithoutNotice': '1',
                'accounttype': 'LK',
                'lastSelectedRealm': '1',  # Индекс последнего выбранного реалма
                'realmList': realmlist,  # Адрес сервера
                'patchlist': f"'{realmlist}'",  # Адрес сервера для патчей
                'accountListType': "1",  # Тип списка аккаунтов
                'autoSelect': "1",  # Автовыбор аккаунта
                'autoConnect': "1"  # Автоподключение
            }
            
            for key, value in defaults.items():
                if key not in config:
                    config[key] = value
            
            # Записываем обновленный конфиг
            with open(config_path, 'w', encoding='utf-8') as f:
                for key, value in config.items():
                    # Если значение похоже на число, записываем без кавычек
                    if value.replace('.', '').isdigit():
                        f.write(f'SET {key} {value}\n')
                    else:
                        f.write(f'SET {key} "{value}"\n')
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating Config.wtf: {e}")
            return False

    def set_account_info(self, username: str, account_id: int):
        """Устанавливает данные аккаунта для автологина"""
        self.account_username = username
        self.account_id = account_id

    def launch_game(self) -> bool:
        """Запускает игру с заданными параметрами"""
        try:
            game_path = self.settings.get('game', {}).get('path', '')
            if not game_path or not self.validate_game_path(game_path):
                self.logger.error("Invalid game path")
                return False

            # Обновляем realmlist
            realmlist = self.settings.get('game', {}).get('realmlist', 'logon.server.com')
            if not self.update_realmlist(game_path, realmlist):
                return False

            # Обновляем Config.wtf для автологина
            if self.account_username and not self.update_config_wtf(game_path):
                return False

            # Формируем путь к исполняемому файлу
            exe_path = str(Path(game_path) / 'Wow.exe')

            # Формируем параметры запуска
            launch_options = self.settings.get('game', {}).get('launch_options', '').split()
            
            # Добавляем параметры графики
            graphics = self.settings.get('graphics', {})
            if graphics.get('windowed', False):
                launch_options.append('-windowed')
            
            resolution = graphics.get('resolution', '1920x1080')
            if resolution:
                width, height = resolution.split('x')
                launch_options.extend(['-width', width, '-height', height])

            # Запускаем процесс
            if self.platform == 'linux':
                try:
                    runner = self.settings.get('game', {}).get('runner', 'wine')
                    
                    if runner == 'portproton':
                        cmd = ['portproton', exe_path] + launch_options
                    elif runner == 'wine':
                        cmd = ['wine', exe_path] + launch_options
                    elif runner == 'lutris':
                        cmd = ['lutris', 'rungame', exe_path] + launch_options
                    elif runner == 'proton':
                        cmd = ['proton', 'run', exe_path] + launch_options
                    elif runner == 'crossover':
                        cmd = ['crossover', exe_path] + launch_options
                    else:
                        raise RuntimeError(f"Неизвестный эмулятор: {runner}")
                      
                    # Добавляем переменные окружения для Wine
                    env = os.environ.copy()
                    if self.settings.get('game', {}).get('wineprefix'):
                        env['WINEPREFIX'] = self.settings['game']['wineprefix']
                    env['WINEARCH'] = 'win32'
                      
                    # Запускаем процесс
                    Popen(cmd, env=env)
                    
                except Exception as e:
                    self.logger.error(f"Error launching with Wine: {e}")
                    return False
                    
            elif self.platform == 'darwin':
                Popen(['open', exe_path, '--args'] + launch_options)
            else:
                Popen([exe_path] + launch_options)
                
            return True

        except Exception as e:
            self.logger.error(f"Error launching game: {e}")
            return False 

    def _check_free_space(self, path: str) -> bool:
        """Проверяет достаточно ли свободного места"""
        try:
            free_space = shutil.disk_usage(path).free
            return free_space >= self.required_size
        except Exception as e:
            self.logger.error(f"Error checking free space: {e}")
            return False

    def _verify_client_files(self, path: str) -> tuple[bool, list[str]]:
        """Проверяет целостность файлов клиента"""
        missing_files = []
        game_path = Path(path)
        
        # Список критически важных файлов и их MD5
        required_files = {
            'Wow.exe': 'expected_md5_1',
            'Data/common.MPQ': 'expected_md5_2',
            'Data/common-2.MPQ': 'expected_md5_3',
            'Data/expansion.MPQ': 'expected_md5_4',
            'Data/lichking.MPQ': 'expected_md5_5',
            'Data/patch.MPQ': 'expected_md5_6',
        }
        
        for file_path, expected_md5 in required_files.items():
            full_path = game_path / file_path
            if not full_path.exists():
                missing_files.append(file_path)
                continue
                
            # TODO: Добавить проверку MD5
        
        return len(missing_files) == 0, missing_files

    async def _get_client_info(self):
        """Получает информацию о клиенте с сервера"""
        if not self.client_info:
            self.client_info = await self.server_api.get_client_info()
        return self.client_info
        
    def _verify_client_version(self, path: str) -> bool:
        """Проверяет версию клиента"""
        try:
            exe_path = Path(path) / "Wow.exe"
            if not exe_path.exists():
                return False
                
            # TODO: Добавить проверку версии из exe
            return True
        except Exception as e:
            self.logger.error(f"Error verifying client version: {e}")
            return False

    def is_game_running(self) -> bool:
        """Проверяет, запущена ли игра"""
        if self.platform == 'linux':
            # Для Linux проверяем процесс wine
            try:
                result = subprocess.run(['pgrep', '-f', 'Wow.exe'], 
                                      stdout=subprocess.PIPE)
                return result.returncode == 0
            except:
                return False
        else:
            # Для Windows проверяем процесс Wow.exe
            try:
                result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq Wow.exe'],
                                      stdout=subprocess.PIPE)
                return b"Wow.exe" in result.stdout
            except:
                return False

    def _download_client(self):
        """Запускает загрузку клиента"""
        try:
            if not self.torrent_path.exists():
                raise RuntimeError("Торрент файл не найден")

            # Проверяем свободное место
            if not self._check_free_space(self.settings['game']['path']):
                raise RuntimeError("Недостаточно свободного места")

            # Создаем директорию если её нет
            Path(self.settings['game']['path']).mkdir(parents=True, exist_ok=True)

            # Инициализируем TorrentManager
            if not self.torrent_manager:
                self.torrent_manager = TorrentManager()

            # Показываем прогресс в футере
            self.signals.download_progress.emit(0, '', 0)

            # Запускаем загрузку
            self.torrent_manager.start_download(
                torrent_path=str(self.torrent_path),
                save_path=self.settings['game']['path'],
                trackers=self.trackers,
                status_callback=lambda s: self.signals.download_progress.emit(
                    s.progress, s.state, s.speed
                )
            )

        except Exception as e:
            self.logger.error(f"Error downloading client: {e}")
            self.signals.download_error.emit(str(e))
            raise
