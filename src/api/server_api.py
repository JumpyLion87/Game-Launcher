import asyncio
import aiomysql
from dataclasses import dataclass
from typing import Optional, Tuple
import time
import aiohttp

@dataclass
class ServerStatus:
    auth_online: bool
    world_online: bool
    players_online: int
    max_players: int = 1000
    realm_name: str = "WotLK Server"
    uptime: str = "Unknown"

class ServerAPI:
    def __init__(self):
        """Инициализация API для проверки статуса серверов"""
        # Настройки серверов
        self.auth_address = ('185.175.16.107', 3724)
        self.world_address = ('185.175.16.107', 8085)
        # Настройки БД (только чтение)
        self.db_config = {
            'host': '192.168.1.42',
            'port': 3306,
            'user': 'launcher_ro',     # Пользователь для чтения
            'password': 'rPIisIhn46',
            'db': 'acore_characters'
        }
        # Кэш
        self._last_check = None
        self._cache_timeout = 10
        self._players_cache = None
        self._players_cache_time = None
        self._players_cache_timeout = 30
        self.base_url = "https://api.server.com"  # URL вашего API
        
    async def get_players_count(self) -> int:
        """Получает количество игроков через БД"""
        try:
            async with aiomysql.connect(**self.db_config) as conn:
                async with conn.cursor() as cur:
                    # Запрос согласно структуре БД AzerothCore
                    await cur.execute("""
                        SELECT COUNT(*) as count 
                        FROM characters 
                        WHERE online > 0
                    """)
                    result = await cur.fetchone()
                    count = result[0] if result else 0
                    
                    print(f"Current online players: {count}")  # Отладочный вывод
                    
                    # Обновляем кэш
                    self._players_cache = count
                    self._players_cache_time = time.time()
                    
                    return count
        except Exception as e:
            print(f"Error getting players count: {e}")
            return self._players_cache if self._players_cache is not None else 0

    async def check_server(self, host: str, port: int) -> bool:
        """Проверяет доступность сервера"""
        try:
            # Создаем футуру с таймаутом в 2 секунды
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=2.0
            )
            writer.close()
            await writer.wait_closed()
            print(f"Server {host}:{port} is online")
            return True
        except (ConnectionRefusedError, asyncio.TimeoutError):
            print(f"Server {host}:{port} is offline")
            return False
        except Exception as e:
            print(f"Error checking server {host}:{port}: {e}")
            return False

    async def get_server_status(self) -> ServerStatus:
        """Получает статус серверов"""
        # Проверяем кэш
        if self._last_check:
            if (asyncio.get_event_loop().time() - self._last_check[0]) < self._cache_timeout:
                return self._last_check[1]
        
        try:
            # Проверяем оба сервера параллельно
            auth_check, world_check = await asyncio.gather(
                self.check_server(self.auth_address[0], self.auth_address[1]),
                self.check_server(self.world_address[0], self.world_address[1])
            )
            
            # Если world сервер онлайн, получаем количество игроков
            players_online = 0
            if world_check:
                try:
                    players_online = await self.get_players_count()
                except Exception as e:
                    print(f"Error getting players count: {e}")

            print(f"Status: auth={auth_check}, world={world_check}, players={players_online}")
            status = ServerStatus(
                auth_online=auth_check,
                world_online=world_check,
                players_online=players_online
            )
            # Сохраняем результат в кэш
            self._last_check = (asyncio.get_event_loop().time(), status)
            return status
        except Exception as e:
            print(f"Error in get_server_status: {e}")
            return ServerStatus(
                auth_online=False,
                world_online=False,
                players_online=0
            ) 

    async def get_client_info(self) -> dict:
        """Получает информацию о клиенте с сервера"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/client/info") as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        raise Exception("Failed to get client info")
        except Exception as e:
            self.logger.error(f"Error getting client info: {e}")
            raise 