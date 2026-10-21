import pytest
from backend.domain.packet import Packet
from backend.config import settings

@pytest.fixture(scope='session')
def packet():
    return Packet.read(settings.packet_path)
