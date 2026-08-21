"""
TASK-S061 (item 1 du plan Parcage) -- verrouille avant d'ecrire le CRUD
ParkingLot. Les 7 scenarios demandes par Philippe le 2026-08-19, un par cas.
"""
from app.core.numbering import check_internal_number_available, check_internal_range_available
from app.models.ivr import PagingGroup, ParkingLot, RingGroup
from app.models.sip import SIPExtension
from tests.conftest import make_tenant


async def test_extension_existante_bloque_plage_parking(db_session):
    tenant = await make_tenant(db_session)
    db_session.add(SIPExtension(
        tenant_id=tenant.id, extension="701", name="Poste 701",
        username=f"{tenant.account_number}-701", password="x",
    ))
    await db_session.flush()

    conflicts = await check_internal_range_available(db_session, tenant.id, 701, 720)

    assert len(conflicts) == 1
    assert conflicts[0].object_type == "extension"


async def test_ring_group_bloque_pilote_parking(db_session):
    tenant = await make_tenant(db_session)
    db_session.add(RingGroup(tenant_id=tenant.id, name="Reception", extension="700", members=""))
    await db_session.flush()

    conflicts = await check_internal_number_available(db_session, tenant.id, "700")

    assert len(conflicts) == 1
    assert conflicts[0].object_type == "ring_group"


async def test_paging_group_bloque_plage_parking(db_session):
    tenant = await make_tenant(db_session)
    db_session.add(PagingGroup(tenant_id=tenant.id, name="Atelier", extension="710"))
    await db_session.flush()

    conflicts = await check_internal_range_available(db_session, tenant.id, 701, 720)

    assert len(conflicts) == 1
    assert conflicts[0].object_type == "paging_group"


async def test_lots_de_parking_chevauchants_refuses(db_session):
    tenant = await make_tenant(db_session)
    db_session.add(ParkingLot(
        tenant_id=tenant.id, name="Lot A", park_extension="700",
        parking_slots_start=701, parking_slots_end=720,
    ))
    await db_session.flush()

    conflicts = await check_internal_range_available(db_session, tenant.id, 715, 730)

    assert len(conflicts) == 1
    assert conflicts[0].object_type == "parking_lot_range"


async def test_lots_de_parking_adjacents_acceptes(db_session):
    tenant = await make_tenant(db_session)
    db_session.add(ParkingLot(
        tenant_id=tenant.id, name="Lot A", park_extension="700",
        parking_slots_start=701, parking_slots_end=720,
    ))
    await db_session.flush()

    conflicts = await check_internal_range_available(db_session, tenant.id, 721, 740)

    assert conflicts == []


async def test_isolation_entre_tenants_acceptee(db_session):
    tenant_a = await make_tenant(db_session)
    tenant_b = await make_tenant(db_session)
    db_session.add(SIPExtension(
        tenant_id=tenant_a.id, extension="701", name="Poste 701",
        username=f"{tenant_a.account_number}-701", password="x",
    ))
    await db_session.flush()

    conflicts = await check_internal_range_available(db_session, tenant_b.id, 701, 720)

    assert conflicts == []


async def test_editer_un_lot_sans_changer_sa_plage_acceptee(db_session):
    tenant = await make_tenant(db_session)
    lot = ParkingLot(
        tenant_id=tenant.id, name="Lot A", park_extension="700",
        parking_slots_start=701, parking_slots_end=720,
    )
    db_session.add(lot)
    await db_session.flush()

    conflicts = await check_internal_range_available(
        db_session, tenant.id, 701, 720, exclude_object=("parking_lot", str(lot.id)),
    )

    assert conflicts == []
