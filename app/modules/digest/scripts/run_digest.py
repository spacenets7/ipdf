"""Cron-friendly: python scripts/run_digest.py --user USER_ID --refresh."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import db
from app.modules.digest.digest import build_digest


def main():
    parser=argparse.ArgumentParser(description='Build a LazyDigest for a saved reader')
    parser.add_argument('--user',help='Reader ID; omit to list saved readers')
    parser.add_argument('--refresh',action='store_true')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    db.init_db()
    if not args.user:
        for user in db.query('SELECT id,name,level FROM users'):
            print(user['id'],user['name'],user['level'])
        return
    user=db.get_user(args.user)
    if not user:
        parser.error('Reader not found. Create a reading profile in the web app first.')
    try:
        digest=build_digest(user,refresh=args.refresh)
    except Exception as exc:
        print(f'Build failed: {exc}',file=sys.stderr)
        raise SystemExit(1)
    output=args.output or db.settings.data_dir/f'digest-{digest["id"]}.md'
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(digest['markdown'],encoding='utf-8')
    print(f'Digest {digest["id"]}: {len(digest["rows"])} papers. Saved {output.resolve()}')
    for warning in digest['warnings']:
        print('Note:',warning)


if __name__=='__main__':
    main()
