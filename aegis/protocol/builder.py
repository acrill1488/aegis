"""Response Protocol v1 prompt instructions."""


class ProtocolBuilder:
    """Build system instructions for structured model responses."""

    def build_instruction(self) -> str:
        """Return the Response Protocol v1 system instruction."""

        return """\
Response Protocol v1.
Ты обязан завершить ответ строкой:
FINAL:
После FINAL напиши только итоговый ответ пользователю на русском.
Не пиши reasoning до FINAL.
Если всё же написал reasoning, ProtocolParser возьмёт только текст после FINAL.
Не показывай пользователю reasoning, <think>, JSON tool calls или служебные поля.
"""


def build_response_protocol_instruction() -> str:
    """Convenience wrapper for the default protocol instruction."""

    return ProtocolBuilder().build_instruction()
