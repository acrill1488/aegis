import os
from pathlib import Path
from typing import List, Dict, Optional
import yaml
import git

class WorkspaceManager:
    def __init__(self, config_path: str = "config/workspaces.yaml"):
        self.config_path = Path(config_path)
        self._config = None
    
    @property
    def config(self) -> Dict:
        if self._config is None:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    self._config = yaml.safe_load(f) or {}
            else:
                self._config = {}
        return self._config
    
    def root(self) -> Path:
        """Возвращает корневую директорию рабочего пространства"""
        root_path = self.config.get('root', '')
        if not root_path:
            # Если не задано в конфиге, используем default
            root_path = "F:\\AI_WORKSPACE"
        return Path(root_path)
    
    def ensure_structure(self) -> List[Path]:
        """Создает необходимую структуру папок"""
        workspace_root = self.root()
        folders = self.config.get('folders', {})
        
        created_paths = []
        
        # Создаем корневую директорию
        if not workspace_root.exists():
            workspace_root.mkdir(parents=True, exist_ok=True)
            created_paths.append(workspace_root)
        
        # Создаем все указанные папки
        for folder_name in folders.values():
            folder_path = workspace_root / folder_name
            if not folder_path.exists():
                folder_path.mkdir(parents=True, exist_ok=True)
                created_paths.append(folder_path)
        
        return created_paths
    
    def list_projects(self) -> List[str]:
        """Список всех проектов в рабочем пространстве"""
        workspace_root = self.root()
        folders = self.config.get('folders', {})
        
        projects_folder = workspace_root / folders.get('projects', 'projects')
        
        if not projects_folder.exists():
            return []
        
        projects = []
        for item in projects_folder.iterdir():
            if item.is_dir():
                projects.append(item.name)
        
        return projects
    
    def create_project(self, name: str) -> Path:
        """Создает новый проект"""
        workspace_root = self.root()
        folders = self.config.get('folders', {})
        
        projects_folder = workspace_root / folders.get('projects', 'projects')
        project_path = projects_folder / name
        
        if not project_path.exists():
            project_path.mkdir(parents=True, exist_ok=True)
            
            # Инициализируем git репозиторий если возможно
            try:
                git.Repo.init(project_path)
            except git.exc.GitCommandError:
                pass  # Если не удалось инициализировать git, продолжаем
            
            return project_path
        
        return project_path
    
    def project_path(self, name: str) -> Path:
        """Возвращает путь к проекту по имени"""
        workspace_root = self.root()
        folders = self.config.get('folders', {})
        
        projects_folder = workspace_root / folders.get('projects', 'projects')
        return projects_folder / name
    
    def describe_project(self, name: str) -> Dict:
        """Описание проекта"""
        project_path = self.project_path(name)
        
        # Проверяем наличие git репозитория
        has_git = False
        try:
            git.Repo(project_path)
            has_git = True
        except (git.exc.InvalidGitRepositoryError, git.exc.GitCommandError):
            pass
        
        # Проверяем наличие README файла
        readme_path = project_path / "README.md"
        has_readme = readme_path.exists()
        
        # Подсчитываем количество файлов
        file_count = 0
        if project_path.exists():
            for item in project_path.rglob("*"):
                if item.is_file():
                    file_count += 1
        
        return {
            "name": name,
            "path": str(project_path),
            "exists": project_path.exists(),
            "has_git": has_git,
            "has_readme": has_readme,
            "file_count": file_count
        }