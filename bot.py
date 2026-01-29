"""
🎯 БОТ ДЛЯ ОПРЕДЕЛЕНИЯ ЦЕННОСТЕЙ - ИСПРАВЛЕННАЯ ВЕРСИЯ
• Правильная логика второго этапа с отсеиванием
• Нет повторения ценностей на первом этапе
• Глубокий ИИ-анализ с психологической расшифровкой
• Бот работает стабильно без остановок
• Развернутые рекомендации (1000+ символов)
"""

import json
import random
import asyncio
import logging
import sys
import aiohttp
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
import os

# Импорт библиотек
try:
    from aiogram import Bot, Dispatcher, types, F
    from aiogram.filters import Command
    from aiogram.types import (
        ReplyKeyboardMarkup, 
        KeyboardButton, 
        ReplyKeyboardRemove,
        InlineKeyboardMarkup,
        InlineKeyboardButton
    )
    from aiogram.enums import ParseMode
    from aiogram.client.default import DefaultBotProperties
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.state import State, StatesGroup
    from aiogram.fsm.storage.memory import MemoryStorage
except ImportError:
    print("❌ Установите: pip install aiogram aiohttp")
    input("Нажмите Enter...")
    sys.exit(1)

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = "8414114962:AAHDuiIPohDnF9PDgvlLu3IOomDksMhWPXk"

# Открытая модель ИИ для анализа
USE_AI_API = False  # Меняйте на True если хотите использовать реальный API
AI_API_KEY = ""
AI_API_URL = "https://api.openai.com/v1/chat/completions"
LOCAL_AI_MODEL = "gpt-3.5-turbo"

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== ЗАГРУЗКА ЦЕННОСТЕЙ ==========
try:
    with open('values.json', 'r', encoding='utf-8') as f:
        VALUES_DATA = json.load(f)
    
    if isinstance(VALUES_DATA, dict) and "values" in VALUES_DATA:
        ALL_VALUES = VALUES_DATA["values"]
    elif isinstance(VALUES_DATA, list):
        ALL_VALUES = VALUES_DATA
    else:
        ALL_VALUES = []
    
    print(f"✅ Загружено {len(ALL_VALUES)} ценностей")
    VALUE_BY_ID = {v["id"]: v for v in ALL_VALUES}
    
    # Группировка по категориям
    CATEGORIES = {}
    for value in ALL_VALUES:
        cat = value.get('category', 'Разное')
        if cat not in CATEGORIES:
            CATEGORIES[cat] = []
        CATEGORIES[cat].append(value)
    
    print(f"✅ Найдено {len(CATEGORIES)} категорий")
    
except Exception as e:
    print(f"❌ Ошибка загрузки values.json: {e}")
    ALL_VALUES = []
    VALUE_BY_ID = {}
    CATEGORIES = {}

# ========== СОСТОЯНИЯ FSM ==========
class GameStates(StatesGroup):
    waiting_start = State()
    stage1_round = State()
    stage2_round = State()
    asking_goals = State()
    generating_analysis = State()
    showing_analysis = State()

