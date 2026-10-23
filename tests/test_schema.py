import pytest
from pydantic import ValidationError
from app.schema import IPDF,parse_number


def document():
    return dict(meta=dict(title='Paper',authors=[],source_url='/source.pdf',level='beginner',pages=1,paper_id='hash'),
        sections=[dict(id='p1',title='Intro',page=1,text='Evidence')],
        provenance=dict(model='mock',prompt_versions={},generated_at='2026-10-23T00:00:00Z'))


def chart_document():
    data=document()
    data['tables']=[dict(id='t1',label='Table 1',page=1,cells=[['Model','Accuracy'],['A','81.2%'],['B','85.7%']])]
    data['charts']=[dict(id='c1',type='bar',title='Accuracy',page=1,source_table='t1',caption='from Table 1, p.1',
        generated_by=dict(plugin='charts',prompt_version='charts/0.1.0',model='mock',source_page=1),
        series=[dict(name='Accuracy',labels=['A','B'],values=[81.2,85.7],source_cells=[dict(row=1,column=1),dict(row=2,column=1)])])]
    return data


def test_roundtrip_and_version():
    value=IPDF(**document())
    assert IPDF.model_validate_json(value.model_dump_json())==value
    with pytest.raises(ValidationError):
        IPDF(**(document()|{'ipdf_version':'0.2'}))


def test_core_format_without_optional_meta_extensions():
    data=document()
    del data['meta']['pages']
    del data['meta']['paper_id']
    data['sections'][0]['page']=2
    value=IPDF(**data)
    assert value.meta.pages==2
    assert len(value.meta.paper_id)==64


def test_chart_numbers_cannot_be_invented():
    data=chart_document()
    IPDF(**data)
    data['charts'][0]['series'][0]['values'][0]=99
    with pytest.raises(ValidationError,match='parsed numeric source cells'):
        IPDF(**data)


def test_bad_references_and_pages():
    data=document()
    data['glossary']=[dict(term='Term',definition='Definition',section_id='missing',page=1,
        generated_by=dict(plugin='glossary',prompt_version='1',model='mock',source_page=1))]
    with pytest.raises(ValidationError):
        IPDF(**data)
    data=chart_document()
    data['charts'][0]['page']=2
    with pytest.raises(ValidationError):
        IPDF(**data)


@pytest.mark.parametrize('raw,value',[('1,234.5',1234.5),('81.2%',81.2),('−3.2',-3.2),('1.2e-3',.0012),('1.2 ± 0.2',None),('n/a',None)])
def test_numeric_evidence_parser(raw,value):
    assert parse_number(raw)==value
