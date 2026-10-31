"""Day 6 pages: the publication record binds every download by hash; the stand page shows pins, tabs and no approval."""
import hashlib, json
from pathlib import Path
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

pytestmark = pytest.mark.django_db
ROOT = Path(__file__).resolve().parents[3].parent / 'docs/audit/day-6'


def _login(client, settings):
    settings.HYBRID_BOTTLE_ENABLED = True
    user = get_user_model().objects.create_superuser('day6-owner', password='test'); client.force_login(user); return user


def test_stand_page_shows_day6_pins_every_tab_hash_checked_downloads_and_no_approval(client, settings):
    _login(client, settings)
    response = client.get(reverse('dashboard:assembly_master')); body = response.content.decode()
    assert response.status_code == 200 and 'D1' in body and 'Designer review needed' in body and 'Approve' not in body and 'revision 2' in body
    record = json.loads((ROOT / 'publication.json').read_text())
    for tab in ('surfaces', 'render', 'cut', 'device', 'library', 'history'):
        assert client.get(reverse('dashboard:assembly_master') + '?tab=' + tab).status_code == 200
    assert client.get(reverse('dashboard:assembly_master') + '?tab=nonsense').status_code == 404
    for role in ('owner-pick', 'render-front', 'presentation', 'cut-layout', 'surface-bindings'):
        served = client.get(reverse('dashboard:day6_file', args=[role]))
        assert served.status_code == 200
        assert hashlib.sha256(b''.join(served.streaming_content)).hexdigest() == record['downloads'][role]['sha256']
    assert client.get(reverse('dashboard:day6_file', args=['no-such-role'])).status_code == 404


def test_day5_stand_keeps_its_historical_route_and_the_serum_page_lists_revision_4_as_history(client, settings):
    _login(client, settings)
    historical = client.get(reverse('dashboard:day5_stand')).content.decode()
    assert 'No candidate meets the release bar yet.' in historical
    serum = client.get(reverse('dashboard:hybrid_master')).content.decode()
    assert 'Bottle revision 4 sheet' in serum and 'not pinned' in serum and 'Approve' not in serum


def test_a_changed_artifact_is_refused(client, settings, tmp_path, monkeypatch):
    _login(client, settings)
    import shutil
    from apps.dashboard import day6_views
    copy = tmp_path / 'docs/audit/day-6'; copy.parent.mkdir(parents=True); shutil.copytree(ROOT, copy, symlinks=True, ignore=shutil.ignore_patterns('*.zip', 'render*', 'bottle', 'library', 'cut-layout', 'stand'))
    record = json.loads((copy / 'publication.json').read_text())
    pick = copy / record['downloads']['owner-pick']['path']; pick.parent.mkdir(parents=True, exist_ok=True); pick.write_bytes(b'not the picture')
    monkeypatch.setattr(day6_views, 'root', lambda: copy)
    assert client.get(reverse('dashboard:assembly_master')).status_code == 404
