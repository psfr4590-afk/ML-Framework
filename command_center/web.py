from fastapi import FastAPI,HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from .store import DatasetStore
from .secrets import credentials
store=DatasetStore(); app=FastAPI(title='Model Lab')
PAGE='M²S MODEL TRAINING PIPELINE'
class CredentialSet(BaseModel): name:str; secret:str; provider:str='custom'; kind:str='token'; env_var:str=''; description:str=''; identity:str=''
@app.on_event('startup')
def seed(): store.ensure_seed_datasets()
@app.get('/',response_class=HTMLResponse)
def index(): return HTMLResponse(f'<html><body><h1>{PAGE}</h1></body></html>')
@app.get('/api/datasets')
def datasets(): store.ensure_seed_datasets(); return store.list()
@app.get('/api/datasets/{did}')
def dataset(did:int):
 d=store.get(did)
 if not d: raise HTTPException(404,'dataset not found')
 return d
@app.get('/api/credentials')
def credential_list(): return credentials.list()
@app.post('/api/credentials')
def credential_set(item:CredentialSet): return credentials.set(item.name,item.secret,item.provider,item.kind,item.env_var,item.description,item.identity)
@app.delete('/api/credentials/{name}')
def credential_delete(name:str): return {'deleted':credentials.delete(name)}
@app.get('/api/credentials/{name}/test')
def credential_test(name:str): return credentials.test(name)
