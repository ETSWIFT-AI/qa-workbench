"""OS keyring storage and conservative textual redaction."""
import re
from urllib.parse import urlsplit,urlunsplit

SECRET_NAME=re.compile(r'QA_[A-Z0-9_]{1,60}\Z')

def keyring_api():
    import keyring
    backend=keyring.get_keyring()
    # Only explicitly supported OS-backed stores. Plaintext/plugin fallbacks are rejected.
    if not backend.__class__.__module__.startswith(('keyring.backends.Windows','keyring.backends.macOS','keyring.backends.SecretService')):
        raise RuntimeError('Supported OS credential store unavailable. Configure Windows Credential Locker, macOS Keychain or Linux Secret Service.')
    return keyring

def secret_set(project,name,value):
    if not SECRET_NAME.fullmatch(name) or not isinstance(value,str) or not value or len(value)>8192:raise ValueError('Use a QA_UPPERCASE_NAME and a nonempty value (max 8192 characters)')
    keyring_api().set_password('website-qa-project-'+str(project),name,value)

def secret_delete(project,name):
    if not SECRET_NAME.fullmatch(name):raise ValueError('Invalid secret name')
    keyring_api().delete_password('website-qa-project-'+str(project),name)

def secret_get(project,name):
    if not SECRET_NAME.fullmatch(name):raise ValueError('Invalid secret name')
    value=keyring_api().get_password('website-qa-project-'+str(project),name)
    if value is None:raise ValueError('Missing private input: '+name)
    return value

def redact(text,values=()):
    text=str(text)
    parts=set()
    for value in values:
        if value:
            parts.add(str(value));parts.update(p for p in str(value).splitlines() if p)
    for value in sorted(parts,key=len,reverse=True):text=text.replace(value,'[REDACTED]')
    text=re.sub(r'(?i)(authorization\s*[:=]\s*)([^\r\n]+)',r'\1[REDACTED]',text)
    text=re.sub(r'(?i)((?:password|token|api[_-]?key|secret)\s*["\x27]?\s*[:=]\s*["\x27]?)([^\s,"\x27}]+)',r'\1[REDACTED]',text)
    def url(m):
        try:
            p=urlsplit(m[0]);host=p.hostname or ''
            if ':' in host:host='['+host+']'
            if p.port:host+=':'+str(p.port)
            return urlunsplit((p.scheme,host,p.path,'REDACTED' if p.query else '', ''))
        except ValueError:return '[URL REDACTED]'
    return re.sub(r'https?://[^\s<>"\x27]+',url,text)
