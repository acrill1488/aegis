import os
import json
import uuid
from datetime import datetime
from typing import List, Optional

from aegis.events import EventBus

from .models import MemoryRecord

class MemoryManager:
    """Memory manager for AEGIS system."""
    
    def __init__(self, event_bus: Optional[EventBus] = None):
        self.event_bus = event_bus
        # Используем путь F:\AI_WORKSPACE\memory\memory.json как указано в задаче
        self.memory_file = r"F:\AI_WORKSPACE\memory\memory.json"
        os.makedirs(os.path.dirname(self.memory_file), exist_ok=True)
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        """Ensure the memory file exists."""
        if not os.path.exists(self.memory_file):
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                json.dump([], f)
    
    def add(self, type: str, title: str, content: str, tags: Optional[List[str]] = None, metadata: Optional[dict] = None) -> MemoryRecord:
        """Add a new memory record."""
        # Создаем уникальный ID
        record_id = str(uuid.uuid4())
        
        # Создаем запись
        record = MemoryRecord(
            id=record_id,
            created_at=datetime.now(),
            type=type,
            title=title,
            content=content,
            tags=tags or [],
            metadata=metadata or {}
        )
        
        # Читаем существующие записи
        records = self._load_records()
        
        # Добавляем новую запись
        records.append(record)
        
        # Сохраняем обновленный список
        self._save_records(records)

        return record
    
    def list(self) -> List[MemoryRecord]:
        """List all memory records."""
        return self._load_records()
    
    def search(self, query: str) -> List[MemoryRecord]:
        """Search memory records by query."""
        records = self._load_records()
        results = []
        
        for record in records:
            # Ищем в заголовке, содержимом и тегах
            if (query.lower() in record.title.lower() or 
                query.lower() in record.content.lower() or
                any(query.lower() in tag.lower() for tag in record.tags)):
                results.append(record)
        
        return results
    
    def get(self, id: str) -> Optional[MemoryRecord]:
        """Get a specific memory record by ID."""
        records = self._load_records()
        for record in records:
            if record.id == id:
                return record
        return None
    
    def list_summary(self) -> str:
        """Get a summary of all memory records."""
        records = self._load_records()
        if not records:
            return "Память пуста"
        
        summary = f"Найдено {len(records)} записей в памяти:\n"
        for record in records[:5]:  # Показываем первые 5 записей
            summary += f"- {record.title} ({record.type})\n"
        
        if len(records) > 5:
            summary += f"... и еще {len(records) - 5} записей\n"
            
        return summary
    
    def _load_records(self) -> List[MemoryRecord]:
        """Load memory records from file."""
        try:
            with open(self.memory_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Преобразуем данные в объекты MemoryRecord
            records = []
            for item in data:
                record = MemoryRecord(
                    id=item['id'],
                    created_at=datetime.fromisoformat(item['created_at']),
                    type=item['type'],
                    title=item['title'],
                    content=item['content'],
                    tags=item['tags'],
                    metadata=item['metadata']
                )
                records.append(record)
            
            return records
        except Exception:
            # Если файл поврежден или не существует, возвращаем пустой список
            return []
    
    def _save_records(self, records: List[MemoryRecord]):
        """Save memory records to file."""
        try:
            # Преобразуем объекты MemoryRecord в словари для сохранения
            data = []
            for record in records:
                data.append({
                    'id': record.id,
                    'created_at': record.created_at.isoformat(),
                    'type': record.type,
                    'title': record.title,
                    'content': record.content,
                    'tags': record.tags,
                    'metadata': record.metadata
                })
            
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            # В случае ошибки, логируем и продолжаем
            print(f"Ошибка сохранения памяти: {e}")
