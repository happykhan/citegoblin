"""Attach static, relevant documentation links to user-facing errors."""
BASE='https://happykhan.github.io/citegoblin/'


def help_url(message):
    text=str(message).casefold()
    routes=(
        (('unrecognized arguments','invalid choice','the following arguments are required'),'reference/cli/'),
        (('polling interval',),'guides/monitoring/'),
        (('keychain','secret store','token file'),'reference/troubleshooting/#no-supported-operating-system-keychain-is-available'),
        (('google request failed (http 403)','google request failed (http 404)','denied access','permission denied','edit/comment'),'reference/troubleshooting/#google-returned-http-403'),
        (('allowlist','test user'),'getting-started/beta-testing/'),
        (('references text has manual edits',),'guides/citations/#manual-edits-to-references'),
        (('incomplete','uncertain','journal','revision','replay','differs','changed','plan hash','batch hash','outside authorised','native structure'),'reference/troubleshooting/#document-changed-or-a-previous-run-is-incomplete'),
        (('sign-in','sign in','oauth','consent','authorisation','credentials','refresh token','per-file permission'),'getting-started/google-login/'),
        (('multiple tabs','tab id','document tab','document link','google docs url','google document id'),'getting-started/first-document/#copy-the-document-url'),
        (('formatter','node.js','npm','install citegoblin'),'getting-started/install/'),
        (('style','csl','locale'),'guides/styles/'),
        (('pending suggestion','suggested deletion'),'reference/integrity/'),
        (('quote','anchor','selection','selected text','matches','occurrence'),'reference/troubleshooting/#quote-has-multiple-matches-or-the-comment-anchor-is-unavailable'),
        (('cleanup','binomial','scientific-name','approved','italic','abbreviat','name list'),'guides/cleanup/'),
        (('doi','pmid','crossref','pubmed','reference','identifier','citation source','command'),'guides/citations/'),
    )
    return BASE+next((path for words,path in routes if any(word in text for word in words)),'reference/troubleshooting/')


def with_help(message):
    message=str(message)
    if '\n\nHelp: '+BASE in message:return message
    return message+'\n\nHelp: '+help_url(message)


def link_errors(value):
    """Leave normal output and internal exception messages unchanged."""
    if isinstance(value,list):return [link_errors(item)for item in value]
    if isinstance(value,dict):
        return {key:with_help(item) if key in ('error','cacheError')and isinstance(item,str) else link_errors(item)for key,item in value.items()}
    return value
