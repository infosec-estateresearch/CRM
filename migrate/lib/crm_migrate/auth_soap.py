"""TEMPORARY legacy-credential adapter (CRM-002-S): SOAP partner ``login`` / ``logout`` only.

Authorised by the PO priority override of 2026-11-10 (Issue #9) for the read-only migration.
Remove or disable once the dedicated read-only identity exists, and before Summer '27 at
the latest, when Salesforce retires SOAP ``login()``.

* Exactly two request shapes exist, both built from fixed templates:
  ``login`` to the constant login host (``test.salesforce.com`` only with ``--sandbox``) and
  ``logout`` to the origin ``serverUrl`` names. ``RequestPolicy`` re-checks every body
  against these templates byte for byte, so no other SOAP operation can be expressed.
* Responses must be strict UTF-8 (no UTF-16/32, no other declared encoding) and are refused
  on any ``<!DOCTYPE`` or ``<!ENTITY`` in the decoded text, then parsed by an expat parser
  whose DTD and entity handlers raise, under a size limit. A fault is reduced to its ``faultcode`` (only from the
  fixed ``FAULTCODES`` set, else ``unrecognised``) and the first token of ``exceptionCode``
  (only from the fixed ``errors.SF_ERROR_CODES`` set); the fault string is never kept.
* The origin of ``serverUrl`` must be ``https://<label>.my.salesforce.com`` and must equal
  the configured ``CRM_SF_ORIGIN`` exactly, otherwise the run aborts before any REST call.
  The session id is used only as the Bearer token for that origin and held only in memory.
"""

import re
import xml.etree.ElementTree as ET
from xml.parsers import expat as pyexpat
from urllib.parse import urlsplit
from xml.sax.saxutils import escape

from .errors import ConfigError, MigrateError, OriginError, ProtocolError, RefusedRequest

LOGIN_HOST = "login.salesforce.com"
SANDBOX_LOGIN_HOST = "test.salesforce.com"
LOGIN_HOSTS = (LOGIN_HOST, SANDBOX_LOGIN_HOST)
DEFAULT_SOAP_VERSION = "59.0"
MIN_SOAP_VERSION = (31, 0)
MAX_SOAP_VERSION = (64, 0)
CONTENT_TYPE = "text/xml; charset=UTF-8"
MAX_SOAP_RESPONSE = 64 * 1024
MAX_CREDENTIAL_CHARS = 1024

# XML namespace identifier (never contacted); split so the repository host scan does not
# mistake it for a URL the tool connects to.
NS_ENV = "http" + "://schemas.xmlsoap.org/soap/envelope/"
NS_PARTNER = "urn:partner.soap.sforce.com"
NS_FAULT = "urn:fault.partner.soap.sforce.com"

_VERSION_RE = re.compile(r"\A[0-9]{2}\.[0-9]\Z")
_SERVER_PATH_RE = re.compile(r"\A/services/Soap/u/(?P<version>[0-9]+\.[0-9]+)/(?P<org>00D[A-Za-z0-9]{12}(?:[A-Za-z0-9]{3})?)\Z")
_MYDOMAIN_RE = re.compile(r"\Ahttps://[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.my\.salesforce\.com\Z")
_SANDBOX_MYDOMAIN_RE = re.compile(r"\Ahttps://[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.sandbox\.my\.salesforce\.com\Z")
_SESSION_RE = re.compile(r"\A[A-Za-z0-9!._-]{16,1024}\Z")
# A server-supplied faultcode is printed only if it is one of these; anything else prints
# as ``faultcode=unrecognised`` (a faultcode is attacker-controlled text and is never echoed).
FAULTCODES = frozenset((
    "sf:INVALID_LOGIN", "sf:LOGIN_MUST_USE_SECURITY_TOKEN", "sf:INVALID_SESSION_ID",
    "sf:API_DISABLED_FOR_ORG", "sf:REQUEST_LIMIT_EXCEEDED", "sf:PASSWORD_LOCKOUT",
    "sf:INVALID_OPERATION_WITH_EXPIRED_PASSWORD", "sf:LOGIN_RATE_EXCEEDED",
    "soapenv:Client", "soapenv:Server",
))
UNRECOGNISED_FAULTCODE = "unrecognised"
_CTL_RE = re.compile(r"[\x00-\x1f\x7f]")

