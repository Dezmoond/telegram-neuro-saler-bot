#!/usr/bin/env python3
# -*- coding: utf-8 -*-

def test_completion_logic():
    """Тестирует новую логику завершения диалога"""
    
    # Новые фразы завершения
    completion_phrases = [
        "оформляем доступ",
        "готовы к оплате", "переходим к оплате", "оформляем оплату", "оплачиваем",
        "спасибо за общение", "до связи", "удачного дня", "до свидания",
        "удачи с наймом", "до скорой встречи", "всего доброго"
    ]
    
    # Тестовые ответы
    test_responses = [
        # ❌ Не должны завершать диалог
        "Интеграция может потребовать отдельную оплату за настройку",
        "Стоимость оплаты составляет 10000 рублей",
        "Включена оплата в тариф",
        "Оплата не требуется для базового функционала",
        
        # ✅ Должны завершать диалог
        "Готовы к оплате тарифа Про",
        "Переходим к оплате",
        "Оформляем оплату прямо сейчас",
        "Спасибо за общение!",
        "До связи!",
        "Удачи с наймом!",
        "До свидания!"
    ]
    
    print("🧪 Тестирование логики завершения диалога\n")
    
    for i, response in enumerate(test_responses, 1):
        should_complete = any(phrase in response.lower() for phrase in completion_phrases)
        matched_phrases = [phrase for phrase in completion_phrases if phrase in response.lower()]
        
        status = "✅ ЗАВЕРШЕНИЕ" if should_complete else "❌ ПРОДОЛЖЕНИЕ"
        print(f"{i}. {status}")
        print(f"   Ответ: {response}")
        if matched_phrases:
            print(f"   Найденные фразы: {matched_phrases}")
        print()

if __name__ == "__main__":
    test_completion_logic()
