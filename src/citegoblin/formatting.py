import copy
import json
from pathlib import Path
import shutil
import subprocess

from .styles import FORMATTER, load_style


def format_registry(registry):
    registry=copy.deepcopy(registry)
    from .metadata_cleanup import effective_csl
    for reference in registry['records'].values():reference['csl']=effective_csl(reference)
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
    cleanup=registry.get('referenceCleanup',{})
    if cleanup.get('enabled'):
        from .binomials import clean_reference_text,overlay_styles
        text,changes,skipped=clean_reference_text(preview['bibliography'],cleanup['names'],abbreviations=cleanup.get('abbreviations',False))
        preview['bibliography']=text
        preview['bibliographyStyles']=overlay_styles(preview['bibliographyStyles'],changes)
        preview['referenceNames']=changes;preview['referenceNamesSkipped']=skipped
        # Native text/style spans are the rendered result after reference cleanup.
        preview.pop('bibliographyHtml',None)
    return preview
