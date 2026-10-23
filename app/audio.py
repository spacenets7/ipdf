"""Hosted speech only; browser SpeechSynthesis is the fallback."""
import hashlib
import logging
import threading
import os
from urllib.parse import quote
import httpx
from app import db
from app.config import settings
log=logging.getLogger(__name__)
_lock=threading.Lock()

def create_audio(script,provider=None):
    if (provider or settings.tts_provider)!='elevenlabs' or not settings.eleven_key or not settings.eleven_voice:
        return {'provider':'browser','script':script,'message':'Using your browser voice.'}
    voice=settings.eleven_voice+':'+settings.eleven_model
    key=hashlib.sha256((script+voice+'elevenlabs').encode()).hexdigest()
    target=settings.data_dir/'audio'/f'{key}.mp3'
    with _lock:
        if target.is_file():
            return {'provider':'elevenlabs','audio_url':f'/media/audio/{key}.mp3','cached':True}
        spent=db.query("SELECT COALESCE(SUM(chars),0) AS n FROM usage WHERE kind='tts' AND purpose='section_narration'",one=True)['n']
        if spent+len(script)>int(os.getenv('TTS_CHARACTER_BUDGET','8000')):
            return {'provider':'browser','script':script,'message':'The hosted audio character budget is reached. Using browser speech.'}
        try:
            with httpx.Client(timeout=60) as client:
                response=client.post('https://api.elevenlabs.io/v1/text-to-speech/'+quote(settings.eleven_voice,safe=''),
                    headers={'xi-api-key':settings.eleven_key,'Accept':'audio/mpeg'},
                    json={'text':script,'model_id':settings.eleven_model})
            response.raise_for_status()
            if not response.content or not response.headers.get('content-type','').startswith('audio/'):
                raise ValueError('Provider did not return audio')
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(response.content)
            db.execute('INSERT INTO usage(kind,backend,model,purpose,chars,cost) VALUES(?,?,?,?,?,?)',
                ('tts','elevenlabs',settings.eleven_model,'section_narration',len(script),len(script)*settings.tts_price/1000))
            return {'provider':'elevenlabs','audio_url':f'/media/audio/{key}.mp3','cached':False}
        except Exception as exc:
            log.warning('ElevenLabs unavailable (%s); using browser speech',type(exc).__name__)
            db.execute('INSERT INTO usage(kind,backend,model,purpose,chars,cost) VALUES(?,?,?,?,?,0)',
                ('tts','elevenlabs',settings.eleven_model,'failed_attempt',len(script)))
            return {'provider':'browser','script':script,
                'message':'ElevenLabs is unavailable or its quota was reached. Using your browser voice.'}
