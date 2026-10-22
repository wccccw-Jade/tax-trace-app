"""Private local attachment store. Object storage can replace this adapter at deployment."""
from pathlib import Path
from uuid import uuid4
from backend.config import settings


class LocalAttachments:
    def put(self, data: bytes) -> str:
        key=uuid4().hex
        settings.attachment_dir.mkdir(parents=True,exist_ok=True)
        (settings.attachment_dir/key).write_bytes(data)
        return key

    def read(self, key: str) -> bytes:
        # Keys are generated internally, never derived from an uploaded filename.
        if len(key)!=32 or any(c not in '0123456789abcdef' for c in key):
            raise FileNotFoundError(key)
        return (settings.attachment_dir/key).read_bytes()

    def remove(self, key: str):
        (settings.attachment_dir/key).unlink(missing_ok=True)


attachments=LocalAttachments()
