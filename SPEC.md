# iPDF 0.1 — Interactive Paper Document Format

Status: experimental, open JSON interchange format. MIME: `application/json`.
Extensions: `.ipdf.json` (data) and `.ipdf.html` (portable viewer + data).
UTF-8, 1-based source page numbers, stable IDs, and no executable content in data.
The normative validation contract is `app/schema.py` (Pydantic v2). Unknown fields
and versions are rejected; readers must explicitly support a version.

## Required top-level shape

```json
{
  "ipdf_version": "0.1",
  "meta": {"title":"Paper", "authors":[], "source_url":"https://example.org/paper.pdf", "level":"beginner", "pages":1, "paper_id":"sha256"},
  "sections": [{"id":"p1", "title":"Introduction", "page":1, "text":"Original source text."}],
  "glossary": [], "flashcards": [], "charts": [], "narration": [],
  "provenance": {"model":"configured-provider-model", "prompt_versions":{}, "generated_at":"2026-10-23T00:00:00Z"},
  "tables": [], "figures": [], "issues": [], "assets": {}
}
```

`level`: `beginner`, `intermediate`, or `expert`. Source section text is extracted,
never rewritten as a summary. Collections may be empty when generation/extraction
fails. `issues` records the affected plugin/page and a safe diagnostic message.
`meta.pages` and `meta.paper_id` are optional extensions on input: readers can
infer the highest source page and a stable content identity when absent. The app
always writes them. `simpler_script` is optional for external producers; the app's
narration plugin always supplies it. Readers must explain when simpler replay is
unavailable rather than silently generating it.

## Generated blocks

Every generated glossary entry, flashcard, chart, and narration has `page` and:

```json
{"generated_by":{"plugin":"glossary", "prompt_version":"glossary/0.1.0", "model":"actual-model-used", "source_page":1}}
```

`source_page` must equal `page`. Sections are ordered by page. `section_id`
references an existing section on the same page. IDs are unique within collections.
The global provenance also records prompt versions, actual backends, generation
time, token counts and recorded dollar cost; unset prices are explicitly marked.

| Collection | Additional fields |
|---|---|
| `glossary` | `term`, `definition`, `section_id` |
| `flashcards` | `id`, `front`, `back`, `section_id` |
| `narration` | `section_id`, `script`, `simpler_script`, `audio_url` (nullable), `simpler_audio_url` (nullable) |
| `charts` | `id`, `type` (`bar`/`line`), `title`, `series`, `source_table`, `caption` |

Narration is one segment per source section when generation succeeds. Scripts are
spoken English with an intro and outro, short sentences, no Markdown, and equations
described in words. A pre-generated `simpler_script` permits walking-mode replay
without any model call from the renderer. Scripts are capped at 3,800 / 1,800
characters, respectively, so each fits one hosted speech request.

## Tables and chart evidence

`tables` is an evidence extension containing `{id,label,page,cells,extraction}`.
`cells` is a rectangular or ragged grid of original strings/nulls, extracted by
PyMuPDF. `extraction` is `pymupdf`. Rows and columns are **zero-based** in cell refs.
The original table caption/number is used when detected; otherwise the label is
`Unnumbered table <index>` and that fact stays visible.

Each chart series is:

```json
{"name":"Accuracy (%)", "labels":["Baseline","Method"], "values":[81.2,85.7], "source_cells":[{"row":1,"column":1},{"row":2,"column":1}]}
```

Every value MUST match a whole-cell number parsed from `source_table` at the exact
given coordinate. Currency symbols, grouping commas, scientific notation and a
trailing percent sign are accepted; uncertainty pairs, intervals and ambiguous
multi-number cells are rejected. Percent values retain the source scale (81.2%,
not 0.812). Non-finite values are forbidden. An LLM selects rows/columns but NEVER
supplies plotted values. No detected usable table means no chart. The document
validator rechecks all numeric references independently of the generation plugin.

Caption is exactly `from Table N, p.X` (or the detected unnumbered-table label),
and the viewer links it to the original PDF at `#page=X`. This rule also applies
to downloaded/exported JSON loaded by another renderer.

## Figures and assets

`figures`: `{id,page,caption,data_url}` containing only extracted raster image
assets. Decorative images/small logos may be omitted. No image is AI generated.
`assets.original_pdf` optionally embeds a PDF data URL in the self-contained HTML
export. Export can also replace hosted audio URLs with base64 audio data URLs.
The web version may instead link to its stored PDF. Figure data URLs are limited
to PNG/JPEG/WebP; original PDF assets to PDF; audio to MPEG. Renderers insert text
with text nodes, and only accept safe HTTP(S), relative or typed data URLs.

## Layers

1. `ingest/`: PDF/arXiv -> page-tagged sections, tables, figures; no model calls.
2. `generate/`: independent plugins -> validated blocks with model, prompt
   version and source page; at most two retries, then drop/log the invalid block.
   Optional DEEP selects tables and judges grounding, otherwise FAST is used.
3. `render/`: viewer/audio player reads ONLY valid iPDF JSON. It never invokes
   generation, extraction or an LLM. Browser speech uses scripts already in JSON.

The orchestration layer coordinates these layers and job progress. Renderers may
request cached/hosted audio synthesis for an existing script. That request performs
no LLM work. `Explain simpler` selects the existing simpler narration.

Generation cache identity: `(paper content hash, level, FAST model, DEEP model,
prompt versions)`. A provider failure is recorded, never presented as successful
AI output. Source-only documents remain valid and readable without credentials.
