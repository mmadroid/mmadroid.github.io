# bot.py
import asyncio
import logging
import sqlite3
import json
import random
from aiogram import Bot, Dispatcher, types
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from aiohttp import web
import aiohttp_jinja2
import jinja2
from game_logic import MonopolyGame

API_TOKEN = "8787759522:AAEucC1BJaeRCRucOuKlmwxVxGQlwvFj5AE"
WEB_APP_URL = "https://mmadroid.github.io/"  # URL вашего веб-приложения

# База данных для хранения игр
conn = sqlite3.connect('games.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS games
             (game_id TEXT PRIMARY KEY, state TEXT)''')
conn.commit()

games = {}  # кэш игр {game_id: MonopolyGame}

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# ========== Команды бота ==========
@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    await message.answer("Добро пожаловать в Монополию!\nИспользуйте /create_game для создания новой игры или /join <код> для присоединения.")

@dp.message_handler(commands=['create_game'])
async def create_game(message: types.Message):
    game_id = str(random.randint(1000, 9999))
    # Создаём игру с текущим пользователем
    game = MonopolyGame(game_id, [message.from_user.id])
    games[game_id] = game
    # Сохраняем в БД
    c.execute("INSERT INTO games (game_id, state) VALUES (?, ?)", (game_id, json.dumps({})))
    conn.commit()
    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("Присоединиться", callback_data=f"join_{game_id}"),
        InlineKeyboardButton("Начать игру", callback_data=f"start_{game_id}")
    )
    await message.answer(f"Игра создана! Код: {game_id}\nОтправьте этот код друзьям или нажмите кнопку.", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data.startswith('join_'))
async def join_game(callback: types.CallbackQuery):
    game_id = callback.data.split('_')[1]
    if game_id not in games:
        await callback.answer("Игра не найдена")
        return
    game = games[game_id]
    if len(game.players) >= 4:
        await callback.answer("Игра уже заполнена")
        return
    if callback.from_user.id in game.players:
        await callback.answer("Вы уже в игре")
        return
    game.players[callback.from_user.id] = {
        "name": callback.from_user.full_name,
        "money": 1500,
        "position": 0,
        "jail_turns": 0,
        "cards": [],
        "properties": {}
    }
    game.player_order.append(callback.from_user.id)
    await callback.message.edit_text(f"Игрок {callback.from_user.full_name} присоединился. Всего игроков: {len(game.players)}")
    await callback.answer("Вы присоединились!")

@dp.callback_query_handler(lambda c: c.data.startswith('start_'))
async def start_game(callback: types.CallbackQuery):
    game_id = callback.data.split('_')[1]
    if game_id not in games:
        await callback.answer("Игра не найдена")
        return
    game = games[game_id]
    if len(game.players) < 2:
        await callback.answer("Нужно минимум 2 игрока")
        return
    # Отправляем всем игрокам ссылку на мини-приложение
    webapp_url = f"{WEB_APP_URL}?game_id={game_id}"
    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("Играть", web_app=WebAppInfo(url=webapp_url))
    )
    for pid in game.players:
        try:
            await bot.send_message(pid, f"Игра {game_id} началась! Нажмите кнопку, чтобы открыть игровое поле.", reply_markup=keyboard)
        except:
            pass
    await callback.message.edit_text("Игра начата!")

# ========== HTTP сервер для взаимодействия с клиентом ==========
async def handle_state(request):
    data = await request.json()
    game_id = data.get('game_id')
    player_id = data.get('player_id')
    if game_id not in games:
        return web.json_response({"error": "Game not found"})
    game = games[game_id]
    if player_id not in game.players:
        return web.json_response({"error": "Player not in game"})
    state = game.get_state(player_id)
    return web.json_response(state)

async def handle_action(request):
    data = await request.json()
    game_id = data.get('game_id')
    player_id = data.get('player_id')
    action = data.get('action')
    if game_id not in games:
        return web.json_response({"error": "Game not found"})
    game = games[game_id]
    if player_id not in game.players:
        return web.json_response({"error": "Player not in game"})
    if action == "roll":
        result = game.roll_dice(player_id)
        return web.json_response(result)
    elif action == "buy":
        cell_idx = data.get('cell')
        # Проверим, что клетка доступна
        cell = game.cells[cell_idx]
        if cell["owner"] is not None:
            return web.json_response({"error": "Cell already owned"})
        player = game.players[player_id]
        if player["money"] >= cell["price"]:
            player["money"] -= cell["price"]
            cell["owner"] = player_id
            return web.json_response({"success": True, "state": game.get_state(player_id)})
        else:
            return web.json_response({"error": "Not enough money"})
    elif action == "end_turn":
        game.next_turn()
        return web.json_response({"state": game.get_state(player_id)})
    return web.json_response({"error": "Unknown action"})

app = web.Application()
app.router.add_post('/state', handle_state)
app.router.add_post('/action', handle_action)

async def on_startup(dp):
    # Запускаем aiohttp сервер на порту 8080
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)