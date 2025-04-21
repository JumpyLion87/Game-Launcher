import asyncio
import aiomysql
from dataclasses import dataclass
from typing import Optional
import hashlib
import binascii
import time

@dataclass
class AuthResult:
    success: bool
    message: str
    account_id: Optional[int] = None
    username: Optional[str] = None
    gmlevel: Optional[int] = 0

class AuthAPI:
    def __init__(self):
        # Кэшируем подключение
        self._pool = None
        self.db_config = {
            'host': '0.0.0.0',
            'port': 3306,
            'user': 'launcher_ro',
            'password': '',
            'db': 'acore_auth'
        }
        # Константы для SRP6
        self.N = 0x894B645E89E1535BBDAD5B8B290650530801B18EBFBF5E8FAB3C82872A3E9BB7
        self.g = 7
        
    async def get_pool(self):
        """Получение или создание пула подключений"""
        if self._pool is None:
            self._pool = await aiomysql.create_pool(**self.db_config)
        return self._pool

    def _calculate_verifier(self, username: str, password: str, salt: bytes) -> bytes:
        """
        Вычисляет верификатор для SRP6
        """
        # 1. Вычисляем h1 = SHA1("USERNAME:PASSWORD")
        username = username.upper()
        password = password.upper()
        h1 = hashlib.sha1(f"{username}:{password}".encode()).digest()
        
        # 2. Вычисляем h2 = SHA1(salt || h1)
        h2 = int.from_bytes(
            hashlib.sha1(salt + h1).digest(),
            byteorder='little'
        )
        
        # 3. Вычисляем (g^h2) % N используя встроенную функцию pow
        verifier = pow(self.g, h2, self.N)
        
        # 4. Конвертируем в байты в little-endian порядке
        return verifier.to_bytes(32, byteorder='little')

    async def login(self, username: str, password: str) -> AuthResult:
        try:
            pool = await self.get_pool()
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    # Получаем данные аккаунта
                    await cur.execute("""
                        SELECT id, username, salt, verifier, locked
                        FROM account 
                        WHERE username = %s
                    """, (username.upper(),))
                    
                    result = await cur.fetchone()
                    
                    if not result:
                        return AuthResult(
                            success=False,
                            message="Неверное имя пользователя или пароль"
                        )
                    
                    account_id, db_username, salt, stored_verifier, locked = result
                    
                    # Проверяем блокировку
                    if locked:
                        return AuthResult(
                            success=False,
                            message="Аккаунт заблокирован"
                        )
                    
                    # Вычисляем верификатор
                    calculated_verifier = self._calculate_verifier(username, password, salt)
                    
                    # Сравниваем верификаторы
                    if calculated_verifier != stored_verifier:
                        return AuthResult(
                            success=False,
                            message="Неверное имя пользователя или пароль"
                        )
                    
                    return AuthResult(
                        success=True,
                        message="Успешная авторизация",
                        account_id=account_id,
                        username=db_username,
                        gmlevel=0
                    )
                    
        except ConnectionRefusedError:
            raise  # Пробрасываем ошибку выше для обработки в диалоге
        except aiomysql.OperationalError as e:
            if e.args[0] == 2003:  # Can't connect to MySQL server
                raise ConnectionRefusedError("Сервер базы данных недоступен")
            raise
        except Exception as e:
            print(f"Error during login: {e}")
            return AuthResult(
                success=False,
                message="Ошибка при авторизации"
            ) 
