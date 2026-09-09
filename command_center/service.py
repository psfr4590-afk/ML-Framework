from .store import DatasetStore
from .config import load_groups
from .secrets import credentials
store=DatasetStore()
def init(): return store.ensure_seed_datasets()
def add(name,description='',group_id=None): return store.create(name,description,group_id=group_id)
def status(did=None): return store.refresh_pipeline_state(did) if did is not None else [store.refresh_pipeline_state(d['id']) for d in store.list()]
def groups(): return load_groups()
def credential_list(): return credentials.list()
def credential_set(name,secret,provider='custom',kind='token',env_var='',description='',identity=''): return credentials.set(name,secret,provider,kind,env_var,description,identity)
def credential_delete(name): return credentials.delete(name)
def credential_test(name): return credentials.test(name)
