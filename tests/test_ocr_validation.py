from aegis.ocr.validation import validate_recognition


def test_cli_artifact_paths_are_printed_once(monkeypatch):
    from io import StringIO

    from rich.console import Console

    from aegis.ocr import cli
    from aegis.ocr.models import OCRResult

    stream = StringIO()
    monkeypatch.setattr(cli, "console", Console(file=stream, force_terminal=False))
    result = OCRResult(
        provider="unlimited",
        text="recognized",
        artifacts=[
            {"path": "result.txt"},
            {"path": "result.txt", "id": "registered-copy"},
            {"path": "result.json"},
        ],
    )
    cli._print_result(result, json_output=False)
    output = stream.getvalue()
    assert output.count("result.txt") == 1
    assert output.count("result.json") == 1


def test_markdown_image_only_is_not_valid_recognition():
    result = validate_recognition("![](images/0.jpg)\n")
    assert result.valid is False
    assert result.reason == "markdown_images_only"
    assert result.visible_text_length == 0
    assert result.markdown_image_count == 1


def test_visible_text_with_markdown_image_is_valid():
    result = validate_recognition("Просроченная задолженность\n![](images/0.jpg)")
    assert result.valid is True
    assert result.visible_text_length > 0
    assert result.markdown_image_count == 1


def test_html_image_and_bare_image_path_are_not_text():
    assert validate_recognition('<img src="scan.png">').valid is False
    assert validate_recognition("images/page-1.jpg").valid is False


def test_detection_image_placeholder_is_not_text():
    result = validate_recognition("<|det|>image [176, 0, 825, 999]<|/det|>")
    assert result.valid is False
    assert result.visible_text_length == 0


def test_unreadable_and_detection_coordinates_are_not_text():
    result = validate_recognition("<|det|>title [0, 0, 123, 14]<|/det|>[Unreadable]")
    assert result.valid is False
