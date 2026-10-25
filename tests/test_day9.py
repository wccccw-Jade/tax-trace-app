"""Day 9: cloud configuration, private storage boundaries, and recoverable storage failures."""
from io import BytesIO
import boto3
from botocore.response import StreamingBody
from botocore.stub import Stubber,ANY
from botocore.exceptions import EndpointConnectionError
import pytest
from pydantic import ValidationError
from backend.config import Settings
from backend.storage import S3Attachments,LocalAttachments
from test_story_a import story,identity,claim


def test_hosted_config_normalizes_driver_and_requires_durable_store():
    for url in ['postgres://demo:secret@db.invalid/example','postgresql://demo:secret@db.invalid/example']:
        s=Settings(_env_file=None,database_url=url,app_env='production',attachment_backend='s3',s3_bucket='private-demo')
        assert s.database_url.startswith('postgresql+psycopg://') and s.database_url.endswith('sslmode=require')
    with pytest.raises(ValidationError):Settings(_env_file=None,app_env='production')
    with pytest.raises(ValidationError):Settings(_env_file=None,attachment_backend='s3')


def test_private_s3_roundtrip_and_missing_object():
    client=boto3.client('s3',region_name='us-east-1',aws_access_key_id='testing',aws_secret_access_key='testing')
    store=S3Attachments('private-demo',prefix='demo/attachments/',client=client)
    data=b'Private invented evidence'
    with Stubber(client) as stub:
        stub.add_response('put_object',{}, {'Bucket':'private-demo','Key':ANY,'Body':data,'ContentType':'application/octet-stream'})
        key=store.put(data)
        assert len(key)==32
        params={'Bucket':'private-demo','Key':'demo/attachments/'+key}
        stub.add_response('get_object',{'Body':StreamingBody(BytesIO(data),len(data))},params)
        assert store.read(key)==data
        stub.add_client_error('get_object',service_error_code='NoSuchKey',http_status_code=404,expected_params=params)
        with pytest.raises(FileNotFoundError):store.read(key)
        stub.add_response('delete_object',{},params);store.remove(key)
        stub.assert_no_pending_responses()
    for method in [store.read,store.remove]:
        with pytest.raises(FileNotFoundError):method('../credentials')


def test_local_attachment_keys_and_private_file_mode(tmp_path):
    store=LocalAttachments(tmp_path);key=store.put(b'Invented evidence')
    assert store.read(key)==b'Invented evidence'
    assert (tmp_path/key).stat().st_mode & 0o777==0o600
    for method in [store.read,store.remove]:
        with pytest.raises(FileNotFoundError):method('../escape')
    store.remove(key);assert not (tmp_path/key).exists()


def test_failed_cloud_upload_returns_safe_retry_and_preserves_question(story,monkeypatch):
    client,_=story;identity(client,'st-01')
    r=client.post('/api/collaboration/questions',params={'ref':'v3:SchB.1.2'},json={'expected_revision':claim(client)['revision'],'recipient':'cu-01','prompt':'Please provide supporting evidence for this test.'})
    q=r.json();identity(client,'cu-01')
    class OfflineStore:
        def put(self,data):raise EndpointConnectionError(endpoint_url='https://storage.invalid?secret=DO_NOT_EXPOSE')
    monkeypatch.setattr('backend.collaboration_api.attachments',OfflineStore())
    response=client.post('/api/collaboration/questions/'+q['ref']+'/answers',json={'expected_revision':q['revision'],'text':'Invented attachment for recovery test.','files':[{'filename':'test.txt','content_base64':'ZXZpZGVuY2U='}]})
    assert response.status_code==503 and 'Retry' in response.json()['detail']
    assert 'DO_NOT_EXPOSE' not in response.text
    thread=client.get('/api/collaboration/questions').json()[0]
    assert thread['revision']==q['revision'] and thread['answers']==[]


def test_hosted_session_cookie_is_secure(story,monkeypatch):
    client,_=story
    monkeypatch.setattr('backend.api.settings.app_env','production')
    result=client.post('/api/session',json={'actor_id':'st-01'})
    cookie=result.headers['set-cookie'].lower()
    assert 'secure' in cookie and 'httponly' in cookie and 'samesite=strict' in cookie