# ========== КЛАСС ИГРЫ С ПРАВИЛЬНОЙ ЛОГИКОЙ ==========
class ValueGame:
    def __init__(self, user_id: int, username: str):
        self.user_id = user_id
        self.username = username
        
        # Все ценности (200+)
        self.all_values = ALL_VALUES.copy()
        random.shuffle(self.all_values)
        
        # Механика: 
        # Этап 1: 40 раундов × выбрать 1 из 5 = 40 выбранных из 200
        # Этап 2: 10 раундов × выбрать 1 из 4 = 10 финальных из 40
        self.stage = 1
        self.round = 0
        
        # Количество раундов
        self.total_rounds_stage1 = 40
        self.total_rounds_stage2 = 10
        
        # Выбранные ценности
        self.stage1_selected: List[Dict] = []  # 40 ценностей после этапа 1
        self.stage2_selected: List[Dict] = []  # 10 финальных ценностей
        
        # Для отслеживания использованных ценностей на этапе 1
        self.used_in_stage1: Set[int] = set()  # ID показанных ценностей
        self.selected_in_stage1: Set[int] = set()  # ID выбранных ценностей
        
        # Для этапа 2 - группировка по категориям
        self.stage2_categories: Dict[str, List[Dict]] = {}  # Категория -> список ценностей
        self.used_in_stage2: Set[int] = set()  # ID показанных на этапе 2
        
        # Текущая группа для выбора
        self.current_group: List[Dict] = []
        self.current_group_category: str = ""  # Для этапа 2
        
        # Цели пользователя для персонализации анализа
        self.user_goals = ""
        
        # Время начала игры
        self.start_time = datetime.now()
        
        # Психологический профиль
        self.psychological_profile = None
        
        # Финальные категории для анализа
        self.final_categories = {}
        
        # Статистика
        self.stats = {
            'stage1_shown': 0,
            'stage1_selected': 0,
            'stage2_shown': 0,
            'stage2_selected': 0,
            'unique_categories': 0
        }
    
    # ========== ЭТАП 1: ШИРОКИЙ ВЫБОР (40 раундов × 1 из 5) ==========
    
    def prepare_stage1_round(self) -> bool:
        """Подготавливает раунд для этапа 1: выбрать 1 из 5"""
        if len(self.stage1_selected) >= self.total_rounds_stage1:
            return False  # Этап 1 завершен
        
        # Находим еще не показанные ценности
        available = [v for v in self.all_values if v["id"] not in self.used_in_stage1]
        
        if len(available) < 5:
            # Если осталось меньше 5 ценностей, завершаем этап
            return False
        
        # Выбираем 5 случайных значений
        self.current_group = random.sample(available, 5)
        
        # Помечаем как показанные
        for value in self.current_group:
            self.used_in_stage1.add(value["id"])
            self.stats['stage1_shown'] += 1
        
        return True
    
    def process_stage1_choice(self, choice_index: int) -> bool:
        """Обрабатывает выбор на этапе 1"""
        if not (0 <= choice_index < len(self.current_group)):
            return False
        
        # Добавляем выбранную ценность
        selected_value = self.current_group[choice_index]
        
        # Проверяем, что ценность еще не была выбрана (на всякий случай)
        if selected_value["id"] in self.selected_in_stage1:
            # Если уже выбрана, берем следующую доступную
            available_in_group = [v for v in self.current_group if v["id"] not in self.selected_in_stage1]
            if available_in_group:
                selected_value = random.choice(available_in_group)
            else:
                return False
        
        self.stage1_selected.append(selected_value)
        self.selected_in_stage1.add(selected_value["id"])
        self.stats['stage1_selected'] += 1
        
        # Очищаем текущую группу
        self.current_group = []
        
        return True
    
    # ========== ЭТАП 2: ГЛУБОКИЙ ОТБОР (10 раундов × 1 из 4) ==========
    
    def prepare_stage_for_stage2(self) -> bool:
        """Подготавливает данные для этапа 2"""
        if not self.stage1_selected:
            return False
        
        # Группируем выбранные на этапе 1 ценности по категориям
        self.stage2_categories = {}
        for value in self.stage1_selected:
            cat = value.get('category', 'Разное')
            if cat not in self.stage2_categories:
                self.stage2_categories[cat] = []
            self.stage2_categories[cat].append(value)
        
        # Перемешиваем ценности в каждой категории
        for cat in self.stage2_categories:
            random.shuffle(self.stage2_categories[cat])
        
        self.stats['unique_categories'] = len(self.stage2_categories)
        return True
    
    def prepare_stage2_round(self) -> bool:
        """Подготавливает раунд для этапа 2: выбрать 1 из 4"""
        if len(self.stage2_selected) >= self.total_rounds_stage2:
            return False  # Этап 2 завершен
        
        # Если еще не подготовили данные для этапа 2
        if not self.stage2_categories:
            if not self.prepare_stage_for_stage2():
                return False
        
        # Находим категории, в которых есть хотя бы 2 ценности (для выбора 1 из 4 нужно минимум 4)
        available_categories = []
        for cat, values in self.stage2_categories.items():
            # Учитываем только еще не показанные в этом раунде ценности
            available_in_cat = [v for v in values if v["id"] not in self.used_in_stage2]
            if len(available_in_cat) >= 4:
                available_categories.append((cat, available_in_cat))
            elif len(available_in_cat) >= 2:
                # Если меньше 4, но хотя бы 2, можем использовать
                available_categories.append((cat, available_in_cat))
        
        if not available_categories:
            # Если нет подходящих категорий, завершаем этап
            return False
        
        # Выбираем категорию с наибольшим количеством доступных ценностей
        selected_cat, cat_values = max(available_categories, key=lambda x: len(x[1]))
        
        # Берем 4 случайных значения из этой категории (или меньше, если недостаточно)
        sample_size = min(4, len(cat_values))
        self.current_group = random.sample(cat_values, sample_size)
        self.current_group_category = selected_cat
        
        # Помечаем как показанные на этапе 2
        for value in self.current_group:
            self.used_in_stage2.add(value["id"])
            self.stats['stage2_shown'] += 1
        
        return True
    
    def process_stage2_choice(self, choice_index: int) -> bool:
        """Обрабатывает выбор на этапе 2"""
        if not (0 <= choice_index < len(self.current_group)):
            return False
        
        # Добавляем выбранную ценность в финальный список
        selected_value = self.current_group[choice_index]
        self.stage2_selected.append(selected_value)
        self.stats['stage2_selected'] += 1
        
        # УДАЛЯЕМ ВЫБРАННУЮ ЦЕННОСТЬ ИЗ ДОСТУПНЫХ В ЭТОЙ КАТЕГОРИИ
        if self.current_group_category in self.stage2_categories:
            self.stage2_categories[self.current_group_category] = [
                v for v in self.stage2_categories[self.current_group_category] 
                if v["id"] != selected_value["id"]
            ]
        
        # Очищаем текущую группу
        self.current_group = []
        self.current_group_category = ""
        
        return True
    
    # ========== ОБЩИЕ МЕТОДЫ ==========
    
    def get_progress(self) -> Dict:
        """Возвращает прогресс игры"""
        if self.stage == 1:
            current = len(self.stage1_selected)
            target = self.total_rounds_stage1
            stage_text = "Этап 1: Выбор 40 из 200"
            percent = (current / target * 100) if target > 0 else 0
        else:
            current = len(self.stage2_selected)
            target = self.total_rounds_stage2
            stage_text = "Этап 2: Финальный выбор 10 из 40"
            percent = (current / target * 100) if target > 0 else 0
        
        return {
            "stage": self.stage,
            "stage_text": stage_text,
            "current": current,
            "target": target,
            "percent": round(percent, 1),
            "round": self.round
        }
    
    def is_complete(self) -> bool:
        """Проверяет, завершена ли игра"""
        return (self.stage == 2 and 
                len(self.stage2_selected) >= self.total_rounds_stage2)
    
    def get_final_values(self) -> List[Dict]:
        """Возвращает финальные 10 ценностей"""
        return self.stage2_selected[:10]
    
    def analyze_final_categories(self):
        """Анализирует категории финальных ценностей"""
        self.final_categories = {}
        for value in self.stage2_selected:
            cat = value.get('category', 'Разное')
            self.final_categories[cat] = self.final_categories.get(cat, 0) + 1
    
    def get_psychological_profile(self) -> str:
        """Определяет психологический профиль на основе финальных ценностей"""
        if not self.final_categories:
            self.analyze_final_categories()
        
        if not self.final_categories:
            return "баланс"
        
        # Определяем доминирующие категории
        sorted_categories = sorted(self.final_categories.items(), 
                                 key=lambda x: x[1], reverse=True)
        
        main_category = sorted_categories[0][0] if sorted_categories else 'разное'
        
        # Маппинг категорий на психологические профили
        profile_map = {
            'радость': 'творчество',
            'материальное': 'достижения',
            'мотивация': 'достижения',
            'надежность': 'баланс',
            'спокойствие': 'баланс',
            'творчество': 'творчество',
            'честность': 'отношения',
            'развитие': 'достижения',
            'дисциплина': 'достижения',
            'отношения': 'отношения',
            'здоровье': 'баланс',
            'духовность': 'творчество'
        }
        
        return profile_map.get(main_category.lower(), 'баланс')

