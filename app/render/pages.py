import json
from pathlib import Path
from jinja2 import Environment,FileSystemLoader,select_autoescape
from app.config import ROOT
from app.schema import IPDF

ROOT_RENDER=ROOT/'app/render'
env=Environment(loader=FileSystemLoader(ROOT_RENDER/'templates'),autoescape=select_autoescape(['html']))


def safe_json(document):
    return document.model_dump_json().replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')


def viewer(document: IPDF,document_id='',*,standalone=False):
    scripts={}
    if standalone:
        for name in ('vendor/chart.umd.js','viewer.js','audio-player.js'):
            scripts[name]=(ROOT_RENDER/'static'/name).read_text(encoding='utf-8')
    return env.get_template('viewer.html').render(title=document.meta.title,
        document_id=document_id,ipdf_json=safe_json(document),standalone=standalone,
        inline_css=(ROOT_RENDER/'static/style.css').read_text(encoding='utf-8') if standalone else '',scripts=scripts)


def export_html(document: IPDF):
    """All source/audio assets arrive inside JSON, assembled by the orchestrator."""
    return viewer(document,standalone=True)
