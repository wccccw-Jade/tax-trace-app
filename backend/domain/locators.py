"""Conservative spans in the ORIGINAL printed text. Never use synthetic boxes as scan coordinates."""
import re


def normalized(text):
    chars, positions = [], []
    for i, c in enumerate(text):
        if c.isalnum():
            chars.append(c.lower())
            positions.append(i)
    return ''.join(chars), positions


def locate(extraction, printed):
    candidates = [extraction.get('text_as_read', '')]
    field = extraction['field'].lower()
    patterns = {'page_total': r'Page total\s+([\d,]+)', 'box4c': r'4c gross proceeds from sale\s+([\d,]+(?:\.\d+)?)',
                'interest_sek': r'interest[^\d]*([\d,]+(?:\.\d+)?)'}
    pattern = patterns.get(field)
    if field.startswith('box') and field[3:].isdigit():
        pattern = rf'\bbox\s+{field[3:]}\b[^;]*?([\d,]+\.\d{{2}})'
    if pattern:
        matches = list(re.finditer(pattern, printed, re.I))
        if len(matches) == 1:
            m = matches[0]
            return {'resolved': True, 'layer': 'field_mapping', 'start': m.start(1), 'end': m.end(1), 'quote': m.group(1)}
    text, positions = normalized(printed)
    for candidate in candidates:
        needle, _ = normalized(str(candidate))
        if not needle:
            continue
        hits = [m.start() for m in re.finditer(re.escape(needle), text)]
        # A number must not be a substring of a larger number.
        hits = [h for h in hits if not (needle.isdigit() and ((h and text[h-1].isdigit()) or (h+len(needle)<len(text) and text[h+len(needle)].isdigit())))]
        if len(hits) == 1:
            h = hits[0]
            start, end = positions[h], positions[h+len(needle)-1]+1
            return {'resolved': True, 'layer': 'normalized', 'start': start, 'end': end, 'quote': printed[start:end]}
    return {'resolved': False, 'layer': 'unresolved', 'reason': 'No unique field/text match; manual anchor required.'}


def packet_locators(packet):
    return {e['id']: locate(e, packet.resolve(f"doc:{e['document_id']}#page{e['page']}")['printed_content'])
            for e in packet.data['extracted_values']}
