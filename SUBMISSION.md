*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 3: Slow and Steady](https://dev.to/challenges/hacktoberfest-week3-2026-10-19)*

## What I Built

I like the idea of reading research papers. I like the part where I have to look up the same unfamiliar term, make my own study cards, and reconstruct the explanation from three different tabs considerably less.

So I built **iPDF: research at your own pace**.

It turns a PDF or arXiv paper into an interactive edition: the original text, with explanations and study tools around it. It is also an open, versioned JSON format, so the result can exist independently of the application that generated it. The name means “interactive PDF”; the portable formats are `.ipdf.json` and `.ipdf.html`, rather than a new binary PDF standard.

The workflow is straightforward:

1. Sign in with GitHub and upload a paper, or enter its arXiv ID.
2. Choose beginner, intermediate or expert, your background, and what you want to get out of it.
3. Let background jobs prepare the tools while you do something else.
4. Come back to read, study, ask questions or listen.

Tap an underlined term for a definition. Save it to your deck. Work through flashcards. Follow a prerequisite path and mark the concepts you already know. Ask about the current section and get an answer with a supporting quotation and page reference.

Or press play. Narration follows the sections, highlights the current one, and offers a simpler explanation. Walking mode gives the audio controls room to breathe. ElevenLabs provides optional hosted narration; browser speech is the fallback.

The paper stays the main content. A summary is not the main output. Students, developers entering a new field, and readers who prefer listening get to spend less effort assembling a study setup before they can start learning.

## Demo

- **[Project site and browser reader](https://spacenets7.github.io/ipdf/)** — no account needed to try the authored interactive sample or open an exported JSON file locally.
- **[Full application](https://ipdf-tvvn.onrender.com/)** — GitHub sign-in, PDF/arXiv preparation, private libraries, tutor and listening.
- **[Try the sample directly](https://spacenets7.github.io/ipdf/demo.html)** — working glossary terms, study cards and browser narration, clearly labelled as an authored format demonstration.

**Video demo:** _Walkthrough link to be added._

![iPDF project site with an interactive format preview](https://spacenets7.github.io/ipdf/assets/pages-preview.png)

For a quick test, open the sample, tap “provenance,” save the term, answer the study card, then press **Listen to paper**. To test generation, open the full app and use the arXiv example or upload a text-based PDF. Choose browser voice to avoid ElevenLabs usage.

GitHub Pages hosts the reader; Python and generation run on Render. The free Render instance can take time to wake up and its temporary storage can reset. Export editions you want to keep. The prototype does not guarantee that an overnight upload will be ready in the morning.

## Code

{% github spacenets7/ipdf %}

The repository is [MIT licensed](https://github.com/spacenets7/ipdf/blob/main/LICENSE). It includes the [format specification](https://github.com/spacenets7/ipdf/blob/main/SPEC.md), Pydantic schema, generation plugins, viewer, mocked tests and deployment configuration.

## How I Built It

The open-weight model used in the live generation checks was **[gpt-oss-120b](https://github.com/openai/gpt-oss)**, served through a hosted OpenAI-compatible endpoint. Its upstream project uses the Apache 2.0 license. No model runs on the reader’s laptop.

I separated the application into three layers:

```text
PDF / arXiv
    ↓
ingest — PyMuPDF, page-tagged sections, tables and figures
    ↓
generate — glossary, flashcards, narration and table-derived charts
    ↓
iPDF 0.1 JSON — validated blocks with source references and provenance
    ↓
render — vanilla JavaScript reader, Chart.js and audio controls
```

FastAPI connects the workflow. SQLite stores accounts, jobs, caches and learning state. Background workers return a job ID quickly; the browser polls for progress. The renderer consumes completed JSON and never makes an LLM call.

The generation client takes its endpoint, API key and model from environment variables. Glossary depth, flashcard difficulty and narration style change with the reader’s level. Each generated block records its source page, model and prompt version. Invalid blocks get up to two retries before being dropped and logged.

**Paper Instruments’ Ultramarine** is the optional DEEP backend for table selection and claim grounding. Charts have an additional constraint: every plotted number must match a parsed cell in the source table. If extraction fails, there is no chart. The model does not get to fill the gap with plausible numbers.

The tutor builds on the same source discipline. Supported answers need an exact quotation from the selected section and a grounding check. Questions outside the available evidence receive a refusal. Familiarity and recent conversation help shape explanations; they do not retrain the model.

**ElevenLabs** turns narration into cached MP3 segments when selected. Browser speech keeps the reading and sample experience usable without an audio API key. Optional speech input uses the browser’s speech service; this is not an ElevenLabs realtime Agent integration.

Real usage mattered more to me than a “cheap per paper” claim without evidence. These are the recorded Ultramarine/DEEP cost components from bounded one-page checks:

| Check | Recorded DEEP cost |
| --- | ---: |
| Local personalized generation | $0.00601245 |
| Deployed upload → generation workflow | $0.00253510 |

Those figures are based on recorded usage and configured DEEP rates. They are **not complete per-paper bills**: FAST pricing was not configured, and audio is separate. The deployed audio check synthesized 2,379 characters and returned a playable MP3. I have not measured a full-paper cost benchmark.

The latest mocked suite has **51 passing tests**, including schema validation, chart evidence, account isolation, OAuth and job recovery. Ingestion and table evidence were checked on Attention Is All You Need, BERT and ResNet. The complete authenticated generation/listening smoke check used one page; I am not presenting it as a full three-paper generation benchmark. [Validation details](https://github.com/spacenets7/ipdf/blob/main/VALIDATION.md) record the scope and limitations.

The interface uses a dark, quiet workspace inspired by [T3 Code](https://t3.codes/). It is implemented in original HTML/CSS and vanilla JavaScript. The architecture uses FastAPI, Pydantic, PyMuPDF, Jinja2, SQLite and vendored Chart.js. The earlier digest module is preserved in the repository; iPDF is the research-paper workflow built around the open document format.

## Why Does Open Innovation Matter?

The useful output of an AI tool should not disappear when I close its chat window.

For iPDF, openness has two concrete jobs. The first is model choice. An open-weight model such as gpt-oss gives other developers access to the weights and the ability to deploy or adapt the model under its license. A closed-model API does not provide those weights. This build uses hosted inference to keep the application lightweight, but it does not hardcode a provider or model into the document format.

The second is ownership of the result. Anyone can inspect the JSON, validate source references, write a different viewer, or add a generation plugin. A reader can keep a self-contained HTML edition rather than depend on an account to reopen it.

Endpoint compatibility alone is not unique to open models, and hosted inference still sends source excerpts to providers. I am not claiming that generation is offline or private from those providers. The practical benefit is that the model, pipeline and output are separate things that can evolve independently. The schema and page references stay useful when the model changes.

That makes iPDF something people can build on, rather than another destination their papers have to live inside.

## My Agent Session

I built with assistance from **Codex**, using an iterative loop: implement a step, run mocked tests, inspect real output, then check the browser at phone width. The work included the pivot from a digest to an open document format, source-table validation, hosted audio, GitHub login and the mobile reader.

The [commit history](https://github.com/spacenets7/ipdf/commits/main/) and [validation log](https://github.com/spacenets7/ipdf/blob/main/VALIDATION.md) document the implementation and checks. A public agent-session transcript is not attached; those links are a build record, not a transcript.

<!-- Optional before publishing: replace this comment with a reviewed, sanitized public session link or a valid agent_session embed. Do not paste private logs, credentials or machine paths. -->

*AI disclosure: Codex assisted with implementation and drafted this write-up. The technical claims above are tied to the repository and recorded checks.*

## The Lazy Payoff

In this week’s authenticated test, one upload produced five glossary entries, three flashcards and a narration segment. A separate preparation job produced nine source-linked concepts. A question about the Transformer returned a cited answer; familiarity and conversation history survived a reload. The portable HTML and JSON downloads worked, and anonymous requests could not open the private edition.

That is the payoff I can demonstrate today: I did not have to manually prompt for a glossary, copy questions into a separate deck, write a narration script, and then connect every result back to the page myself. The pipeline assembled those pieces once.

I have not run a timed study or measured learning gains. The saved effort is a demonstrated workflow reduction, not an invented “hours saved” statistic. My goal is modest: let the reader spend less time preparing to understand a paper, and more time actually understanding it—even if that happens one section at a time, on a slow walk.

## Prize Categories

- **Best Use of Render** — the Dockerized FastAPI application runs on Render, including ingestion, hosted-generation jobs, private libraries and audio delivery.
- **Best Use of Ultramarine** — Paper Instruments’ Ultramarine is used as the optional DEEP backend for source grounding and table selection. Recorded run costs and their limits are reported above.
- **Best Use of ElevenLabs** — optional section narration is synthesized into cached MP3 audio, with browser speech available as a fallback.
- **Best Use of GitHub Copilot** — entering through the challenge’s listed **GitHub Actions automation** option: Actions runs the mocked tests and static-reader build on pushes and pull requests. The coding assistant used was Codex; I am not claiming Copilot usage.
