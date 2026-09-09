import ssl
import urllib.request
import json
import os
import asyncio
from datetime import datetime

# Отключаем строгую проверку SSL-сертификатовдляпервой загрузки утилит Flet на Windows
ssl._create_default_https_context = ssl._create_unverified_context

import flet as ft

SAVE_FILE = "rpg_data.json"
# Главная функция асинхронная
async def main(page: ft.Page):
    page.title = "Task RPG: Protected Edition"
    page.theme_mode = ft.ThemeMode.DARK
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.scroll = "adaptive"
    page.padding = 20

    # 1. ЗАГРУЗКА И НАДЕЖНОЕ СОХРАНЕНИЕ ДАННЫХ (Добавлен ключ "active_tasks")
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE, "r", encoding="utf-8") as f:
                user_data = json.load(f)
                if "history" not in user_data:
                    user_data["history"] = []
                if "active_tasks" not in user_data:  # Восстановление квестов при перезапуске
                    user_data["active_tasks"] = []
                if "level" not in user_data or "xp" not in user_data:
                    raise ValueError  # Принудительно сбросить, если файл поврежден
        except Exception:
            user_data = {"level": 1, "xp": 0, "xp_to_next": 100, "history": [], "active_tasks": []}
    else:
        user_data = {"level": 1, "xp": 0, "xp_to_next": 100, "history": [], "active_tasks": []}

    def save_progress():
        try:
            with open(SAVE_FILE, "w", encoding="utf-8") as f:
                json.dump(user_data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Ошибка сохранения: {e}")

    def get_grade(lvl):
        if lvl < 5: return "Новичок 🪵"
        elif lvl < 10: return "Искатель 🧭"
        elif lvl < 20: return "Ветеран ⚔️"
        elif lvl < 40: return "Мастер 🔮"
        else: return "Легенда 👑"

    # Функция добавления записи в историю (с защитой от спецсимволов)
    def add_to_history(task_title, status):
        safe_title = str(task_title).strip().replace("\n", " ")
        current_time = datetime.now().strftime("%H:%M:%S")
        user_data["history"].insert(0, {"title": safe_title, "status": status, "time": current_time})
        user_data["history"] = user_data["history"][:30]  # Храним последние 30 записей
        save_progress()

    # 2. ИНТЕРФЕЙС ПРОФИЛЯ И ОПЫТА
    lvl_text = ft.Text(value=f"Уровень {user_data['level']}", size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER)
    grade_text = ft.Text(value=get_grade(user_data['level']), size=13, weight=ft.FontWeight.W_300, color=ft.Colors.AMBER_200)
    xp_text = ft.Text(value=f"{user_data['xp']} / {user_data['xp_to_next']} XP", size=12, color=ft.Colors.BLUE_200)
    xp_progress = ft.ProgressBar(value=user_data["xp"] / user_data["xp_to_next"], width=300, color=ft.Colors.AMBER, bgcolor=ft.Colors.BLUE_GREY_700)

    profile_card = ft.Card(
        content=ft.Container(
            content=ft.Column(
                controls=[lvl_text, grade_text, xp_progress, xp_text],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=15,
        ),
        margin=10,
        animate_scale=ft.Animation(300, ft.AnimationCurve.BOUNCE_OUT)
    )

    async def update_profile_ui():
        lvl_text.value = f"Уровень {user_data['level']}"
        grade_text.value = get_grade(user_data['level'])
        xp_text.value = f"{user_data['xp']} / {user_data['xp_to_next']} XP"
        xp_progress.value = min(1.0, max(0.0, user_data["xp"] / user_data["xp_to_next"]))
        save_progress()
        page.update()

    async def gain_xp(amount=25):
        user_data["xp"] += amount
        while user_data["xp"] >= user_data["xp_to_next"]:
            user_data["xp"] -= user_data["xp_to_next"]
            user_data["level"] += 1
            user_data["xp_to_next"] = int(user_data["xp_to_next"] * 1.2)
            profile_card.scale = 1.12
            page.update()
            await asyncio.sleep(0.2)
            profile_card.scale = 1.0
            page.update()
            page.snack_bar = ft.SnackBar(
                content=ft.Text(f"🎉 Грейд повышен! Теперь вы: {get_grade(user_data['level'])} ({user_data['level']} ур.)"),
                bgcolor=ft.Colors.AMBER_800,
                open=True
            )
        await update_profile_ui()

    # 3. СПИСОК ЗАДАЧ
    tasks_list = ft.Column(spacing=10, width=350)

    # Список для отслеживания текущих задач
    active_tasks_titles = set(user_data["active_tasks"])

    async def final_remove(task_container, task_title):
        if task_container in tasks_list.controls:
            tasks_list.controls.remove(task_container)
        if task_title in active_tasks_titles:
            active_tasks_titles.remove(task_title)

        user_data["active_tasks"] = list(active_tasks_titles)
        save_progress()
        page.update()

    # АНИМАЦИЯ 1: Плавное удаление с защитой от двойного клика
    async def animate_delete(task_container, checkbox_widget, delete_btn_widget, task_title):
        checkbox_widget.disabled = True
        delete_btn_widget.disabled = True
        task_container.opacity = 0.4
        task_container.update()

        add_to_history(task_title, "Удалено ❌")
        await asyncio.sleep(1.0)

        task_container.offset = ft.Offset(-1, 0)
        task_container.opacity = 0
        task_container.update()

        await asyncio.sleep(0.25)
        task_container.height = 0
        task_container.update()

        await asyncio.sleep(0.2)
        await final_remove(task_container, task_title)

    # АНИМАЦИЯ 2: Выполнение квеста с защитой от двойного клика
    async def animate_complete(task_container, checkbox_widget, delete_btn_widget, task_text, task_title):
        checkbox_widget.disabled = True
        delete_btn_widget.disabled = True
        task_text.style = ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH, color=ft.Colors.GREEN_200)
        task_container.bgcolor = ft.Colors.with_opacity(0.15, ft.Colors.GREEN_700)
        task_container.update()

        add_to_history(task_title, "Выполнено 🎉")
        await gain_xp(25)
        await asyncio.sleep(1.0)

        task_container.width = 0
        task_container.height = 0
        task_container.opacity = 0
        task_container.update()

        await asyncio.sleep(0.25)
        await final_remove(task_container, task_title)

    # Обработчики событий
    async def check_task(e, checkbox_widget, delete_btn_widget, task_text, task_container, task_title):
        if e.control.value:
            await animate_complete(task_container, checkbox_widget, delete_btn_widget, task_text, task_title)

    async def delete_click(e, checkbox_widget, delete_btn_widget, task_container, task_title):
        await animate_delete(task_container, checkbox_widget, delete_btn_widget, task_title)

    # Вспомогательная функция отрисовки UI для сохраненных задач
    def render_task_on_screen(title_text):
        task_text = ft.Text(value=title_text, size=16, expand=True)

        task_container = ft.Container(
            content=ft.Row(vertical_alignment=ft.CrossAxisAlignment.CENTER),
            opacity=1, offset=ft.Offset(0, 0), height=50, width=350, border_radius=8,
            padding=ft.Padding(10, 0, 5, 0), animate_opacity=200,
            animate_offset=ft.Animation(250, ft.AnimationCurve.EASE_OUT),
            animate_size=ft.Animation(250, ft.AnimationCurve.EASE_IN_OUT),
        )

        checkbox = ft.Checkbox()
        delete_btn = ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, icon_color=ft.Colors.RED_300)

        checkbox.on_change = lambda e: page.run_task(check_task, e, checkbox, delete_btn, task_text, task_container,
                                                     title_text)
        delete_btn.on_click = lambda e: page.run_task(delete_click, e, checkbox, delete_btn, task_container, title_text)

        task_container.content.controls = [checkbox, task_text, delete_btn]
        tasks_list.controls.append(task_container)

    # ДОБАВЛЕНИЕ ЗАДАЧИ
    async def add_task_click(e):
        clean_title = new_task_input.value.strip()

        if not clean_title:
            return

        if clean_title in active_tasks_titles:
            page.snack_bar = ft.SnackBar(ft.Text("Этот квест уже взят! ⚔️"), open=True, bgcolor=ft.Colors.RED_800)
            page.update()
            return

        add_task_btn.scale = 0.8
        page.update()
        await asyncio.sleep(0.1)
        add_task_btn.scale = 1.0
        page.update()

        active_tasks_titles.add(clean_title)

        user_data["active_tasks"] = list(active_tasks_titles)
        save_progress()

        render_task_on_screen(clean_title)
        new_task_input.value = ""
        page.update()

    # 4. ИНТЕРФЕЙС ИСТОРИИ (Нижняя шторка)
    history_list = ft.ListView(expand=True, spacing=10, padding=10)

    def close_bottom_sheet(e):
        bs.open = False
        page.update()

    bs = ft.BottomSheet(
        content=ft.Container(
            content=ft.Column(controls=[
                ft.Container(
                    content=ft.Text("📜 История квестов", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER),
                    margin=ft.Margin(0, 10, 0, 10), alignment=ft.alignment.Alignment(0, 0)
                ),
                ft.Divider(height=1, color=ft.Colors.BLUE_GREY_800),
                ft.Container(content=history_list, expand=True),
                ft.FilledButton("Закрыть", on_click=close_bottom_sheet, bgcolor=ft.Colors.AMBER, color=ft.Colors.BLACK)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=15, height=380, bgcolor=ft.Colors.BLUE_GREY_900, border_radius=ft.BorderRadius(15, 15, 0, 0)
        )
    )

    page.overlay.append(bs)

    async def show_history_click(e):
        history_list.controls.clear()
        if not user_data["history"]:
            history_list.controls.append(
                ft.Text("История пока пуста. Выполните квест! ⚔️", size=14, color=ft.Colors.GREY_500,
                        text_align=ft.TextAlign.CENTER)
            )
        else:
            for item in user_data["history"]:
                history_list.controls.append(
                    ft.Row(controls=[
                        ft.Text(f"[{item['time']}]", size=12, color=ft.Colors.BLUE_GREY_400),
                        ft.Text(f"{item['status']}", size=12, weight=ft.FontWeight.BOLD,
                                color=ft.Colors.GREEN_400 if "Выполнено" in item['status'] else ft.Colors.RED_400),
                        ft.Text(f"{item['title']}", size=14, expand=True, overflow=ft.TextOverflow.ELLIPSIS)
                    ], alignment=ft.MainAxisAlignment.START)
                )
        bs.open = True
        page.update()

    # 5. ЭЛЕМЕНТЫ УПРАВЛЕНИЯ
    new_task_input = ft.TextField(hint_text="Новое задание...", expand=True, border_color=ft.Colors.BLUE_GREY_700,
                                  focused_border_color=ft.Colors.AMBER)
    add_task_btn = ft.FloatingActionButton(icon=ft.Icons.ADD, bgcolor=ft.Colors.AMBER,
                                           on_click=lambda e: page.run_task(add_task_click, e), animate_scale=100)

    history_btn = ft.TextButton(
        content=ft.Text("📜 Посмотреть историю", color=ft.Colors.BLUE_GREY_200),
        icon=ft.Icons.HISTORY, icon_color=ft.Colors.AMBER,
        on_click=lambda e: page.run_task(show_history_click, e)
    )

    # Автоматическая загрузка невыполненных задач на экран при запуске
    for task_title in user_data["active_tasks"]:
        render_task_on_screen(task_title)

    page.add(
        profile_card, history_btn, ft.Divider(height=20, color=ft.Colors.BLUE_GREY_800),
        ft.Container(content=tasks_list, padding=5),
        ft.Row(controls=[new_task_input, add_task_btn], alignment=ft.MainAxisAlignment.CENTER, width=350)
    )
    await update_profile_ui()


if __name__ == "__main__":
    ft.app(target=main)
# Исправление статуса сборки.
