"""Hosted providers only. Boot without keys; generation requires them."""
import os
from dataclasses import dataclass,field
from pathlib import Path
from dotenv import load_dotenv
ROOT=Path(__file__).resolve().parents[1]
load_dotenv(ROOT/'.env')

@dataclass(frozen=True)
class Backend:
    name: str
    base_url: str
    api_key: str=field(repr=False)
    model: str=''
    price_in: float=0
    price_out: float=0

@dataclass
class Settings:
    data_dir: Path=field(default_factory=lambda: Path(os.getenv('DATA_DIR',ROOT/'data')))
    llm_timeout: float=field(default_factory=lambda: float(os.getenv('LLM_TIMEOUT','90')))
    llm_max_tokens: int=field(default_factory=lambda: int(os.getenv('LLM_MAX_TOKENS','3500')))
    rate_limit_max_wait: float=field(default_factory=lambda: float(os.getenv('LLM_RATE_LIMIT_MAX_WAIT','60')))
    tts_provider: str=field(default_factory=lambda: os.getenv('TTS_PROVIDER','browser'))
    eleven_key: str=field(default_factory=lambda: os.getenv('ELEVENLABS_API_KEY',''),repr=False)
    eleven_voice: str=field(default_factory=lambda: os.getenv('ELEVENLABS_VOICE_ID',''))
    eleven_model: str=field(default_factory=lambda: os.getenv('ELEVENLABS_MODEL','eleven_flash_v2_5'))
    tts_price: float=field(default_factory=lambda: float(os.getenv('TTS_PRICE_PER_1K_CHARS','0')))
    max_pages: int=field(default_factory=lambda: int(os.getenv('MAX_PDF_PAGES','80')))
    generation_sections: int=field(default_factory=lambda: int(os.getenv('MAX_GENERATION_SECTIONS','20')))
    max_items: int=20
    offline: bool=False

    @property
    def db_path(self):
        return self.data_dir/'lazydigest.sqlite3'

    def backend(self,name='FAST'):
        fast=Backend('FAST',os.getenv('LLM_BASE_URL','https://router.huggingface.co/v1'),
            os.getenv('LLM_API_KEY',''),os.getenv('LLM_MODEL',''),
            float(os.getenv('FAST_PRICE_IN',os.getenv('PRICE_IN','0'))),
            float(os.getenv('FAST_PRICE_OUT',os.getenv('PRICE_OUT','0'))))
        if name.upper()=='DEEP' and all(os.getenv(k) for k in ('DEEP_BASE_URL','DEEP_API_KEY','DEEP_MODEL')):
            return Backend('DEEP',os.environ['DEEP_BASE_URL'],os.environ['DEEP_API_KEY'],os.environ['DEEP_MODEL'],
                float(os.getenv('DEEP_PRICE_IN','0')),float(os.getenv('DEEP_PRICE_OUT','0')))
        return fast

settings=Settings()
