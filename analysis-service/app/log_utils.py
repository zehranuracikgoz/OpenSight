"""loglara bağlantı adresi yazarken kullanıcı adı ve şifreyi maskeleyen yardımcılar"""
import re

_CREDENTIALS = re.compile(r"(://)[^/@\s]+@")


def mask_uri(text: str) -> str:
    """amqps://user:pass@host/vhost -> amqps://***:***@host/vhost, kullanıcı bilgisi yoksa olduğu gibi"""
    return _CREDENTIALS.sub(r"\1***:***@", text)
