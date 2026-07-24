"""OCR Runtime event names."""

OCR_STARTED = "ocr.started"
OCR_COMPLETED = "ocr.completed"
OCR_FAILED = "ocr.failed"
OCR_PROVIDER_SELECTED = "ocr.provider.selected"
OCR_ARTIFACT_SAVED = "ocr.artifact.saved"
OCR_PROGRESS = "ocr.progress"
OCR_SERVICE_UNAVAILABLE = "ocr.service.unavailable"
OCR_MODEL_LOAD_FAILED = "ocr.model.load_failed"
OCR_INFERENCE_FAILED = "ocr.inference.failed"
OCR_RESOURCE_EXHAUSTED = "ocr.resource.exhausted"
DOCUMENT_CREATED = "document.created"
DOCUMENT_VALIDATED = "document.validated"
DOCUMENT_SAVED = "document.saved"

OCR_EVENTS = {
    "started": OCR_STARTED,
    "completed": OCR_COMPLETED,
    "failed": OCR_FAILED,
    "provider_selected": OCR_PROVIDER_SELECTED,
    "artifact_saved": OCR_ARTIFACT_SAVED,
    "progress": OCR_PROGRESS,
    "service_unavailable": OCR_SERVICE_UNAVAILABLE,
    "model_load_failed": OCR_MODEL_LOAD_FAILED,
    "inference_failed": OCR_INFERENCE_FAILED,
    "resource_exhausted": OCR_RESOURCE_EXHAUSTED,
    "document_created": DOCUMENT_CREATED,
    "document_validated": DOCUMENT_VALIDATED,
    "document_saved": DOCUMENT_SAVED,
}

__all__ = [
    "DOCUMENT_CREATED",
    "DOCUMENT_SAVED",
    "DOCUMENT_VALIDATED",
    "OCR_ARTIFACT_SAVED",
    "OCR_COMPLETED",
    "OCR_EVENTS",
    "OCR_FAILED",
    "OCR_INFERENCE_FAILED",
    "OCR_MODEL_LOAD_FAILED",
    "OCR_PROVIDER_SELECTED",
    "OCR_PROGRESS",
    "OCR_RESOURCE_EXHAUSTED",
    "OCR_SERVICE_UNAVAILABLE",
    "OCR_STARTED",
]
