# Structured Document

## Status

Accepted for OCR Platform / Document Pipeline.

## Purpose

StructuredDocument is the official internal document contract between OCR Platform and all later AI Platform verticals.

The contract normalizes provider-specific OCR output into one stable document shape before any future ingestion, reasoning, retrieval, memory, planning, or vision workflow can consume it.

## Scope

This RFC covers only OCR Platform Document Pipeline.

Included:

- `aegis.document` package
- StructuredDocument models
- OCRResult to StructuredDocument builder
- JSON, Markdown, and Plain Text serialization
- validation of required fields, pages, block ids, and reading order
- `document.json` and `text.txt` runtime artifacts
- `document.created`, `document.validated`, and `document.saved` lifecycle events
- `aegis document validate`, `aegis document inspect`, and `aegis document export`

Excluded:

- Knowledge ingestion
- BGE
- Vector Search
- Vision Language Models
- Qwen-VL
- Memory
- Planner
- Companion

## Contract

StructuredDocument fields:

- `id`
- `source`
- `provider`
- `created_at`
- `language`
- `metadata`
- `plain_text`
- `pages`
- `attachments`
- `statistics`
- `artifacts`

Page fields:

- `number`
- `width`
- `height`
- `rotation`
- `blocks`
- `tables`
- `figures`
- `reading_order`
- `metadata`

Block fields:

- `id`
- `bbox`
- `text`
- `role`
- `confidence`
- `metadata`

Table fields:

- `rows`
- `columns`
- `cells`
- `bbox`
- `confidence`

Figure fields:

- `bbox`
- `caption`
- `metadata`

## Pipeline

The runtime flow is:

```text
OCRResult
  -> StructuredDocumentBuilder.from_ocr_result()
  -> StructuredDocumentValidator.validate()
  -> StructuredDocumentSerializer.write_json(document.json)
  -> StructuredDocumentSerializer.write_plain_text(text.txt)
  -> Document Artifact
```

## Artifact Metadata

Document artifacts include:

- provider
- page count
- block count
- table count
- language

## Compatibility

The Unlimited OCR Provider API remains unchanged. OCRResult remains the provider-neutral OCR output. StructuredDocument is added after OCRResult as a downstream normalized contract, preserving existing OCR provider and CLI behavior.
