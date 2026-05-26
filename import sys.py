import sys
import os
import pickle
import csv
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict

# ==========================================
# БІЗНЕС-ЛОГІКА (Сутності та Менеджер з ЛР5/6)
# ==========================================

class Currency(Enum):
    UAH = "UAH"
    USD = "USD"
    EUR = "EUR"

@dataclass
class User:
    username: str
    email: str

    def __str__(self):
        return f"{self.username} ({self.email})"

class ExpenseRecord:
    def __init__(self, description: str, total_amount: float, paid_by: str, currency: Currency, users: List[str]):
        self.description = description
        self.total_amount = total_amount
        self.paid_by = paid_by
        self.currency = currency
        self.users = users

    def calculate_splits(self) -> Dict[str, float]:
        """Базовий метод розрахунку (перевизначається в нащадках)"""
        return {}

class EqualSplit(ExpenseRecord):
    def calculate_splits(self) -> Dict[str, float]:
        """Сума ділиться порівну між усіма учасниками"""
        if not self.users:
            return {}
        share = round(self.total_amount / len(self.users), 2)
        return {user: share for user in self.users}

class PercentageSplit(ExpenseRecord):
    def __init__(self, description: str, total_amount: float, paid_by: str, currency: Currency, users: List[str], percentages: Dict[str, float]):
        super().__init__(description, total_amount, paid_by, currency, users)
        self.percentages = percentages  # Словник вигляду {username: відсоток}

    def calculate_splits(self) -> Dict[str, float]:
        """Сума ділиться відповідно до вказаних відсотків"""
        splits = {}
        for user in self.users:
            pct = self.percentages.get(user, 0.0)
            splits[user] = round((pct / 100.0) * self.total_amount, 2)
        return splits

