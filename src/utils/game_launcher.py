import os
import subprocess
from pathlib import Path
import logging
import platform
import shutil
import json

class GameLauncher:
    def __init__(self, settings: dict):
        self.settings = settings
        self.logger = logging.getLogger('GameLauncher')
        self.platform = platform.system().lower()
        self.account_username = None
        self.account_id = None

    def validate_game_path(self, path: str) -> bool:
        """Проверяет корректность пути к игре"""
        if not path:
            return False
            
        game_path = Path(path)
        
        # На всех платформах ищем Wow.exe
        exe_name = 'Wow.exe'
        
        required_files = [
            exe_name,
            'Data/common.MPQ',
            'Data/common-2.MPQ'
        ]
        
        try:
            for file in required_files:
                file_path = game_path / file
                if not file_path.exists():
                    self.logger.error(f"Missing required file: {file}")
                    return False
            return True
        except Exception as e:
            self.logger.error(f"Error validating game path: {e}")
            return False

    def update_realmlist(self, path: str, realmlist: str) -> bool:
        """Обновляет файл realmlist.wtf"""
        try:
            data_path = Path(path) / 'Data' / 'realmlist.wtf'
            data_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(data_path, 'w', encoding='utf-8') as f:
                f.write(f'set realmlist {realmlist}\n')
            return True
        except Exception as e:
            self.logger.error(f"Error updating realmlist: {e}")
            return False

    def update_config_wtf(self, path: str) -> bool:
        """Обновляет файл Config.wtf для автологина"""
        try:
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
                config['accountName'] = self.account_username
            
            # Добавляем другие важные настройки если их нет
            defaults = {
                'locale': 'ruRU',
                'readTOS': '1',
                'readEULA': '1',
                'readTerminationWithoutNotice': '1',
                'accounttype': 'LK'
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
            
            # Добавляем параметры автологина если есть данные аккаунта
            if self.account_username and self.account_id:
                launch_options.extend([
                    '-login', self.account_username,
                    '-accountid', str(self.account_id)
                ])
            
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
                    
                    if runner == 'wine':
                        cmd = ['wine', exe_path] + launch_options
                    elif runner == 'lutris':
                        cmd = ['lutris', 'rungame', exe_path] + launch_options
                    elif runner == 'proton':
                        cmd = ['proton', 'run', exe_path] + launch_options
                    elif runner == 'portproton':
                        cmd = ['portproton', 'run', exe_path] + launch_options
                    elif runner == 'crossover':
                        cmd = ['crossover', exe_path] + launch_options
                    else:
                        raise RuntimeError(f"Неизвестный эмулятор: {runner}")
                      
                    # Добавляем переменные окружения для Wine
                    env = os.environ.copy()
                    if self.settings.get('game', {}).get('wineprefix'):
                        env['WINEPREFIX'] = self.settings['game']['wineprefix']
                    env['WINEARCH'] = 'win32'
                    
                    subprocess.Popen(cmd, env=env)
                except Exception as e:
                    self.logger.error(f"Error launching with Wine: {e}")
                    return False
                    
            elif self.platform == 'darwin':
                subprocess.Popen(['open', exe_path, '--args'] + launch_options)
            else:
                subprocess.Popen([exe_path] + launch_options)
                
            return True

        except Exception as e:
            self.logger.error(f"Error launching game: {e}")
            return False 