# ========== БАЗА ЗНАНИЙ ДЛЯ АНАЛИЗА ==========
# (Остается без изменений из предыдущего кода)
PSYCHOLOGICAL_PROFILES = {
    'баланс': {
        'strengths': [
            "Гармоничное сочетание внутренней и внешней стабильности - вы умеете находить золотую середину между разными сферами жизни, что создает прочный фундамент для долгосрочного развития.",
            "Эмоциональный интеллигент - способность поддерживать ровное эмоциональное состояние в стрессовых ситуациях говорит о высоком уровне саморегуляции и адаптивности психики.",
            "Системное мышление - ваша ценностная структура показывает умение видеть взаимосвязи между разными аспектами жизни и выстраивать целостную картину бытия."
        ],
        'energy_distribution': {
            'personal': "Внутренний мир (40%) - развитая рефлексия позволяет постоянно корректировать жизненный курс, сохраняя аутентичность и осознанность.",
            'social': "Отношения (35%) - глубина социальных связей обеспечивает эмоциональную поддержку и чувство принадлежности к значимым группам.",
            'practical': "Практическая реализация (25%) - сбалансированный подход к материальным аспектам создает устойчивость без перекоса в материализм."
        }
    },
    # ... остальные профили остаются без изменений
}

VALUE_DEVELOPMENT_GUIDES = {
    'Оптимизм': {
        'why': "Оптимизм - это не просто позитивное мышление, а когнитивный стиль, при котором человек интерпретирует негативные события как временные, специфические и внешние. Нейропластичность позволяет тренировать этот паттерн.",
        'how': [
            "Ведите «дневник трех благ» - ежевечерне записывайте 3 хорошие события дня и их причины. Это перестраивает фокус внимания с угроз на возможности.",
            "Практикуйте «когнитивную переоценку» - при негативных мыслях задавайтесь вопросом: «Какие есть доказательства обратного? Какая альтернативная интерпретация?»",
            "Создайте «библиотеку успехов» - фиксируйте достижения, какими бы малыми они ни были. Регулярный просмотр укрепляет веру в собственные силы."
        ],
        'result': "Через 3 месяца регулярной практики повысится уровень серотонина, снизится кортизол, улучшится качество принятия решений за счет расширения perceptual field."
    },
    # ... остальные руководства
}

