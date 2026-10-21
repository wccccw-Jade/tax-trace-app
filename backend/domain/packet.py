"""Immutable fixture index and typed, version-scoped reference resolution."""
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


def pointer(value, path):
    if not path:
        return value
    for part in path.lstrip('/').split('/'):
        part = part.replace('~1', '/').replace('~0', '~')
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value

@dataclass
class Packet:
    original: str
    data: dict
    digest: str

    @classmethod
    def read(cls, path):
        raw = Path(path).read_bytes()
        data = json.loads(raw)
        for field in ('documents', 'extracted_values', 'return_versions', 'firm'):
            if field not in data:
                raise ValueError(f'Missing packet section: {field}')
        return cls(raw.decode('utf-8'), data, hashlib.sha256(raw).hexdigest())

    def records(self):
        p = self.data
        rows = {}
        def add(ref, kind, payload):
            if ref in rows:
                raise ValueError(f'Duplicate reference: {ref}')
            rows[ref] = {'ref': ref, 'kind': kind, 'payload': payload}
        for d in p['documents']:
            add(d['id'], 'document', d)
            for page in d['pages']:
                add(f"doc:{d['id']}#page{page['page']}", 'page', {'document_id': d['id'], **page})
        for e in p['extracted_values']:
            add(e['id'], 'extraction', e)
        for k in ('questionnaire', 'messages', 'call_notes'):
            for value in p['client'][k]:
                add(value['id'], 'client_evidence', value)
        for person in p['household']['people']:
            add('household:' + person['id'], 'household', person)
        for event in p['timeline']:
            add('timeline:' + event['id'], 'event', event)
        for version in p['return_versions']:
            add(version['version'], 'version', version)
            for line in version['lines']:
                add(version['version'] + ':' + line['key'], 'claim', {
                    **line, 'version': version['version'], 'evidence_status': 'cited' if line['sources'] or line['inputs'] else 'missing',
                    'check_status': 'not_applicable', 'review_status': 'not_reviewed', 'computation_basis': 'engine'})
            for asset in version['assets']:
                add(version['version'] + ':asset:' + asset['asset_id'], 'asset', asset)
        return rows

    def resolve(self, ref, version='v3'):
        p = self.data
        try:
            if ref.startswith('py:'):
                return pointer(p['prior_years'], ref[3:])
            if ref.startswith('agency:'):
                return pointer(p['tax_agency_records'], ref[7:])
            if ref.startswith('ref:param.'):
                return p['engine_reference']['parameters'][ref[len('ref:param.'):]]
            if ref.startswith('ref:fx.SEK.'):
                return p['engine_reference']['parameters']['fx']['SEK'][ref[len('ref:fx.SEK.'):]]
            if ref.startswith('asset:'):
                v = next(v for v in p['return_versions'] if v['version'] == version)
                return next(a for a in v['assets'] + p['prior_years']['asset_records'] if a['asset_id'] == ref[6:])
            rows = self.index
            key = ref if ref in rows else version + ':' + ref
            return rows[key]['payload']
        except (KeyError, IndexError, ValueError, StopIteration, TypeError):
            return None

    @property
    def index(self):
        if not hasattr(self, '_index'):
            self._index = self.records()
        return self._index

    def edges(self):
        edges = []
        for version in self.data['return_versions']:
            for line in version['lines']:
                for kind, refs in [('input', line['inputs']), ('source', line['sources'])]:
                    for ref in refs:
                        target = version['version'] + ':' + ref if kind == 'input' or ref.startswith('asset:') else ref
                        edges.append({'source': version['version'] + ':' + line['key'], 'target': target,
                                      'kind': kind, 'resolved': self.resolve(ref, version['version']) is not None})
        for document in self.data['documents']:
            for page in document['pages']:
                edges.append({'source': f"doc:{document['id']}#page{page['page']}", 'target': document['id'], 'kind': 'document', 'resolved': True})
        for e in self.data['extracted_values']:
            target = f"doc:{e['document_id']}#page{e['page']}"
            edges.append({'source': e['id'], 'target': target, 'kind': 'source', 'resolved': target in self.index})
        return edges
