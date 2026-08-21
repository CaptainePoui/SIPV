"""
TASK-S061, item 2 -- CRUD ParkingLot. GO explicite de Philippe (2026-08-19),
avec exigence principale : une mise a jour partielle doit etre validee sur
l'etat final COMPLET du lot (pilote + plage fusionnes), jamais sur le seul
champ modifie. Tous les tests passent par le vrai routing HTTP.
"""
from app.models.ivr import ParkingLot
from app.models.sip import SIPExtension
from tests.conftest import make_api_client, make_tenant


# ── Creation ─────────────────────────────────────────────────────────────

async def test_creation_pilote_et_plage_libres_acceptee(db_session):
    tenant = await make_tenant(db_session)
    client = await make_api_client(db_session)

    resp = await client.post(
        f"/api/v1/ivr/parking-lots/tenant/{tenant.id}",
        json={"name": "Lot principal", "park_extension": "700", "parking_slots_start": 701, "parking_slots_end": 720},
    )

    assert resp.status_code == 201
    await client.aclose()


async def test_creation_refuse_si_start_superieur_a_end(db_session):
    tenant = await make_tenant(db_session)
    client = await make_api_client(db_session)

    resp = await client.post(
        f"/api/v1/ivr/parking-lots/tenant/{tenant.id}",
        json={"name": "Lot invalide", "park_extension": "700", "parking_slots_start": 720, "parking_slots_end": 701},
    )

    assert resp.status_code == 400
    await client.aclose()


async def test_creation_refuse_si_pilote_dans_sa_propre_plage(db_session):
    tenant = await make_tenant(db_session)
    client = await make_api_client(db_session)

    resp = await client.post(
        f"/api/v1/ivr/parking-lots/tenant/{tenant.id}",
        json={"name": "Lot invalide", "park_extension": "710", "parking_slots_start": 701, "parking_slots_end": 720},
    )

    assert resp.status_code == 400
    await client.aclose()


# ── Modification -- l'exigence principale de Philippe ───────────────────

async def test_modification_partielle_valide_l_etat_final_complet_pas_le_seul_champ(db_session):
    """
    Reproduit exactement le scenario de Philippe : etendre parking_slots_end
    doit valider TOUTE la nouvelle plage (701-730), pas seulement le nombre
    730 isole -- sinon une collision a 725 passerait inapercue.
    """
    tenant = await make_tenant(db_session)
    db_session.add(SIPExtension(
        tenant_id=tenant.id, extension="725", name="Poste 725",
        username=f"{tenant.account_number}-725", password="x",
    ))
    lot = ParkingLot(tenant_id=tenant.id, name="Lot A", park_extension="700", parking_slots_start=701, parking_slots_end=720)
    db_session.add(lot)
    await db_session.flush()
    client = await make_api_client(db_session)

    resp = await client.put(f"/api/v1/ivr/parking-lots/{lot.id}", json={"parking_slots_end": 730})

    assert resp.status_code == 400
    assert "725" in resp.text or "extension" in resp.text
    await client.aclose()


async def test_modification_exclut_le_lot_lui_meme(db_session):
    tenant = await make_tenant(db_session)
    lot = ParkingLot(tenant_id=tenant.id, name="Lot A", park_extension="700", parking_slots_start=701, parking_slots_end=720)
    db_session.add(lot)
    await db_session.flush()
    client = await make_api_client(db_session)

    resp = await client.put(f"/api/v1/ivr/parking-lots/{lot.id}", json={"name": "Lot A renomme"})

    assert resp.status_code == 200
    await client.aclose()


async def test_modification_du_pilote_seul_revalide_contre_la_plage_inchangee(db_session):
    """Changer SEULEMENT le pilote doit quand meme etre revalide contre la plage existante (fusion)."""
    tenant = await make_tenant(db_session)
    lot = ParkingLot(tenant_id=tenant.id, name="Lot A", park_extension="700", parking_slots_start=701, parking_slots_end=720)
    db_session.add(lot)
    await db_session.flush()
    client = await make_api_client(db_session)

    resp = await client.put(f"/api/v1/ivr/parking-lots/{lot.id}", json={"park_extension": "710"})

    assert resp.status_code == 400
    await client.aclose()


# ── Multi-lot ─────────────────────────────────────────────────────────────

async def test_deux_lots_plage_contre_plage_refuse(db_session):
    tenant = await make_tenant(db_session)
    db_session.add(ParkingLot(tenant_id=tenant.id, name="Lot A", park_extension="700", parking_slots_start=701, parking_slots_end=720))
    await db_session.flush()
    client = await make_api_client(db_session)

    resp = await client.post(
        f"/api/v1/ivr/parking-lots/tenant/{tenant.id}",
        json={"name": "Lot B", "park_extension": "750", "parking_slots_start": 715, "parking_slots_end": 730},
    )

    assert resp.status_code == 400
    await client.aclose()


async def test_pilote_du_nouveau_lot_contre_plage_existante_refuse(db_session):
    tenant = await make_tenant(db_session)
    db_session.add(ParkingLot(tenant_id=tenant.id, name="Lot B existant", park_extension="750", parking_slots_start=751, parking_slots_end=770))
    await db_session.flush()
    client = await make_api_client(db_session)

    resp = await client.post(
        f"/api/v1/ivr/parking-lots/tenant/{tenant.id}",
        json={"name": "Lot A", "park_extension": "760", "parking_slots_start": 701, "parking_slots_end": 720},
    )

    assert resp.status_code == 400
    await client.aclose()


async def test_plage_du_nouveau_lot_contre_pilote_existant_refuse(db_session):
    tenant = await make_tenant(db_session)
    db_session.add(ParkingLot(tenant_id=tenant.id, name="Lot A existant", park_extension="700", parking_slots_start=701, parking_slots_end=720))
    await db_session.flush()
    client = await make_api_client(db_session)

    resp = await client.post(
        f"/api/v1/ivr/parking-lots/tenant/{tenant.id}",
        json={"name": "Lot B", "park_extension": "780", "parking_slots_start": 695, "parking_slots_end": 705},
    )

    assert resp.status_code == 400
    await client.aclose()
