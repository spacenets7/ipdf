"""iPDF 0.1 contract. Renderers consume this format, never provider responses."""
import math
import re
import hashlib
from datetime import datetime
from typing import Literal
from pydantic import BaseModel,Field,ConfigDict,model_validator

Level=Literal['beginner','intermediate','expert']


class Contract(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)


def parse_number(cell):
    """Accept only a whole-cell numeric literal, optionally currency/percent."""
    clean=str(cell or '').strip().replace('−','-').replace('\u2009','').replace('\u00a0','')
    if not re.fullmatch(r'[$€£]?[-+]?(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+)(?:[eE][-+]?\d+)?%?',clean):
        return None
    value=float(re.sub(r'[$€£,%]','',clean))
    return value if math.isfinite(value) else None


class ReaderProfile(Contract):
    background: str=Field(default='',max_length=300)
    goal: Literal['understand','implement','critique']='understand'
    minutes: Literal[5,15,30]=15
    voice: Literal['browser','elevenlabs']='browser'


class Meta(Contract):
    title: str=Field(min_length=1,max_length=800)
    authors: list[str]=Field(default_factory=list)
    source_url: str
    level: Level
    pages: int=Field(default=1,ge=1,le=1000)
    paper_id: str=''
    tts_provider: Literal['elevenlabs','browser']='browser'
    reader: ReaderProfile=Field(default_factory=ReaderProfile)


class Section(Contract):
    id: str
    title: str
    page: int=Field(ge=1)
    text: str=Field(min_length=1)


class GeneratedBy(Contract):
    plugin: str
    prompt_version: str
    model: str=Field(min_length=1)
    source_page: int=Field(ge=1)


class PageBlock(Contract):
    page: int=Field(ge=1)
    generated_by: GeneratedBy

    @model_validator(mode='after')
    def matching_page(self):
        if self.page!=self.generated_by.source_page:
            raise ValueError('Block page must match generation source_page')
        return self


class Glossary(PageBlock):
    term: str=Field(min_length=1,max_length=100)
    definition: str=Field(min_length=1,max_length=1200)
    section_id: str


class Flashcard(PageBlock):
    id: str
    front: str=Field(min_length=1,max_length=500)
    back: str=Field(min_length=1,max_length=1800)
    section_id: str
    choices: list[str]=Field(default_factory=list,max_length=4)
    correct_index: int|None=Field(default=None,ge=0,le=3)

    @model_validator(mode='after')
    def quiz_answer(self):
        if self.choices and (len(self.choices)<2 or len(set(self.choices))!=len(self.choices) or self.correct_index is None or self.correct_index>=len(self.choices)):
            raise ValueError('A quiz needs distinct choices and a valid answer index')
        if not self.choices and self.correct_index is not None:
            raise ValueError('An answer index needs choices')
        return self


class Table(Contract):
    id: str
    label: str
    page: int=Field(ge=1)
    cells: list[list[str|None]]
    extraction: Literal['pymupdf']='pymupdf'


class CellRef(Contract):
    row: int=Field(ge=0)
    column: int=Field(ge=0)


class Series(Contract):
    name: str
    labels: list[str]=Field(min_length=1,max_length=100)
    values: list[float]=Field(min_length=1,max_length=100)
    source_cells: list[CellRef]=Field(min_length=1,max_length=100)

    @model_validator(mode='after')
    def aligned(self):
        if len(self.labels)!=len(self.values) or len(self.values)!=len(self.source_cells):
            raise ValueError('Series labels, values and source_cells must have equal lengths')
        return self


class Chart(PageBlock):
    id: str
    type: Literal['bar','line']
    title: str
    series: list[Series]=Field(min_length=1,max_length=6)
    source_table: str
    caption: str


class Narration(PageBlock):
    section_id: str
    script: str=Field(min_length=1,max_length=3800)
    simpler_script: str=Field(default='',max_length=1800)
    audio_url: str|None=None
    simpler_audio_url: str|None=None


class Figure(Contract):
    id: str
    page: int=Field(ge=1)
    caption: str
    data_url: str


class Provenance(Contract):
    model: str
    prompt_versions: dict[str,str]
    generated_at: datetime
    backends: list[str]=Field(default_factory=list)
    prompt_tokens: int=0
    completion_tokens: int=0
    recorded_cost_usd: float=0
    prices_configured: bool=False


class Issue(Contract):
    plugin: str
    page: int|None=None
    message: str


class Assets(Contract):
    original_pdf: str|None=None


class IPDF(Contract):
    ipdf_version: Literal['0.1']='0.1'
    meta: Meta
    sections: list[Section]=Field(min_length=1)
    glossary: list[Glossary]=Field(default_factory=list)
    flashcards: list[Flashcard]=Field(default_factory=list)
    charts: list[Chart]=Field(default_factory=list)
    narration: list[Narration]=Field(default_factory=list)
    provenance: Provenance
    tables: list[Table]=Field(default_factory=list)
    figures: list[Figure]=Field(default_factory=list)
    issues: list[Issue]=Field(default_factory=list)
    assets: Assets=Field(default_factory=Assets)

    @model_validator(mode='after')
    def source_references(self):
        if 'pages' not in self.meta.model_fields_set:
            self.meta.pages=max(block.page for block in self.sections+self.tables+self.figures)
        if not self.meta.paper_id:
            self.meta.paper_id=hashlib.sha256((self.meta.source_url+'\n'+self.meta.title+'\n'+
                '\n'.join(section.text for section in self.sections)).encode()).hexdigest()
        section_map={s.id:s for s in self.sections}
        if len(section_map)!=len(self.sections):
            raise ValueError('Section IDs must be unique')
        if [s.page for s in self.sections]!=sorted(s.page for s in self.sections):
            raise ValueError('Sections must be in page order')
        table_map={t.id:t for t in self.tables}
        if len(table_map)!=len(self.tables):
            raise ValueError('Table IDs must be unique')
        for blocks in (self.flashcards,self.charts,self.figures):
            if len({b.id for b in blocks})!=len(blocks):
                raise ValueError('Block IDs must be unique within their collection')
        if len({b.section_id for b in self.narration})!=len(self.narration):
            raise ValueError('One narration segment per section')
        for block in self.sections+self.glossary+self.flashcards+self.charts+self.narration+self.tables+self.figures:
            if block.page>self.meta.pages:
                raise ValueError('Page reference exceeds the source document')
        for block in self.glossary+self.flashcards+self.narration:
            if block.section_id not in section_map or section_map[block.section_id].page!=block.page:
                raise ValueError('Generated block must reference its source section and page')
        for chart in self.charts:
            table=table_map.get(chart.source_table)
            if not table or table.page!=chart.page:
                raise ValueError('Chart must reference a table on its source page')
            if chart.caption!=f'from {table.label}, p.{table.page}':
                raise ValueError('Chart caption must name the original table and page')
            for series in chart.series:
                for value,ref in zip(series.values,series.source_cells):
                    try:
                        parsed=parse_number(table.cells[ref.row][ref.column])
                    except IndexError:
                        parsed=None
                    if parsed is None or not math.isclose(value,parsed,rel_tol=1e-10,abs_tol=1e-10):
                        raise ValueError('Chart values must exactly match parsed numeric source cells')
        return self
