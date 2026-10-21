import argparse
import json
from pathlib import Path
from sqlalchemy.orm import Session
from backend.config import settings
from backend.domain.packet import Packet
from backend.domain.audit import run_audit
from backend.importer import import_packet
from backend.persistence.db import engine


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['audit','import'])
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    packet = Packet.read(settings.packet_path)
    if args.command == 'audit':
        result = run_audit(packet)
    else:
        with Session(engine()) as db, db.begin():
            result = import_packet(db, packet)
    output = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + '\n')
        print(f'Wrote {args.output}')
    else:
        print(output)

if __name__ == '__main__':
    main()
