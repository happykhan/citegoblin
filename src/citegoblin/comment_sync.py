"""Verified success resolves commands; failures share one editable error reply."""
from .commands import fingerprint

ERROR_PREFIX = 'CiteGoblin error [v1]:\n'


def upsert_error(client, document_id, comment_id, message, *, replies=None):
    """Rediscover owned replies every time, including after an uncertain POST."""
    content = ERROR_PREFIX + message
    if replies is None:
        replies=client.replies(document_id, comment_id)
    owned = [r for r in replies
             if not r.get('deleted') and r.get('author', {}).get('me')
             and r.get('content', '').startswith(ERROR_PREFIX)]
    if not owned:
        return client.create_reply(document_id, comment_id, content)['id']
    reply = owned[0]
    if reply.get('content') != content:
        client.update_reply(document_id, comment_id, reply['id'], content)
    return reply['id']


def sync_feedback(client, document_id, comments, report, *, verified):
    """Called after readback. Never resolve a changed command or an unverified one."""
    snapshots = {c['id']: c for c in comments}
    successes = report.get('processed', []) + report.get('alreadyProcessed', [])
    keep_open={c['commentId'] for c in successes if c.get('keepOpen')}
    actions = {c['commentId']: None for c in successes} if verified else {}
    actions.update({c['commentId']: c['error'] for c in report['errors']})
    result = {'resolved': [], 'errorReplies': [], 'skipped': [], 'errors': [], 'keptOpen': []}
    # An unchanged existing error needs no mutation or fresh thread read.
    for key,error in list(actions.items()):
        before=snapshots[key]
        if error is None and key in keep_open and before.get('_repliesComplete') and not any(r.get('author',{}).get('me') and not r.get('deleted') and r.get('content','').startswith(ERROR_PREFIX) for r in before.get('replies',[])):
            result['keptOpen'].append(key);del actions[key];continue
        if error is not None and before.get('_repliesComplete'):
            existing=next((r for r in before['replies'] if not r.get('deleted') and r.get('author',{}).get('me')
                           and r.get('content')==ERROR_PREFIX+error),None)
            if existing:
                result['errorReplies'].append({'commentId':key,'replyId':existing['id']})
                del actions[key]
    if not actions:return result
    # One fresh list checks all command fingerprints and returns complete replies.
    try:
        current_comments={c['id']:c for c in client.comments(document_id)}
    except (ValueError,OSError) as failure:
        result['errors'].extend({'commentId':key,'error':str(failure)} for key in actions)
        return result
    for key, error in actions.items():
        before = snapshots[key]
        try:
            current = current_comments.get(key)
            if current is None or current.get('deleted') or current.get('resolved'):
                result['skipped'].append(key)
                continue
            if fingerprint(current) != fingerprint(before):
                result['skipped'].append(key)
                continue
            if error is None and key in keep_open:
                replies=current.get('replies',[]) if current.get('_repliesComplete') else client.replies(document_id,key)
                for reply in replies:
                    if not reply.get('deleted') and reply.get('author',{}).get('me') and reply.get('content','').startswith(ERROR_PREFIX):
                        client.update_reply(document_id,key,reply['id'],'CiteGoblin: bibliography location applied and verified. This comment stays open.')
                result['keptOpen'].append(key);continue
            if error is None:
                try:
                    client.resolve_comment(document_id, key)
                except (ValueError, OSError) as failure:
                    error = 'Citation command applied and verified, but resolving the comment failed: ' + str(failure)
                else:
                    result['resolved'].append(key)
                    continue
            reply_id = upsert_error(client, document_id, key, error,
                                    replies=current.get('replies',[]) if current.get('_repliesComplete') else None)
            result['errorReplies'].append({'commentId': key, 'replyId': reply_id})
        except (ValueError, OSError) as failure:
            # A denied comment write must not turn a verified citation into a repeat insertion.
            result['errors'].append({'commentId': key, 'error': str(failure)})
    return result
