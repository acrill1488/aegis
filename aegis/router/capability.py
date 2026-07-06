class CapabilityRouter:
    def detect(self, prompt: str) -> str:
        """
        Detect the capability based on the prompt content.
        
        Args:
            prompt (str): The input prompt to analyze
            
        Returns:
            str: The detected capability ("coding", "vision", "image", or "general")
        """
        # Convert prompt to lowercase for case-insensitive matching
        lower_prompt = prompt.lower()
        
        # Check for coding-related keywords
        coding_keywords = [
            'code', 'python', 'powershell', 'docker', 'git', 
            'ошибка', 'код', 'скрипт', 'файл', 'проект', 
            'тест', 'commit', 'refactor', 'рефакторинг'
        ]
        
        if any(keyword in lower_prompt for keyword in coding_keywords):
            return "coding"
            
        # Check for vision-related keywords
        vision_keywords = [
            'экран', 'скриншот', 'вижу', 'посмотри', 
            'окно', 'изображение', 'картинка'
        ]
        
        if any(keyword in lower_prompt for keyword in vision_keywords):
            return "vision"
            
        # Check for image generation keywords
        image_keywords = [
            'нарисуй', 'сгенерируй изображение', 'картинку', 
            'логотип', 'дизайн'
        ]
        
        if any(keyword in lower_prompt for keyword in image_keywords):
            return "image"
            
        # Default to general capability
        return "general"