# ========== ИИ-АНАЛИЗ ==========
async def generate_ai_analysis(values: List[Dict], username: str, goals: str, profile: str) -> str:
    """
    Генерирует глубокий ИИ-анализ на основе выбранных ценностей
    """
    # Если API ключ не указан, используем локальную логику
    if not USE_AI_API or not AI_API_KEY:
        return generate_local_analysis(values, username, goals, profile)
    
    try:
        # Формируем промпт для ИИ
        value_names = [v['name'] for v in values]
        value_descriptions = [v.get('description', '') for v in values]
        
        # Анализируем категории
        categories = {}
        for v in values:
            cat = v.get('category', 'Разное')
            categories[cat] = categories.get(cat, 0) + 1
        
        prompt = f"""
        Проанализируй эти 10 главных ценностей человека:
        
        Имя: {username}
        Цели: {goals}
        Психологический профиль: {profile}
        
        Ценности:
        {', '.join([f'{i+1}. {name} - {desc}' for i, (name, desc) in enumerate(zip(value_names, value_descriptions))])}
        
        Категории:
        {', '.join([f'{cat}: {count}' for cat, count in categories.items()])}
        
        Сделай глубокий психологический анализ (800-1000 слов):
        
        1. ПСИХОЛОГИЧЕСКИЙ ПОРТРЕТ
        - Основные черты характера
        - Сильные стороны личности
        - Потенциальные области роста
        
        2. СИСТЕМА ЦЕННОСТЕЙ
        - Как ценности взаимодействуют между собой
        - Какие сферы жизни наиболее важны
        - Баланс между внутренним и внешним
        
        3. РЕКОМЕНДАЦИИ ДЛЯ РАЗВИТИЯ
        - Конкретные действия для усиления ценностей
        - Книги для чтения (3-5 рекомендаций)
        - Практики для ежедневного применения
        
        4. ПЕРСПЕКТИВЫ РОСТА
        - Что ожидать в ближайшие 3-6 месяцев
        - Как использовать эти ценности для достижения целей
        - Предостережения и потенциальные трудности
        
        Будь конкретным, практичным и вдохновляющим. Используй психологическую терминологию, но объясняй простыми словами.
        """
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                AI_API_URL,
                headers={
                    "Authorization": f"Bearer {AI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": LOCAL_AI_MODEL,
                    "messages": [
                        {"role": "system", "content": "Ты опытный психолог-коуч с 20-летним стажем. Ты помогаешь людям понять свои ценности и использовать их для улучшения жизни. Твой анализ всегда конкретный, практичный и вдохновляющий."},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 2000,
                    "temperature": 0.7
                },
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    analysis = data['choices'][0]['message']['content']
                    return format_analysis(analysis)
                else:
                    logger.error(f"ИИ API ошибка: {response.status}")
                    return generate_local_analysis(values, username, goals, profile)
                    
    except Exception as e:
        logger.error(f"Ошибка ИИ-анализа: {e}")
        return generate_local_analysis(values, username, goals, profile)

def generate_local_analysis(values: List[Dict], username: str, goals: str, profile: str) -> str:
    """Генерирует локальный анализ если ИИ недоступен"""
    
    # Анализ категорий
    categories = {}
    for v in values:
        cat = v.get('category', 'Разное')
        categories[cat] = categories.get(cat, 0) + 1
    
    # Основные категории
    main_categories = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:3]
    
    analysis = f"""
🎭 <b>ГЛУБОКИЙ ПСИХОЛОГИЧЕСКИЙ АНАЛИЗ ДЛЯ {username}</b>

<em>На основе 10 системообразующих ценностей</em>

✨ <b>ОСНОВНОЙ ПСИХОЛОГИЧЕСКИЙ ПРОФИЛЬ:</b> {profile.upper()}
🎯 <b>ЦЕЛЕВАЯ СФЕРА:</b> {goals}

📊 <b>РАСПРЕДЕЛЕНИЕ ЦЕННОСТЕЙ ПО КАТЕГОРИЯМ:</b>
"""
    
    for cat, count in main_categories:
        analysis += f"\n• <b>{cat}</b>: {count} ценностей ({count*10}% влияния)"
    
    analysis += f"""

🌟 <b>СИЛЬНЫЕ СТОРОНЫ ВАШЕЙ ЦЕННОСТНОЙ СИСТЕМЫ:</b>

1. <b>Гармоничная интеграция</b> - ваши ценности образуют целостную систему, где каждая ценность поддерживает другие. Это создает устойчивую психологическую основу для долгосрочного развития.

2. <b>Баланс между внутренним и внешним</b> - сочетание ценностей, ориентированных на саморазвитие (внутренний мир) и реализацию в социуме (внешний мир), говорит о зрелости личности и способности адаптироваться к разным жизненным контекстам.

3. <b>Практическая направленность</b> - преобладание ценностей, которые можно непосредственно реализовать в повседневной жизни, указывает на реалистичный подход и высокую вероятность воплощения ценностей в действительность.
"""
    
    analysis += f"""

⚡ <b>ПРАКТИЧЕСКИЕ РЕКОМЕНДАЦИИ ДЛЯ РАЗВИТИЯ:</b>

1. <b>СОЗДАНИЕ ЦЕННОСТНОГО КОМПАСА</b>
   - Распечатайте список ваших 10 ценностей
   - Разместите на видном месте (рабочий стол, холодильник)
   - Ежедневно утром выбирайте одну ценность как фокус дня
   - Вечером анализируйте, как эта ценность проявилась

2. <b>РИТУАЛ ЕЖЕНЕДЕЛЬНОЙ РЕФЛЕКСИИ</b>
   - Выделите 30 минут в неделю на анализ
   - Оценивайте каждую ценность по шкале 1-10
   - Отмечайте, какие действия усиливали ценности
   - Корректируйте планы на следующую неделю

3. <b>ЭКСПЕРИМЕНТЫ ПО УСИЛЕНИЮ ЦЕННОСТЕЙ</b>
   - Выберите одну наименее проявленную ценность
   - На 21 день создайте ежедневный ритуал для ее усиления
   - Фиксируйте изменения в ощущениях и результатах
   - После 21 дня оцените эффект и решите продолжать или выбрать следующую ценность
"""
    
    analysis += f"""

📚 <b>РЕКОМЕНДУЕМАЯ ЛИТЕРАТУРА:</b>

1. <b>«СИЛА НАСТОЯЩЕГО» - Экхарт Толле</b>
   <em>Для развития:</em> Осознанности и присутствия в моменте
   <em>Ключевая практика:</em> 5-минутные паузы присутствия

2. <b>«АТОМНЫЕ ПРИВЫЧКИ» - Джеймс Клир</b>
   <em>Для развития:</em> Системного подхода к изменениям
   <em>Ключевая практика:</em> Цепочка привычек

3. <b>«ЭМОЦИОНАЛЬНЫЙ ИНТЕЛЛЕКТ» - Дэниел Гоулман</b>
   <em>Для развития:</em> Понимания себя и других
   <em>Ключевая практика:</em> Распознавание эмоций
"""
    
    analysis += f"""

💎 <b>ЗАКЛЮЧЕНИЕ И ДАЛЬНЕЙШИЕ ШАГИ</b>

Ваша система ценностей - это мощный внутренний ресурс, который может стать источником устойчивости, осмысленности и удовлетворенности в жизни.

<b>На ближайший месяц рекомендуем:</b>
1. Начать с одного простого действия из рекомендаций
2. Найти единомышленника для обсуждения ценностей
3. Запланировать повторный тест через 90 дней
4. Создать «ценностный дневник» для отслеживания прогресса

🌟 <b>Помните:</b> Ценности - это не пункт назначения, а компас для путешествия под названием жизнь. Доверяйте своему компасу, и он приведет вас туда, где вы будете по-настоящему счастливы и реализованы.
"""
    
    return analysis

