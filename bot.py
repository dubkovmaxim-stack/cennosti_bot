@dp.message(GameStates.stage2_round)
async def handle_stage2_input(message: types.Message, state: FSMContext):
    """Обработка ввода на Stage2"""
    user_id = message.from_user.id
    
    if user_id not in active_games:
        await message.answer("❌ Начните тест заново", reply_markup=get_main_keyboard())
        return
    
    game = active_games[user_id]
    text = message.text.strip()
    
    # Обработка специальных команд
    if text == "🔄 ПОВТОРИТЬ ВВОД":
        await send_next_round(message, game, state)
        return
    
    if text == "🏁 ЗАВЕРШИТЬ ТЕСТ":
        await message.answer("❌ Тест прерван. Начните заново: 🎮 НАЧАТЬ ТЕСТ", reply_markup=get_main_keyboard())
        await state.clear()
        return
    
    # Проверяем что это число от 1 до 4
    if text not in ["1", "2", "3", "4"]:
        await message.answer("❌ Нажмите кнопку 1-4", reply_markup=get_stage2_keyboard())
        return
    
    choice_index = int(text) - 1
    
    # Проверяем валидность выбора
    if choice_index >= len(game.current_values):
        await message.answer(f"❌ Выберите число от 1 до {len(game.current_values)}", reply_markup=get_stage2_keyboard())
        return
    
    # Обрабатываем выбор
    success = game.process_stage2_choice(choice_index)
    
    if success:
        await send_next_round(message, game, state)
    else:
        await message.answer("❌ Ошибка обработки. Попробуйте еще раз.", reply_markup=get_stage2_keyboard())
