"""
TASK-S061, items 3+4 -- dialplan du pilote de parcage (700 -> valet_park ...
auto in start end) ET de la plage de reprise/parcage direct (701-7xx ->
valet_park ... $1, une seule regle dialplan pour toute la plage). GO
explicite de Philippe (2026-08-19). PAS encore dans ce fichier :
timeout/orbit, valet_info, BLF, provisioning, ERPCRM.

Tests sur le XML REELLEMENT genere par l'endpoint xml_curl (pas un appel
direct a une fonction utilitaire) -- exigence explicite de Philippe.
"""
import re

from app.models.ivr import ParkingLot
from tests.conftest import make_api_client, make_tenant


async def _dialplan_xml(client, account_number: str, destination: str = "700") -> str:
    resp = await client.post(
        "/api/v1/xml_curl",
        data={"section": "dialplan", "Caller-Context": f"internal-{account_number}", "Caller-Destination-Number": destination},
    )
    assert resp.status_code == 200
    return resp.text


async def test_tenant_a_700_genere_la_bonne_cle_et_plage(db_session):
    tenant = await make_tenant(db_session)
    lot = ParkingLot(tenant_id=tenant.id, name="Parking principal", park_extension="700", parking_slots_start=701, parking_slots_end=720)
    db_session.add(lot)
    await db_session.flush()
    client = await make_api_client(db_session)

    xml = await _dialplan_xml(client, tenant.account_number)

    expected_key = f"tenant_{tenant.id}_parking_{lot.id}"
    assert f'data="{expected_key} auto in 701 720"' in xml
    await client.aclose()


async def test_tenant_b_700_genere_sa_propre_cle_et_plage(db_session):
    tenant = await make_tenant(db_session)
    lot = ParkingLot(tenant_id=tenant.id, name="Parking principal", park_extension="700", parking_slots_start=701, parking_slots_end=720)
    db_session.add(lot)
    await db_session.flush()
    client = await make_api_client(db_session)

    xml = await _dialplan_xml(client, tenant.account_number)

    expected_key = f"tenant_{tenant.id}_parking_{lot.id}"
    assert f'data="{expected_key} auto in 701 720"' in xml
    await client.aclose()


async def test_renommer_le_lot_ne_change_pas_la_cle_freeswitch(db_session):
    tenant = await make_tenant(db_session)
    lot = ParkingLot(tenant_id=tenant.id, name="Parking principal", park_extension="700", parking_slots_start=701, parking_slots_end=720)
    db_session.add(lot)
    await db_session.flush()
    client = await make_api_client(db_session)
    expected_key = f"tenant_{tenant.id}_parking_{lot.id}"

    xml_before = await _dialplan_xml(client, tenant.account_number)
    assert f'data="{expected_key} auto in 701 720"' in xml_before

    lot.name = "Réception"
    await db_session.flush()

    xml_after = await _dialplan_xml(client, tenant.account_number)
    assert f'data="{expected_key} auto in 701 720"' in xml_after
    await client.aclose()


async def test_deux_tenants_memes_pilote_et_plage_donnent_deux_cles_differentes(db_session):
    tenant_a = await make_tenant(db_session)
    tenant_b = await make_tenant(db_session)
    lot_a = ParkingLot(tenant_id=tenant_a.id, name="Parking principal", park_extension="700", parking_slots_start=701, parking_slots_end=720)
    lot_b = ParkingLot(tenant_id=tenant_b.id, name="Parking principal", park_extension="700", parking_slots_start=701, parking_slots_end=720)
    db_session.add_all([lot_a, lot_b])
    await db_session.flush()
    client = await make_api_client(db_session)

    xml_a = await _dialplan_xml(client, tenant_a.account_number)
    xml_b = await _dialplan_xml(client, tenant_b.account_number)

    key_a = f"tenant_{tenant_a.id}_parking_{lot_a.id}"
    key_b = f"tenant_{tenant_b.id}_parking_{lot_b.id}"

    assert key_a != key_b
    assert f'data="{key_a} auto in 701 720"' in xml_a
    assert key_b not in xml_a
    assert f'data="{key_b} auto in 701 720"' in xml_b
    assert key_a not in xml_b
    await client.aclose()


# ── Étape 4 : plage 701-7xx, une seule règle dialplan pour toute la plage ──

