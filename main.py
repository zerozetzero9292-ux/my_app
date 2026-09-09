import ssl
import urllib.request
import json
import os
import asyncio
from datetime import datetime

# Отключаем строгую проверку SSL-сертификатов для первой загрузки утилит Flet на Windows
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

    # 1. ЗАГРУЗКА И НАДЕЖНОЕ СОХРАНЕНИЕ ДАННЫХ
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE, "r", encoding="utf-8") as f:
                user_data = json.load(f)
                if "history" not in user_data:
                    user_data["history"] = []
                if "level" not in user_data or "xp" not in user_data:
                    raise ValueError  # Принудительно сбросить, если файл поврежден
        except Exception:
            user_data = {"level": 1, "xp": 0, "xp_to_next": 100, "history": []}
    else:
        user_data = {"level": 1, "xp": 0, "xp_to_next": 100, "history": []}

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
    grade_text = ft.Text(value=get_grade(user_data['level']), size=13, weight=ft.FontWeight.W_300,
                         color=ft.Colors.AMBER_200)
    xp_text = ft.Text(value=f"{user_data['xp']} / {user_data['xp_to_next']} XP", size=12, color=ft.Colors.BLUE_200)

    # Кастомная шкала опыта из контейнеров со встроенной плавной анимацией
    MAX_BAR_WIDTH = 300

    # Внутренний ползунок, который плавно растет и меняет цвета
    xp_progress_fill = ft.Container(
        width=int(MAX_BAR_WIDTH * (user_data["xp"] / user_data["xp_to_next"])),
        height=12,
        bgcolor=ft.Colors.AMBER,
        border_radius=6,
        animate=ft.Animation(600, ft.AnimationCurve.EASE_OUT)  # Плавная анимация цвета и ширины
    )

    # Внешняя серая подложка прогресс-бара
    xp_progress = ft.Container(
        content=ft.Row([xp_progress_fill], alignment=ft.MainAxisAlignment.START),
        width=MAX_BAR_WIDTH,
        height=12,
        bgcolor=ft.Colors.BLUE_GREY_700,
        border_radius=6,
        padding=0
    )

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

        # Плавно рассчитываем новую ширину ползунка
        progress_ratio = min(1.0, max(0.0, user_data["xp"] / user_data["xp_to_next"]))
        xp_progress_fill.width = int(MAX_BAR_WIDTH * progress_ratio)

        save_progress()
        page.update()

    # Начисление опыта с плавным перекрашиванием кастомной шкалы
    async def gain_xp(amount=25, color_theme=ft.Colors.AMBER):
        user_data["xp"] += amount

        # Плавно перекрашиваем ползунок в цвет сложности
        xp_progress_fill.bgcolor = color_theme
        page.update()

        while user_data["xp"] >= user_data["xp_to_next"]:
            # Ползунок плавно долетает до 100%
            xp_progress_fill.width = MAX_BAR_WIDTH
            page.update()
            await asyncio.sleep(0.4)

            user_data["xp"] -= user_data["xp_to_next"]
            user_data["level"] += 1
            user_data["xp_to_next"] = int(user_data["xp_to_next"] * 1.2)

            # Мгновенно сбрасываем ширину в ноль, чтобы начать заполнять новый уровень сначала
            xp_progress_fill.animate = None  # Отключаем на миг анимацию для резкого сброса
            xp_progress_fill.width = 0
            profile_card.scale = 1.12
            page.update()
            await asyncio.sleep(0.1)

            # Возвращаем анимацию обратно
            xp_progress_fill.animate = ft.Animation(600, ft.AnimationCurve.EASE_OUT)
            page.update()
            await asyncio.sleep(0.2)

            profile_card.scale = 1.0
            page.update()
            page.snack_bar = ft.SnackBar(
                content=ft.Text(
                    f"🎉 Грейд повышен! Теперь вы: {get_grade(user_data['level'])} ({user_data['level']} ур.)"),
                bgcolor=ft.Colors.AMBER_800,
                open=True
            )

        await update_profile_ui()

        # После заполнения шкала плавно возвращает свой стандартный янтарный цвет
        await asyncio.sleep(0.6)
        xp_progress_fill.bgcolor = ft.Colors.AMBER
        page.update()

    # 3. СПИСОК ЗАДАЧ
    tasks_list = ft.Column(spacing=10, width=350)
    active_tasks_titles = set()

    async def final_remove(task_container, task_title):
        if task_container in tasks_list.controls:
            tasks_list.controls.remove(task_container)
        if task_title in active_tasks_titles:
            active_tasks_titles.remove(task_title)
        page.update()

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

    async def animate_complete(task_container, checkbox_widget, delete_btn_widget, task_text, task_title, xp_reward,
                               color_theme):
        checkbox_widget.disabled = True
        delete_btn_widget.disabled = True

        task_text.style = ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH, color=ft.Colors.GREEN_100)
        task_container.bgcolor = ft.Colors.with_opacity(0.3, ft.Colors.GREEN_900)
        task_container.update()

        add_to_history(task_title, f"Выполнено (+{xp_reward} XP) 🎉")
        await gain_xp(xp_reward, color_theme)  # Запуск кастомной анимации шкалы
        await asyncio.sleep(1.0)

        task_container.width = 0
        task_container.height = 0
        task_container.opacity = 0
        task_container.update()

        await asyncio.sleep(0.25)
        await final_remove(task_container, task_title)

    async def check_task(e, checkbox_widget, delete_btn_widget, task_text, task_container, task_title, xp_reward,
                         color_theme):
        if e.control.value:
            await animate_complete(task_container, checkbox_widget, delete_btn_widget, task_text, task_title, xp_reward,
                                   color_theme)

    async def delete_click(e, checkbox_widget, delete_btn_widget, task_container, task_title):
        await animate_delete(task_container, checkbox_widget, delete_btn_widget, task_title)

    # Внутренняя функция создания задачи после выбора сложности во всплывающем окне
    async def create_task_with_difficulty(clean_title, difficulty):
        if difficulty == "Medium":
            xp_reward = 50
            card_bg = ft.Colors.with_opacity(0.12, ft.Colors.ORANGE_700)
            color_theme = ft.Colors.ORANGE_400  # Тема полосы опыта (желто-оранжевый)
        elif difficulty == "Hard":
            xp_reward = 75
            card_bg = ft.Colors.with_opacity(0.15, ft.Colors.RED_900)
            color_theme = ft.Colors.RED_400  # Тема полосы опыта (красноватый)
        else:
            xp_reward = 25
            card_bg = ft.Colors.with_opacity(0.1, ft.Colors.GREEN_700)
            color_theme = ft.Colors.GREEN_400  # Тема полосы опыта (зеленый)

        active_tasks_titles.add(clean_title)

        # Чистый текст задачи без префиксов
        inner_text_widget = ft.Text(value=clean_title, size=16, expand=True, overflow=ft.TextOverflow.ELLIPSIS)

        task_container = ft.Container(
            content=ft.Row(vertical_alignment=ft.CrossAxisAlignment.CENTER),
            opacity=0, offset=ft.Offset(0, -0.2), height=50, width=350, border_radius=8,
            bgcolor=card_bg,
            padding=ft.Padding(10, 0, 5, 0), animate_opacity=200,
            animate_offset=ft.Animation(250, ft.AnimationCurve.EASE_OUT),
            animate_size=ft.Animation(250, ft.AnimationCurve.EASE_IN_OUT),
        )

        checkbox = ft.Checkbox()
        delete_btn = ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, icon_color=ft.Colors.RED_300)

        # Передаем color_theme в логику чекбокса
        checkbox.on_change = lambda e: page.run_task(check_task, e, checkbox, delete_btn, inner_text_widget,
                                                     task_container,
                                                     clean_title, xp_reward, color_theme)
        delete_btn.on_click = lambda e: page.run_task(delete_click, e, checkbox, delete_btn, task_container,
                                                      clean_title)

        task_container.content.controls = [checkbox, inner_text_widget, delete_btn]
        tasks_list.controls.append(task_container)
        new_task_input.value = ""
        page.update()

        task_container.opacity = 1
        task_container.offset = ft.Offset(0, 0)
        task_container.update()

    # НАЖАТИЕ НА ПЛЮСИК (Вызывает всплывающее диалоговое окно через overlay)
    async def add_task_click(e):
        clean_title = new_task_input.value.strip()

        if not clean_title:
            return

        if clean_title in active_tasks_titles:
            page.snack_bar = ft.SnackBar(ft.Text("Этот квест уже взят! ⚔️"), open=True, bgcolor=ft.Colors.RED_800)
            page.update()
            return

        # Анимация клика по кнопке плюс
        add_task_btn.scale = 0.8
        page.update()
        await asyncio.sleep(0.1)
        add_task_btn.scale = 1.0
        page.update()

        # Функция закрытия диалога при выборе сложности
        async def select_difficulty(diff_value):
            dialog.open = False
            page.update()
            await create_task_with_difficulty(clean_title, diff_value)

        # Конструируем всплывающее меню
        dialog = ft.AlertDialog(
            title=ft.Text("Выберите сложность квеста", size=16, weight=ft.FontWeight.BOLD,
                          text_align=ft.TextAlign.CENTER),
            content=ft.Column(
                controls=[
                    ft.Button("🟢 Легко (+25 XP)", on_click=lambda _: page.run_task(select_difficulty, "Easy"),
                              width=220, color=ft.Colors.GREEN_100,
                              bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.GREEN_700)),
                    ft.Button("🟡 Средно (+50 XP)", on_click=lambda _: page.run_task(select_difficulty, "Medium"),
                              width=220, color=ft.Colors.ORANGE_100,
                              bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.ORANGE_700)),
                    ft.Button("🔴 Тяжело (+75 XP)", on_click=lambda _: page.run_task(select_difficulty, "Hard"),
                              width=220, color=ft.Colors.RED_100,
                              bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.RED_700)),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                height=140,
                width=240
            ),
            open=True
        )

        page.overlay.append(dialog)
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
                ft.Button("Закрыть", on_click=close_bottom_sheet, bgcolor=ft.Colors.AMBER, color=ft.Colors.BLACK)
            ], alignment=ft.MainAxisAlignment.CENTER),
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

    page.add(
        profile_card, history_btn, ft.Divider(height=20, color=ft.Colors.BLUE_GREY_800),
        ft.Container(content=tasks_list, padding=5),
        ft.Row(controls=[new_task_input, add_task_btn], alignment=ft.MainAxisAlignment.CENTER, width=350)
    )
    await update_profile_ui()


if __name__ == "__main__":
    ft.run(main)
