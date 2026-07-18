"""
mod_xml_curl — FreeSWITCH dynamic XML configuration endpoint.

FreeSWITCH calls POST /api/v1/xml_curl (form-encoded) for every config lookup.
We return XML; FreeSWITCH uses it as if it were a local config file.

Sections handled:
  directory     → SIP user auth + variables (called on every REGISTER / INVITE)
  dialplan      → call routing (called on every call)
  configuration → ivr.conf menus (called when ivr application runs)

Multi-tenant mapping:
  Tenant.account_number  = FreeSWITCH domain  (e.g.  "ACME")
  SIPExtension.username  = SIP user id         (e.g.  "ACME-201")
  Internal dialplan ctx  = "internal-ACME"
  Inbound trunk context  = "public"

FreeSWITCH sofia profile must have:
  <param name="context" value="public"/>          ← for inbound trunk calls
  <param name="xml-curl-use-dynamic-hash" value="false"/>

event_socket.conf.xml xml-curl pointing to:
  http://127.0.0.1:8020/api/v1/xml_curl
"""
import html
import uuid as uuid_mod
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.tenant import Tenant
from app.models.sip import SIPExtension, TenantDID
from app.models.dialplan import InboundRoute, OutboundRoute
from app.models.ivr import IVR, IVROption, RingGroup

router = APIRouter()

# ── Helpers ────────────────────────────────────────────────────────────────────

XML_HDR = '<?xml version="1.0" encoding="UTF-8" standalone="no"?>'

NOT_FOUND = f"""{XML_HDR}
<document type="freeswitch/xml">
  <section name="result">
    <result status="not found"/>
  </section>
</document>"""


def _resp(xml: str) -> Response:
    return Response(content=xml, media_type="text/xml")


def xe(v) -> str:
    """Escape value for XML attributes/text."""
    return html.escape(str(v or ""), quote=True)


def _context_name(account_number: str) -> str:
    return f"internal-{account_number}"


def _bridge(username: str, domain: str) -> str:
    return f"sofia/internal/{xe(username)}@{xe(domain)}"


# ── Main router ────────────────────────────────────────────────────────────────

@router.post("")
async def xml_curl(request: Request, db: AsyncSession = Depends(get_db)):
    """FreeSWITCH mod_xml_curl — main entry point."""
    form = await request.form()
    section = form.get("section", "")

    if section == "directory":
        return await _handle_directory(form, db)
    if section == "dialplan":
        return await _handle_dialplan(form, db)
    if section == "configuration":
        return await _handle_configuration(form, db)
    return _resp(NOT_FOUND)


# ── DIRECTORY ─────────────────────────────────────────────────────────────────