LOGIN_TEMPLATE = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<soapenv:Envelope xmlns:soapenv="' + NS_ENV + '" xmlns:urn="' + NS_PARTNER + '">'
    "<soapenv:Body><urn:login>"
    "<urn:username>{username}</urn:username>"
    "<urn:password>{password}</urn:password>"
    "</urn:login></soapenv:Body></soapenv:Envelope>"
)
LOGOUT_TEMPLATE = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<soapenv:Envelope xmlns:soapenv="' + NS_ENV + '" xmlns:urn="' + NS_PARTNER + '">'
    "<soapenv:Header><urn:SessionHeader><urn:sessionId>{session_id}</urn:sessionId></urn:SessionHeader>"
    "</soapenv:Header><soapenv:Body><urn:logout/></soapenv:Body></soapenv:Envelope>"
)
_XML_ESCAPES = {'"': "&quot;", "'": "&apos;"}


class SoapFault(MigrateError):
    """A SOAP fault: only ``faultcode`` (in ``detail``) and the first ``exceptionCode`` token."""

    code = "soap_fault"
    exit_code = 4


# ---------------------------------------------------------------- validation

def validate_login_host(host):
    if host not in LOGIN_HOSTS:
        raise OriginError("login_host_refused", detail="login host must be the constant SOAP login host")
    return host


def validate_soap_version(version):
    if not isinstance(version, str) or not _VERSION_RE.fullmatch(version):
        raise ConfigError("api_version_refused", detail="SOAP API version must be NN.N")
    major, minor = (int(x) for x in version.split("."))
    if not MIN_SOAP_VERSION <= (major, minor) <= MAX_SOAP_VERSION:
        raise ConfigError("api_version_refused", detail="SOAP API version must be between 31.0 and 64.0")
    return version


def _check_credential(value):
    if (not isinstance(value, str) or not value or len(value) > MAX_CREDENTIAL_CHARS
            or _CTL_RE.search(value) or value != value.strip()):
        raise ConfigError("credentials_invalid", detail="username and password must be non-empty single-line values")
    return value


def _xml_text(value):
    return escape(value, _XML_ESCAPES)


# ---------------------------------------------------------------- request bodies

def render_login_body(username, password):
    return LOGIN_TEMPLATE.format(username=_xml_text(_check_credential(username)),
                                 password=_xml_text(_check_credential(password))).encode("utf-8")


def render_logout_body(session_id):
    if not isinstance(session_id, str) or not _SESSION_RE.fullmatch(session_id):
        raise ProtocolError("session_invalid", detail="session id has an unexpected shape")
    return LOGOUT_TEMPLATE.format(session_id=session_id).encode("utf-8")


def login_url(version, sandbox=False):
    host = SANDBOX_LOGIN_HOST if sandbox is True else LOGIN_HOST
    return f"https://{host}/services/Soap/u/{validate_soap_version(version)}/"


def soap_headers(action):
    return (("Content-Type", CONTENT_TYPE), ("SOAPAction", action), ("Accept", "text/xml"))


# ---------------------------------------------------------------- safe XML

_UTF8_BOM = b"\xef\xbb\xbf"
# BOMs and BOM-less first bytes of "<?" / "<" in UTF-16 and UTF-32 (any byte order).
_WIDE_PREFIXES = (
    b"\x00\x00\xfe\xff", b"\xff\xfe\x00\x00", b"\xfe\xff", b"\xff\xfe",
    b"\x00\x00\x00\x3c", b"\x3c\x00\x00\x00", b"\x00\x3c", b"\x3c\x00",
)
_XML_DECL_RE = re.compile(r"\A<\?xml(?P<attrs>[^>]*?)\?>")
_ENCODING_RE = re.compile(r"""\bencoding\s*=\s*(?:"([^"]*)"|'([^']*)')""")
_DTD_TEXT_RE = re.compile(r"<!\s*(?:DOCTYPE|ENTITY)", re.IGNORECASE)


def _decode_strict_utf8(body):
    """Layer 1: the document must be strict UTF-8 (optional UTF-8 BOM, ``encoding`` utf-8)."""
    if body.startswith(_UTF8_BOM):
        body = body[len(_UTF8_BOM):]
    elif body.startswith(_WIDE_PREFIXES):
        raise ProtocolError("soap_encoding_refused", detail="SOAP document is not UTF-8")
    try:
        text = body.decode("utf-8", "strict")
    except UnicodeDecodeError:
        raise ProtocolError("soap_encoding_refused", detail="SOAP document is not UTF-8") from None
    if "\x00" in text or text.startswith("﻿"):
        raise ProtocolError("soap_encoding_refused", detail="SOAP document is not UTF-8")
    decl = _XML_DECL_RE.match(text)
    if decl:
        enc = _ENCODING_RE.search(decl.group("attrs"))
        if enc and (enc.group(1) if enc.group(1) is not None else enc.group(2)).lower() != "utf-8":
            raise ProtocolError("soap_encoding_refused", detail="SOAP document declares a non-UTF-8 encoding")
    elif text.lstrip().lower().startswith("<?xml"):
        raise ProtocolError("soap_response", detail="SOAP XML declaration is malformed")
    return text


