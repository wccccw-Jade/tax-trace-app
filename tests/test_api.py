from fastapi.testclient import TestClient
from backend.api import app, staff, identity
from fastapi import HTTPException
import pytest


def test_health_and_public_actor_directory():
    with TestClient(app) as client:
        assert client.get('/api/health').json()['status']=='ok'
        response = client.get('/api/actors')
        assert response.status_code==200
        assert len(response.json())==8
        assert 'ssn' not in response.text
        assert client.get('/okafor_lindqvist_2025_packet.json').status_code==404


def test_client_cannot_access_internal_routes():
    app.dependency_overrides[identity] = lambda: {'id':'cu-01','role':'client'}
    # Staff guard runs before route/database work.
    try:
        with TestClient(app) as client:
            assert client.get('/api/records').status_code==403
            assert client.get('/api/audit').status_code==403
            assert client.get('/api/trace?ref=D01').status_code==403
            assert client.put('/api/locators/ev-0001', json={'expected_revision':1,'start':0,'end':1}).status_code==403
    finally:
        app.dependency_overrides.clear()
