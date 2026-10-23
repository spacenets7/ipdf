import logging
from datetime import datetime,timezone
from app import db
from app.config import settings
from app.schema import IPDF,Meta,Provenance,Issue
from app.generate import glossary,flashcards,narration,charts
from app.generate.common import VERSIONS,reader_context
from app.llm import run_id,ProviderUnavailable

log=logging.getLogger(__name__)


def finish(document):
    usage=db.query('SELECT * FROM usage WHERE run_id=?',(run_id.get(),)) if run_id.get() else []
    document.provenance.prompt_tokens=sum(r['prompt_tokens'] for r in usage)
    document.provenance.completion_tokens=sum(r['completion_tokens'] for r in usage)
    document.provenance.recorded_cost_usd=sum(r['cost'] for r in usage)
    document.provenance.backends=sorted({r['backend'] for r in usage})
    document.provenance.prices_configured=bool(usage) and all(
        settings.backend(name).price_in>0 or settings.backend(name).price_out>0
        for name in document.provenance.backends)
    return IPDF.model_validate(document.model_dump())


def build(paper,level,progress=lambda percent,message:None):
    chosen=settings.backend()
    document=IPDF(meta=Meta(title=paper.title,authors=paper.authors,source_url=paper.source_url,
        level=level,reader=reader_context.get(),pages=paper.pages,paper_id=paper.paper_id,tts_provider=reader_context.get().get('voice',settings.tts_provider) if reader_context.get().get('voice',settings.tts_provider) in ('elevenlabs','browser') else 'browser'),sections=paper.sections,tables=paper.tables,
        figures=paper.figures,issues=[Issue(plugin='ingest',message=w) for w in paper.warnings],
        provenance=Provenance(model=chosen.model or 'unconfigured',prompt_versions=VERSIONS,
            generated_at=datetime.now(timezone.utc),prices_configured=bool(chosen.price_in or chosen.price_out)))
    if not chosen.api_key or not chosen.model:
        document.issues.append(Issue(plugin='configuration',message='Source-only edition: set LLM_API_KEY and LLM_MODEL to generate learning blocks.'))
        return finish(document)
    sections=paper.sections[:settings.generation_sections]
    total=max(1,len(sections)*3+len(paper.tables))
    done=0
    for section in sections:
        for plugin,name in ((glossary,'glossary'),(flashcards,'flashcards'),(narration,'narration')):
            progress(25+int(65*done/total),f'Creating {name} · page {section.page} of {paper.pages}')
            try:
                blocks=plugin.build(section,level,paper.paper_id)
                getattr(document,name).extend(blocks)
            except ProviderUnavailable as exc:
                document.issues.append(Issue(plugin='configuration',page=section.page,message=str(exc)))
                return finish(document)
            except Exception as exc:
                log.warning('Dropped %s p.%d after bounded retries (%s)',name,section.page,type(exc).__name__)
                document.issues.append(Issue(plugin=name,page=section.page,message='Generation or grounding failed after bounded retries; block omitted.'))
            done+=1
    if len(sections)<len(paper.sections):
        document.issues.append(Issue(plugin='limits',message=f'Learning blocks generated for the first {len(sections)} sections; all extracted pages remain readable.'))
    for table in paper.tables:
        section=next((s for s in paper.sections if s.page==table.page),None)
        if not section:
            continue
        progress(25+int(65*done/total),f'Checking numeric evidence · {table.label}, page {table.page}')
        try:
            document.charts.extend(charts.build(table,section,level,paper.paper_id))
        except Exception as exc:
            log.warning('Dropped chart %s (%s)',table.id,type(exc).__name__)
            document.issues.append(Issue(plugin='charts',page=table.page,message='Chart plan did not match extracted table cells; chart omitted.'))
        done+=1
    return finish(document)
