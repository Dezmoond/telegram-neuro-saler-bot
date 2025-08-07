import json
import os
from datetime import datetime, timedelta
from typing import Dict, List

class DialogLogger:
    def __init__(self, dialogs_folder: str = "dialogs"):
        self.dialogs_folder = dialogs_folder
        if not os.path.exists(dialogs_folder):
            os.makedirs(dialogs_folder)
    
    def save_dialog(self, user_id: int, dialog_data: Dict) -> str:
        """Сохраняет диалог в файл"""
        # Создаем имя файла: user_id_YYYY-MM-DD_HH-MM-SS.json
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{user_id}_{timestamp}.json"
        filepath = os.path.join(self.dialogs_folder, filename)
        
        # Подготавливаем данные для JSON (конвертируем datetime в строки)
        json_data = self._prepare_for_json(dialog_data)
        
        # Сохраняем диалог
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        
        return filepath
    
    def _prepare_for_json(self, data):
        """Подготавливает данные для сериализации в JSON"""
        if isinstance(data, dict):
            return {key: self._prepare_for_json(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._prepare_for_json(item) for item in data]
        elif isinstance(data, datetime):
            return data.isoformat()
        else:
            return data
    
    def add_message(self, user_id: int, message: str, response: str, agent_communication: Dict) -> None:
        """Добавляет сообщение в текущий диалог пользователя"""
        timestamp = datetime.now().isoformat()
        
        # Извлекаем только текст сообщения для логирования
        response_text = response
        if isinstance(response, str) and response.strip().startswith('{'):
            try:
                import json
                response_data = json.loads(response)
                response_text = response_data.get('message', response)
            except:
                response_text = response
        
        message_data = {
            "timestamp": timestamp,
            "client_message": message,
            "neuro_salesman_response": response_text,
            "agent_communication": agent_communication,
            "full_response": response  # Сохраняем полный ответ с JSON для отладки
        }
        
        # Добавляем сообщение в диалог пользователя
        if not hasattr(self, 'current_dialogs'):
            self.current_dialogs = {}
        
        if user_id not in self.current_dialogs:
            self.current_dialogs[user_id] = {
                "user_id": user_id,
                "start_time": timestamp,
                "messages": [],
                "last_activity": datetime.now()  # Добавляем отслеживание активности
            }
        
        self.current_dialogs[user_id]["messages"].append(message_data)
        self.current_dialogs[user_id]["last_activity"] = datetime.now()  # Обновляем время активности
    
    def finish_dialog(self, user_id: int, reason: str = "manual") -> str:
        """Завершает диалог и сохраняет его в файл"""
        if not hasattr(self, 'current_dialogs') or user_id not in self.current_dialogs:
            return None
        
        dialog = self.current_dialogs[user_id].copy()  # Создаем копию
        dialog["end_time"] = datetime.now().isoformat()
        dialog["finish_reason"] = reason  # Добавляем причину завершения
        
        # Сохраняем диалог
        filepath = self.save_dialog(user_id, dialog)
        
        # Удаляем из текущих диалогов
        del self.current_dialogs[user_id]
        
        return filepath
    
    def get_dialog_summary(self, user_id: int) -> Dict:
        """Возвращает краткую информацию о текущем диалоге"""
        if not hasattr(self, 'current_dialogs') or user_id not in self.current_dialogs:
            return None
        
        dialog = self.current_dialogs[user_id]
        return {
            "user_id": user_id,
            "start_time": dialog["start_time"],
            "message_count": len(dialog["messages"]),
            "last_activity": dialog["last_activity"].isoformat() if hasattr(dialog, 'last_activity') else None,
            "last_message_time": dialog["messages"][-1]["timestamp"] if dialog["messages"] else None
        }
    
    def get_inactive_dialogs(self, timeout_minutes: int = 10) -> List[int]:
        """Возвращает список пользователей с неактивными диалогами"""
        if not hasattr(self, 'current_dialogs'):
            return []
        
        inactive_users = []
        timeout = timedelta(minutes=timeout_minutes)
        now = datetime.now()
        
        for user_id, dialog in self.current_dialogs.items():
            if "last_activity" in dialog:
                time_since_activity = now - dialog["last_activity"]
                if time_since_activity > timeout:
                    inactive_users.append(user_id)
        
        return inactive_users
    
    def cleanup_inactive_dialogs(self, timeout_minutes: int = 10) -> List[str]:
        """Завершает все неактивные диалоги и возвращает список сохраненных файлов"""
        inactive_users = self.get_inactive_dialogs(timeout_minutes)
        saved_files = []
        
        for user_id in inactive_users:
            filepath = self.finish_dialog(user_id, reason="timeout")
            if filepath:
                saved_files.append(filepath)
        
        return saved_files 