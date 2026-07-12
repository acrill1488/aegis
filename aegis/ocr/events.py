"""OCR Runtime event names."""

OCR_STARTED = "ocr.started"
OCR_COMPLETED = "ocr.completed"
OCR_FAILED = "ocr.failed"
OCR_PROVIDER_SELECTED = "ocr.provider.selected"
OCR_ARTIFACT_SAVED = "ocr.artifact.saved"

OCR_EVENTS = {
    "started": OCR_STARTED,
    "completed": OCR_COMPLETED,
    "failed": OCR_FAILED,
    "provider_selected": OCR_PROVIDER_SELECTED,
    "artifact_saved": OCR_ARTIFACT_SAVED,
}

__all__ = [
    "OCR_ARTIFACT_SAVED",
    "OCR_COMPLETED",
    "OCR_EVENTS",
    "OCR_FAILED",
    "OCR_PROVIDER_SELECTED",
    "OCR_STARTED",
]
