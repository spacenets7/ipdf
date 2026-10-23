import json
import math
import re
from datetime import datetime, timezone
from app.modules.digest.levels import DIFFICULTY
from app.modules.digest.sources.arxiv import TOPICS


def topic_matches(topic, text, tags):
    topic = topic.lower()
    canonical = TOPICS.get(topic,topic).lower()
    if canonical in [t.lower() for t in tags]:
        return True
    words = re.findall(r'\w+',topic)
    haystack = set(re.findall(r'\w+',text.lower()))
    return bool(words) and all(word in haystack for word in words)


def score(row, user, level, seen_ids=()):
    summary = row['summary']
    tags = summary['topic_tags'] + json.loads(row['item'].get('tags_json','[]'))
    text = row['item']['title']+' '+row['item']['raw_text'][:4000]+' '+' '.join(tags)
    relevance = sum(user['topic_weights'].get(topic,1.0) for topic in user['topics'] if topic_matches(topic,text,tags))
    # Feedback also weights source/model tags, not only the checkbox topics.
    relevance += .25*sum(user['topic_weights'].get(tag,1.0)-1 for tag in set(tags))
    try:
        published = datetime.fromisoformat(row['item']['published'].replace('Z','+00:00'))
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        age = max(0,(datetime.now(timezone.utc)-published).total_seconds()/86400)
    except ValueError:
        age = 30
    novelty = math.exp(-age/7) + (0 if row['item']['id'] in seen_ids else .5)
    mismatch = abs(summary['difficulty']-DIFFICULTY[level])*.4
    priority = {'read_first':.3,'skim':0,'skip':-.5}[summary['read_priority']]
    return round(2*relevance+novelty-mismatch+priority,4)


def rank(rows,user,level,seen_ids=()):
    for row in rows:
        row['score'] = score(row,user,level,seen_ids)
    return sorted(rows,key=lambda row:row['score'],reverse=True)[:8]
