from fastapi import HTTPException
from app import db,auth

def document(request,document_id,write=False):
    access=db.query('SELECT * FROM document_access WHERE document_id=?',(document_id,),one=True)
    user=auth.account(request)
    if access and ((user and access['account_id']==user['id']) or (access['public'] and not write)):
        return access
    raise HTTPException(404,'Interactive paper not found or not shared with you.')

def media(request,field,url):
    user=auth.account(request)
    account_id=user['id'] if user else ''
    if field=='paper':
        row=db.query('SELECT 1 FROM ipdfs i JOIN document_access a ON a.document_id=i.id WHERE i.paper_id=? AND (a.account_id=? OR a.public=1)',(url,account_id),one=True)
    else:
        row=db.query('SELECT 1 FROM ipdfs i JOIN document_access a ON a.document_id=i.id WHERE i.json LIKE ? AND (a.account_id=? OR a.public=1)',('%'+url+'%',account_id),one=True)
        if not row and user:
            row=db.query('SELECT 1 FROM tutor_turns WHERE account_id=? AND answer_json LIKE ?',(account_id,'%'+url+'%'),one=True)
    if not row:raise HTTPException(404,'Media not found or not shared with you.')
