import json
from app import db
from app.modules.digest.levels import shift_level
from app.modules.digest.rank import topic_matches

SIGNALS = ('up','down','too_hard','too_easy')


def apply_feedback(user_id, item_id, signal):
    if signal not in SIGNALS:
        raise ValueError('Unknown feedback signal')
    # Read-modify-write and duplicate detection share one write transaction.
    with db.connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        user = conn.execute('SELECT * FROM users WHERE id=?',(user_id,)).fetchone()
        item = conn.execute('SELECT * FROM items WHERE id=?',(item_id,)).fetchone()
        if not user or not item:
            raise ValueError('Unknown reader or paper')
        last = conn.execute('SELECT signal FROM feedback WHERE user_id=? AND item_id=? ORDER BY id DESC LIMIT 1',
                            (user_id,item_id)).fetchone()
        if last and last['signal'] == signal:
            return {'level':user['level'],'level_offset':user['level_offset'],'duplicate':True}
        weights = json.loads(user['topic_weights_json'])
        if signal in ('up','down'):
            tags = set(json.loads(item['tags_json']))
            summaries = conn.execute('SELECT json FROM summaries WHERE item_id=?',(item_id,)).fetchall()
            for summary in summaries:
                tags.update(json.loads(summary['json']).get('topic_tags',[]))
            for topic in json.loads(user['topics_json']):
                if topic_matches(topic,item['title']+' '+item['raw_text'],tags):
                    tags.add(topic)
            delta = .1 if signal == 'up' else -.1
            for tag in tags:
                weights[tag] = round(max(.1,min(3,weights.get(tag,1)+delta)),3)
        level,offset = shift_level(user['level'],user['level_offset'],signal)
        conn.execute('UPDATE users SET level=?,level_offset=?,topic_weights_json=? WHERE id=?',
                     (level,offset,json.dumps(weights),user_id))
        conn.execute('INSERT INTO feedback(user_id,item_id,signal) VALUES(?,?,?)',(user_id,item_id,signal))
    return {'level':level,'level_offset':offset,'topic_weights':weights,'duplicate':False}
