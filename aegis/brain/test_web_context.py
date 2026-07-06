"""
Test module for web context functionality.
"""

import unittest
from aegis.brain.web_context import needs_web_context, build_web_context


class TestWebContext(unittest.TestCase):
    def test_needs_web_context_keywords(self):
        """Test that keywords trigger web context detection."""
        test_cases = [
            ("Какая погода сегодня?", True),
            ("Найди последние новости", True),
            ("Сколько стоит эта модель?", True),
            ("Покажи актуальную цену", True),
            ("Какой курс валют?", True),
            ("Новости 2026 года", True),
            ("GitHub репозиторий", True),
            ("Hugging Face документация", True),
            ("Сравни библиотеки", True),
            ("Интернет поиск", True),
            ("Сайт компании", True),
            ("Ссылка на релиз", True),
            ("Новая версия 2026", True),
        ]
        
        for prompt, expected in test_cases:
            with self.subTest(prompt=prompt):
                result = needs_web_context(prompt)
                self.assertEqual(result, expected, f"Failed for prompt: {prompt}")
    
    def test_needs_web_context_no_keywords(self):
        """Test that prompts without keywords don't trigger web context."""
        test_cases = [
            "Привет, как дела?",
            "Расскажи анекдот",
            "Объясни концепцию",
            "Создай план",
            "Вычисли результат",
        ]
        
        for prompt in test_cases:
            with self.subTest(prompt=prompt):
                result = needs_web_context(prompt)
                self.assertFalse(result, f"Unexpectedly detected web context for: {prompt}")
    
    def test_needs_web_context_case_insensitive(self):
        """Test that keyword detection is case insensitive."""
        test_cases = [
            ("КАКАЯ ПОГОДА СЕГОДНЯ?", True),
            ("найди последние НОВОСТИ", True),
            ("GitHub РЕПОЗИТОРИЙ", True),
        ]
        
        for prompt, expected in test_cases:
            with self.subTest(prompt=prompt):
                result = needs_web_context(prompt)
                self.assertEqual(result, expected, f"Failed for case insensitive prompt: {prompt}")


if __name__ == '__main__':
    unittest.main()