async def _handle_directory(form, db: AsyncSession) -> Response:
    """
    Return SIP user credentials + variables for a given domain/user.
    Called by FreeSWITCH on every REGISTER and authenticated INVITE.

    FreeSWITCH form fields:
      key_value  = domain (= account_number)
      user       = SIP username (= SIPExtension.username)
    """
    domain = form.get("key_value", "") or form.get("domain", "")
    # FreeSWITCH envoie parfois le username d'auth avec un "@" (et parfois "@domaine") en
    # suffixe (ex: "t1001-100@") — on ne garde que la partie avant le "@".
    username = form.get("user", "").split("@")[0]

    # Lookup tenant by account_number (= domain)
    result = await db.execute(
        select(Tenant).where(Tenant.account_number == domain, Tenant.is_active == True)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        return _resp(NOT_FOUND)

    # Lookup specific user if provided
    if username:
        result = await db.execute(
            select(SIPExtension).where(
                SIPExtension.username == username,
                SIPExtension.tenant_id == tenant.id,
                SIPExtension.is_active == True,
            )
        )
        ext = result.scalar_one_or_none()
        if not ext:
            return _resp(NOT_FOUND)
        return _resp(_directory_single_user(tenant, ext))

    # No specific user → return full domain with all extensions
    result = await db.execute(
        select(SIPExtension).where(
            SIPExtension.tenant_id == tenant.id,
            SIPExtension.is_active == True,
        )
    )
    extensions = result.scalars().all()
    return _resp(_directory_full_domain(tenant, extensions))


_CODEC_MAP = {"ulaw": "PCMU", "alaw": "PCMA", "g722": "G722", "g729": "G729"}


def _user_xml(ext: "SIPExtension", domain: str) -> str:
    cid_name = xe(ext.caller_id_name or ext.name)
    cid_num = xe(ext.caller_id_number or ext.extension)
    context = xe(_context_name(domain))
    vm = "true" if ext.voicemail_enabled else "false"
    codec_var = ""
    fs_codec = _CODEC_MAP.get(ext.codec)
    if fs_codec:
        codec_var = f'\n                <variable name="absolute_codec_string" value="{fs_codec}"/>'
    return f"""            <user id="{xe(ext.username)}">
              <params>
                <param name="password" value="{xe(ext.password)}"/>
              </params>
              <variables>
                <variable name="user_context" value="{context}"/>
                <variable name="effective_caller_id_name" value="{cid_name}"/>
                <variable name="effective_caller_id_number" value="{cid_num}"/>
                <variable name="outbound_caller_id_name" value="{cid_name}"/>
                <variable name="outbound_caller_id_number" value="{cid_num}"/>
                <variable name="voicemail_enabled" value="{vm}"/>
                <variable name="accountcode" value="{xe(ext.username)}"/>
                <variable name="toll_allow" value="domestic,international,local"/>{codec_var}
              </variables>
            </user>"""


def _directory_single_user(tenant: "Tenant", ext: "SIPExtension") -> str:
    domain = xe(tenant.account_number)
    dial_str = (
        "{presence_id=${dialed_user}@${dialed_domain}}"
        "${sofia_contact(*/${dialed_user}@${dialed_domain})}"
    )
    return f"""{XML_HDR}
<document type="freeswitch/xml">
  <section name="directory">
    <domain name="{domain}">
      <params>
        <param name="dial-string" value="{xe(dial_str)}"/>
      </params>
      <groups>
        <group name="default">
          <users>
{_user_xml(ext, tenant.account_number)}
          </users>
        </group>
      </groups>
    </domain>
  </section>
</document>"""


def _directory_full_domain(tenant: "Tenant", extensions: list) -> str:
    domain = xe(tenant.account_number)
    dial_str = (
        "{presence_id=${dialed_user}@${dialed_domain}}"
        "${sofia_contact(*/${dialed_user}@${dialed_domain})}"
    )
    users_xml = "\n".join(_user_xml(ext, tenant.account_number) for ext in extensions)
    return f"""{XML_HDR}
<document type="freeswitch/xml">
  <section name="directory">
    <domain name="{domain}">
      <params>
        <param name="dial-string" value="{xe(dial_str)}"/>
      </params>
      <groups>
        <group name="default">
          <users>
{users_xml}
          </users>
        </group>
      </groups>
    </domain>
  </section>
</document>"""


# ── DIALPLAN ──────────────────────────────────────────────────────────────────

async def _handle_dialplan(form, db: AsyncSession) -> Response:
    """
    Return routing rules for a given context.

    internal-{account}  → local extension calls, voicemail, outbound
    public              → inbound DID routing (from trunks)
    """
    context = form.get("context", "")
    destination = form.get("destination_number", "")

    if context.startswith("internal-"):
        account = context[len("internal-"):]
        return await _dialplan_internal(account, destination, db)

    if context == "public":
        return await _dialplan_public(destination, db)

    return _resp(NOT_FOUND)


async def _dialplan_internal(account: str, destination: str, db: AsyncSession) -> Response:
    """
    Dialplan for internal tenant context.
    Handles:
      - Extension-to-extension calls
      - Ring group calls
      - Voicemail access (*97, *98)
      - Outbound calls via configured routes
    """
    result = await db.execute(
        select(Tenant).where(Tenant.account_number == account, Tenant.is_active == True)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        return _resp(NOT_FOUND)

    # All active extensions for this tenant
    result = await db.execute(
        select(SIPExtension).where(
            SIPExtension.tenant_id == tenant.id,
            SIPExtension.is_active == True,
        )
    )
    extensions = result.scalars().all()

    # Ring groups
    result = await db.execute(
        select(RingGroup).where(
            RingGroup.tenant_id == tenant.id,
            RingGroup.is_active == True,
        )
    )
    ring_groups = result.scalars().all()

    # Outbound routes (ordered by priority)
    result = await db.execute(
        select(OutboundRoute).where(
            OutboundRoute.tenant_id == tenant.id,
            OutboundRoute.is_active == True,
        ).order_by(OutboundRoute.priority)
    )
    out_routes = result.scalars().all()

    ctx = xe(f"internal-{account}")
    domain = xe(account)
    ext_entries = _ext_dialplan_entries(extensions, domain)
    rg_entries = _ringgroup_dialplan_entries(ring_groups, domain)
    outbound_entries = _outbound_dialplan_entries(out_routes, account)

    xml = f"""{XML_HDR}
<document type="freeswitch/xml">
  <section name="dialplan">
    <context name="{ctx}">

      <!-- Voicemail check: *97 -->
      <extension name="voicemail_check">
        <condition field="destination_number" expression="^\\*97$">
          <action application="answer"/>
          <action application="voicemail" data="check default ${{domain_name}} ${{caller_id_number}}"/>
        </condition>
      </extension>

      <!-- Voicemail direct: *98+extension -->
      <extension name="voicemail_direct">
        <condition field="destination_number" expression="^\\*98([0-9]+)$">
          <action application="answer"/>
          <action application="voicemail" data="default ${{domain_name}} $1"/>
        </condition>
      </extension>

{ext_entries}
{rg_entries}
{outbound_entries}

      <!-- Catch-all: busy -->
      <extension name="catchall">
        <condition field="destination_number" expression="^(.*)$">
          <action application="respond" data="486 Busy Here"/>
        </condition>
      </extension>

    </context>
  </section>
</document>"""
    return _resp(xml)


def _ext_dialplan_entries(extensions: list, domain: str) -> str:
    entries = []
    for ext in extensions:
        name = xe(f"ext_{ext.extension}")
        num = xe(ext.extension)
        bridge = _bridge(ext.username, domain)
        vm_action = ""
        if ext.voicemail_enabled:
            vm_action = f'\n          <action application="voicemail" data="default ${{domain_name}} {xe(ext.username)}"/>'
        entries.append(f"""      <!-- Extension {ext.extension}: {xe(ext.name)} -->
      <extension name="{name}">
        <condition field="destination_number" expression="^{num}$">
          <action application="set" data="ringback=${{us-ring}}"/>
          <action application="bridge" data="{bridge}"/>{vm_action}
        </condition>
      </extension>""")
    return "\n\n".join(entries)


def _ringgroup_dialplan_entries(ring_groups: list, domain: str) -> str:
    entries = []
    for rg in ring_groups:
        name = xe(f"rg_{rg.extension}")
        num = xe(rg.extension)
        members = [m.strip() for m in (rg.members or "").split(",") if m.strip()]
        if not members:
            continue
        if rg.ring_strategy == "simultaneous":
            # All at once: separate with :_:
            bridge_str = ":_:".join(_bridge(m, domain) for m in members)
        else:
            # Hunt: one at a time
            bridge_str = ":".join(_bridge(m, domain) for m in members)
        timeout = xe(str(rg.ring_time))
        entries.append(f"""      <!-- Ring group {rg.extension}: {xe(rg.name)} -->
      <extension name="{name}">
        <condition field="destination_number" expression="^{num}$">
          <action application="set" data="call_timeout={timeout}"/>
          <action application="set" data="ringback=${{us-ring}}"/>
          <action application="bridge" data="{xe(bridge_str)}"/>
        </condition>
      </extension>""")
    return "\n\n".join(entries)


def _outbound_dialplan_entries(routes: list, account: str) -> str:
    entries = []
    for route in routes:
        patterns = [p.strip() for p in (route.dial_patterns or "").split(",") if p.strip()]
        for pattern in patterns:
            # Convert NANP patterns to regex
            regex = _pattern_to_regex(pattern)
            strip = route.strip_digits or 0
            prepend = xe(route.prepend_digits or "")
            gw_name = xe(f"{account}-gw-{str(route.trunk_id)[:8]}")
            route_name = xe(f"outbound_{route.name}_{pattern}")

            strip_action = ""
            if strip > 0:
                strip_action = f'\n          <action application="set" data="effective_caller_id_number=${{caller_id_number}}"/>'

            entries.append(f"""      <!-- Outbound: {xe(route.name)} pattern {xe(pattern)} -->
      <extension name="{route_name}">
        <condition field="destination_number" expression="{xe(regex)}">
          <action application="set" data="outbound_caller_id_number=${{caller_id_number}}"/>{strip_action}
          <action application="bridge" data="sofia/gateway/{gw_name}/{prepend}$1"/>
        </condition>
      </extension>""")
    return "\n\n".join(entries)


def _pattern_to_regex(pattern: str) -> str:
    """Convert Asterisk-style dial pattern to FreeSWITCH regex."""
    if pattern.endswith("."):
        # Strip trailing dot wildcard — match one or more
        base = pattern[:-1]
        base = base.replace("N", "[2-9]").replace("X", "[0-9]").replace("Z", "[1-9]")
        return f"^{base}(.+)$"
    p = pattern.replace("N", "[2-9]").replace("X", "[0-9]").replace("Z", "[1-9]")
    return f"^({p})$"


async def _dialplan_public(destination: str, db: AsyncSession) -> Response:
    """
    Dialplan for inbound calls from trunks (context=public).
    Matches DID number → routes to extension, IVR, or voicemail.
    """
    # Normalize DID: try with and without leading 1
    dids_to_try = [destination]
    if destination.startswith("1") and len(destination) == 11:
        dids_to_try.append(destination[1:])
    elif len(destination) == 10:
        dids_to_try.append("1" + destination)

    result = await db.execute(
        select(InboundRoute)
        .join(Tenant, InboundRoute.tenant_id == Tenant.id)
        .where(
            InboundRoute.did_number.in_(dids_to_try),
            InboundRoute.is_active == True,
            Tenant.is_active == True,
        )
    )
    route = result.scalar_one_or_none()
    if not route:
        return _resp(NOT_FOUND)

    # Get tenant for domain name
    tenant_result = await db.execute(
        select(Tenant).where(Tenant.id == route.tenant_id)
    )
    tenant = tenant_result.scalar_one_or_none()
    if not tenant:
        return _resp(NOT_FOUND)

    domain = xe(tenant.account_number)
    dest_num = xe(destination)
    actions = await _inbound_actions(route, tenant, db)

    xml = f"""{XML_HDR}
<document type="freeswitch/xml">
  <section name="dialplan">
    <context name="public">

      <extension name="inbound_{dest_num}">
        <condition field="destination_number" expression="^{dest_num}$">
          <action application="set" data="domain_name={domain}"/>
{actions}
        </condition>
      </extension>

    </context>
  </section>
</document>"""
    return _resp(xml)


async def _inbound_actions(route: "InboundRoute", tenant: "Tenant", db: AsyncSession) -> str:
    """Generate dialplan actions for an inbound route destination."""
    domain = tenant.account_number
    dest_type = route.destination_type
    dest = route.destination

    if dest_type == "extension":
        bridge = _bridge(dest, domain)
        return f"""          <action application="set" data="ringback=${{us-ring}}"/>
          <action application="bridge" data="{xe(bridge)}"/>"""

    if dest_type == "ivr":
        # dest = IVR UUID or name
        ivr_menu_name = xe(f"ivr_{dest}")
        return f"""          <action application="answer"/>
          <action application="sleep" data="1000"/>
          <action application="ivr" data="{ivr_menu_name}"/>"""

    if dest_type == "queue":
        queue_name = xe(dest)
        return f"""          <action application="answer"/>
          <action application="sleep" data="1000"/>
          <action application="callcenter" data="{queue_name}@default"/>"""

    if dest_type == "voicemail":
        return f"""          <action application="answer"/>
          <action application="voicemail" data="default ${{domain_name}} {xe(dest)}"/>"""

    if dest_type == "hangup":
        return '          <action application="hangup" data="CALL_REJECTED"/>'

    return '          <action application="hangup" data="UNALLOCATED_NUMBER"/>'


# ── CONFIGURATION (IVR menus) ─────────────────────────────────────────────────

async def _handle_configuration(form, db: AsyncSession) -> Response:
    """
    Return module configuration XML.
    Currently handles: ivr.conf (IVR menus).
    """
    key_value = form.get("key_value", "")

    if key_value == "ivr.conf":
        return await _config_ivr(db)

    return _resp(NOT_FOUND)


async def _config_ivr(db: AsyncSession) -> Response:
    """
    Return ivr.conf with all active IVR menus across all tenants.
    FreeSWITCH calls this when the `ivr` dialplan application runs.
    """
    result = await db.execute(
        select(IVR)
        .where(IVR.is_active == True)
        .options(selectinload(IVR.options))
    )
    ivrs = result.scalars().all()

    menus_xml = ""
    for ivr in ivrs:
        menu_name = xe(f"ivr_{ivr.id}")
        greeting = xe(ivr.greeting_text or "ivr/ivr-welcome.wav")
        timeout_ms = (ivr.timeout_seconds or 10) * 1000
        max_fail = ivr.max_retries or 3

        # Get tenant for domain
        tenant_result = await db.execute(select(Tenant).where(Tenant.id == ivr.tenant_id))
        tenant = tenant_result.scalar_one_or_none()
        domain = tenant.account_number if tenant else ""

        options_xml = ""
        for opt in sorted(ivr.options, key=lambda o: o.digit):
            action_param = _ivr_option_action(opt, domain)
            options_xml += f"""      <entry action="menu-exec-app" digits="{xe(opt.digit)}" param="{xe(action_param)}"/>\n"""

        menus_xml += f"""    <menu name="{menu_name}"
          greet-long="{greeting}"
          greet-short="{greeting}"
          invalid-sound="ivr/ivr-that_was_an_invalid_entry.wav"
          exit-sound="voicemail/vm-goodbye.wav"
          timeout="{timeout_ms}"
          max-failures="{max_fail}"
          max-timeouts="{max_fail}">
{options_xml}    </menu>\n"""

    xml = f"""{XML_HDR}
<document type="freeswitch/xml">
  <section name="configuration">
    <configuration name="ivr.conf" description="IVR menus">
      <menus>
{menus_xml}      </menus>
    </configuration>
  </section>
</document>"""
    return _resp(xml)


def _ivr_option_action(opt: "IVROption", domain: str) -> str:
    """Generate the FreeSWITCH menu entry param for an IVR option."""
    if opt.destination_type == "extension":
        bridge = _bridge(opt.destination, domain)
        return f"bridge {bridge}"
    if opt.destination_type == "ivr":
        return f"ivr ivr_{opt.destination}"
    if opt.destination_type == "voicemail":
        return f"voicemail default ${{domain_name}} {opt.destination}"
    if opt.destination_type == "queue":
        return f"callcenter {opt.destination}@default"
    return "hangup NORMAL_CLEARING"