class GroupLedger:
    def __init__(self, ledger_name: str):
        self.ledger_name = ledger_name
        self.users: Dict[str, User] = {}
        self.expenses: List[ExpenseRecord] = []
        self.db_filename = "ledger_state.pkl"

    def add_user(self, user: User):
        if user.username in self.users:
            raise ValueError(f"Користувач з іменем '{user.username}' вже існує!")
        self.users[user.username] = user
        print(f" [Success] Користувача '{user.username}' успішно додано до групи.")

    def add_expense(self, expense: ExpenseRecord):
        # Валідація учасників
        if expense.paid_by not in self.users:
            raise ValueError(f"Платник '{expense.paid_by}' не зареєстрований у групі!")
        for u in expense.users:
            if u not in self.users:
                raise ValueError(f"Учасник витрати '{u}' не зареєстрований у групі!")
        
        self.expenses.append(expense)
        print(f" [Success] Витрату '{expense.description}' ({expense.total_amount} {expense.currency.value}) успішно додано.")

    def get_balances(self) -> Dict[str, float]:
        """Складна логіка взаєморозрахунків (хто кому скільки винен/хто переплатив)"""
        balances = {username: 0.0 for username in self.users}
        
        for exp in self.expenses:
            # Платнику повертається вся сума, яку він вніс
            balances[exp.paid_by] += exp.total_amount
            
            # Віднімаємо частку кожного учасника згідно з його типом розподілу
            splits = exp.calculate_splits()
            for user, share in splits.items():
                if user in balances:
                    balances[user] -= share
                    
        return {user: round(bal, 2) for user, bal in balances.items()}

    def display_all_info(self):
        print(f"\n--- Стан трекера спільних витрат: '{self.ledger_name}' ---")
        print(f"Зареєстровані користувачі ({len(self.users)}):")
        if not self.users:
            print("  (немає користувачів)")
        for u in self.users.values():
            print(f"  • {u}")
            
        print(f"\nІсторія витрат ({len(self.expenses)}):")
        if not self.expenses:
            print("  (немає записів про витрати)")
        for i, exp in enumerate(self.expenses, 1):
            split_type = "Порівну" if isinstance(exp, EqualSplit) else "У відсотках"
            print(f"  {i}. [{split_type}] {exp.description}: всього {exp.total_amount} {exp.currency.value}. Оплатив: {exp.paid_by}.")

        print("\nПоточний баланс учасників (позитивний — йому винні, негативний — він винен):")
        balances = self.get_balances()
        for user, bal in balances.items():
            color = ""
            if bal > 0: color = " (Хтось має повернути кошти)"
            elif bal < 0: color = " (Потрібно повернути борг)"
            print(f"  • {user}: {bal} {color}")

    def save_to_pickle(self):
        try:
            with open(self.db_filename, "wb") as f:
                pickle.dump((self.users, self.expenses), f)
            print(f" [System] Базу даних '{self.db_filename}' успішно збережено.")
        except Exception as e:
            print(f" [Error] Не вдалося зберегти стан системи: {e}")

    def load_from_pickle(self):
        if os.path.exists(self.db_filename):
            try:
                with open(self.db_filename, "rb") as f:
                    self.users, self.expenses = pickle.load(f)
                print(f" [System] Стан системи успішно відновлено з файлу '{self.db_filename}'.")
            except Exception as e:
                print(f" [Warning] Помилка зчитування файлу конфігурації ({e}). Ініціалізовано порожню базу.")
        else:
            print(" [Info] Файл збереження стану не знайдено. Створено нову чисту групу.")

    def export_balances_csv(self):
        filename = "balances_report.csv"
        try:
            balances = self.get_balances()
            with open(filename, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Користувач", "Баланс (борг/надлишок)"])
                for user, bal in balances.items():
                    writer.writerow([user, bal])
            print(f" [System] Фінансовий звіт CSV успішно згенеровано у файл '{filename}'.")
        except Exception as e:
            print(f" [Error] Не вдалося експортувати звіт: {e}")

# ==========================================
# КОНСОЛЬНИЙ ІНТЕРФЕЙС (CLI)
# ==========================================

def show_menu():
    print("\n" + "="*45)
    print("      ГОЛОВНЕ МЕНЮ: SPLITWISE TRACKER      ")
    print("="*45)
    print("1. Показати повну інформацію та баланси")
    print("2. Додати нового користувача")
    print("3. Додати новий запис про витрату")
    print("4. Зберегти стан системи (Pickle)")
    print("5. Експортувати баланси у звіт CSV")
    print("0. Безпечний вихід із програми")
    print("="*45)

if __name__ == "__main__":
    # Ініціалізація головного менеджера
    ledger = GroupLedger(ledger_name = "Вінницькі Студенти")
    ledger.load_from_pickle()
    
    print("\nЛаскаво просимо до Трекера Спільних Витрат v1.0")
    
    # Головний життєвий цикл програми
    while True:
        show_menu()
        try:
            choice = input("Оберіть дію (0-5): ").strip()
            match choice:
                case "1":
                    ledger.display_all_info()
                case "2":
                    print("\n--- Реєстрація нового користувача ---")
                    username = input("Введіть унікальне ім'я (псевдонім): ").strip()
                    if not username:
                        raise ValueError("Ім'я користувача не може бути порожнім!")
                    email = input("Введіть електронну пошту: ").strip()
                    if "@" not in email:
                        raise ValueError("Некоректний формат email (відсутній символ '@')!")
                    ledger.add_user(User(username=username, email=email))
                case "3":
                    print("\n--- Створення нової спільної витрати ---")
                    if not ledger.users:
                        raise ValueError("Неможливо створити витрату: у групі немає жодного користувача!")
                    description = input("Опис витрати (напр., 'Продукти', 'Оренда'): ").strip()
                    if not description:
                        raise ValueError("Опис витрати обов'язково має бути заповнений!")
                    total_amount = float(input("Введіть повну суму витрати: "))
                    if total_amount <= 0:
                        raise ValueError("Сума витрати повинна бути строго більшою за нуль!")
                    paid_by = input("Хто сплатив цю суму? (введіть username): ").strip()
                    print(f"Оберіть валюту із доступних: {[c.value for c in Currency]}")
                    curr_input = input("Введіть назву валюти: ").strip().upper()
                    if curr_input not in [c.value for c in Currency]:
                        raise ValueError("Така валюта не підтримується системою!")
                    currency = Currency(curr_input)
                    # Визначення списку учасників
                    print("\nВведіть імена учасників (username), між якими ділиться сума, через кому.")
                    print("Приклад: user1, user2, user3")
                    users_input = input("Список учасників: ")
                    participants = [u.strip() for u in users_input.split(",") if u.strip()]
                    if not participants:
                        raise ValueError("Список учасників розподілу не може бути порожнім!")
                    # Вибір типу розподілу
                    print("\nТип розподілу витрат:")
                    print("1. Порівну між усіма (EqualSplit)")
                    print("2. У відсотковому співвідношенні (PercentageSplit)")
                    split_choice = input("Ваш вибір (1 або 2): ").strip()
                    match split_choice:
                        case "1":
                            expense = EqualSplit(description, total_amount, paid_by, currency, participants)
                            ledger.add_expense(expense)
                        case "2":
                            percentages = {}
                            print("\nВведіть відсоток для кожного учасника (сума повинна дорівнювати 100%):")
                            total_pct = 0.0
                            for p in participants:
                                pct = float(input(f"  Відсоток для {p} (%): "))
                                if pct < 0:
                                    raise ValueError("Відсоток не може бути від'ємним!")
                                percentages[p] = pct
                                total_pct += pct
                            # Невелика перевірка на точність суми відсотків
                            if abs(total_pct - 100.0) > 0.01:
                                raise ValueError(f"Помилка розподілу! Сума часток дорівнює {total_pct}%, а має бути рівно 100%.")
                            expense = PercentageSplit(description, total_amount, paid_by, currency, participants, percentages)
                            ledger.add_expense(expense)
                        case _:
                            print(" [Warning] Невідомий тип розподілу! Спробуйте створити витрату спочатку.")
                case "4":
                    ledger.save_to_pickle()
                case "5":
                    ledger.export_balances_csv()
                case "0":
                    print("\n[Вихід] Автоматичне збереження стану перед виходом...")
                    ledger.save_to_pickle()
                    print("Дякуємо, що використовували Трекер Спільних Витрат! Бувай!")
                    sys.exit(0)
                case _:
                    print(" [Warning] Невідома команда! Будь ласка, оберіть пункт меню від 0 до 5.")
        except ValueError as e:
            print(f"\n [Помилка введення даних]: {e}")
            print("Спробуйте виконати дію знову. Будьте уважні при введенні текстових і числових полів.")
        except Exception as e:
            print(f"\n [Критична помилка системи]: {e}")
            print("Будь ласка, повідомте адміністратора.")
