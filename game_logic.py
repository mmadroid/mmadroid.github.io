# game_logic.py
import random
import json
from typing import List, Dict, Optional
from game_data import cells_data

class MonopolyGame:
    def __init__(self, game_id: str, players: List[int]):
        self.game_id = game_id
        self.players = {pid: {
            "name": f"Игрок {i+1}",
            "money": 1500,
            "position": 0,
            "jail_turns": 0,
            "cards": [],  # карточки "Выход из тюрьмы"
            "properties": {}  # {cell_index: {"houses": 0, "mortgaged": False}}
        } for i, pid in enumerate(players)}
        self.player_order = players
        self.current_player_idx = 0
        self.doubles_count = 0
        self.active = True
        self.winner = None

        # Инициализация клеток
        self.cells = []
        for idx, data in enumerate(cells_data):
            self.cells.append({
                "index": idx,
                "name": data["name"],
                "type": data["type"],
                "price": data["price"],
                "rent": data["rent"],
                "color": data.get("color"),
                "group": data.get("group"),
                "owner": None,
                "houses": 0,
                "mortgaged": False
            })

    def get_state(self, player_id: int) -> dict:
        """Возвращает состояние игры для конкретного игрока (с его приватной информацией)"""
        state = {
            "players": {},
            "current_player": self.player_order[self.current_player_idx],
            "winner": self.winner,
            "cells": self.cells,
            "your_id": player_id,
            "doubles_count": self.doubles_count
        }
        for pid, data in self.players.items():
            state["players"][pid] = {
                "name": data["name"],
                "money": data["money"],
                "position": data["position"],
                "jail_turns": data["jail_turns"],
                "in_jail": data["jail_turns"] > 0,
                "cards": len(data["cards"])
            }
        return state

    def next_turn(self):
        self.current_player_idx = (self.current_player_idx + 1) % len(self.player_order)
        self.doubles_count = 0

    def roll_dice(self, player_id: int) -> dict:
        if self.winner:
            return {"error": "Игра уже завершена"}
        if self.player_order[self.current_player_idx] != player_id:
            return {"error": "Сейчас не ваш ход"}
        player = self.players[player_id]
        if player["jail_turns"] > 0:
            # В тюрьме: бросок для выхода
            dice1 = random.randint(1, 6)
            dice2 = random.randint(1, 6)
            if dice1 == dice2:
                player["jail_turns"] = 0
                msg = f"Вы вышли из тюрьмы (дубль {dice1})!"
                self.next_turn()
                return {"dice": [dice1, dice2], "message": msg, "state": self.get_state(player_id)}
            else:
                player["jail_turns"] -= 1
                if player["jail_turns"] == 0:
                    # Платим штраф 50
                    player["money"] -= 50
                    player["jail_turns"] = 0
                    msg = f"Вы не вышли из тюрьмы, заплатили штраф 50 и вышли."
                else:
                    msg = f"Вы не вышли из тюрьмы. Осталось попыток: {player['jail_turns']}"
                self.next_turn()
                return {"dice": [dice1, dice2], "message": msg, "state": self.get_state(player_id)}
        # Обычный ход
        dice1 = random.randint(1, 6)
        dice2 = random.randint(1, 6)
        is_double = (dice1 == dice2)
        steps = dice1 + dice2
        old_pos = player["position"]
        new_pos = (old_pos + steps) % 40
        player["position"] = new_pos
        # Если прошли старт
        if new_pos < old_pos:
            player["money"] += 200
        # Обработка клетки
        cell = self.cells[new_pos]
        result = self.handle_cell(player_id, cell)
        if is_double:
            self.doubles_count += 1
            if self.doubles_count == 3:
                # Три дубля подряд -> в тюрьму
                self.go_to_jail(player_id)
                self.doubles_count = 0
                self.next_turn()
                result["message"] = "Три дубля подряд! Вы отправляетесь в тюрьму."
            else:
                # Игрок ходит снова
                pass
        else:
            self.doubles_count = 0
            self.next_turn()
        result["dice"] = [dice1, dice2]
        result["state"] = self.get_state(player_id)
        return result

    def handle_cell(self, player_id: int, cell: dict) -> dict:
        player = self.players[player_id]
        if cell["type"] == "property" or cell["type"] == "railroad" or cell["type"] == "utility":
            if cell["owner"] is None:
                # Можно купить
                return {"action": "buy", "cell": cell["index"], "price": cell["price"]}
            elif cell["owner"] != player_id:
                # Платим аренду
                rent = self.calc_rent(cell, player_id)
                if player["money"] >= rent:
                    player["money"] -= rent
                    self.players[cell["owner"]]["money"] += rent
                    return {"message": f"Вы заплатили аренду {rent} игроку {self.players[cell['owner']]['name']}"}
                else:
                    # Банкротство
                    return self.bankruptcy(player_id, cell["owner"])
            else:
                return {"message": "Это ваша собственность"}
        elif cell["type"] == "chance":
            return self.draw_chance(player_id)
        elif cell["type"] == "chest":
            return self.draw_chest(player_id)
        elif cell["type"] == "tax":
            player["money"] -= cell["rent"]
            return {"message": f"Вы заплатили налог {cell['rent']}"}
        elif cell["type"] == "goto_prison":
            self.go_to_jail(player_id)
            return {"message": "Вы отправляетесь в тюрьму"}
        elif cell["type"] == "start":
            return {"message": "Старт"}
        elif cell["type"] == "parking":
            return {"message": "Бесплатная стоянка"}
        elif cell["type"] == "prison":
            return {"message": "Вы просто посетили тюрьму"}
        return {"message": ""}

    def calc_rent(self, cell: dict, player_id: int) -> int:
        # Упрощённый расчёт
        owner = self.players[cell["owner"]]
        if cell["type"] == "property":
            group = cell["group"]
            # Проверяем монополию
            monopoly = True
            for i, c in enumerate(self.cells):
                if c["type"] == "property" and c["group"] == group and c["owner"] != cell["owner"]:
                    monopoly = False
                    break
            if monopoly and cell["houses"] == 0:
                return cell["rent"][0] * 2
            else:
                return cell["rent"][cell["houses"]]
        elif cell["type"] == "railroad":
            owned_railroads = sum(1 for c in self.cells if c["type"] == "railroad" and c["owner"] == cell["owner"])
            return [25, 50, 100, 200][owned_railroads-1]
        elif cell["type"] == "utility":
            owned_utilities = sum(1 for c in self.cells if c["type"] == "utility" and c["owner"] == cell["owner"])
            # аренда = (сумма кубиков) * множитель
            # но у нас нет кубиков в этом контексте, для простоты возьмем фиксированную
            return 4 if owned_utilities == 1 else 10
        return 0

    def go_to_jail(self, player_id: int):
        player = self.players[player_id]
        player["position"] = 10  # клетка тюрьмы
        player["jail_turns"] = 3
        player["money"] = max(player["money"], 0)

    def bankruptcy(self, loser_id: int, creditor_id: int = None):
        loser = self.players[loser_id]
        # Все активы передаются кредитору или банку
        if creditor_id is not None:
            creditor = self.players[creditor_id]
            creditor["money"] += loser["money"]
            # Передача недвижимости
            for i, cell in enumerate(self.cells):
                if cell["owner"] == loser_id:
                    cell["owner"] = creditor_id
                    cell["houses"] = 0
                    cell["mortgaged"] = False
        else:
            # Банк забирает всё
            pass
        # Удалить игрока
        del self.players[loser_id]
        self.player_order.remove(loser_id)
        if len(self.players) == 1:
            self.winner = self.player_order[0]
            return {"message": f"Игрок {loser['name']} обанкротился. Победитель {self.players[self.winner]['name']}!"}
        # Если текущий игрок был удалён, переключаем ход
        if self.current_player_idx >= len(self.player_order):
            self.current_player_idx = 0
        return {"message": f"Игрок {loser['name']} обанкротился."}

    def draw_chance(self, player_id: int) -> dict:
        # Упрощённый список карт
        cards = [
            "Вы выиграли конкурс красоты +50", lambda p: p["money"]+50,
            "Банк выплачивает вам дивиденды +100", lambda p: p["money"]+100,
            "Идите на улицу Старт", lambda p: self.move_to_start(p),
            "Заплатите штраф 50", lambda p: p["money"]-50,
            "Выходите из тюрьмы бесплатно", lambda p: p["cards"].append("get_out_of_jail"),
            "Отправляйтесь в тюрьму", lambda p: self.go_to_jail(p)
        ]
        card = random.choice(cards)
        # применить эффект
        # ...
        return {"message": f"Шанс: {card[0]}"}

    def draw_chest(self, player_id: int) -> dict:
        # аналогично
        pass