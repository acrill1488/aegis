import uuid
import os
import json
from datetime import datetime
from typing import List, Optional
from aegis.session.models import AegisSession


class SessionManager:
    def __init__(self):
        # Путь к файлу сессий
        self.sessions_file = "F:/AI_WORKSPACE/sessions/sessions.json"
        
        # Создаем директорию, если она не существует
        os.makedirs(os.path.dirname(self.sessions_file), exist_ok=True)
        
        # Загружаем существующие сессии
        self._sessions: dict[str, AegisSession] = {}
        self._active_session_id: Optional[str] = None
        self._load_sessions()

    def create(self, workspace: Optional[str] = None, role: str = "assistant", capability: str = "general") -> AegisSession:
        session_id = str(uuid.uuid4())
        session = AegisSession(
            id=session_id,
            created_at=datetime.now(),
            workspace=workspace,
            role=role,
            capability=capability
        )
        self._sessions[session_id] = session
        # Автоматически делаем новую сессию активной
        self._active_session_id = session_id
        self._save_sessions()
        return session

    def get(self, session_id: str) -> Optional[AegisSession]:
        return self._sessions.get(session_id)

    def list_sessions(self) -> List[AegisSession]:
        return list(self._sessions.values())

    def set_active(self, session_id: str) -> None:
        if session_id in self._sessions:
            self._active_session_id = session_id
            self._save_sessions()

    def active(self) -> Optional[AegisSession]:
        if self._active_session_id is not None:
            return self._sessions.get(self._active_session_id)
        return None

    def _load_sessions(self):
        """Загружает сессии из JSON-файла."""
        try:
            if os.path.exists(self.sessions_file):
                with open(self.sessions_file, 'r') as f:
                    data = json.load(f)
                    
                # Восстанавливаем активную сессию
                if 'active_session_id' in data:
                    self._active_session_id = data['active_session_id']
                
                # Восстанавливаем сессии
                for session_data in data.get('sessions', []):
                    # Конвертируем дату из ISO формата
                    session_data['created_at'] = datetime.fromisoformat(session_data['created_at'])
                    session = AegisSession(**session_data)
                    self._sessions[session.id] = session
        except Exception as e:
            print(f"Error loading sessions: {e}")

    def _save_sessions(self):
        """Сохраняет сессии в JSON-файл."""
        try:
            # Подготавливаем данные для сохранения
            data = {
                'active_session_id': self._active_session_id,
                'sessions': []
            }
            
            for session in self._sessions.values():
                session_dict = {
                    'id': session.id,
                    'created_at': session.created_at.isoformat(),  # Сохраняем в ISO формате
                    'workspace': session.workspace,
                    'role': session.role,
                    'capability': session.capability,
                    'metadata': session.metadata
                }
                data['sessions'].append(session_dict)
            
            # Сохраняем в файл
            with open(self.sessions_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving sessions: {e}")
