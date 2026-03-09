#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CyberStreet Bot v2.2.0
Production-ready VK bot for gaming club
Author: CyberStreet Team
License: Proprietary
"""

import json
import random
import logging
import sqlite3
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.utils import get_random_id

# ============================================================================
# КОНФИГУРАЦИЯ - ЗДЕСЬ НУЖНО ВСТАВИТЬ СВОИ ДАННЫЕ
# ============================================================================

class Config:
    """Централизованная конфигурация бота"""
    
    # === ВАЖНО: ЗАМЕНИТЕ ЭТИ ЗНАЧЕНИЯ НА СВОИ ===
    VK_TOKEN = "vk1.a.S2d36_yK67YswWnSFYcN5kaDDHN7NrVLyOGh4mPi3vKqpQee3iEIS8SI8-IJ7aTFdpsxd9HT0InOmgiY5h_Jp0yQNaGH155oEIq0oc62phvaF_JtUvr_pMXuAXcJ8lYUbIy6Vcpmk8Kdw4uV3Ia-um23JuH3wl6b7QPqugJlE80KDguwmRC6uivUJDszHbGpq8Y8yrprmqFNa5saYqMyQg"  # Сюда вставить токен сообщества
    GROUP_ID = 236431563  # Сюда вставить ID группы (без минуса)
    # =============================================
    
    # Настройки базы данных
    DB_PATH = Path(__file__).parent / "cyberstreet.db"
    
    # Настройки сокровищ
    TREASURE_ATTEMPTS_PER_PERIOD = 3  # Количество попыток за период
    TREASURE_PERIOD_DAYS = 14  # Период в днях (14 дней)
    
    # Настройки логирования
    LOG_LEVEL = logging.INFO
    LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
    
    # Телефоны и ссылки
    PHONE_CHKALOVA = "+7 (937) 135-85-95"
    PHONE_IKRANOE = "+7 (902) 111-16-90"
    TELEGRAM_LINK = "t.me/cyberstreet30"
    VK_LINK = "vk.com/cyberstreet_30"


# ============================================================================
# МОДЕЛИ ДАННЫХ
# ============================================================================

class Branch(str, Enum):
    """Филиалы клуба (используем Enum для типобезопасности)"""
    CHKALOVA = "chkalova"
    IKRANOE = "ikranoe"
    
    def __str__(self):
        return self.value
    
    @property
    def display_name(self) -> str:
        names = {
            Branch.CHKALOVA: "Астрахань (Чкалова)",
            Branch.IKRANOE: "Икряное"
        }
        return names[self]
    
    @property
    def address(self) -> str:
        addresses = {
            Branch.CHKALOVA: "ул. Чкалова 78а",
            Branch.IKRANOE: "ул. Советская 34"
        }
        return addresses[self]
    
    @property
    def phone(self) -> str:
        phones = {
            Branch.CHKALOVA: Config.PHONE_CHKALOVA,
            Branch.IKRANOE: Config.PHONE_IKRANOE
        }
        return phones[self]


@dataclass
class PriceConfig:
    """Цены на аренду ПК"""
    branch: Branch
    weekday_1h: int
    weekday_3h: int
    weekday_5h: int
    weekend_1h: int
    weekend_3h: int
    weekend_5h: int
    
    @classmethod
    def for_branch(cls, branch: Branch) -> 'PriceConfig':
        """Фабричный метод - создаёт конфиг для конкретного филиала"""
        prices = {
            Branch.CHKALOVA: cls(
                branch=branch,
                weekday_1h=90, weekday_3h=240, weekday_5h=350,
                weekend_1h=100, weekend_3h=270, weekend_5h=370
            ),
            Branch.IKRANOE: cls(
                branch=branch,
                weekday_1h=100, weekday_3h=270, weekday_5h=370,
                weekend_1h=110, weekend_3h=290, weekend_5h=400
            )
        }
        return prices[branch]


@dataclass
class PlayStationPrices:
    """Цены на PlayStation (только для Икряного)"""
    per_hour: int = 250
    three_hours: int = 600
    night: int = 1500  # 22:00 - 08:00
    
    @property
    def night_period(self) -> str:
        return "22:00 - 08:00"


@dataclass
class ComputerSpec:
    """Характеристики компьютера"""
    zone: str
    count: int
    cpu: str
    gpu: str
    ram: Optional[str] = None
    monitor: Optional[str] = None
    keyboard: Optional[str] = None
    mouse: Optional[str] = None
    headset: Optional[str] = None


class PCSpecs:
    """Характеристики компьютеров по филиалам"""
    
    CHKALOVA = [
        ComputerSpec(
            zone="Общий зал",
            count=15,
            cpu="Intel i5-12400F",
            gpu="MSI RTX 3060 / AMD RADEON RX6600",
            monitor="AOC 24″ 165Hz",
            keyboard="Ardor gaming blade",
            mouse="Logitech G102",
            headset="HyperX Stinger 2"
        ),
        ComputerSpec(
            zone="BOOTCAMP",
            count=5,
            cpu="Intel i5-13400F",
            gpu="NVIDIA RTX 3060 Ti",
            monitor="AOC 25″ 240Hz",
            keyboard="Dark Project 5075 (механическая)",
            mouse="Logitech G102",
            headset="HAVIT H2008D"
        )
    ]
    
    IKRANOE = [
        ComputerSpec(
            zone="Общий зал",
            count=17,
            cpu="Intel i5-12400F",
            gpu="GeForce RTX 5060",
            ram="DDR5 16GB",
            monitor="AOC 24″ 180Hz",
            keyboard="Redragon",
            mouse="Logitech G102",
            headset="HyperX Stinger 2"
        ),
        ComputerSpec(
            zone="VIP зал",
            count=5,
            cpu="Intel i5-13400F",
            gpu="GeForce RTX 5060",
            ram="DDR4 32GB",
            monitor="AOC 27″ 240Hz",
            keyboard="Механическая",
            mouse="Logitech G102",
            headset="HyperX Stinger 2"
        )
    ]
    
    @classmethod
    def for_branch(cls, branch: Branch) -> List[ComputerSpec]:
        return cls.CHKALOVA if branch == Branch.CHKALOVA else cls.IKRANOE


@dataclass
class TreasurePrize:
    """Приз из сундука с сокровищами"""
    id: str
    name: str
    description: str
    chance: float  # 0.0 - 1.0
    emoji: str = "🎁"
    
    def format_message(self) -> str:
        return f"{self.emoji} {self.name}\n{self.description}"


class TreasurePrizes:
    """Все доступные призы с весами для рандома"""
    
    _PRIZES = [
        TreasurePrize(
            id="miss",
            name="Мимо!",
            description="Здесь нет сокровищ... Попробуй в другой раз!",
            chance=0.60,
            emoji="😢"
        ),
        TreasurePrize(
            id="cashback_30_small",
            name="КЭШБЭК 30%",
            description="Закидываешь 100₽ → получаешь 130₽ на счёт! 🎉",
            chance=0.25,
            emoji="💰"
        ),
        TreasurePrize(
            id="cashback_50",
            name="Кэшбек 50%",
            description="Пополняй счёт и получай +50% сверху! 💎",
            chance=0.10,
            emoji="💎"
        ),
        TreasurePrize(
            id="cashback_30_big",
            name="КЭШБЭК 30% (БОЛЬШОЙ)",
            description="Закидываешь 300₽ → получаешь 390₽ на счёт! 🏆",
            chance=0.05,
            emoji="🏆"
        )
    ]
    
    @classmethod
    def get_random(cls) -> TreasurePrize:
        """Возвращает случайный приз с учётом шансов"""
        r = random.random()
        cumulative = 0.0
        
        for prize in cls._PRIZES:
            cumulative += prize.chance
            if r < cumulative:
                return prize
        
        return cls._PRIZES[-1]  # fallback


class Games:
    """Список игр"""
    
    LIST = [
        "DOTA 2", "CS2", "PUBG", "Apex Legends",
        "GTA 5", "World of Tanks", "VALORANT", "FORTNITE"
    ]
    
    @classmethod
    def format_list(cls) -> str:
        """Форматирует список игр для вывода"""
        return " • ".join(cls.LIST)


# ============================================================================
# РАБОТА С БАЗОЙ ДАННЫХ
# ============================================================================

class Database:
    """
    Синглтон для работы с SQLite
    Используем паттерн Singleton для единственного подключения к БД
    """
    
    _instance: Optional['Database'] = None
    _connection: Optional[sqlite3.Connection] = None
    
    def __new__(cls) -> 'Database':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self) -> None:
        """Инициализация подключения и создание таблиц"""
        self._connection = sqlite3.connect(
            Config.DB_PATH,
            detect_types=sqlite3.PARSE_DECLTYPES,
            check_same_thread=False  # Важно для VK longpoll
        )
        self._connection.row_factory = sqlite3.Row
        self._create_tables()
    
    def _create_tables(self) -> None:
        """Создание всех необходимых таблиц"""
        with self._connection:
            # Таблица для хранения глобального периода сокровищ
            self._connection.execute("""
                CREATE TABLE IF NOT EXISTS treasure_period (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    period_start TIMESTAMP NOT NULL,
                    period_end TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Пользователи
            self._connection.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    vk_id INTEGER PRIMARY KEY,
                    selected_branch TEXT NOT NULL DEFAULT 'chkalova',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Открытия сокровищ (привязаны к периоду)
            self._connection.execute("""
                CREATE TABLE IF NOT EXISTS treasure_opens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vk_id INTEGER NOT NULL,
                    prize_id TEXT NOT NULL,
                    period_start TIMESTAMP NOT NULL,
                    opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (vk_id) REFERENCES users (vk_id)
                )
            """)
            
            # Индекс для быстрого подсчёта открытий за период
            self._connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_treasure_opens_period 
                ON treasure_opens(vk_id, period_start)
            """)
            
            # Создаём первый период, если его нет
            self._ensure_period_exists()
    
    def _ensure_period_exists(self) -> None:
        """Создаёт первый период сокровищ, если таблица пуста"""
        cursor = self._connection.execute("SELECT COUNT(*) FROM treasure_period")
        if cursor.fetchone()[0] == 0:
            self._create_new_period()
    
    def _create_new_period(self) -> Tuple[datetime, datetime]:
        """Создаёт новый 14-дневный период"""
        now = datetime.now()
        period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        period_end = period_start + timedelta(days=Config.TREASURE_PERIOD_DAYS)
        
        with self._connection:
            self._connection.execute("""
                INSERT OR REPLACE INTO treasure_period (id, period_start, period_end)
                VALUES (1, ?, ?)
            """, (period_start, period_end))
        
        return period_start, period_end
    
    def get_current_period(self) -> Tuple[datetime, datetime]:
        """
        Возвращает текущий период сокровищ.
        Если период истёк, создаёт новый.
        """
        cursor = self._connection.execute("""
            SELECT period_start, period_end FROM treasure_period WHERE id = 1
        """)
        row = cursor.fetchone()
        
        if not row:
            return self._create_new_period()
        
        period_start = datetime.fromisoformat(row['period_start'])
        period_end = datetime.fromisoformat(row['period_end'])
        now = datetime.now()
        
        # Если период истёк - создаём новый
        if now > period_end:
            return self._create_new_period()
        
        return period_start, period_end
    
    def get_period_info(self) -> Dict[str, Any]:
        """Возвращает информацию о текущем периоде"""
        period_start, period_end = self.get_current_period()
        now = datetime.now()
        
        days_left = (period_end - now).days
        hours_left = ((period_end - now).seconds // 3600)
        
        return {
            'start': period_start,
            'end': period_end,
            'days_left': max(0, days_left),
            'hours_left': max(0, hours_left),
            'is_active': now <= period_end
        }
    
    def get_or_create_user(self, vk_id: int) -> sqlite3.Row:
        """Получает пользователя или создаёт нового"""
        with self._connection:
            # Пробуем найти
            cursor = self._connection.execute(
                "SELECT * FROM users WHERE vk_id = ?",
                (vk_id,)
            )
            user = cursor.fetchone()
            
            if user is None:
                # Создаём нового
                self._connection.execute(
                    "INSERT INTO users (vk_id) VALUES (?)",
                    (vk_id,)
                )
                cursor = self._connection.execute(
                    "SELECT * FROM users WHERE vk_id = ?",
                    (vk_id,)
                )
                user = cursor.fetchone()
            else:
                # Обновляем last_seen
                self._connection.execute(
                    "UPDATE users SET last_seen = CURRENT_TIMESTAMP WHERE vk_id = ?",
                    (vk_id,)
                )
            
            return user
    
    def update_user_branch(self, vk_id: int, branch: Branch) -> None:
        """Обновляет выбранный филиал пользователя"""
        with self._connection:
            self._connection.execute(
                "UPDATE users SET selected_branch = ? WHERE vk_id = ?",
                (branch.value, vk_id)
            )
    
    def get_period_opens(self, vk_id: int) -> int:
        """Сколько раз пользователь открывал сундуки в текущем периоде"""
        period_start, _ = self.get_current_period()
        
        with self._connection:
            cursor = self._connection.execute("""
                SELECT COUNT(*) FROM treasure_opens 
                WHERE vk_id = ? AND period_start = ?
            """, (vk_id, period_start.isoformat()))
            
            return cursor.fetchone()[0]
    
    def add_treasure_open(self, vk_id: int, prize_id: str) -> None:
        """Записывает открытие сокровища"""
        period_start, _ = self.get_current_period()
        
        with self._connection:
            self._connection.execute("""
                INSERT INTO treasure_opens (vk_id, prize_id, period_start)
                VALUES (?, ?, ?)
            """, (vk_id, prize_id, period_start.isoformat()))
    
    def get_user_stats(self, vk_id: int) -> Dict[str, int]:
        """Возвращает статистику пользователя за всё время"""
        with self._connection:
            cursor = self._connection.execute("""
                SELECT 
                    COUNT(*) as total_opens,
                    SUM(CASE WHEN prize_id != 'miss' THEN 1 ELSE 0 END) as total_prizes
                FROM treasure_opens 
                WHERE vk_id = ?
            """, (vk_id,))
            
            row = cursor.fetchone()
            if row and row['total_opens']:
                return {
                    'total_opens': row['total_opens'],
                    'total_prizes': row['total_prizes'] or 0
                }
            return {'total_opens': 0, 'total_prizes': 0}
    
    def get_all_users_count(self) -> int:
        """Возвращает общее количество пользователей"""
        with self._connection:
            cursor = self._connection.execute("SELECT COUNT(*) FROM users")
            return cursor.fetchone()[0]
    
    def get_period_stats(self) -> Dict[str, Any]:
        """Возвращает статистику по текущему периоду"""
        period_start, period_end = self.get_current_period()
        
        with self._connection:
            # Всего открытий в периоде
            cursor = self._connection.execute("""
                SELECT 
                    COUNT(*) as total_opens,
                    COUNT(DISTINCT vk_id) as unique_users,
                    SUM(CASE WHEN prize_id != 'miss' THEN 1 ELSE 0 END) as total_prizes
                FROM treasure_opens 
                WHERE period_start = ?
            """, (period_start.isoformat(),))
            
            row = cursor.fetchone()
            
            return {
                'total_opens': row['total_opens'] if row else 0,
                'unique_users': row['unique_users'] if row else 0,
                'total_prizes': row['total_prizes'] or 0,
                'period_start': period_start,
                'period_end': period_end
            }


# ============================================================================
# ФОРМАТТЕРЫ СООБЩЕНИЙ
# ============================================================================

class MessageFormatter:
    """
    Класс для форматирования сообщений
    Используем символы псевдографики для красоты
    """
    
    # Символы для рамок
    BOX = {
        'tl': '╔', 'tr': '╗', 'bl': '╚', 'br': '╝',
        'h': '═', 'v': '║', 'hl': '╠', 'hr': '╣',
        'tm': '╦', 'bm': '╩', 'mm': '╬'
    }
    
    @classmethod
    def _box_line(cls, text: str, width: int = 40, align: str = 'left') -> str:
        """Создаёт строку внутри рамки"""
        text = text[:width-4]  # Обрезаем, если слишком длинное
        if align == 'left':
            return f"{cls.BOX['v']} {text:<{width-3}} {cls.BOX['v']}"
        elif align == 'center':
            return f"{cls.BOX['v']} {text:^{width-3}} {cls.BOX['v']}"
        else:
            return f"{cls.BOX['v']} {text:>{width-3}} {cls.BOX['v']}"
    
    @classmethod
    def _box_header(cls, text: str, width: int = 40) -> str:
        """Создаёт заголовок в рамке"""
        return f"{cls.BOX['tl']}{cls.BOX['h'] * (width-2)}{cls.BOX['tr']}\n" + \
               cls._box_line(text, width, 'center') + "\n" + \
               f"{cls.BOX['hl']}{cls.BOX['h'] * (width-2)}{cls.BOX['hr']}"
    
    @classmethod
    def _box_footer(cls, width: int = 40) -> str:
        """Создаёт подвал рамки"""
        return f"{cls.BOX['bl']}{cls.BOX['h'] * (width-2)}{cls.BOX['br']}"
    
    @classmethod
    def price_list(cls, branch: Branch) -> str:
        """Форматированный прайс-лист"""
        prices = PriceConfig.for_branch(branch)
        width = 44
        
        lines = [
            cls._box_header(f"🎮 CYBERSTREET | {branch.display_name}", width),
            f"{cls.BOX['v']} 📍 {branch.address:<{width-5}} {cls.BOX['v']}",
            cls._box_line("", width),
            cls._box_line("💻 АРЕНДА ПК", width, 'center'),
            cls._box_line("", width),
            cls._box_line("Будние дни:", width),
            cls._box_line(f"  1 час: {prices.weekday_1h:3}₽", width),
            cls._box_line(f"  3 часа: {prices.weekday_3h:3}₽", width),
            cls._box_line(f"  5 часов: {prices.weekday_5h:3}₽", width),
            cls._box_line("", width),
            cls._box_line("Выходные (ПТ-ВС):", width),
            cls._box_line(f"  1 час: {prices.weekend_1h:3}₽", width),
            cls._box_line(f"  3 часа: {prices.weekend_3h:3}₽", width),
            cls._box_line(f"  5 часов: {prices.weekend_5h:3}₽", width)
        ]
        
        # PlayStation только для Икряного
        if branch == Branch.IKRANOE:
            ps = PlayStationPrices()
            lines.extend([
                cls._box_line("", width),
                cls._box_line("🎯 PLAYSTATION", width, 'center'),
                cls._box_line("", width),
                cls._box_line(f"  1 час: {ps.per_hour:3}₽", width),
                cls._box_line(f"  3 часа: {ps.three_hours:3}₽", width),
                cls._box_line(f"  Ночь ({ps.night_period}): {ps.night:3}₽", width)
            ])
        
        lines.append(cls._box_footer(width))
        return "\n".join(lines)
    
    @classmethod
    def pc_specs(cls, branch: Branch) -> str:
        """Характеристики компьютеров"""
        specs = PCSpecs.for_branch(branch)
        width = 48
        lines = [cls._box_header(f"🖥️ КОМПЬЮТЕРЫ | {branch.display_name}", width)]
        
        for spec in specs:
            lines.extend([
                cls._box_line("", width),
                cls._box_line(f"🔥 {spec.zone} ({spec.count} шт.)", width, 'center'),
                cls._box_line(f"  CPU: {spec.cpu}", width),
                cls._box_line(f"  GPU: {spec.gpu}", width),
            ])
            
            if spec.ram:
                lines.append(cls._box_line(f"  RAM: {spec.ram}", width))
            if spec.monitor:
                lines.append(cls._box_line(f"  Монитор: {spec.monitor}", width))
            if spec.keyboard:
                lines.append(cls._box_line(f"  Клавиатура: {spec.keyboard}", width))
            if spec.mouse:
                lines.append(cls._box_line(f"  Мышь: {spec.mouse}", width))
            if spec.headset:
                lines.append(cls._box_line(f"  Гарнитура: {spec.headset}", width))
        
        lines.append(cls._box_footer(width))
        return "\n".join(lines)
    
    @classmethod
    def games_list(cls) -> str:
        """Список игр"""
        width = 44
        games_str = Games.format_list()
        
        # Разбиваем на строки по 35 символов
        line_length = 35
        games_lines = []
        current = ""
        
        for word in games_str.split(" • "):
            if len(current) + len(word) + 3 > line_length:
                games_lines.append(current)
                current = word
            else:
                if current:
                    current += " • " + word
                else:
                    current = word
        if current:
            games_lines.append(current)
        
        lines = [cls._box_header("🎮 ДОСТУПНЫЕ ИГРЫ", width)]
        lines.append(cls._box_line("", width))
        
        for game_line in games_lines:
            lines.append(cls._box_line(game_line, width, 'center'))
        
        lines.extend([
            cls._box_line("", width),
            cls._box_line("❓ Не нашли игру?", width, 'center'),
            cls._box_line("Напишите нам - установим!", width, 'center'),
            cls._box_footer(width)
        ])
        
        return "\n".join(lines)
    
    @classmethod
    def contacts(cls) -> str:
        """Контакты и адреса"""
        width = 44
        lines = [
            cls._box_header("📞 КОНТАКТЫ", width),
            cls._box_line("", width),
            cls._box_line("📍 Астрахань (Чкалова)", width),
            cls._box_line(f"   {Branch.CHKALOVA.address}", width),
            cls._box_line(f"   📱 {Config.PHONE_CHKALOVA}", width),
            cls._box_line("", width),
            cls._box_line("📍 Икряное", width),
            cls._box_line(f"   {Branch.IKRANOE.address}", width),
            cls._box_line(f"   📱 {Config.PHONE_IKRANOE}", width),
            cls._box_line("", width),
            cls._box_line("⏰ Работаем: 24/7", width, 'center'),
            cls._box_line("", width),
            cls._box_line(f"📫 Telegram: {Config.TELEGRAM_LINK}", width),
            cls._box_line(f"   VK: {Config.VK_LINK}", width),
            cls._box_footer(width)
        ]
        return "\n".join(lines)
    
    @classmethod
    def treasure_info(cls, attempts_used: int, attempts_left: int, period_info: Dict[str, Any], stats: Dict[str, int]) -> str:
        """Информация о сокровищах"""
        width = 44
        days_left = period_info['days_left']
        hours_left = period_info['hours_left']
        
        lines = [
            cls._box_header("🏴‍☠️ СОКРОВИЩА КЛУБА", width),
            cls._box_line("", width),
            cls._box_line(f"📅 Период: {Config.TREASURE_PERIOD_DAYS} дней", width),
            cls._box_line(f"⏳ До конца периода:", width),
            cls._box_line(f"   {days_left} дн {hours_left:02d} ч", width, 'center'),
            cls._box_line("", width),
            cls._box_line(f"🎯 Попытки в периоде:", width),
            cls._box_line(f"   Использовано: {attempts_used}/3", width),
            cls._box_line(f"   Осталось: {attempts_left}/3", width),
            cls._box_line("", width),
            cls._box_line(f"📊 Твоя статистика:", width),
            cls._box_line(f"   Всего открыто: {stats['total_opens']}", width),
            cls._box_line(f"   Призов получено: {stats['total_prizes']}", width),
            cls._box_line("", width),
            cls._box_line("🎁 Шансы на призы:", width),
            cls._box_line("   60% - мимо", width),
            cls._box_line("   25% - кэшбек 30% (100→130₽)", width),
            cls._box_line("   10% - кэшбек 50%", width),
            cls._box_line("   5% - кэшбек 30% (300→390₽)", width),
            cls._box_footer(width)
        ]
        
        return "\n".join(lines)
    
    @classmethod
    def treasure_result(cls, prize: TreasurePrize, attempts_left: int, period_info: Dict[str, Any], stats: Dict[str, int]) -> str:
        """Результат открытия сокровища"""
        width = 44
        lines = [cls._box_header("🏴‍☠️ СОКРОВИЩЕ ОТКРЫТО", width)]
        
        if prize.id != "miss":
            lines.extend([
                cls._box_line("", width),
                cls._box_line("🎉 ПОЗДРАВЛЯЕМ! 🎉", width, 'center'),
            ])
        
        lines.extend([
            cls._box_line("", width),
            cls._box_line(f"{prize.emoji} {prize.name}", width, 'center'),
            cls._box_line(prize.description[:width-6], width, 'center'),
            cls._box_line("", width),
            cls._box_line(f"Осталось попыток: {attempts_left}/3", width),
            cls._box_line("", width),
            cls._box_line(f"До конца периода:", width),
            cls._box_line(f"{period_info['days_left']} дн {period_info['hours_left']:02d} ч", width, 'center'),
            cls._box_line("", width),
            cls._box_line(f"Всего открыто: {stats['total_opens']}", width),
            cls._box_line(f"Призов получено: {stats['total_prizes']}", width),
            cls._box_footer(width)
        ])
        
        return "\n".join(lines)
    
    @classmethod
    def no_attempts(cls, period_info: Dict[str, Any]) -> str:
        """Нет попыток в этом периоде"""
        width = 44
        lines = [
            cls._box_header("😴 ПОПЫТКИ ЗАКОНЧИЛИСЬ", width),
            cls._box_line("", width),
            cls._box_line("Ты уже открыл все 3 сундука", width, 'center'),
            cls._box_line("в этом 14-дневном периоде.", width, 'center'),
            cls._box_line("", width),
            cls._box_line("Следующий период начнётся:", width, 'center'),
            cls._box_line(f"через {period_info['days_left']} дн {period_info['hours_left']:02d} ч", width, 'center'),
            cls._box_line("", width),
            cls._box_line("Следи за обновлениями!", width, 'center'),
            cls._box_footer(width)
        ]
        return "\n".join(lines)
    
    @classmethod
    def period_reset_notification(cls, period_info: Dict[str, Any]) -> str:
        """Уведомление о сбросе периода"""
        width = 44
        lines = [
            cls._box_header("🔄 НОВЫЙ ПЕРИОД СОКРОВИЩ", width),
            cls._box_line("", width),
            cls._box_line("Внимание! Начался новый", width, 'center'),
            cls._box_line("14-дневный период!", width, 'center'),
            cls._box_line("", width),
            cls._box_line("У тебя снова есть 3 попытки", width, 'center'),
            cls._box_line("открыть сокровища! 🎁", width, 'center'),
            cls._box_line("", width),
            cls._box_line("Заходи и испытай удачу!", width, 'center'),
            cls._box_footer(width)
        ]
        return "\n".join(lines)


# ============================================================================
# КЛАВИАТУРЫ
# ============================================================================

class KeyboardBuilder:
    """Билдер для клавиатур VK"""
    
    @staticmethod
    def main_menu() -> str:
        """Главное меню"""
        kb = VkKeyboard(one_time=False, inline=False)
        
        # Первая строка
        kb.add_button("🎮 Аренда ПК", VkKeyboardColor.PRIMARY)
        kb.add_button("🎯 PlayStation", VkKeyboardColor.PRIMARY)
        kb.add_line()
        
        # Вторая строка
        kb.add_button("💰 Цены", VkKeyboardColor.SECONDARY)
        kb.add_button("🏆 Сокровища", VkKeyboardColor.POSITIVE)
        kb.add_line()
        
        # Третья строка
        kb.add_button("🖥️ Характеристики ПК", VkKeyboardColor.SECONDARY)
        kb.add_button("🎮 Список игр", VkKeyboardColor.SECONDARY)
        kb.add_line()
        
        # Четвёртая строка
        kb.add_button("📍 Филиалы", VkKeyboardColor.PRIMARY)
        kb.add_button("📞 Контакты", VkKeyboardColor.SECONDARY)
        
        return kb.get_keyboard()
    
    @staticmethod
    def branches_menu() -> str:
        """Меню выбора филиала"""
        kb = VkKeyboard(one_time=False, inline=False)
        
        kb.add_button("📍 Чкалова 78а", VkKeyboardColor.PRIMARY)
        kb.add_button("📍 Икряное", VkKeyboardColor.PRIMARY)
        kb.add_line()
        kb.add_button("🔙 Назад", VkKeyboardColor.SECONDARY)
        
        return kb.get_keyboard()
    
    @staticmethod
    def back_button() -> str:
        """Только кнопка назад"""
        kb = VkKeyboard(one_time=False, inline=False)
        kb.add_button("🔙 Назад в меню", VkKeyboardColor.SECONDARY)
        return kb.get_keyboard()
    
    @staticmethod
    def treasure_menu(attempts_left: int) -> str:
        """Меню сокровищ с отображением попыток"""
        kb = VkKeyboard(one_time=False, inline=False)
        
        btn_text = f"🏆 Открыть сундук ({attempts_left}/3)"
        kb.add_button(btn_text, VkKeyboardColor.POSITIVE)
        kb.add_line()
        kb.add_button("🔙 Назад", VkKeyboardColor.SECONDARY)
        
        return kb.get_keyboard()


# ============================================================================
# ОСНОВНОЙ БОТ
# ============================================================================

class CyberStreetBot:
    """Основной класс бота"""
    
    def __init__(self):
        """Инициализация бота"""
        self._setup_logging()
        self.logger = logging.getLogger(__name__)
        
        self.logger.info("Инициализация бота CyberStreet...")
        
        # Проверяем конфигурацию
        self._validate_config()
        
        # Инициализируем VK
        self.vk_session = vk_api.VkApi(token=Config.VK_TOKEN)
        self.vk = self.vk_session.get_api()
        self.longpoll = VkBotLongPoll(self.vk_session, Config.GROUP_ID)
        
        # База данных
        self.db = Database()
        
        # Кэш последнего проверенного периода
        self.last_period_check = None
        self.current_period_end = None
        
        # Маппинг текстовых команд
        self.text_commands = {
            'начать': self._cmd_start,
            'старт': self._cmd_start,
            'меню': self._cmd_main_menu,
            'назад': self._cmd_main_menu,
            'главное меню': self._cmd_main_menu,
        }
        
        self.logger.info("Бот успешно инициализирован")
    
    def _setup_logging(self) -> None:
        """Настройка логирования"""
        logging.basicConfig(
            level=Config.LOG_LEVEL,
            format=Config.LOG_FORMAT,
            datefmt=Config.LOG_DATE_FORMAT
        )
    
    def _validate_config(self) -> None:
        """Проверка конфигурации"""
        if Config.VK_TOKEN == "vk1.a.example_token":
            self.logger.error("❌ ТОКЕН НЕ НАСТРОЕН! Вставьте свой токен в Config.VK_TOKEN")
            raise ValueError("VK_TOKEN не настроен")
        
        if Config.GROUP_ID == 123456789:
            self.logger.error("❌ ID ГРУППЫ НЕ НАСТРОЕН! Вставьте свой ID в Config.GROUP_ID")
            raise ValueError("GROUP_ID не настроен")
        
        self.logger.info(f"✓ Бот настроен для группы {Config.GROUP_ID}")
        self.logger.info(f"✓ Период сокровищ: {Config.TREASURE_PERIOD_DAYS} дней")
        self.logger.info(f"✓ Попыток за период: {Config.TREASURE_ATTEMPTS_PER_PERIOD}")
    
    def _send_message(
        self, 
        peer_id: int, 
        message: str, 
        keyboard: Optional[str] = None,
        attachment: Optional[str] = None
    ) -> bool:
        """
        Отправка сообщения с обработкой ошибок
        
        Args:
            peer_id: ID получателя
            message: Текст сообщения
            keyboard: Клавиатура (JSON строка)
            attachment: Вложения
        
        Returns:
            bool: Успешно ли отправлено
        """
        try:
            params = {
                'peer_id': peer_id,
                'message': message,
                'random_id': get_random_id()
            }
            
            if keyboard:
                params['keyboard'] = keyboard
            if attachment:
                params['attachment'] = attachment
            
            self.vk.messages.send(**params)
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка отправки сообщения: {e}", exc_info=True)
            return False
    
    def _check_period_reset(self) -> bool:
        """
        Проверяет, не начался ли новый период
        Возвращает True, если период только что сбросился
        """
        period_info = self.db.get_period_info()
        
        # Если это первая проверка
        if self.current_period_end is None:
            self.current_period_end = period_info['end']
            return False
        
        # Если период изменился
        if period_info['end'] != self.current_period_end:
            self.logger.info(f"🔄 Начался новый период сокровищ! Действует до {period_info['end']}")
            self.current_period_end = period_info['end']
            return True
        
        return False
    
    def run(self) -> None:
        """Запуск бота (основной цикл)"""
        self.logger.info("🚀 Бот запущен и ожидает сообщения...")
        
        # Проверяем период при старте
        period_info = self.db.get_period_info()
        self.current_period_end = period_info['end']
        self.logger.info(f"📅 Текущий период сокровищ до: {period_info['end']}")
        
        last_period_check = datetime.now()
        
        while True:
            try:
                # Проверяем сброс периода раз в час
                now = datetime.now()
                if (now - last_period_check).seconds > 3600:
                    if self._check_period_reset():
                        # Можно добавить рассылку уведомлений всем пользователям
                        self.logger.info("🔄 Период сокровищ сброшен!")
                    last_period_check = now
                
                for event in self.longpoll.listen():
                    if event.type == VkBotEventType.MESSAGE_NEW:
                        self._handle_message(event)
                    
            except Exception as e:
                self.logger.error(f"Критическая ошибка в цикле: {e}", exc_info=True)
                time.sleep(5)  # Пауза перед перезапуском
    
    def _handle_message(self, event: VkBotEventType) -> None:
        """Обработка входящего сообщения"""
        try:
            message = event.object['message']
            user_id = message['from_id']
            text = message['text'].strip()
            peer_id = message['peer_id']
            
            # Получаем пользователя
            user = self.db.get_or_create_user(user_id)
            selected_branch = Branch(user['selected_branch'])
            
            self.logger.info(f"Сообщение от {user_id} ({selected_branch}): {text[:50]}")
            
            # Проверяем точное совпадение с командами
            text_lower = text.lower()
            
            if text_lower in self.text_commands:
                self.text_commands[text_lower](user_id, peer_id, user)
                return
            
            # Обработка кнопок по тексту (эмодзи + текст)
            if "аренда пк" in text_lower or "🎮 аренда" in text_lower:
                self._cmd_pc_rent(user_id, peer_id, user)
            elif "playstation" in text_lower or "🎯" in text_lower:
                self._cmd_playstation(user_id, peer_id, user)
            elif "цены" in text_lower or "💰" in text_lower:
                self._cmd_prices(user_id, peer_id, user)
            elif "сокровища" in text_lower or "🏆" in text_lower:
                self._cmd_treasure(user_id, peer_id, user)
            elif "характеристики" in text_lower or "🖥️" in text_lower:
                self._cmd_specs(user_id, peer_id, user)
            elif "список игр" in text_lower or "игры" in text_lower or "🎮" in text_lower:
                self._cmd_games(user_id, peer_id, user)
            elif "филиалы" in text_lower or "📍" in text_lower:
                self._cmd_branches(user_id, peer_id, user)
            elif "контакты" in text_lower or "📞" in text_lower:
                self._cmd_contacts(user_id, peer_id, user)
            elif "чкалова" in text_lower:
                self._cmd_select_branch(user_id, peer_id, Branch.CHKALOVA)
            elif "икряное" in text_lower:
                self._cmd_select_branch(user_id, peer_id, Branch.IKRANOE)
            elif "открыть сундук" in text_lower:
                self._cmd_open_treasure(user_id, peer_id, user)
            else:
                self._send_message(
                    peer_id,
                    "🤖 Я не понял команду. Вот главное меню:",
                    KeyboardBuilder.main_menu()
                )
                
        except Exception as e:
            self.logger.error(f"Ошибка обработки сообщения: {e}", exc_info=True)
            self._send_message(
                peer_id,
                "❌ Произошла ошибка. Попробуйте позже.",
                KeyboardBuilder.main_menu()
            )
    
    # ========== ОБРАБОТЧИКИ КОМАНД ==========
    
    def _cmd_start(self, user_id: int, peer_id: int, user: sqlite3.Row) -> None:
        """Команда /start"""
        welcome = (
            "👋 Добро пожаловать в CyberStreet!\n\n"
            "Я официальный бот киберклуба. Помогу с ценами, "
            "расскажу о компьютерах и даже подарю сокровища! 🎁\n\n"
            "Выберите филиал:"
        )
        self._send_message(peer_id, welcome, KeyboardBuilder.branches_menu())
    
    def _cmd_main_menu(self, user_id: int, peer_id: int, user: sqlite3.Row) -> None:
        """Возврат в главное меню"""
        branch = Branch(user['selected_branch'])
        self._send_message(
            peer_id,
            f"📍 Текущий филиал: {branch.display_name}",
            KeyboardBuilder.main_menu()
        )
    
    def _cmd_pc_rent(self, user_id: int, peer_id: int, user: sqlite3.Row) -> None:
        """Аренда ПК"""
        branch = Branch(user['selected_branch'])
        prices = PriceConfig.for_branch(branch)
        
        msg = (
            f"💻 Аренда ПК | {branch.display_name}\n\n"
            f"Будние дни:\n"
            f"• 1 час: {prices.weekday_1h}₽\n"
            f"• 3 часа: {prices.weekday_3h}₽\n"
            f"• 5 часов: {prices.weekday_5h}₽\n\n"
            f"Выходные (ПТ-ВС):\n"
            f"• 1 час: {prices.weekend_1h}₽\n"
            f"• 3 часа: {prices.weekend_3h}₽\n"
            f"• 5 часов: {prices.weekend_5h}₽"
        )
        
        self._send_message(peer_id, msg, KeyboardBuilder.back_button())
    
    def _cmd_playstation(self, user_id: int, peer_id: int, user: sqlite3.Row) -> None:
        """PlayStation (только Икряное)"""
        branch = Branch(user['selected_branch'])
        
        if branch != Branch.IKRANOE:
            msg = (
                "🎯 PlayStation доступен только в филиале Икряное!\n\n"
                "📍 Адрес: ул. Советская 34\n"
                f"📱 Телефон: {Config.PHONE_IKRANOE}"
            )
            self._send_message(peer_id, msg, KeyboardBuilder.back_button())
            return
        
        ps = PlayStationPrices()
        msg = (
            "🎯 PLAYSTATION | Икряное\n\n"
            f"• 1 час: {ps.per_hour}₽\n"
            f"• 3 часа: {ps.three_hours}₽\n"
            f"• Ночь ({ps.night_period}): {ps.night}₽"
        )
        
        self._send_message(peer_id, msg, KeyboardBuilder.back_button())
    
    def _cmd_prices(self, user_id: int, peer_id: int, user: sqlite3.Row) -> None:
        """Полный прайс-лист"""
        branch = Branch(user['selected_branch'])
        msg = MessageFormatter.price_list(branch)
        self._send_message(peer_id, msg, KeyboardBuilder.back_button())
    
    def _cmd_treasure(self, user_id: int, peer_id: int, user: sqlite3.Row) -> None:
        """Меню сокровищ"""
        attempts_used = self.db.get_period_opens(user_id)
        attempts_left = max(0, Config.TREASURE_ATTEMPTS_PER_PERIOD - attempts_used)
        period_info = self.db.get_period_info()
        stats = self.db.get_user_stats(user_id)
        
        msg = MessageFormatter.treasure_info(attempts_used, attempts_left, period_info, stats)
        
        if attempts_left > 0:
            keyboard = KeyboardBuilder.treasure_menu(attempts_left)
        else:
            keyboard = KeyboardBuilder.back_button()
        
        self._send_message(peer_id, msg, keyboard)
    
    def _cmd_open_treasure(self, user_id: int, peer_id: int, user: sqlite3.Row) -> None:
        """Открыть сокровище"""
        attempts_used = self.db.get_period_opens(user_id)
        
        if attempts_used >= Config.TREASURE_ATTEMPTS_PER_PERIOD:
            period_info = self.db.get_period_info()
            self._send_message(peer_id, MessageFormatter.no_attempts(period_info), KeyboardBuilder.main_menu())
            return
        
        # Получаем приз
        prize = TreasurePrizes.get_random()
        
        # Записываем в БД
        self.db.add_treasure_open(user_id, prize.id)
        
        # Статистика
        stats = self.db.get_user_stats(user_id)
        period_info = self.db.get_period_info()
        
        # Оставшиеся попытки
        attempts_left = Config.TREASURE_ATTEMPTS_PER_PERIOD - (attempts_used + 1)
        
        # Отправляем результат
        msg = MessageFormatter.treasure_result(prize, attempts_left, period_info, stats)
        keyboard = KeyboardBuilder.treasure_menu(attempts_left)
        
        self._send_message(peer_id, msg, keyboard)
        
        self.logger.info(f"Пользователь {user_id} открыл сундук: {prize.id}")
    
    def _cmd_specs(self, user_id: int, peer_id: int, user: sqlite3.Row) -> None:
        """Характеристики ПК"""
        branch = Branch(user['selected_branch'])
        msg = MessageFormatter.pc_specs(branch)
        self._send_message(peer_id, msg, KeyboardBuilder.back_button())
    
    def _cmd_games(self, user_id: int, peer_id: int, user: sqlite3.Row) -> None:
        """Список игр"""
        msg = MessageFormatter.games_list()
        self._send_message(peer_id, msg, KeyboardBuilder.back_button())
    
    def _cmd_branches(self, user_id: int, peer_id: int, user: sqlite3.Row) -> None:
        """Меню выбора филиала"""
        self._send_message(
            peer_id,
            "📍 Выберите филиал:",
            KeyboardBuilder.branches_menu()
        )
    
    def _cmd_select_branch(self, user_id: int, peer_id: int, branch: Branch) -> None:
        """Выбор филиала"""
        self.db.update_user_branch(user_id, branch)
        
        msg = (
            f"✅ Филиал {branch.display_name} выбран!\n\n"
            f"📍 Адрес: {branch.address}\n"
            f"📱 Телефон: {branch.phone}"
        )
        
        self._send_message(peer_id, msg, KeyboardBuilder.main_menu())
    
    def _cmd_contacts(self, user_id: int, peer_id: int, user: sqlite3.Row) -> None:
        """Контакты"""
        msg = MessageFormatter.contacts()
        self._send_message(peer_id, msg, KeyboardBuilder.back_button())


# ============================================================================
# ТОЧКА ВХОДА
# ============================================================================

if __name__ == "__main__":
    try:
        bot = CyberStreetBot()
        bot.run()
    except KeyboardInterrupt:
        logging.info("👋 Бот остановлен пользователем")
    except Exception as e:
        logging.error(f"💥 Фатальная ошибка: {e}", exc_info=True)
        raise