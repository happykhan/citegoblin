import json
from pathlib import Path
import shutil
import subprocess

from .styles import FORMATTER, load_style


def format_registry(registry):
    info,xml=load_style(registry['style'])
    node = shutil.which('node')
    if not node:
        raise ValueError('Node.js is required by the pinned CSL formatter')
    if not (FORMATTER/'node_modules/citeproc').exists():
        raise ValueError('Run citegoblin setup-formatter first')
    result = subprocess.run([node, str(FORMATTER/'format.cjs')], input=json.dumps(dict(registry,styleXml=xml)),
                            text=True, capture_output=True, timeout=60, check=False)
    if result.returncode:
        raise ValueError('CSL formatter failed: '+result.stderr[:1500])
    preview=json.loads(result.stdout)
    from .richtext import inline_styles
    preview['citationStyles']={c['id']:inline_styles(preview['citationHtml'][c['id']],c['text']) for c in preview['citations']}
    preview['bibliographyStyles']=inline_styles(preview['bibliographyHtml'],preview['bibliography'])
    return preview
