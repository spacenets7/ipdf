# iPDF validation — 23 October 2026

## Implementation/process checks

| Step | Actual result |
|---|---|
| 1. Hosted-only pivot | Passed. App boots with no keys; mocked clients work. Removed inference service from Compose, local speech dependency from requirements/venv, and downloaded local model/voice artifacts. Digest source preserved under `app/modules/digest/`. |
| 2. Format | Passed. `SPEC.md`, Pydantic iPDF 0.1 and generated JSON Schema. Tests reject bad versions, pages, section refs, captions and invented chart numbers. |
| 3. Ingestion | Passed on three downloaded real arXiv PDFs. Source pages/text, tables and raster figures extracted with PyMuPDF. TLS failure fixed using bounded official-host retries. |
| 4. Learning plugins | Complete implementation; mocked hosted-client end-to-end passes at beginner/intermediate/expert. **Live hosted output not run: LLM_API_KEY and LLM_MODEL are still blank.** `scripts/validate_hosted.py` reports this explicitly. |
| 5. Charts | Deterministic evidence mapping verified against tables in all three real PDFs. Hosted selection remains pending credentials. Chart values always come from parsed cells, with independent document validation. |
| 6. Viewer | Passed in the browser: source sections, glossary popover, saved deck, chart and inspectable numeric values. Fixture is labelled MOCKED UI FIXTURE and is not counted as hosted output. |
| 7. Audio/mobile | Browser speech entered playback and completed simpler replay at a 390 px viewport; walking mode controls and section highlighting verified. Media Session handlers implemented. Physical phone / lock-screen behavior not tested. ElevenLabs failure/cache behavior tested with mocks; no real API call without keys. |
| 8. Exports/deployment | Raw JSON and HTML exports pass. Standalone HTML loaded on a separate static server with embedded PDF Blob page links and no external CSS/JS. Docker Compose configuration passes validation; Docker engine is unavailable, so no image build/container run or public deployment is claimed. |
| 9. Tests/E2E | **34 passed** in the final suite. Three real-paper source-only HTTP runs completed, including create/status/view/JSON/HTML exports. |

## Real PDFs and table evidence

| Paper | arXiv | Pages | Conservative table candidates | Verified chart evidence |
|---|---|---:|---:|---|
| Attention Is All You Need | 1706.03762 | 15 | 1 | Table 4, p.10; WSJ 23 F1 values including 88.3, 90.4, 91.7, 91.3 |
| BERT | 1810.04805 | 16 | 5 | Table 1, p.6; QQP values 66.1, 64.8, 70.3, 71.2, 72.1 |
| Deep Residual Learning for Image Recognition | 1512.03385 | 12 | 6 | Table 5, p.6; top-5 error values 7.32, 6.66, 6.8, 4.94, 4.82, 3.57 |

These charts were built using explicitly deterministic test plans, **not an
unconfigured hosted model**. Each plotted point includes its zero-based cell
coordinate, and Pydantic independently verifies the original parsed value.
Borderless candidates containing prose or fragmented decimal columns were
rejected. Candidate counts are not a claim that every table in the paper was found.

## Live HTTP run

| Paper / level | POST create response | Create → validated viewer + both exports |
|---|---:|---:|
| Attention / beginner | 62 ms | 5.86 s |
| BERT / intermediate | 31 ms | 6.06 s |
| ResNet / expert | 31 ms | 7.11 s |

All three editions are explicitly source-only: **zero generated glossary entries,
flashcards, charts and narration** while hosted credentials are absent. This is
not represented as AI generation success or a hosted performance benchmark.
Full annotated workflows are covered by mocked OpenAI-compatible HTTP responses
at all three levels; those tests assert render/export/audio do not call an LLM.

## Browser proof