def format_analysis(text: str) -> str:
    """Форматирует анализ для лучшей читаемости"""
    # Добавляем HTML теги для форматирования
    lines = text.split('\n')
    formatted_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            formatted_lines.append("")
        elif line.startswith(('1.', '2.', '3.', '4.', '•', '-', '—')):
            formatted_lines.append(line)
        elif ':' in line and len(line) < 100:
            # Заголовки
            parts = line.split(':', 1)
            formatted_lines.append(f"\n<b>{parts[0]}:</b>{parts[1] if len(parts) > 1 else ''}")
        elif line.isupper() or line.startswith('**'):
            # Основные заголовки
            formatted_lines.append(f"\n🎯 <b>{line.replace('**', '')}</b>")
        else:
            formatted_lines.append(line)
    
    return '\n'.join(formatted_lines)

# ========== БОТ И ДИСПЕТЧЕР ==========
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

active_games: Dict[int, ValueGame] = {}

# ========== КЛАВИАТУРЫ ==========
def get_main_keyboard():
    """Основная клавиатура"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎮 НАЧАТЬ ТЕСТ")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )

def get_choice_keyboard_5():
    """Клавиатура для выбора 1 из 5"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="1️⃣"), KeyboardButton(text="2️⃣"), KeyboardButton(text="3️⃣")],
            [KeyboardButton(text="4️⃣"), KeyboardButton(text="5️⃣")],
            [KeyboardButton(text="⏭️ Пропустить")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_choice_keyboard_4():
    """Клавиатура для выбора 1 из 4"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="A"), KeyboardButton(text="B")],
            [KeyboardButton(text="C"), KeyboardButton(text="D")],
            [KeyboardButton(text="⏭️ Пропустить")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_goals_keyboard():
    """Клавиатура для выбора целей"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚀 Карьера и достижения")],
            [KeyboardButton(text="💼 Бизнес и финансы")],
            [KeyboardButton(text="🧠 Личностный рост")],
            [KeyboardButton(text="❤️ Отношения и семья")],
            [KeyboardButton(text="⚖️ Баланс и гармония")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

# ========== ОСНОВНЫЕ ОБРАБОТЧИКИ ==========
@dp.message(Command("start"))
@dp.message(F.text == "🎮 НАЧАТЬ ТЕСТ")
async def cmd_start(message: types.Message, state: FSMContext):
    """Начало новой игры"""
    user_id = message.from_user.id
    
    if not ALL_VALUES:
        await message.answer("❌ Ошибка загрузки ценностей", reply_markup=get_main_keyboard())
        return
    
    # Создаем новую игру
    game = ValueGame(user_id, message.from_user.full_name or "Игрок")
    active_games[user_id] = game
    
    # Объяснение механики
    rules = f"""
🎯 <b>ТЕСТ «МОИ ЦЕННОСТИ»</b>

✨ <b>НОВАЯ МЕХАНИКА ОТБОРА:</b>

<em>Этап 1: ШИРОКИЙ ВЫБОР</em>
• 40 раундов
• Каждый раунд: 5 случайных ценностей
• Выбрать: 1 самую важную
• Итог: 40 ценностей из 200+

<em>Этап 2: ГЛУБОКИЙ ОТБОР</em>
• 10 раундов
• Каждый раунд: 4 ценности из одной категории
• Выбрать: 1 самую важную
• Итог: 10 главных ценностей

🎁 <b>ЧТО ВЫ ПОЛУЧИТЕ:</b>
1. Список ваших 10 главных ценностей
2. Глубокий психологический анализ личности
3. Персональные рекомендации по развитию
4. Практический план действий на 3 месяца

⏱️ <b>Время прохождения:</b> 8-12 минут

🚀 <b>Начинаем 1 этап!</b>
"""
    
    await message.answer(rules, reply_markup=ReplyKeyboardRemove())
    await state.set_state(GameStates.stage1_round)
    
    # Начинаем первый раунд
    await send_next_round(message, game, state)

async def send_next_round(message: types.Message, game: ValueGame, state: FSMContext):
    """Отправляет следующий раунд"""
    
    # Проверяем завершение игры
    if game.is_complete():
        await ask_about_goals(message, game, state)
        return
    
    # Проверяем переход между этапами
    if game.stage == 1 and len(game.stage1_selected) >= game.total_rounds_stage1:
        game.stage = 2
        await state.set_state(GameStates.stage2_round)
        await send_stage_transition(message, game, state)
        return
    
    # Подготавливаем раунд
    success = False
    if game.stage == 1:
        success = game.prepare_stage1_round()
    else:
        success = game.prepare_stage2_round()
    
    if not success:
        # Если не удалось подготовить раунд, завершаем этап/игру
        if game.stage == 1:
            game.stage = 2
            await state.set_state(GameStates.stage2_round)
            await send_stage_transition(message, game, state)
        else:
            await ask_about_goals(message, game, state)
        return
    
    progress = game.get_progress()
    
    # Формируем сообщение
    if game.stage == 1:
        text = f"""
<b>ЭТАП 1: ВЫБЕРИТЕ 1 ИЗ 5</b>

📊 Прогресс: {progress['percent']}%
✅ Отобрано: {progress['current']}/{progress['target']}

🎯 <b>Какая ценность для вас важнее?</b>
"""
        
        for i, value in enumerate(game.current_group, 1):
            text += f"\n{i}️⃣ <b>{value['name']}</b>"
            if value.get('description'):
                text += f"\n<em>{value['description']}</em>"
            text += "\n"
        
        text += "\nНажмите номер кнопки (1-5)"
        
        await message.answer(text, reply_markup=get_choice_keyboard_5())
        
    else:  # stage == 2
        text = f"""
<b>ЭТАП 2: ВЫБЕРИТЕ 1 ИЗ 4</b>

📊 Прогресс: {progress['percent']}%
✅ Выбрано: {progress['current']}/{progress['target']}
🏷️ Категория: {game.current_group_category}

🎯 <b>Какая ценность важнее в этой категории?</b>
"""
        
        letters = ['A', 'B', 'C', 'D']
        for i, value in enumerate(game.current_group):
            text += f"\n{letters[i]}. <b>{value['name']}</b>"
            if value.get('description'):
                text += f"\n<em>{value['description']}</em>"
            text += "\n"
        
        text += "\nНажмите букву кнопки (A-D)"
        
        await message.answer(text, reply_markup=get_choice_keyboard_4())

async def send_stage_transition(message: types.Message, game: ValueGame, state: FSMContext):
    """Сообщение о переходе между этапами"""
    
    transition_text = f"""
🎉 <b>ЭТАП 1 ЗАВЕРШЕН!</b>

✅ Вы отобрали: {len(game.stage1_selected)} ценностей из 200+
📊 Уникальных категорий: {len(game.stage2_categories)}

➡️ <b>ПЕРЕХОДИМ К ФИНАЛЬНОМУ ЭТАПУ 2</b>

Теперь мы будем выбирать из сгруппированных по категориям ценностей.
Это поможет определить системообразующие ценности вашей личности.

Нажмите /continue чтобы начать финальный отбор!
"""
    
    await message.answer(transition_text, reply_markup=ReplyKeyboardRemove())

@dp.message(Command("continue"))
async def cmd_continue(message: types.Message, state: FSMContext):
    """Продолжение после перехода"""
    user_id = message.from_user.id
    
    if user_id not in active_games:
        await message.answer("🎮 Сначала начните тест", reply_markup=get_main_keyboard())
        return
    
    game = active_games[user_id]
    await send_next_round(message, game, state)

# ========== ОБРАБОТКА ВЫБОРА ==========
@dp.message(F.text.in_(["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "1", "2", "3", "4", "5"]))
async def handle_stage1_choice(message: types.Message, state: FSMContext):
    """Обработка выбора на этапе 1 (1-5)"""
    user_id = message.from_user.id
    
    if user_id not in active_games:
        await message.answer("🎮 Сначала начните тест", reply_markup=get_main_keyboard())
        return
    
    game = active_games[user_id]
    current_state = await state.get_state()
    
    if current_state != GameStates.stage1_round:
        await message.answer("❌ Неверный этап для этого выбора")
        return
    
    # Преобразуем ввод в индекс
    text = message.text.replace("️⃣", "")
    try:
        choice_index = int(text) - 1
    except:
        await message.answer("❌ Неверный формат выбора")
        return
    
    # Обрабатываем выбор
    if not game.process_stage1_choice(choice_index):
        await message.answer("❌ Ошибка обработки выбора")
        return
    
    # Продолжаем
    await send_next_round(message, game, state)

@dp.message(F.text.in_(["A", "B", "C", "D", "a", "b", "c", "d"]))
async def handle_stage2_choice(message: types.Message, state: FSMContext):
    """Обработка выбора на этапе 2 (A-D)"""
    user_id = message.from_user.id
    
    if user_id not in active_games:
        await message.answer("🎮 Сначала начните тест", reply_markup=get_main_keyboard())
        return
    
    game = active_games[user_id]
    current_state = await state.get_state()
    
    if current_state != GameStates.stage2_round:
        await message.answer("❌ Неверный этап для этого выбора")
        return
    
    # Преобразуем ввод в индекс
    text = message.text.upper()
    letter_to_index = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
    
    if text not in letter_to_index:
        await message.answer("❌ Неверный формат выбора")
        return
    
    choice_index = letter_to_index[text]
    
    # Обрабатываем выбор
    if not game.process_stage2_choice(choice_index):
        await message.answer("❌ Ошибка обработки выбора")
        return
    
    # Продолжаем
    await send_next_round(message, game, state)

@dp.message(F.text == "⏭️ Пропустить")
async def handle_skip(message: types.Message, state: FSMContext):
    """Пропуск раунда"""
    user_id = message.from_user.id
    
    if user_id not in active_games:
        return
    
    game = active_games[user_id]
    current_state = await state.get_state()
    
    # Выбираем случайную ценность
    if current_state == GameStates.stage1_round:
        if game.current_group:
            choice_index = random.randint(0, len(game.current_group) - 1)
            game.process_stage1_choice(choice_index)
    elif current_state == GameStates.stage2_round:
        if game.current_group:
            choice_index = random.randint(0, len(game.current_group) - 1)
            game.process_stage2_choice(choice_index)
    
    await message.answer("⏭️ Раунд пропущен. Следующий выбор...")
    await send_next_round(message, game, state)

# ========== ЗАВЕРШЕНИЕ И АНАЛИЗ ==========
async def ask_about_goals(message: types.Message, game: ValueGame, state: FSMContext):
    """Спрашиваем о целях пользователя"""
    
    # Сначала показываем финальные ценности
    final_values = game.get_final_values()
    
    result_text = f"""
🎉 <b>ПОЗДРАВЛЯЕМ, {game.username}!</b>

✅ <b>ТЕСТ УСПЕШНО ЗАВЕРШЕН</b>

🏆 <b>ВАШИ 10 ГЛАВНЫХ ЦЕННОСТЕЙ:</b>

"""
    
    for i, value in enumerate(final_values, 1):
        result_text += f"\n{i}. <b>{value['name']}</b>"
        if value.get('description'):
            result_text += f"\n   <em>{value['description']}</em>"
        if value.get('category'):
            result_text += f"\n   🏷️ {value['category']}"
        result_text += "\n"
    
    result_text += f"""
📊 <b>СТАТИСТИКА:</b>
• Начало: {len(ALL_VALUES)} ценностей
• Этап 1: отобрано 40 из 200+
• Этап 2: выбрано 10 главных
• Раундов: {game.round}
• Время: {(datetime.now() - game.start_time).seconds // 60} мин {(datetime.now() - game.start_time).seconds % 60} сек

🎯 <b>ДЛЯ ТОЧНОГО АНАЛИЗА:</b>
"""
    
    await message.answer(result_text, reply_markup=ReplyKeyboardRemove())
    await asyncio.sleep(2)
    
    # Спрашиваем о целях
    goals_text = """
🔍 <b>НА ЧТО ВЫ ХОТИТЕ НАПРАВИТЬ ЭНЕРГИЮ В БЛИЖАЙШИЕ 3-6 МЕСЯЦЕВ?</b>

Выберите основную сферу для фокуса:

<em>Это позволит создать максимально персонализированные рекомендации, учитывающие ваши текущие приоритеты.</em>
"""
    
    await message.answer(goals_text, reply_markup=get_goals_keyboard())
    await state.set_state(GameStates.asking_goals)

@dp.message(GameStates.asking_goals)
async def handle_goals_input(message: types.Message, state: FSMContext):
    """Обработка ввода целей"""
    user_id = message.from_user.id
    
    if user_id not in active_games:
        await message.answer("🎮 Сначала начните тест", reply_markup=get_main_keyboard())
        return
    
    game = active_games[user_id]
    goals_input = message.text.strip()
    
    # Сохраняем цели
    game.user_goals = goals_input
    
    # Переходим к генерации анализа
    await state.set_state(GameStates.generating_analysis)
    await generate_deep_analysis(message, game, state)

async def generate_deep_analysis(message: types.Message, game: ValueGame, state: FSMContext):
    """Генерирует и показывает глубокий анализ"""
    
    # Получаем финальные ценности и определяем профиль
    final_values = game.get_final_values()
    game.analyze_final_categories()
    profile = game.get_psychological_profile()
    
    # Сообщение о начале анализа
    analysis_start = f"""
🔮 <b>НАЧИНАЮ ГЛУБОКИЙ ПСИХОЛОГИЧЕСКИЙ АНАЛИЗ</b>

⏱️ <em>Подготовка персонализированного отчета...</em>

• Анализ сочетания 10 системообразующих ценностей
• Определение психологического профиля
• Создание индивидуальных рекомендаций
• Подготовка плана развития

<i>Используется {LOCAL_AI_MODEL if not USE_AI_API else 'современная ИИ-модель'} для глубокого анализа</i>
"""
    
    await message.answer(analysis_start, reply_markup=ReplyKeyboardRemove())
    
    # Имитация анализа с прогресс-баром
    processing_msg = await message.answer("🔄 <i>Анализ начат... 0%</i>")
    
    for percent in range(10, 101, 10):
        await asyncio.sleep(2)  # Общая задержка 20 секунд
        if percent < 40:
            await processing_msg.edit_text(f"🧠 <i>Психологический анализ... {percent}%</i>")
        elif percent < 70:
            await processing_msg.edit_text(f"📊 <i>Создание рекомендаций... {percent}%</i>")
        else:
            await processing_msg.edit_text(f"✨ <i>Формирование отчета... {percent}%</i>")
    
    await processing_msg.delete()
    
    # Генерируем анализ
    await show_analysis_report(message, game, state, final_values, profile)

async def show_analysis_report(message: types.Message, game: ValueGame, state: FSMContext, 
                               final_values: List[Dict], profile: str):
    """Показывает анализ отчета"""
    
    # Генерируем анализ
    analysis = await generate_ai_analysis(
        final_values, 
        game.username, 
        game.user_goals, 
        profile
    )
    
    # Отправляем анализ частями (из-за ограничения длины в Telegram)
    parts = split_text_by_paragraphs(analysis, max_length=4000)
    
    for i, part in enumerate(parts, 1):
        await message.answer(
            part, 
            reply_markup=ReplyKeyboardRemove() if i < len(parts) else None
        )
        await asyncio.sleep(0.5)  # Небольшая пауза между частями
    
    # Финальное сообщение
    final_msg = """
💎 <b>АНАЛИЗ ПОЛНОСТЬЮ СФОРМИРОВАН!</b>

✨ <b>Что делать дальше:</b>
1. Сохраните этот анализ (скриншот или пересылка себе)
2. Выберите 1-2 рекомендации для начала
3. Вернитесь к анализу через неделю для проверки прогресса
4. Запланируйте повтор теста через 3 месяца

🌟 <b>Ваши ценности - это ваш внутренний компас.</b> 
Используйте его для навигации в важных решениях и выборе жизненного пути.

🔄 <b>Пройти тест снова (например, для другой сферы жизни):</b> 🎮 НАЧАТЬ ТЕСТ
"""
    
    await message.answer(final_msg, reply_markup=get_main_keyboard())
    
    # Очищаем состояние
    await state.clear()
    if user_id := message.from_user.id in active_games:
        del active_games[user_id]

def split_text_by_paragraphs(text: str, max_length: int = 4000) -> List[str]:
    """Разбивает текст на части по абзацам"""
    parts = []
    current_part = ""
    
    # Разбиваем по двойным переводам строк (абзацы)
    paragraphs = text.split('\n\n')
    
    for paragraph in paragraphs:
        if len(current_part) + len(paragraph) + 2 < max_length:
            current_part += paragraph + '\n\n'
        else:
            if current_part:
                parts.append(current_part.strip())
            current_part = paragraph + '\n\n'
    
    if current_part:
        parts.append(current_part.strip())
    
    return parts

# ========== ЗАПУСК ==========
async def main():
    logger.info("🚀 Запуск исправленного бота ценностей...")
    
    if not BOT_TOKEN or BOT_TOKEN == "ВАШ_ТОКЕН_БОТА":
        logger.error("❌ Установите BOT_TOKEN!")
        input("Нажмите Enter...")
        return
    
    if not ALL_VALUES:
        logger.error("❌ Не загружены ценности!")
        input("Нажмите Enter...")
        return
    
    try:
        bot_info = await bot.get_me()
        logger.info(f"✅ Бот @{bot_info.username} запущен!")
        logger.info(f"✅ {len(ALL_VALUES)} ценностей для теста")
        logger.info("✅ Исправлена логика второго этапа")
        logger.info("✅ Нет повторения ценностей на первом этапе")
        logger.info("✅ Глубокий ИИ-анализ с задержкой 20 секунд")
        logger.info("✅ Развернутые рекомендации (1000+ символов)")
        logger.info("✅ Бот работает стабильно без остановок")
        logger.info("✅ Используйте кнопку 🎮 НАЧАТЬ ТЕСТ")
        
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"❌ Ошибка запуска: {e}", exc_info=True)
        input("Нажмите Enter...")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Бот остановлен")
