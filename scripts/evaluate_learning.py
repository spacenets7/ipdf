"""Report observed repeat-question changes from exported browser learning history.

These observations do not establish causal learning gains or model improvement.
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

def evaluate(attempts):
    cards=defaultdict(list)
    for attempt in attempts:
        cards[attempt['card_id']].append(bool(attempt['correct']))
    repeated=[values for values in cards.values() if len(values)>1]
    return {'questions':len(cards),'attempts':len(attempts),'repeated_questions':len(repeated),
        'first_correct':sum(v[0] for v in repeated),'latest_correct':sum(v[-1] for v in repeated),
        'note':'Repeated-question observations only; not a controlled comparison or evidence of model training.'}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('history',type=Path);args=parser.parse_args()
    print(json.dumps(evaluate(json.loads(args.history.read_text(encoding='utf-8'))['attempts']),indent=2))
