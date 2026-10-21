from sqlalchemy import select
from backend.domain.audit import run_audit
from backend.domain.locators import packet_locators
from backend.persistence.models import PacketImport, Record, Edge


def import_packet(db, packet):
    if db.get(PacketImport, packet.digest):
        return {'hash': packet.digest, 'created': False}
    report = run_audit(packet)
    db.add(PacketImport(id=packet.digest, original=packet.original, report=report))
    db.flush()
    rows = packet.index
    locators = packet_locators(packet)
    for ref, row in rows.items():
        payload = row['payload']
        if row['kind'] == 'document':
            payload = {**payload, 'disposition': 'unresolved', 'disposition_reason': None}
        if row['kind'] == 'extraction':
            payload = {**payload, 'locator': locators[ref]}
        db.add(Record(packet_id=packet.digest, ref=ref, kind=row['kind'], payload=payload))
    for edge in packet.edges():
        db.add(Edge(packet_id=packet.digest, **edge))
    db.flush()
    return {'hash': packet.digest, 'created': True, **report['counts']}
