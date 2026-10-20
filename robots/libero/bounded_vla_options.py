"""Finite VLA prompt variants from the public instruction, never model prose."""
import re

STYLES = ('template','original_clause','full_task','a1_description')


def instruction_clauses(instruction):
    """Keep original noun/region wording and resolve only explicit 'it'."""
    clauses = re.split(r'\s+(?:and|then|and then)\s+(?=(?:pick|put|place|open|close|turn|push)\b)',
        instruction.strip(),flags=re.IGNORECASE)
    source = None
    result = []
    for clause in clauses[:16]:
        match = re.match(r'(?:pick up|grasp|take)\s+(?:the\s+)?(.+)',clause,re.I)
        if match:
            source = match[1]
        if source and re.match(r'(?:put|place)\s+it\b',clause,re.I):
            clause = re.sub(r'^(put|place)\s+it\b',lambda m:m[1]+' the '+source,clause,flags=re.I)
        result.append(clause)
    return result


def clause_for_mode(instruction,mode,names=()):
    actions = {'pick':r'pick|grasp|take','on':r'put|place','in':r'put|place',
        'push':r'push','open':r'open','close':r'close','turn_on':r'turn on','turn_off':r'turn off'}
    clauses = [c for c in instruction_clauses(instruction)
        if re.match(actions.get(mode,r'.*'),c,re.I)]
    if not clauses:
        return None
    tokens = set(re.findall(r'[a-z]+',' '.join(names).lower()))-{'the','of','area','surface'}
    scores = [len(tokens&set(re.findall(r'[a-z]+',clause.lower()))) for clause in clauses]
    best = max(scores)
    winners = [c for c,s in zip(clauses,scores) if s==best]
    return winners[0] if len(winners)==1 else None


def render_variant(instruction,parameters,template,names=()):
    mode = parameters['mode']
    if mode=='task' or parameters.get('prompt_style')=='full_task':
        return instruction
    if mode=='instruction':
        clauses = instruction_clauses(instruction)
        index = parameters['clause_id']
        if not 0 <= index < len(clauses):
            raise ValueError('instruction clause ID is outside the published instruction')
        return clauses[index]
    style = parameters.get('prompt_style','template')
    if style=='original_clause':
        return clause_for_mode(instruction,mode,names) or template
    if style=='a1_description':
        if mode=='pick' and names:
            return f'Grasp the {names[0]} and lift it off the surface.'
        if mode in {'open','close'} and names:
            return f'{"Pull" if mode=="open" else "Push"} the {names[0]} {"open" if mode=="open" else "closed"}.'
        if mode in {'on','in'} and len(names)>1:
            return f'Place the {names[0]} {mode} the {names[1]}.'
        clause = clause_for_mode(instruction,mode,names) or template
        return clause[0].upper()+clause[1:].rstrip('.')+'.'
    return template
