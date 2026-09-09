import ssl
import urllib.request
import json
import os
import asyncio
from datetime import datetime

ssl._create_default_https_context = ssl._create_unverified_context

import flet as ft

SAVE_FILE = "rpg_data.json"

async def main(page: ft.Page):
    page.title = "Task RPG: Protected Edition"
    page.theme_mode = ft.ThemeMode.DARK
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.scroll = "adaptive"
    page.padding = 20

    # Загрузка данных
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE, "r", encoding="utf-8") as f:
                user_data = json.load(f)
                if "history" not in user_data:
                    user_data["history"] = []
                else:
                    validated_history = []
                    for item in user_data["history"]:
                        if isinstance(item, dict) and all(k in item for k in ("title", "status", "time")):
                            validated_history.append(item)
                    user_data["history"] = validated_history

                if "level" not in user_data or "xp" not in user_data or "xp_to_next" not in user_data:
                    raise ValueError("Missing critical fields")

                if "tasks" not in user_data:
                    user_data["tasks"] = []
        except Exception:
            user_data = {"level": 1, "xp": 0, "xp_to_next": 100, "history": [], "tasks": []}
    else:
        user_data = {"level": 1, "xp": 0, "xp_to_next": 100, "history": [], "tasks": []}

    xp_lock = asyncio.Lock()

    def save_progress():
        try:
            with open(SAVE_FILE, "w", encoding="utf-8") as f:
                json.dump(user_data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            page.snack_bar = ft.SnackBar(
                content=ft.Text(f"❌ Ошибка сохранения: {e}", color=ft.Colors.RED_200),
                bgcolor=ft.Colors.RED_900,
                open=True
            )
            page.update()
            print(f"Ошибка сохранения: {e}")

    def get_grade(lvl):
        if lvl < 5: return "Новичок 🪵"
        elif lvl < 10: return "Искатель 🧭"
        elif lvl < 20: return "Ветеран ⚔️"
        elif lvl < 40: return "Мастер 🔮"
        else: return "Легенда 👑"

    def add_to_history(task_title, status):
        safe_title = str(task_title).strip().replace("\n", " ")
        current_time = datetime.now().strftime("%H:%M:%S")
        user_data["history"].insert(0, {"title": safe_title, "status": status, "time": current_time})
        user_data["history"] = user_data["history"][:30]
        save_progress()

    # --- Профиль ---
    lvl_text = ft.Text(value=f"Уровень {user_data['level']}", size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER)
    grade_text = ft.Text(value=get_grade(user_data['level']), size=13, weight=ft.FontWeight.W_300, color=ft.Colors.AMBER_200)
    xp_text = ft.Text(value=f"{user_data['xp']} / {user_data['xp_to_next']} XP", size=12, color=ft.Colors.BLUE_200)

    MAX_BAR_WIDTH = 300
    xp_progress_fill = ft.Container(
        width=int(MAX_BAR_WIDTH * (user_data["xp"] / user_data["xp_to_next"])),
        height=12,
        bgcolor=ft.Colors.AMBER,
        border_radius=6,
        animate=ft.Animation(600, ft.AnimationCurve.EASE_OUT)
    )
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
            content=ft.Column(controls=[lvl_text, grade_text, xp_progress, xp_text], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=15,
        ),
        margin=10,
        animate_scale=ft.Animation(300, ft.AnimationCurve.BOUNCE_OUT)
    )

    async def update_profile_ui():
        lvl_text.value = f"Уровень {user_data['level']}"
        grade_text.value = get_grade(user_data['level'])
        xp_text.value = f"{user_data['xp']} / {user_data['xp_to_next']} XP"
        progress_ratio = min(1.0, max(0.0, user_data["xp"] / user_data["xp_to_next"]))
        xp_progress_fill.width = int(MAX_BAR_WIDTH * progress_ratio)
        save_progress()
        page.update()

    async def gain_xp(amount=25, color_theme=ft.Colors.AMBER):
        async with xp_lock:
            user_data["xp"] += amount
            xp_progress_fill.bgcolor = color_theme
            page.update()
            level_up_messages = []

            while user_data["xp"] >= user_data["xp_to_next"]:
                xp_progress_fill.width = MAX_BAR_WIDTH
                page.update()
                await asyncio.sleep(0.4)

                user_data["xp"] -= user_data["xp_to_next"]
                user_data["level"] += 1
                user_data["xp_to_next"] = int(user_data["xp_to_next"] * 1.2)

                await update_profile_ui()

                xp_progress_fill.animate = None
                xp_progress_fill.width = 0
                profile_card.scale = 1.12
                page.update()
                await asyncio.sleep(0.1)

                xp_progress_fill.animate = ft.Animation(600, ft.AnimationCurve.EASE_OUT)
                page.update()
                await asyncio.sleep(0.2)

                profile_card.scale = 1.0
                page.update()
                level_up_messages.append(f"🎉 Грейд повышен! Теперь вы: {get_grade(user_data['level'])} ({user_data['level']} ур.)")

            if level_up_messages:
                final_msg = "\n".join(level_up_messages) if len(level_up_messages) > 1 else level_up_messages[0]
                page.snack_bar = ft.SnackBar(content=ft.Text(final_msg, size=14), bgcolor=ft.Colors.AMBER_800, open=True)
                page.update()

            await update_profile_ui()
            await asyncio.sleep(0.6)
            xp_progress_fill.bgcolor = ft.Colors.AMBER
            page.update()

    # --- Список задач ---
    tasks_list = ft.Column(spacing=10, width=350)
    active_tasks_titles = set()
    processing_tasks = set()

    def create_task_container(clean_title, difficulty, save_to_file=True, update_now=True):
        if clean_title not in active_tasks_titles:
            active_tasks_titles.add(clean_title)

        if difficulty == "Medium":
            xp_reward = 50
            card_bg = ft.Colors.with_opacity(0.12, ft.Colors.ORANGE_700)
            color_theme = ft.Colors.ORANGE_400
        elif difficulty == "Hard":
            xp_reward = 75
            card_bg = ft.Colors.with_opacity(0.15, ft.Colors.RED_900)
            color_theme = ft.Colors.RED_400
        else:
            xp_reward = 25
            card_bg = ft.Colors.with_opacity(0.1, ft.Colors.GREEN_700)
            color_theme = ft.Colors.GREEN_400

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

        async def check_task(e, cb, db, text_widget, container, title, reward, color):
            if e.control.value:
                await animate_complete(container, cb, db, text_widget, title, reward, color)

        async def delete_click(e, cb, db, container, title):
            await animate_delete(container, cb, db, title)

        checkbox.on_change = lambda e: page.run_task(check_task, e, checkbox, delete_btn, inner_text_widget,
                                                     task_container, clean_title, xp_reward, color_theme)
        delete_btn.on_click = lambda e: page.run_task(delete_click, e, checkbox, delete_btn, task_container, clean_title)

        task_container.content.controls = [checkbox, inner_text_widget, delete_btn]
        tasks_list.controls.append(task_container)

        task_container.opacity = 1
        task_container.offset = ft.Offset(0, 0)

        if save_to_file:
            user_data["tasks"].append({"title": clean_title, "difficulty": difficulty})
            save_progress()

        if update_now:
            page.update()
        return task_container

    # --- Плавное удаление с вертикальным сдвигом ---
    async def animate_delete(task_container, checkbox_widget, delete_btn_widget, task_title):
        if task_title in processing_tasks:
            return
        processing_tasks.add(task_title)
        try:
            checkbox_widget.disabled = True
            delete_btn_widget.disabled = True

            controls = tasks_list.controls
            index = controls.index(task_container) if task_container in controls else -1
            if index == -1:
                return

            height = 50  # фиксированная высота контейнера

            # Сдвигаем все контейнеры ниже удаляемого вверх на высоту
            for i in range(index + 1, len(controls)):
                controls[i].offset = ft.Offset(0, -height)
                controls[i].animate_offset = ft.Animation(300, ft.AnimationCurve.EASE_OUT)

            # Анимируем исчезновение удаляемого
            task_container.height = 0
            task_container.opacity = 0
            task_container.update()

            # Ждём завершения анимации сдвига и исчезновения
            await asyncio.sleep(0.35)

            # Удаляем контейнер из списка
            if task_container in controls:
                controls.remove(task_container)

            # Сбрасываем смещения у оставшихся (они уже на месте) без анимации
            for c in controls:
                # Отключаем анимацию, чтобы не было рывка
                c.animate_offset = None
                c.offset = ft.Offset(0, 0)
                # Восстанавливаем анимацию для будущих операций
                c.animate_offset = ft.Animation(250, ft.AnimationCurve.EASE_OUT)

            add_to_history(task_title, "Удалено ❌")
            user_data["tasks"] = [t for t in user_data["tasks"] if t["title"] != task_title]
            save_progress()
            active_tasks_titles.discard(task_title)
        finally:
            processing_tasks.discard(task_title)
            page.update()

    async def animate_complete(task_container, checkbox_widget, delete_btn_widget, task_text, task_title, xp_reward, color_theme):
        if task_title in processing_tasks:
            return
        processing_tasks.add(task_title)
        try:
            checkbox_widget.disabled = True
            delete_btn_widget.disabled = True

            task_text.style = ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH, color=ft.Colors.GREEN_100)
            task_container.bgcolor = ft.Colors.with_opacity(0.3, ft.Colors.GREEN_900)
            task_container.update()

            add_to_history(task_title, f"Выполнено (+{xp_reward} XP) 🎉")
            user_data["tasks"] = [t for t in user_data["tasks"] if t["title"] != task_title]
            save_progress()

            await gain_xp(xp_reward, color_theme)

            # Такая же анимация удаления
            controls = tasks_list.controls
            index = controls.index(task_container) if task_container in controls else -1
            if index == -1:
                return

            height = 50
            for i in range(index + 1, len(controls)):
                controls[i].offset = ft.Offset(0, -height)
                controls[i].animate_offset = ft.Animation(300, ft.AnimationCurve.EASE_OUT)

            task_container.height = 0
            task_container.opacity = 0
            task_container.update()

            await asyncio.sleep(0.35)

            if task_container in controls:
                controls.remove(task_container)

            for c in controls:
                c.animate_offset = None
                c.offset = ft.Offset(0, 0)
                c.animate_offset = ft.Animation(250, ft.AnimationCurve.EASE_OUT)

            active_tasks_titles.discard(task_title)
        finally:
            processing_tasks.discard(task_title)
            page.update()

    # -----------------------------------------

    async def create_task_with_difficulty(clean_title, difficulty):
        create_task_container(clean_title, difficulty, save_to_file=True, update_now=True)
        new_task_input.value = ""
        page.update()

    # --- Добавление задачи ---
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

        add_task_btn.disabled = True
        page.update()

        async def select_difficulty(diff_value):
            dialog.open = False
            page.update()
            add_task_btn.disabled = False
            page.update()
            await create_task_with_difficulty(clean_title, diff_value)

        def on_dialog_dismiss(e):
            add_task_btn.disabled = False
            page.update()

        dialog = ft.AlertDialog(
            title=ft.Text("Выберите сложность квеста", size=16, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
            content=ft.Column(
                controls=[
                    ft.Button("🟢 Легко (+25 XP)", on_click=lambda _: page.run_task(select_difficulty, "Easy"),
                              width=220, color=ft.Colors.GREEN_100, bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.GREEN_700)),
                    ft.Button("🟡 Средне (+50 XP)", on_click=lambda _: page.run_task(select_difficulty, "Medium"),
                              width=220, color=ft.Colors.ORANGE_100, bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.ORANGE_700)),
                    ft.Button("🔴 Тяжело (+75 XP)", on_click=lambda _: page.run_task(select_difficulty, "Hard"),
                              width=220, color=ft.Colors.RED_100, bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.RED_700)),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                height=140,
                width=240
            ),
            on_dismiss=on_dialog_dismiss,
            open=True
        )
        page.overlay.append(dialog)
        page.update()

    # --- История ---
    history_list = ft.ListView(expand=True, spacing=10, padding=10)

    def close_bottom_sheet(e):
        bs.open = False
        page.update()

    bs = ft.BottomSheet(
        content=ft.Container(
            content=ft.Column(controls=[
                ft.Container(content=ft.Text("📜 История квестов", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER),
                             margin=ft.Margin(0, 10, 0, 10), alignment=ft.alignment.Alignment(0, 0)),
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
            history_list.controls.append(ft.Text("История пока пуста. Выполните квест! ⚔️", size=14, color=ft.Colors.GREY_500, text_align=ft.TextAlign.CENTER))
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

    # --- Управление ---
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

    # Восстановление задач
    for task in user_data.get("tasks", []):
        title = task.get("title", "")
        difficulty = task.get("difficulty", "Easy")
        if title and title not in active_tasks_titles:
            create_task_container(title, difficulty, save_to_file=False, update_now=False)
        elif title:
            print(f"Дубликат задачи '{title}' пропущен при восстановлении.")

    page.update()
    await update_profile_ui()

if __name__ == "__main__":
    ft.run(main)