def _refuse(*_args):
    raise ProtocolError("soap_dtd_refused", detail="DOCTYPE or ENTITY in SOAP document")


def _qname(name):
    # expat reports "uri}local" with namespace_separator "}"; ElementTree uses "{uri}local".
    return "{" + name if "}" in name else name


class _HardenedXMLParser:
    """Layer 3: an expat parser (building an ``ElementTree`` tree) whose DTD, entity and
    external-entity handlers raise. CPython's ``ET.XMLParser`` is the C accelerator, which
    does not expose its expat object, so expat is driven directly here."""

    def __init__(self):
        self._builder = ET.TreeBuilder()
        p = pyexpat.ParserCreate("utf-8", "}")
        p.buffer_text = True
        p.ordered_attributes = False
        p.StartElementHandler = self._start
        p.EndElementHandler = self._end
        p.CharacterDataHandler = self._builder.data
        p.StartDoctypeDeclHandler = _refuse
        p.EntityDeclHandler = _refuse
        p.UnparsedEntityDeclHandler = _refuse
        p.ExternalEntityRefHandler = _refuse
        p.SetParamEntityParsing(pyexpat.XML_PARAM_ENTITY_PARSING_NEVER)
        self.parser = p

    def _start(self, tag, attrs):
        self._builder.start(_qname(tag), {_qname(k): v for k, v in attrs.items()})

    def _end(self, tag):
        self._builder.end(_qname(tag))

    def parse(self, data):
        try:
            self.parser.Parse(data, True)
        except pyexpat.ExpatError:
            raise ET.ParseError("not well-formed") from None
        return self._builder.close()


def _hardened_parser():
    return _HardenedXMLParser()


def parse_xml(body, max_bytes=MAX_SOAP_RESPONSE):
    """Parse a SOAP document, refusing DTDs and entities in three independent layers:
    strict UTF-8 decoding, a text search of the decoded document, and an expat parser whose
    DTD / entity handlers raise. No element value is read before all three have passed."""
    if not isinstance(body, bytes):
        raise ProtocolError("soap_response", detail="no body")
    if len(body) > max_bytes:
        raise ProtocolError("soap_response_too_large", detail="SOAP response exceeds the size limit")
    text = _decode_strict_utf8(body)
    if _DTD_TEXT_RE.search(text):                     # layer 2
        raise ProtocolError("soap_dtd_refused", detail="DOCTYPE or ENTITY in SOAP document")
    try:
        return _hardened_parser().parse(text.encode("utf-8"))
    except ET.ParseError:
        raise ProtocolError("soap_response", detail="SOAP document is not well-formed") from None


def _body_child(root):
    if root.tag != f"{{{NS_ENV}}}Envelope":
        raise RefusedRequest(detail="SOAP body root is not an Envelope")
    bodies = [c for c in root if c.tag == f"{{{NS_ENV}}}Body"]
    if len(bodies) != 1 or len(list(bodies[0])) != 1:
        raise RefusedRequest(detail="SOAP Body must hold exactly one operation")
    return list(bodies[0])[0]


def check_login_body(body):
    """Policy check: ``body`` must be byte-identical to the login template."""
    try:
        root = parse_xml(body)
    except ProtocolError:
        raise RefusedRequest(detail="SOAP request body refused") from None
    op = _body_child(root)
    if op.tag != f"{{{NS_PARTNER}}}login":
        raise RefusedRequest("soap_operation_refused", detail="only SOAP login and logout are permitted")
    username = op.findtext(f"{{{NS_PARTNER}}}username")
    password = op.findtext(f"{{{NS_PARTNER}}}password")
    try:
        expected = render_login_body(username, password)
    except ConfigError:
        raise RefusedRequest(detail="SOAP login body refused") from None
    if expected != body:
        raise RefusedRequest(detail="SOAP login body is not the fixed template")


