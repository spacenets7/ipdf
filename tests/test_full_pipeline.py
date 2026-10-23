import json
import httpx
import pytest
from openai import OpenAI
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.schema import IPDF
from test_ingest import make_pdf
from test_ipdf_routes import wait


@pytest.mark.parametrize('level',['beginner','intermediate','expert'])
def test_hosted_mock_end_to_end_all_levels(level,monkeypatch):
    calls=[]
    def handler(request):
        body=json.loads(request.content)
        system=body['messages'][0]['content']
        calls.append(body)
        if '"title": "Grounding"' in system:
            value={'supported':True,'reasons':[]}
        elif '"title": "GlossaryOutput"' in system:
            value={'entries':[{'term':'Research','definition':'A systematic investigation of a question.'}]}
        elif '"title": "CardsOutput"' in system:
            value={'cards':[{'front':'What does this page discuss?','back':'Interactive papers and their source text layer.','choices':['Interactive papers','Cooking','Astronomy'],'correct_index':0}]}
        elif '"title": "NarrationOutput"' in system:
            value={'script':'This section discusses research on interactive papers and the source text layer.',
                   'simpler_script':'A paper can be made interactive while keeping its original words.'}
        else:
            raise AssertionError(system)
        return httpx.Response(200,json={'id':'mock','object':'chat.completion','created':0,'model':'mock-model',
            'choices':[{'index':0,'message':{'role':'assistant','content':json.dumps(value)},'finish_reason':'stop'}],
            'usage':{'prompt_tokens':10,'completion_tokens':20,'total_tokens':30}})
    def factory(**kwargs):
        return OpenAI(**kwargs,http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr('app.llm.OpenAI',factory)
    monkeypatch.setattr(settings,'tts_provider','browser')
    with TestClient(app) as client:
        response=client.post('/ipdf/create',files={'pdf':('paper.pdf',make_pdf())},data={'level':level,'background':'Python and statistics','goal':'implement','minutes':'5'})
        state=wait(client,response.json()['job_id'])
        assert state['state']=='ready',state
        document_id=state['result_id']
        document=IPDF.model_validate(client.get(f'/ipdf/{document_id}.json').json())
        assert len(document.glossary)==len(document.flashcards)==len(document.narration)==2
        assert document.meta.level==level
        assert document.meta.reader.goal=='implement'
        assert document.flashcards[0].choices[document.flashcards[0].correct_index]=='Interactive papers'
        assert any('Python and statistics' in call['messages'][1]['content'] for call in calls)
        assert document.provenance.prompt_tokens==len(calls)*10
        assert all(block.generated_by.model=='mock-model' for block in document.glossary)
        audio=client.post(f'/audio/{document_id}/p1?simpler=true')
        assert audio.status_code==202
        result=wait(client,audio.json()['job_id'])
        assert result['result']['provider']=='browser'
        assert result['result']['script']==document.narration[0].simpler_script
        count=len(calls)
        exported=client.get(f'/ipdf/{document_id}/export')
        assert exported.status_code==200
        assert len(calls)==count  # Rendering/export/audio never invoke the LLM.
