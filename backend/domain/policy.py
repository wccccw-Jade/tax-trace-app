"""Versioned firm settings; operational settings do not invalidate tax review."""
from copy import deepcopy
from decimal import Decimal
from sqlalchemy import select
from backend.persistence.models import Record


def standards(db,packet):
    cache_key='standards:'+packet.digest
    if cache_key in db.info:return deepcopy(db.info[cache_key])
    row=db.scalar(select(Record).where(Record.packet_id==packet.digest,Record.ref=='firm:policy'))
    value=deepcopy(row.payload['standards'] if row else packet.data['firm']['starter_standards'])
    value.setdefault('partner_threshold',1000)
    value.setdefault('retention_years',7)
    db.info[cache_key]=deepcopy(value)
    return value


def tax_policy(db,packet):
    p=standards(db,packet)
    def stable(v):
        if isinstance(v,dict):return {k:stable(x) for k,x in v.items()}
        if isinstance(v,list):return [stable(x) for x in v]
        if isinstance(v,(int,float,Decimal)) and not isinstance(v,bool):return format(Decimal(str(v)).normalize(),'f')
        return v
    return stable({k:p[k] for k in ('verification_types','variance_review','required_steps','partner_threshold')})
