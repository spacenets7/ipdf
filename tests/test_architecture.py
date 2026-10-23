import ast
from pathlib import Path


def test_layers_do_not_import_one_another():
    root=Path(__file__).resolve().parents[1]/'app'
    for layer in ('ingest','generate','render'):
        for path in (root/layer).rglob('*.py'):
            tree=ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                names=[node.module or ''] if isinstance(node,ast.ImportFrom) else [a.name for a in node.names] if isinstance(node,ast.Import) else []
                for other in {'ingest','generate','render'}-{layer}:
                    assert not any(name==f'app.{other}' or name.startswith(f'app.{other}.') for name in names),path


def test_renderer_has_no_model_calls_or_generation_requests():
    root=Path(__file__).resolve().parents[1]/'app/render'
    source='\n'.join(path.read_text(encoding='utf-8') for path in root.rglob('*.py'))
    assert 'chat_json' not in source
    assert 'OpenAI' not in source
    for name in ('viewer.js','audio-player.js'):
        source=(root/'static'/name).read_text(encoding='utf-8')
        assert '/ipdf/create' not in source
        assert 'chat/completions' not in source
