from types import SimpleNamespace as NS
from unittest.mock import patch
import pytest
from app.schema import Section,Table,IPDF
from app.llm import Result
from app.generate.glossary import build as glossary,GlossaryOutput,Entry
from app.generate.charts import build as charts,ChartPlan
from app.generate.common import generate
from test_schema import chart_document


def test_glossary_metadata_and_source_reference():
    section=Section(id='p2',title='Method',page=2,text='Attention is used in this method.')
    result=Result(GlossaryOutput(entries=[Entry(term='Attention',definition='A mechanism for relating parts of a sequence.')]),'hosted-test','FAST')
    with patch('app.generate.glossary.generate',return_value=result):
        blocks=glossary(section,'beginner','paper')
    assert blocks[0].page==2
    assert blocks[0].generated_by.model=='hosted-test'
    assert blocks[0].generated_by.prompt_version=='glossary/0.2.0'


def test_chart_values_come_from_parser_not_model():
    data=chart_document()
    table=Table(**data['tables'][0])
    section=Section(id='p1',title='Results',page=1,text='Table 1 compares accuracy.')
    plan=ChartPlan(usable=True,title='Accuracy',label_column=0,header_row=0,value_columns=[1],data_rows=[1,2])
    with patch('app.generate.charts.generate',return_value=Result(plan,'hosted','DEEP')):
        blocks=charts(table,section,'intermediate','paper')
    assert blocks[0].series[0].values==[81.2,85.7]
    data['charts']=[blocks[0].model_dump()]
    IPDF(**data)


def test_cache_avoids_generation_and_grounding():
    section=Section(id='p1',title='Intro',page=1,text='Attention is used.')
    output=GlossaryOutput(entries=[])
    with patch('app.generate.common.chat_json',return_value=Result(output,'mock-model','FAST')) as chat:
        generate(GlossaryOutput,'glossary',section,'beginner','paper','prompt',ground=False)
        generate(GlossaryOutput,'glossary',section,'beginner','paper','prompt',ground=False)
    assert chat.call_count==1
