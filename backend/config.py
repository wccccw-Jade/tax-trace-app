from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / '.env', extra='ignore')
    database_url: str = 'postgresql+psycopg://miraflores:miraflores@localhost:5432/miraflores'
    packet_path: Path = ROOT / 'okafor_lindqvist_2025_packet.json'
    attachment_dir: Path = ROOT / 'var/attachments'

settings = Settings()