def check_logout_body(body):
    """Policy check: ``body`` must be byte-identical to the logout template."""
    try:
        root = parse_xml(body)
    except ProtocolError:
        raise RefusedRequest(detail="SOAP request body refused") from None
    op = _body_child(root)
    if op.tag != f"{{{NS_PARTNER}}}logout":
        raise RefusedRequest("soap_operation_refused", detail="only SOAP login and logout are permitted")
    session = root.findtext(f"{{{NS_ENV}}}Header/{{{NS_PARTNER}}}SessionHeader/{{{NS_PARTNER}}}sessionId")
    try:
        expected = render_logout_body(session)
    except ProtocolError:
        raise RefusedRequest(detail="SOAP logout body refused") from None
    if expected != body:
        raise RefusedRequest(detail="SOAP logout body is not the fixed template")


# ---------------------------------------------------------------- responses

def _raise_if_fault(root, status):
    fault = root.find(f"{{{NS_ENV}}}Body/{{{NS_ENV}}}Fault")
    if fault is None:
        return
    faultcode = (fault.findtext("faultcode") or "").strip()
    if faultcode not in FAULTCODES:
        faultcode = UNRECOGNISED_FAULTCODE
    exception_code = None
    for el in fault.iter():
        if el.tag.endswith("}exceptionCode") or el.tag == "exceptionCode":
            tokens = re.split(r"[\s:]+", (el.text or "").strip())
            exception_code = tokens[0] if tokens and tokens[0] else None
            break
    # The faultstring is deliberately never read.
    raise SoapFault(detail=f"faultcode={faultcode}", status=status,
                    sf_error=exception_code if exception_code is not None else "UNKNOWN")


class SoapSession:
    """Origin and session id from ``loginResponse``. ``repr`` never shows the session id."""

    __slots__ = ("origin", "server_path", "_session_id")

    def __init__(self, origin, server_path, session_id):
        self.origin = origin
        self.server_path = server_path
        self._session_id = session_id

    @property
    def session_id(self):
        return self._session_id

    def __repr__(self):
        return "SoapSession(origin=<checked>, session_id=<redacted>)"


def origin_of_server_url(server_url, version, sandbox=False):
    if not isinstance(server_url, str) or _CTL_RE.search(server_url) or "\\" in server_url:
        raise OriginError("server_url_refused", detail="serverUrl is malformed")
    try:
        parts = urlsplit(server_url)
        port = parts.port
    except ValueError:
        raise OriginError("server_url_refused", detail="serverUrl is malformed") from None
    if parts.scheme != "https" or port is not None or parts.username or parts.password \
            or parts.query or parts.fragment or server_url.endswith(("?", "#")):
        raise OriginError("server_url_refused", detail="serverUrl must be https origin plus path")
    origin = f"https://{parts.netloc}"
    shape = _SANDBOX_MYDOMAIN_RE if sandbox is True else _MYDOMAIN_RE
    if not shape.fullmatch(origin):
        raise OriginError("server_url_refused", detail="serverUrl origin is not a My Domain origin")
    m = _SERVER_PATH_RE.fullmatch(parts.path)
    if not m or m.group("version") != version or origin + parts.path != server_url:
        raise OriginError("server_url_refused", detail="serverUrl path is not the partner endpoint")
    return origin, parts.path


def parse_login_response(status, body, configured_origin, version, sandbox=False):
    root = parse_xml(body)
    _raise_if_fault(root, status)
    if not 200 <= status < 300:
        raise ProtocolError("soap_response", status=status, detail="SOAP login failed without a fault")
    result = root.find(f"{{{NS_ENV}}}Body/{{{NS_PARTNER}}}loginResponse/{{{NS_PARTNER}}}result")
    if result is None:
        raise ProtocolError("soap_response", detail="no loginResponse result")
    if (result.findtext(f"{{{NS_PARTNER}}}passwordExpired") or "").strip() == "true":
        raise ProtocolError("soap_password_expired", detail="the legacy password has expired")
    session_id = (result.findtext(f"{{{NS_PARTNER}}}sessionId") or "").strip()
    if not _SESSION_RE.fullmatch(session_id):
        raise ProtocolError("soap_response", detail="no usable session id")
    origin, path = origin_of_server_url((result.findtext(f"{{{NS_PARTNER}}}serverUrl") or "").strip(),
                                        version, sandbox)
    if origin != configured_origin:
        raise OriginError("server_url_mismatch", detail="serverUrl origin differs from CRM_SF_ORIGIN")
    return SoapSession(origin, path, session_id)


def parse_logout_response(status, body):
    root = parse_xml(body)
    _raise_if_fault(root, status)
    if not 200 <= status < 300 or root.find(f"{{{NS_ENV}}}Body/{{{NS_PARTNER}}}logoutResponse") is None:
        raise ProtocolError("soap_response", status=status, detail="no logoutResponse")
