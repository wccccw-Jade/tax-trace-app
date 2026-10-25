"""Heroku release: apply migrations, then import the unchanged packet idempotently."""
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session
from backend.config import ROOT,settings
from backend.persistence.db import engine
from backend.domain.packet import Packet
from backend.importer import import_packet

def main():
    command.upgrade(Config(str(ROOT/'alembic.ini')),'head')
    with Session(engine()) as db,db.begin():
        result=import_packet(db,Packet.read(settings.packet_path))
    print('Release ready: migrations applied; packet '+('imported' if result['created'] else 'already present')+'.')

if __name__=='__main__':main()
