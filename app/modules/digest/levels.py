LEVELS = ('beginner','intermediate','expert')
PROFILES = {
 'beginner': 'Explain jargon inline in ordinary language. Explain why it matters. List prerequisites. No equations. Short sentences.',
 'intermediate': 'Assume undergraduate background. Explain the method, key result and one core equation or idea. List prerequisites.',
 'expert': 'Be terse. Emphasize the delta versus prior work, assumptions, limitations and what to replicate. Prerequisites must be [].',
}
DIFFICULTY = {'beginner':1.5,'intermediate':3,'expert':4.5}


def effective_level(user):
    index = LEVELS.index(user['level'])
    offset = user.get('level_offset',0)
    return LEVELS[max(0,min(2,index+(1 if offset >= .5 else -1 if offset <= -.5 else 0)))]


def shift_level(level, offset, signal):
    offset += -.25 if signal == 'too_hard' else .25 if signal == 'too_easy' else 0
    index = LEVELS.index(level)
    if abs(offset) >= .5:
        index = max(0,min(2,index+(1 if offset > 0 else -1)))
        offset = 0
    return LEVELS[index],offset
