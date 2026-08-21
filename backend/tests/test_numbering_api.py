"""
TASK-S061 -- verifie que le validateur central est REELLEMENT branche dans
les vrais endpoints (pas seulement teste en isolation dans
test_numbering.py). Demande explicite de Philippe (2026-08-19) apres avoir
remarque que le recapitulatif initial ne mentionnait aucun branchement.
Passe par de vraies requetes HTTP contre l'app FastAPI (get_db/auth
surcharges vers la transaction de test -- voir conftest.make_api_client).
"""
from app.models.ivr import PagingGroup, RingGroup
from app.models.sip import SIPExtension
from tests.conftest import make_api_client, make_tenant


async def test_create_extension_via_api_refuse_si_ring_group_deja_sur_ce_numero(db_session):
    tenant = await make_tenant(db_session)
    db_session.add(RingGroup(tenant_id=tenant.id, name="Reception", extension="701", members=""))
    await db_session.flush()
    client = await make_api_client(db_session)

    resp = await client.post(f"/api/v1/extensions/tenant/{tenant.id}", json={"extension": "701", "name": "Poste 701"})

    assert resp.status_code == 400
    assert "ring_group" in resp.text
    await client.aclose()


async def test_create_extension_via_api_accepte_si_numero_libre(db_session):
    tenant = await make_tenant(db_session)
    client = await make_api_client(db_session)

    resp = await client.post(f"/api/v1/extensions/tenant/{tenant.id}", json={"extension": "702", "name": "Poste 702"})

    assert resp.status_code == 201
    await client.aclose()


async def test_create_ring_group_via_api_refuse_si_extension_deja_sur_ce_numero(db_session):
    tenant = await make_tenant(db_session)
    db_session.add(SIPExtension(
        tenant_id=tenant.id, extension="700", name="Poste 700",
        username=f"{tenant.account_number}-700", password="x",
    ))
    await db_session.flush()
    client = await make_api_client(db_session)

    resp = await client.post(
        f"/api/v1/ivr/ring-groups/tenant/{tenant.id}",
        json={"name": "Reception", "extension": "700", "members": []},
    )

    assert resp.status_code == 400
    assert "extension" in resp.text
    await client.aclose()


async def test_update_paging_group_via_api_accepte_de_garder_son_propre_numero(db_session):
    tenant = await make_tenant(db_session)
    pg = PagingGroup(tenant_id=tenant.id, name="Atelier", extension="710")
    db_session.add(pg)
    await db_session.flush()
    client = await make_api_client(db_session)

    resp = await client.put(f"/api/v1/ivr/paging-groups/{pg.id}", json={"extension": "710"})

    assert resp.status_code == 200
    await client.aclose()


async def test_update_paging_group_via_api_refuse_si_collision_reelle(db_session):
    tenant = await make_tenant(db_session)
    db_session.add(SIPExtension(
        tenant_id=tenant.id, extension="711", name="Poste 711",
        username=f"{tenant.account_number}-711", password="x",
    ))
    pg = PagingGroup(tenant_id=tenant.id, name="Atelier", extension="712")
    db_session.add(pg)
    await db_session.flush()
    client = await make_api_client(db_session)

    resp = await client.put(f"/api/v1/ivr/paging-groups/{pg.id}", json={"extension": "711"})

    assert resp.status_code == 400
    assert "extension" in resp.text
    await client.aclose()
