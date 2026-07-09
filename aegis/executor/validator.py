from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ValidationResult:
    success: bool
    rule: str = ""
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class ExecutorValidator:
    """Validate an executor step without performing corrective actions."""

    def validate(
        self,
        rule: Any,
        *,
        before: Any = None,
        after: Any = None,
        action_result: Any = None,
        context: dict[str, Any] | None = None,
    ) -> ValidationResult:
        if rule in (None, {}, []):
            return ValidationResult(success=self._action_succeeded(action_result))

        if callable(rule):
            return self._custom(rule, before, after, action_result, context or {})

        if isinstance(rule, list):
            results = [
                self.validate(
                    item,
                    before=before,
                    after=after,
                    action_result=action_result,
                    context=context,
                )
                for item in rule
            ]
            failed = [result for result in results if not result.success]
            return ValidationResult(
                success=not failed,
                rule="all",
                message=failed[0].message if failed else "All validations passed.",
                metadata={"results": results},
            )

        if not isinstance(rule, dict):
            return ValidationResult(False, "invalid", "Validation rule must be a dict.")

        rule_type = str(rule.get("type") or rule.get("kind") or "").strip()
        if not rule_type and "callable" in rule:
            rule_type = "custom"

        if rule_type == "contains_text":
            return self._contains_text(rule, after)
        if rule_type == "element_exists":
            return self._element_exists(rule, after)
        if rule_type == "url_changed":
            return self._changed("url_changed", "url", before, after)
        if rule_type == "title_changed":
            return self._changed("title_changed", "title", before, after)
        if rule_type == "custom":
            callback = rule.get("callable") or rule.get("callback")
            if not callable(callback):
                return ValidationResult(False, "custom", "Custom validation is not callable.")
            return self._custom(callback, before, after, action_result, context or {})

        return ValidationResult(False, rule_type or "unknown", "Unsupported validation rule.")

    def _contains_text(self, rule: dict[str, Any], after: Any) -> ValidationResult:
        expected = str(rule.get("text") or rule.get("value") or "")
        text = self._text(after)
        success = expected in text
        return ValidationResult(
            success,
            "contains_text",
            "Text found." if success else f"Text not found: {expected}",
        )

    def _element_exists(self, rule: dict[str, Any], after: Any) -> ValidationResult:
        selector = str(rule.get("selector") or rule.get("element") or "")
        elements = self._value(after, "elements", default=[])
        success = False
        if isinstance(elements, dict):
            success = selector in elements or selector in elements.values()
        elif isinstance(elements, list):
            success = any(self._matches_element(selector, element) for element in elements)
        else:
            success = bool(selector and selector in str(elements))
        return ValidationResult(
            success,
            "element_exists",
            "Element found." if success else f"Element not found: {selector}",
        )

    def _changed(
        self,
        rule_name: str,
        field_name: str,
        before: Any,
        after: Any,
    ) -> ValidationResult:
        before_value = self._value(before, field_name)
        after_value = self._value(after, field_name)
        success = before_value != after_value
        return ValidationResult(
            success,
            rule_name,
            f"{field_name} changed." if success else f"{field_name} did not change.",
            {"before": before_value, "after": after_value},
        )

    def _custom(
        self,
        callback: Callable[..., Any],
        before: Any,
        after: Any,
        action_result: Any,
        context: dict[str, Any],
    ) -> ValidationResult:
        try:
            value = callback(before, after, action_result, context)
        except TypeError:
            value = callback(after)
        if isinstance(value, ValidationResult):
            return value
        if isinstance(value, tuple):
            success = bool(value[0])
            message = str(value[1]) if len(value) > 1 else ""
            return ValidationResult(success, "custom", message)
        return ValidationResult(bool(value), "custom")

    def _action_succeeded(self, action_result: Any) -> bool:
        if action_result is None:
            return True
        if isinstance(action_result, dict) and "success" in action_result:
            return bool(action_result["success"])
        success = getattr(action_result, "success", None)
        return True if success is None else bool(success)

    def _text(self, value: Any) -> str:
        for key in ("text", "content", "body", "title", "url"):
            item = self._value(value, key)
            if item is not None:
                return str(item)
        return str(value or "")

    def _value(self, value: Any, key: str, default: Any = None) -> Any:
        if isinstance(value, dict):
            return value.get(key, default)
        return getattr(value, key, default)

    def _matches_element(self, selector: str, element: Any) -> bool:
        if isinstance(element, dict):
            return selector in {
                str(element.get("selector", "")),
                str(element.get("id", "")),
                str(element.get("name", "")),
                str(element.get("text", "")),
            }
        return selector in str(element)
