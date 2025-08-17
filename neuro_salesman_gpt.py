import json
import re
import os
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from openai import OpenAI

class NeuroSalesmanGPT:
    def __init__(self, api_key: str = None):
        # Инициализация OpenAI
        self.client = None
        if api_key:
            self.client = OpenAI(api_key=api_key)
        else:
            # Пытаемся получить API ключ из переменных окружения
            env_api_key = os.getenv('OPENAI_API_KEY')
            if env_api_key and env_api_key != "your_openai_api_key_here":
                self.client = OpenAI(api_key=env_api_key)
            else:
                print("⚠️  OpenAI API ключ не настроен. Бот будет работать в тестовом режиме.")
        
        # Загружаем суперпромт
        self.system_prompt = self._load_super_prompt()
        
        # История диалогов для каждого пользователя
        self.conversation_history = {}
        
    def _load_super_prompt(self) -> str:
        """Загружает суперпромт из файла"""
        try:
            with open('Промт нейро-продажника для API верс 3_1.txt', 'r', encoding='utf-8') as file:
                return file.read()
        except FileNotFoundError:
            return "Промт не найден"
    
    def _get_conversation_history(self, user_id: int) -> List[Dict]:
        """Получает историю диалога для пользователя"""
        if user_id not in self.conversation_history:
            self.conversation_history[user_id] = []
        return self.conversation_history[user_id]
    
    def _add_to_history(self, user_id: int, role: str, content: str):
        """Добавляет сообщение в историю диалога"""
        history = self._get_conversation_history(user_id)
        history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
    
    def _generate_response_with_gpt(self, user_id: int, user_message: str) -> Tuple[str, Dict]:
        """Генерирует ответ используя GPT и суперпромт"""
        
        # Добавляем сообщение пользователя в историю
        self._add_to_history(user_id, "user", user_message)
        
        # Если клиент не инициализирован, возвращаем тестовый ответ
        if not self.client:
            test_response = f"Тестовый режим: Получено сообщение '{user_message}'. Для полноценной работы настройте OPENAI_API_KEY."
            self._add_to_history(user_id, "assistant", test_response)
            return test_response, {}
        
        # Формируем сообщения для GPT
        messages = [
            {
                "role": "system",
                "content": self.system_prompt
            }
        ]
        
        # Добавляем историю диалога
        history = self._get_conversation_history(user_id)
        for msg in history[:-1]:  # Исключаем последнее сообщение пользователя
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        # Добавляем текущее сообщение пользователя
        messages.append({
            "role": "user",
            "content": user_message
        })
        
        try:
            # Добавляем небольшую задержку для избежания превышения лимитов
            time.sleep(1)
            
            # Вызываем GPT с форматированием JSON
            response = self.client.chat.completions.create(
                model="gpt-4.1-mini",  # Используем gpt-4.1-mini
                messages=messages,
                temperature=0.25,  # Немного увеличиваем для более живого общения
                top_p=1.0,  # Контролируем разнообразие ответов
                frequency_penalty=0.2,  # Снижаем повторения
                presence_penalty=0.1,  # Поощряем новые темы
                max_tokens=1000,
                response_format={'type': 'json_object'}  # Заставляем GPT возвращать JSON
            )
            
            # Получаем ответ
            assistant_response = response.choices[0].message.content
            
            # Добавляем ответ ассистента в историю
            self._add_to_history(user_id, "assistant", assistant_response)
            
            # Парсим JSON ответ
            try:
                response_data = json.loads(assistant_response)
                agent_communication = response_data.get('agent_communication', {})
                message_text = response_data.get('message', assistant_response)
                return message_text, agent_communication
            except json.JSONDecodeError:
                # Если JSON не парсится, возвращаем как есть
                return assistant_response, {}
            
        except Exception as e:
            error_response = f"Извините, произошла ошибка при обработке вашего сообщения: {str(e)}"
            return error_response, {}
    
    def _extract_agent_communication(self, response: str) -> Dict:
        """Извлекает информацию о коммуникации агентов из ответа"""
        # Пытаемся найти JSON в ответе
        try:
            # Ищем JSON блок
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                return json.loads(json_str)
        except:
            pass
        
        # Если JSON не найден, создаем базовую структуру
        return {
            "agent_communication": {
                "agent_branch": {"input": "user_message", "output": "sales"},
                "agent_block": {"input": "sales", "output": "qualification"},
                "agent_profile": {"input": "qualification", "output": {}},
                "final_agent": {"type": "gpt_response", "input": {}, "output": response}
            }
        }
    

    
    def process_message(self, user_id: int, message: str) -> Tuple[str, Dict]:
        """Основной метод обработки сообщения пользователя"""
        
        # Генерируем ответ с помощью GPT и суперпромта
        response, agent_communication = self._generate_response_with_gpt(user_id, message)
        
        return response, agent_communication
    
    def get_conversation_history(self, user_id: int) -> List[Dict]:
        """Возвращает историю диалога пользователя"""
        return self._get_conversation_history(user_id)
    
    def reset_conversation(self, user_id: int):
        """Сбрасывает историю диалога для пользователя"""
        if user_id in self.conversation_history:
            del self.conversation_history[user_id] 