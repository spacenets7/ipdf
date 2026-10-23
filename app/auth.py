"""GitHub OAuth with PKCE and opaque, revocable server-side sessions."""
import base64
import hashlib
import os
import secrets
import time
from urllib.parse import urlencode
import httpx
from fastapi import APIRouter,Request,HTTPException
from fastapi.responses import RedirectResponse
from app import db

router=APIRouter()
COOKIE='ipdf_session'
def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def base_url():
    return os.getenv('APP_BASE_URL','http://127.0.0.1:8000').rstrip('/')

def account(request):
    token=request.cookies.get(COOKIE,'')
    if not token:return None
    return db.query('SELECT a.* FROM accounts a JOIN sessions s ON s.account_id=a.id WHERE s.token_hash=? AND s.expires>?',
        (digest(token),time.time()),one=True)

def require_account(request):
    user=account(request)
    if not user:raise HTTPException(401,'Sign in with GitHub to use your private library.')
    return user

@router.get('/auth/github')
def login():
    client=os.getenv('GITHUB_CLIENT_ID') or os.getenv('CLIENT_ID')
    if not client or not (os.getenv('GITHUB_CLIENT_SECRET') or os.getenv('CLIENT_SECRET')):
        raise HTTPException(503,'GitHub login is awaiting server OAuth configuration.')
    state=secrets.token_urlsafe(32);verifier=secrets.token_urlsafe(64)
    db.execute('DELETE FROM oauth_states WHERE expires<?',(time.time(),))
    db.execute('INSERT INTO oauth_states VALUES(?,?,?)',(digest(state),verifier,time.time()+600))
    challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    response=RedirectResponse('https://github.com/login/oauth/authorize?'+urlencode(dict(client_id=client,
        redirect_uri=base_url()+'/auth/github/callback',state=state,code_challenge=challenge,code_challenge_method='S256')))
    response.set_cookie('ipdf_oauth_state',state,max_age=600,httponly=True,secure=base_url().startswith('https:'),samesite='lax')
    return response

@router.get('/auth/github/callback')
def callback(request:Request,code:str='',state:str=''):
    cookie=request.cookies.get('ipdf_oauth_state','')
    if not state or not cookie or not secrets.compare_digest(cookie,state) or not code:
        raise HTTPException(400,'Invalid sign-in state. Start sign-in again.')
    with db.connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row=conn.execute('SELECT * FROM oauth_states WHERE state_hash=? AND expires>?',(digest(state),time.time())).fetchone()
        if not row:raise HTTPException(400,'Sign-in expired or was already used.')
        conn.execute('DELETE FROM oauth_states WHERE state_hash=?',(digest(state),))
    try:
        with httpx.Client(timeout=20) as client:
            result=client.post('https://github.com/login/oauth/access_token',headers={'Accept':'application/json'},data={
                'client_id':os.getenv('GITHUB_CLIENT_ID') or os.getenv('CLIENT_ID'),'client_secret':os.getenv('GITHUB_CLIENT_SECRET') or os.getenv('CLIENT_SECRET'),
                'redirect_uri':base_url()+'/auth/github/callback','code':code,'code_verifier':row['verifier']})
            result.raise_for_status();token=result.json().get('access_token')
            if not token:raise ValueError('Rejected OAuth code')
            profile=client.get('https://api.github.com/user',headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json'})
            profile.raise_for_status();profile=profile.json()
        account_id='github:'+str(profile['id'])
        db.execute('INSERT INTO accounts(id,login) VALUES(?,?) ON CONFLICT(id) DO UPDATE SET login=excluded.login',(account_id,profile['login']))
    except (httpx.HTTPError,ValueError,KeyError):
        raise HTTPException(502,'GitHub sign-in could not finish. Try again.')
    # GitHub tokens are deliberately not persisted; the app only needs identity.
    opaque=secrets.token_urlsafe(48)
    db.execute('INSERT INTO sessions VALUES(?,?,?)',(digest(opaque),account_id,time.time()+30*86400))
    response=RedirectResponse('/library',status_code=303)
    response.set_cookie(COOKIE,opaque,max_age=30*86400,httponly=True,secure=base_url().startswith('https:'),samesite='lax')
    response.delete_cookie('ipdf_oauth_state')
    return response

@router.post('/auth/logout')
def logout(request:Request):
    db.execute('DELETE FROM sessions WHERE token_hash=?',(digest(request.cookies.get(COOKIE,'')),))
    response=RedirectResponse('/',status_code=303);response.delete_cookie(COOKIE);return response
