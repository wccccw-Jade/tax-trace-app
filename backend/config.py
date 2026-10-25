from pathlib import Path
from typing import Literal
from pydantic import field_validator,model_validator
from pydantic_settings import BaseSettings,SettingsConfigDict

ROOT=Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config=SettingsConfigDict(env_file=ROOT/'.env',extra='ignore')
    database_url:str='postgresql+psycopg://miraflores:miraflores@localhost:5432/miraflores'
    packet_path:Path=ROOT/'okafor_lindqvist_2025_packet.json'
    attachment_dir:Path=ROOT/'var/attachments'
    app_env:Literal['development','production']='development'
    attachment_backend:Literal['local','s3']='local'
    s3_bucket:str|None=None
    s3_region:str|None=None
    s3_endpoint_url:str|None=None
    s3_prefix:str='attachments/'

    @field_validator('database_url',mode='before')
    @classmethod
    def postgres_driver(cls,value):
        for prefix in ('postgres://','postgresql://'):
            if value.startswith(prefix):return 'postgresql+psycopg://'+value[len(prefix):]
        return value

    @model_validator(mode='after')
    def durable_cloud_storage(self):
        if self.attachment_backend=='s3' and not self.s3_bucket:
            raise ValueError('S3_BUCKET is required for private object storage')
        if self.app_env=='production' and self.attachment_backend!='s3':
            raise ValueError('Production requires private S3 storage; dyno files are not durable')
        if self.app_env=='production' and 'sslmode=' not in self.database_url:
            self.database_url+=('&' if '?' in self.database_url else '?')+'sslmode=require'
        return self

settings=Settings()