def _slot_condition_block(xml: str, key: str) -> str:
    """Isole le bloc <extension> des slots (celui qui utilise `$1`, pas `auto in`).
    Cherche specifiquement la condition destination_number -- depuis
    l'ajout de l'orbit dynamique (item 6), il y a aussi une <condition>
    imbriquee pour sip_h_Referred-By entre les deux, rfind("<condition")
    seul attraperait la mauvaise."""
    marker = f'{key} $1'
    idx = xml.find(marker)
    assert idx != -1, f"aucun bloc slots trouve pour la cle {key}"
    start = xml.rfind('<condition field="destination_number"', 0, idx)
    assert start != -1, "condition destination_number introuvable avant le marqueur"
    return xml[start:idx]


async def test_lot_701_720_une_seule_regle_pour_toute_la_plage(db_session):
    tenant = await make_tenant(db_session)
    lot = ParkingLot(tenant_id=tenant.id, name="Lot A", park_extension="700", parking_slots_start=701, parking_slots_end=720)
    db_session.add(lot)
    await db_session.flush()
    client = await make_api_client(db_session)
    key = f"tenant_{tenant.id}_parking_{lot.id}"

    xml = await _dialplan_xml(client, tenant.account_number)

    # une seule extension XML pour les slots (pas 20) : un seul bloc "$1" pour ce lot
    assert xml.count(f'{key} $1') == 1
    # le pilote 700 utilise "auto in", jamais "$1"
    assert f'{key} auto in 701 720' in xml
    condition = _slot_condition_block(xml, key)
    assert "701" in condition
    assert "720" in condition
    assert "721" not in condition
    # 700 est le pilote, pas un slot -- ne doit pas apparaitre dans la regex des slots
    assert re.search(r"(?<!\d)700(?!\d)", condition) is None
    await client.aclose()


async def test_deux_lots_chaque_numero_atteint_exclusivement_son_propre_lot(db_session):
    tenant = await make_tenant(db_session)
    lot_a = ParkingLot(tenant_id=tenant.id, name="Lot A", park_extension="700", parking_slots_start=701, parking_slots_end=720)
    lot_b = ParkingLot(tenant_id=tenant.id, name="Lot B", park_extension="750", parking_slots_start=751, parking_slots_end=760)
    db_session.add_all([lot_a, lot_b])
    await db_session.flush()
    client = await make_api_client(db_session)
    key_a = f"tenant_{tenant.id}_parking_{lot_a.id}"
    key_b = f"tenant_{tenant.id}_parking_{lot_b.id}"

    xml = await _dialplan_xml(client, tenant.account_number)

    condition_a = _slot_condition_block(xml, key_a)
    condition_b = _slot_condition_block(xml, key_b)

    assert "701" in condition_a and "720" in condition_a
    assert "751" not in condition_a and "760" not in condition_a

    assert "751" in condition_b and "760" in condition_b
    assert "701" not in condition_b and "720" not in condition_b
    await client.aclose()


# ── Item 6 raffiné : timeout_return_mode explicite (demande Philippe 2026-08-20) ──

async def test_mode_parker_defaut_genere_la_condition_dynamique(db_session):
    tenant = await make_tenant(db_session)
    lot = ParkingLot(tenant_id=tenant.id, name="Lot A", park_extension="700", parking_slots_start=701, parking_slots_end=720)
    db_session.add(lot)
    await db_session.flush()
    client = await make_api_client(db_session)
    key = f"tenant_{tenant.id}_parking_{lot.id}"

    xml = await _dialplan_xml(client, tenant.account_number)

    condition = _slot_condition_block(xml, key)
    assert "sip_h_Referred-By" in condition
    await client.aclose()


async def test_mode_fixed_ignore_le_dynamique_et_utilise_toujours_return_extension(db_session):
    tenant = await make_tenant(db_session)
    lot = ParkingLot(
        tenant_id=tenant.id, name="Lot A", park_extension="700", parking_slots_start=701, parking_slots_end=720,
        return_extension="200", timeout_return_mode="fixed",
    )
    db_session.add(lot)
    await db_session.flush()
    client = await make_api_client(db_session)
    key = f"tenant_{tenant.id}_parking_{lot.id}"

    xml = await _dialplan_xml(client, tenant.account_number)

    condition = _slot_condition_block(xml, key)
    assert "sip_h_Referred-By" not in condition
    assert 'data="valet_parking_orbit_exten=200"' in condition
    await client.aclose()
