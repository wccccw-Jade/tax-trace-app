"""Conservative spans in original printed text; never fabricate a page coordinate."""
import re
from datetime import date


def normalized(text):
    chars, positions = [], []
    for i, c in enumerate(text):
        if c.isalnum():
            chars.append(c.lower())
            positions.append(i)
    return ''.join(chars), positions


def span(start, end, printed, layer='field_mapping'):
    return {'resolved': True, 'layer': layer, 'start': start, 'end': end, 'quote': printed[start:end]}


def scoped_field(extraction, printed):
    """Repeated lot/trip amounts must be located within their own row, not page-wide."""
    field = extraction['field']
    lot = re.fullmatch(r'([NMXC]\d+)_(description|shares|acq|acquired|sold|proceeds|basis|wash|term|covered)', field)
    if lot:
        row_id, column = lot.groups()
        rows = list(re.finditer(r'\b' + re.escape(row_id) + r'\s+([^;]+)', printed))
        if len(rows) != 1:
            return None
        row = rows[0]
        text = row.group(1)
        money = r'([\d,]+(?:\.\d+)?)'
        patterns = {
            'description': r'^(.+?)\s+[\d,.]+\s+sh\b',
            'shares': r'([\d,.]+)\s+sh\b',
            'acq': r'acquired\s+(\d{4}-\d{2}-\d{2})',
            'acquired': r'acquired\s+(\d{4}-\d{2}-\d{2})',
            'sold': r'sold\s+(\d{4}-\d{2}-\d{2})',
            'proceeds': r'proceeds\s+' + money,
            'basis': r'basis\s+' + money,
            'wash': r'wash sale loss disallowed\s+' + money,
            'term': r'\b(short|long)-term',
            'covered': r'\b(noncovered|covered)\b',
        }
        matches = list(re.finditer(patterns[column], text, re.I))
        if len(matches) == 1:
            m = matches[0]
            return span(row.start(1)+m.start(1), row.start(1)+m.end(1), printed)
    trip = re.fullmatch(r'trip(\d+)_(date|destination|purpose|miles)', field)
    if trip:
        index, column = trip.groups()
        trips = list(re.finditer(r'(\d{4}-\d{2}-\d{2})\s+([^;]+?)\s+\(([^)]+)\)\s+([\d,]+) mi\b', printed))
        i = int(index)-1
        if 0 <= i < len(trips):
            group = {'date':1, 'destination':2, 'purpose':3, 'miles':4}[column]
            return span(trips[i].start(group), trips[i].end(group), printed)
    return None


def locate(extraction, printed):
    scoped = scoped_field(extraction, printed)
    if scoped:
        return scoped
    candidates = [extraction.get('text_as_read', '')]
    if extraction.get('value_type') == 'date':
        try:
            d = date.fromisoformat(str(extraction['value']))
            candidates.extend([d.isoformat(), d.strftime('%m/%d/%Y')])
        except (KeyError, ValueError):
            pass
    field = extraction['field'].lower()
    money = r'([\d,]+(?:\.\d+)?)'
    patterns = {'page_total': r'Page total\s+([\d,]+)',
                'box4c': r'4c gross proceeds from sale\s+'+money,
                'interest_sek': r'Interest credited [^:]+: SEK\s+'+money,
                'balance_ye_sek': r'(?<!Highest )Balance 12/31/2025: SEK\s+'+money,
                'max_balance_sek': r'Highest balance during 2025: SEK\s+'+money}
    pattern = patterns.get(field)
    if field.startswith('box') and field[3:].isdigit():
        pattern = rf'\bbox\s+{field[3:]}\b[^;]*?([\d,]+\.\d{{2}})'
    if pattern:
        matches = list(re.finditer(pattern, printed, re.I))
        if len(matches) == 1:
            m = matches[0]
            return span(m.start(1), m.end(1), printed)
    text, positions = normalized(printed)
    for candidate in candidates:
        needle, _ = normalized(str(candidate))
        if not needle:
            continue
        hits = [m.start() for m in re.finditer(re.escape(needle), text)]
        hits = [h for h in hits if not (needle.isdigit() and ((h and text[h-1].isdigit()) or (h+len(needle)<len(text) and text[h+len(needle)].isdigit())))]
        if len(hits) == 1:
            h = hits[0]
            return span(positions[h], positions[h+len(needle)-1]+1, printed, 'normalized')
    return {'resolved': False, 'layer': 'unresolved', 'reason': 'No unique field/text match; manual anchor required.'}


def packet_locators(packet):
    return {e['id']: locate(e, packet.resolve(f"doc:{e['document_id']}#page{e['page']}")['printed_content'])
            for e in packet.data['extracted_values']}
