"""Private attachments: local development or an S3-compatible bucket in production."""
from pathlib import Path
from uuid import uuid4
from backend.config import settings


def checked_key(key):
    if len(key)!=32 or any(c not in '0123456789abcdef' for c in key):raise FileNotFoundError('Invalid attachment key')
    return key


class LocalAttachments:
    def __init__(self,directory=None):self.directory=directory
    @property
    def root(self):return Path(self.directory) if self.directory is not None else settings.attachment_dir
    def put(self,data:bytes)->str:
        key=uuid4().hex;self.root.mkdir(parents=True,exist_ok=True)
        path=self.root/key
        with path.open('xb') as stream:stream.write(data)
        path.chmod(0o600)
        return key
    def read(self,key:str)->bytes:return (self.root/checked_key(key)).read_bytes()
    def remove(self,key:str):(self.root/checked_key(key)).unlink(missing_ok=True)


class S3Attachments:
    def __init__(self,bucket,region=None,endpoint=None,prefix='attachments/',client=None):
        self.bucket=bucket;self.region=region;self.endpoint=endpoint;self.prefix=prefix.rstrip('/')+'/';self._client=client
    @property
    def client(self):
        if self._client is None:
            import boto3
            self._client=boto3.client('s3',region_name=self.region,endpoint_url=self.endpoint)
        return self._client
    def object_key(self,key):return self.prefix+checked_key(key)
    def put(self,data:bytes)->str:
        key=uuid4().hex
        # No public ACL or public URL. Bucket policy must block public access.
        self.client.put_object(Bucket=self.bucket,Key=self.object_key(key),Body=data,ContentType='application/octet-stream')
        return key
    def read(self,key:str)->bytes:
        from botocore.exceptions import ClientError
        try:
            result=self.client.get_object(Bucket=self.bucket,Key=self.object_key(key))
        except ClientError as error:
            if error.response['Error']['Code'] in {'NoSuchKey','404','NotFound'}:raise FileNotFoundError('Attachment not found') from error
            raise
        body=result['Body']
        try:return body.read()
        finally:body.close()
    def remove(self,key:str):self.client.delete_object(Bucket=self.bucket,Key=self.object_key(key))


attachments=(S3Attachments(settings.s3_bucket,settings.s3_region,settings.s3_endpoint_url,settings.s3_prefix)
    if settings.attachment_backend=='s3' else LocalAttachments())