At a requested viewport of **390 × 844**, the page's scroll width equalled its
client width (375 CSS px after the desktop browser's 15 px scrollbar), so there
was no horizontal document overflow. The browser reported no JavaScript errors.

- `data/validation/ui-popover-390.png`: glossary tap and save-to-deck state.
- `data/validation/ui-walking-390.png`: simpler replay in walking mode.
- `data/validation/ui-standalone-chart-390.png`: portable chart and source cells.

These use the clearly labelled mocked UI fixture, with real numeric table
evidence. Standalone export loads without FastAPI rendering or a CDN and links
to its embedded original PDF using a Blob URL at the referenced page.

## Remaining external checks

1. Fill `LLM_API_KEY` and `LLM_MODEL` in `.env`, restart the app, and run
   `python scripts/validate_hosted.py` for real output on one paper at all levels.
2. Re-run `python scripts/validate_e2e.py` for fully annotated real-paper runs.
3. Optional: set DEEP credentials to exercise actual Ultramarine and configure
   real token prices to produce a measured cost-per-paper table.
4. Optional: configure ElevenLabs and test a real TTS call. Until then browser
   speech is the functioning default; mock tests cover hosted caching/fallback.
5. Docker engine/public-host and physical iOS/Android lock-screen checks remain
   unverified. Render's free disk is ephemeral; export to retain a paper.

No real hosted API bill or model-quality result is fabricated. The startup,
schema, evidence mapping, background jobs, viewer, browser speech and portable
exports can all be exercised without a GPU or any model runtime.

## Final command output

```text
pytest -q
34 passed, 1 warning in 10.03s
```

The warning is a Starlette TestClient deprecation for its current httpx adapter;
it does not affect application requests or the mocked-client test results.
Python compilation, JavaScript syntax checks and `docker compose config --quiet`
also passed. The standalone browser check reported zero external script/style
dependencies, an embedded PDF Blob source, no horizontal overflow and no
JavaScript errors. The temporary standalone test server was stopped; iPDF remains
running on `http://127.0.0.1:8000`.


## Hosted credential recheck — 23 October 2026

- Hugging Face token authentication: HTTP 200 (valid token).
- Actual generation using configured `Qwen/Qwen3-8B`: HTTP 402. The provider reports no remaining inference credits; real plugin output remains blocked by billing, not missing credentials.
- ElevenLabs voice-list authentication: HTTP 200; 21 voices returned. `ELEVENLABS_VOICE_ID` is unset and `TTS_PROVIDER=browser`, so no hosted speech was generated and browser speech remains selected.
- Added a regression test and immediate actionable handling for HTTP 402, avoiding repeated generation requests when credits are exhausted.
- Updated suite: **35 passed**, one existing TestClient deprecation warning.

Earlier statements about blank keys describe the initial validation run; this recheck supersedes that configuration status. No keys or account identifiers are recorded here.

## Current hosted setup and budget check — 23 October 2026

This section supersedes the credential and test-count status above. Earlier
three-paper runs remain source-only validation, not hosted generation evidence.

- FAST: Groq `openai/gpt-oss-120b` returned schema-valid JSON (188 input / 107 output tokens).
- DEEP: Ultramarine `ultramarine-1-flash` returned schema-valid JSON (99 input / 63 output tokens).
- Ultramarine's read-only pricing endpoint reported $0.15/million input and
  $0.50/million output tokens. The tiny check consumed $0.00004635. The verified
  rates were added to the local environment's previously zero DEEP price fields.
- ElevenLabs produced a cached 71,514-byte MP3 from a 70-character test script.
  The restricted key cannot read the subscription allowance, so no remaining
  credit count is claimed. `TTS_PROVIDER=browser` remains selected in `.env`.
- No further Ultramarine or ElevenLabs generation was performed after the user
  specified a $5 / 10,000-credit budget. Full-paper paid validation was not run.
- The FAST-only one-page, three-level attempt generated five grounded beginner
  glossary entries. Groq HTTP 429 responses prevented completion of flashcards,
  narration and the other levels. The raw output and incomplete report are in
  `data/validation/fast-smoke-*.ipdf.json` and
  `data/validation/configured-provider-smoke.json`.
- Fixed provider rate handling to honor `Retry-After`, stop on long quota resets,
  and propagate a grounding outage without regenerating an already-paid block
  within the same call. Completed validated blocks remain cached for resubmission.
- Mocked regression suite: **38 passed, 1 warning in 9.01s**. The warning is the
  existing Starlette TestClient deprecation. Tests perform no real inference.

Remaining live checks: a completed annotated paper at all levels, full hosted
three-paper chart/E2E validation, Docker execution/public deployment, and physical
phone background/lock-screen playback. These are not claimed as passed.


## Personalized workflow — 23 October 2026

- Reader level + background + goal + depth target propagate into hosted prompts,
  JSON metadata and cache identity. Browser / ElevenLabs voice is selectable.
- Mocked suite: 42 passed (one existing Starlette deprecation warning). The three
  level E2E tests now include a reader profile and valid multiple-choice output.
- Live HTTP upload of page 1 from Attention Is All You Need completed with five
  glossary entries, three quiz cards and one narration segment. FAST was Groq;
  DEEP grounding was Ultramarine. Tokens: 12,175 input, 13,095 output including
  retries. Recorded DEEP cost: $0.00601245. FAST prices were unset, so this is not
  a complete provider billing total. No table was found on that page; no chart
  was invented. This is a one-page smoke check, not full-paper validation.
- Live ElevenLabs synthesis through the app's audio job endpoint passed for one
  2,150-character narration: 2,239,886 MP3 bytes, served with HTTP 200 and cached.
- Browser: the generated quiz showed source-linked feedback after a wrong answer;
  the subsequent player state was SIMPLER REPLAY / BROWSER VOICE. No JS errors
  were reported. Physical phone lock-screen playback remains unverified.
- Local learning history is exportable/resettable. Evaluation reports observed
  repeated-question results; no model-training or causal learning-gain claim.
- An MIT license and GitHub mocked-test workflow are included. Runtime data,
  provider keys and uploaded papers remain excluded from Git.

Render Docker build and initial public deployment passed at https://ipdf-tvvn.onrender.com/. The Linux CI issue was an absent parent directory for pytest temporary files; the test path now works in a clean checkout.


## Public workflow verification

The deployed app at https://ipdf-tvvn.onrender.com/ passed a one-page real-paper
upload -> background generation -> JSON/HTML export -> ElevenLabs audio job ->
MP3 playback check. Public output: five glossary entries, three quiz cards and
one narration segment. Recorded DEEP usage was $0.0025351; FAST prices were not
configured. Hosted audio: 2,379 characters, 2,502,782 MP3 bytes, HTTP 200. The
browser player reported PLAYING / AUDIO, readyState 4, with no audio error.

Exact 390-pixel emulation showed equal document/client/viewport widths of 390;
walking controls and source-page links were visible. Proof is stored locally in
ignored data/validation/public-walking-390.png. Device emulation was cleared.
Physical phone lock-screen behavior and full-paper hosted three-level/three-paper
runs are still not claimed. The latest Linux GitHub Actions run passed all 42
mocked tests and the Pages build passed. Public docs/ links to the full backend.


## GitHub accounts and private tutor — 23 October 2026

- 51 mocked tests passed. Coverage includes OAuth state/PKCE, successful callback,
  opaque-session creation, logout, private document/export/media access, cross-account
  denial, public reading without paid-tool access, account-bound playback position,
  acyclic source-linked prerequisite maps and serialized restart recovery.
- Library supports up to three PDF submissions, a persistent-in-database preparation
  queue, retry controls and explicit sharing. Prepare jobs map prerequisites; hosted
  audio is pre-generated only when the reader selected ElevenLabs and budget permits.
- Tutor answers use selected-section evidence, exact quotes, bounded same-section
  conversation history and account concept familiarity. Unsupported questions return
  a fixed refusal; supported answers require a separate grounding pass.
- User explicitly chose to retain free Render hosting. No paid upgrade or persistent
  disk was enabled. Overnight completion, retained sessions and retained uploads are
  not guaranteed on that host. Recovery requires surviving database/source files.
- Microphone input is optional browser SpeechRecognition; typed questions and spoken
  answers are supported without it. This is not ElevenLabs' realtime Agent platform.
- GitHub OAuth settings are configured privately on Render with user consent. Live
  sign-in and authenticated browser checks are recorded below after deployment.
