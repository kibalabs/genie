# ruff: noqa: S101
import collections.abc
import importlib
import inspect
import json
import pathlib
import sys
import types
import typing

import pydantic
import pytest
import yaml  # type: ignore[import-untyped]
from core.api.api_request import KibaApiRequest
from core.exceptions import BadRequestException
from core.exceptions import FoundRedirectException
from core.util.typing_util import UNDEFINED
from starlette.applications import Starlette
from starlette.testclient import TestClient

from geniespec.cli import build
from geniespec.cli import watch
from geniespec.genie import Renderer
from geniespec.genie import SemanticValidationException
from geniespec.genie import SyntacticValidationException
from geniespec.languages import PythonLanguageDefinition
from geniespec.types import KibaApi

PACKAGE_NAME = 'genie_test_api'
BASE_SPEC = """
version: 1.0.0
serviceName: genie-test
pythonClientPackageName: genie-test
typescriptClientPackageName: genie-test
defaultAuthentication: none
"""


def _write_spec(specYaml: str, directory: pathlib.Path) -> pathlib.Path:
    specPath = directory / 'api.yaml'
    specPath.write_text(yaml.safe_dump({**yaml.safe_load(BASE_SPEC), **yaml.safe_load(specYaml)}))
    return specPath


def _render(specYaml: str, outputDirectory: pathlib.Path) -> list[pathlib.Path]:
    return build(specPath=_write_spec(specYaml=specYaml, directory=outputDirectory), target='python-server', outputDirectoryPath=outputDirectory / 'out')


def _generate(specYaml: str, outputDirectory: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _render(specYaml=specYaml, outputDirectory=outputDirectory)
    monkeypatch.syspath_prepend(str(outputDirectory / 'out'))
    for moduleName in [name for name in sys.modules if name.split('.')[0] == PACKAGE_NAME]:
        monkeypatch.delitem(sys.modules, moduleName)


def _module(name: str) -> types.ModuleType:
    return importlib.import_module(f'{PACKAGE_NAME}.v1.{name}')


class _AuthResolver:
    def __init__(self) -> None:
        self.policies: list[str] = []

    async def authorize_route(self, *, auth: str, request: KibaApiRequest[pydantic.BaseModel]) -> None:  # noqa: ARG002
        self.policies.append(auth)

    def get_route_security_schemes(self, *, auth: str) -> list[str]:  # noqa: ARG002
        return []


def _client(calls: dict[str, dict[str, object]], returnValues: dict[str, object], authResolver: _AuthResolver | None = None) -> TestClient:
    internalClass = _module('internal').GenieTestApiV1Internal

    def implementation(methodName: str) -> object:
        if not inspect.iscoroutinefunction(getattr(internalClass, methodName)):

            async def stream(_self: object, **kwargs: object) -> collections.abc.AsyncIterator[object]:
                calls[methodName] = kwargs
                for item in typing.cast(list[object], returnValues.get(methodName, [])):
                    yield item

            return stream

        async def method(_self: object, **kwargs: object) -> object:
            calls[methodName] = kwargs
            return returnValues.get(methodName)

        return method

    internal = type('FakeInternal', (internalClass,), {name: implementation(methodName=name) for name in internalClass.__abstractmethods__})()
    return TestClient(Starlette(routes=_module('api').create_routes(internal=internal, authResolver=authResolver or _AuthResolver())))


def test_static_path_segments_match_before_path_parameters(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _generate(
        specYaml="""
resources:
  - singleName: Note
    collectionName: Notes
    parentResource: Person
    attributes:
      - name: person-note-id
        type: String
        isPrimary: true
    transitions:
      - action: LIST
  - singleName: Person
    collectionName: People
    attributes:
      - name: person-id
        type: String
        isPrimary: true
      - name: email
        type: String
        isUnique: true
    transitions:
      - action: GET
""",
        outputDirectory=tmp_path,
        monkeypatch=monkeypatch,
    )
    calls: dict[str, dict[str, object]] = {}
    client = _client(calls=calls, returnValues={'get_person_by_email_v1': _module('resources').PersonV1(personId='p1', email='notes')})
    response = client.get('/people/email/notes')
    assert response.json() == {'person': {'personId': 'p1', 'email': 'notes'}}
    assert calls == {'get_person_by_email_v1': {'email': 'notes'}}


def test_string_defaults_fill_omitted_fields(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _generate(
        specYaml="""
transitions:
  - action: SEARCH
    requestFields:
      - name: sort
        type: String
        defaultValue: recent
""",
        outputDirectory=tmp_path,
        monkeypatch=monkeypatch,
    )
    calls: dict[str, dict[str, object]] = {}
    client = _client(calls=calls, returnValues={})
    client.post('/search', json={})
    defaultSort = calls['search_v1']['sort']
    client.post('/search', json={'sort': 'oldest'})
    assert (defaultSort, calls['search_v1']['sort']) == ('recent', 'oldest')


def test_bounds_clamp_values_and_skip_omitted_fields(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _generate(
        specYaml="""
transitions:
  - action: SEARCH
    requestFields:
      - name: limit
        type: Integer
        minValue: 1
        maxValue: 100
""",
        outputDirectory=tmp_path,
        monkeypatch=monkeypatch,
    )
    calls: dict[str, dict[str, object]] = {}
    client = _client(calls=calls, returnValues={})
    receivedLimits = []
    for body in ({}, {'limit': 1000}, {'limit': 0}, {'limit': 5}):
        client.post('/search', json=body)
        receivedLimits.append(calls['search_v1']['limit'])
    assert receivedLimits == [None, 100, 1, 5]


def test_mapping_types_work_in_parameters_requests_and_responses(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _generate(
        specYaml="""
resources:
  - singleName: Survey
    collectionName: Surveys
    attributes:
      - name: survey-id
        type: String
        isPrimary: true
      - name: answers
        type: Mapping
        mappingKeyType: String
        mappingValueTypes:
          - Integer
        isSettable: true
    transitions:
      - action: CREATE
transitions:
  - action: SCORE
    requestFields:
      - name: weights
        type: Mapping
        mappingKeyType: String
        mappingValueTypes:
          - Float
        isRequired: true
    responseField:
      name: scores
      type: Mapping
      mappingKeyType: String
      mappingValueTypes:
        - Float
        - 'Null'
""",
        outputDirectory=tmp_path,
        monkeypatch=monkeypatch,
    )
    calls: dict[str, dict[str, object]] = {}
    survey = _module('resources').SurveyV1(surveyId='s1', answers={'q1': 3})
    client = _client(calls=calls, returnValues={'create_survey_v1': survey, 'score_v1': {'q1': 1.5, 'q2': None}})
    surveyResponse = client.post('/surveys', json={'answers': {'q1': 3}})
    scoreResponse = client.post('/score', json={'weights': {'q1': 0.5}})
    assert calls == {'create_survey_v1': {'answers': {'q1': 3}}, 'score_v1': {'weights': {'q1': 0.5}}}
    assert surveyResponse.json() == {'survey': {'surveyId': 's1', 'answers': {'q1': 3}}}
    assert scoreResponse.json() == {'scores': {'q1': 1.5, 'q2': None}}


def test_json_values_round_trip_in_resources_requests_responses_and_exceptions(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _generate(
        specYaml="""
resources:
  - singleName: Event
    collectionName: Events
    attributes:
      - name: event-id
        type: String
        isPrimary: true
      - name: payload
        type: Json
        isSettable: true
      - name: details
        type: Mapping
        isNullable: true
        mappingKeyType: String
        mappingValueTypes:
          - Json
      - name: items
        type: List
        listValueTypes:
          - Json
    transitions:
      - action: CREATE
exceptions:
  - name: EventRejectedException
    statusCode: 400
    fields:
      - name: payload
        type: Json
""",
        outputDirectory=tmp_path,
        monkeypatch=monkeypatch,
    )
    resources = _module('resources')
    payload = {'a': [1, 2.5, {'b': None}], 'c': 'd', 'e': True}
    event = resources.EventV1(eventId='e1', payload=payload, details={'k': payload}, items=[payload, 3, None])
    calls: dict[str, dict[str, object]] = {}
    response = _client(calls=calls, returnValues={'create_event_v1': event}).post('/events', json={'payload': payload})
    assert calls == {'create_event_v1': {'payload': payload}}
    assert response.json() == {'event': {'eventId': 'e1', 'payload': payload, 'details': {'k': payload}, 'items': [payload, 3, None]}}
    assert _module('exceptions').EventRejectedExceptionV1(payload=payload, message='rejected').to_dict()['fields'] == {'payload': payload}
    with pytest.raises(pydantic.ValidationError):
        resources.EventV1(eventId='e1', payload={'a': object()}, details=None, items=[])


def test_stream_transitions_yield_one_json_line_per_item(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _generate(
        specYaml="""
resources:
  - singleName: ChatEvent
    collectionName: ChatEvents
    attributes:
      - name: text
        type: String
transitions:
  - action: CHAT
    responseType: stream
    requestFields:
      - name: message
        type: String
        isRequired: true
    responseField:
      name: event
      type: ChatEvent
""",
        outputDirectory=tmp_path,
        monkeypatch=monkeypatch,
    )
    resources = _module('resources')
    calls: dict[str, dict[str, object]] = {}
    client = _client(calls=calls, returnValues={'chat_v1': [resources.ChatEventV1(text='a'), resources.ChatEventV1(text='b')]})
    response = client.post('/chat', json={'message': 'hi'})
    assert [json.loads(line) for line in response.text.splitlines()] == [{'event': {'text': 'a'}}, {'event': {'text': 'b'}}]
    assert calls == {'chat_v1': {'message': 'hi'}}


def test_redirect_transitions_redirect_to_the_returned_location(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _generate(
        specYaml="""
transitions:
  - action: PAYMENT-LINK
    method: GET
    responseType: redirect
    requestFields:
      - name: invoice-no
        type: String
        isRequired: true
""",
        outputDirectory=tmp_path,
        monkeypatch=monkeypatch,
    )
    calls: dict[str, dict[str, object]] = {}
    client = _client(calls=calls, returnValues={'get_payment_link_v1': 'https://pay.example/1'})
    with pytest.raises(FoundRedirectException) as raisedException:
        client.get('/payment-link?invoiceNo=inv-1')
    assert raisedException.value.location == 'https://pay.example/1'
    assert calls == {'get_payment_link_v1': {'invoiceNo': 'inv-1'}}


def test_query_parameters_fields_receive_every_query_parameter(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _generate(
        specYaml="""
transitions:
  - action: WEBHOOK
    method: GET
    requestFields:
      - name: parameters
        type: Mapping
        mappingKeyType: String
        mappingValueTypes:
          - String
        isRequired: true
        source: query-parameters
""",
        outputDirectory=tmp_path,
        monkeypatch=monkeypatch,
    )
    calls: dict[str, dict[str, object]] = {}
    _client(calls=calls, returnValues={}).get('/webhook?ORDERID=o1&STATUS=9')
    assert calls == {'get_webhook_v1': {'parameters': {'ORDERID': 'o1', 'STATUS': '9'}}}
    assert set(_module('endpoints').GetWebhookRequest.model_fields) == set()


def test_long_integer_identifiers_are_read_from_the_path(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _generate(
        specYaml="""
resources:
  - singleName: Order
    collectionName: Orders
    attributes:
      - name: order-id
        type: LongInteger
        isPrimary: true
    transitions:
      - action: GET
""",
        outputDirectory=tmp_path,
        monkeypatch=monkeypatch,
    )
    calls: dict[str, dict[str, object]] = {}
    response = _client(calls=calls, returnValues={'get_order_v1': _module('resources').OrderV1(orderId=5)}).get('/orders/5')
    assert response.json() == {'order': {'orderId': 5}}
    assert calls == {'get_order_v1': {'orderId': 5}}


def test_get_actions_route_before_items_and_read_query_parameters(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _generate(
        specYaml="""
resources:
  - singleName: Thing
    collectionName: Things
    attributes:
      - name: thing-id
        type: String
        isPrimary: true
    transitions:
      - action: GET
      - action: LATEST
        method: GET
        operatesOn: collection
        responseField:
          name: thing
          type: Thing
transitions:
  - action: STATUS
    method: GET
    requestFields:
      - name: verbose
        type: Boolean
    responseField:
      name: is-healthy
      type: Boolean
""",
        outputDirectory=tmp_path,
        monkeypatch=monkeypatch,
    )
    calls: dict[str, dict[str, object]] = {}
    resources = _module('resources')
    client = _client(calls=calls, returnValues={'get_latest_thing_v1': resources.ThingV1(thingId='t-latest'), 'get_thing_v1': resources.ThingV1(thingId='t1'), 'get_status_v1': True})
    responses = [client.get(path).json() for path in ('/things/latest', '/things/t1', '/status?verbose=true')]
    assert responses == [{'thing': {'thingId': 't-latest'}}, {'thing': {'thingId': 't1'}}, {'isHealthy': True}]
    assert calls == {'get_latest_thing_v1': {}, 'get_thing_v1': {'thingId': 't1'}, 'get_status_v1': {'verbose': True}}


def test_operation_names_follow_the_naming_rule() -> None:
    spec = {
        **yaml.safe_load(BASE_SPEC),
        **yaml.safe_load("""
resources:
  - singleName: Person
    collectionName: People
    attributes:
      - name: person-id
        type: String
        isPrimary: true
      - name: email
        type: String
        isUnique: true
    transitions:
      - action: LIST
      - action: GET
  - singleName: Profile
    collectionName: Profiles
    parentResource: Person
    attributes:
      - name: person-id
        type: String
        isPrimary: true
    transitions:
      - action: GET
  - singleName: Member
    collectionName: Members
    attributes:
      - name: member-id
        type: String
        isPrimary: true
  - singleName: Cycle
    collectionName: Cycles
    parentResource: Member
    attributes:
      - name: member-cycle-id
        type: String
        isPrimary: true
    transitions:
      - action: LIST
      - action: GET
      - action: CREATE
      - action: ARCHIVE
        operatesOn: individual
      - action: GENERATE-REPORT
        operatesOn: individual
        isIndirectAction: true
      - action: LATEST
        method: GET
        operatesOn: collection
        responseField:
          name: member-cycle
          type: MemberCycle
      - action: REVOKE
        operatesOn: collection
      - action: CREATE-UPLOAD
        operatesOn: collection
        isIndirectAction: true
  - singleName: PostCycleUpdate
    collectionName: PostCycleUpdates
    parentResource: MemberCycle
    attributes:
      - name: member-cycle-post-cycle-update-id
        type: String
        isPrimary: true
    transitions:
      - action: LIST
  - singleName: Booking
    collectionName: Bookings
    parentResource: Member
    accessibleFrom:
      - root
    attributes:
      - name: member-booking-id
        type: String
        isPrimary: true
    transitions:
      - action: LIST
      - action: GET
  - singleName: Note
    collectionName: Notes
    parentResource: MemberBooking
    accessibleFrom:
      - Member
    attributes:
      - name: member-booking-note-id
        type: String
        isPrimary: true
    transitions:
      - action: LIST
  - singleName: Chat
    collectionName: Chats
    parentResource: Member
    attributes:
      - name: member-chat-id
        type: String
        isPrimary: true
  - singleName: Message
    collectionName: Messages
    parentResource: MemberChat
    attributes:
      - name: member-chat-message-id
        type: String
        isPrimary: true
    transitions:
      - action: LIST
  - singleName: Thread
    collectionName: Threads
    attributes:
      - name: thread-id
        type: String
        isPrimary: true
    transitions:
      - action: CREATE-READ-URL
        operatesOn: individual
        isIndirectAction: true
      - action: LATEST
        method: GET
        operatesOn: collection
        responseField:
          name: thread
          type: Thread
  - singleName: Message
    collectionName: Messages
    parentResource: Thread
    attributes:
      - name: thread-message-id
        type: String
        isPrimary: true
    transitions:
      - action: GET
transitions:
  - action: RELOAD-ALL-DATA
"""),
    }
    renderableApi = Renderer(target='python-server').build_renderable_api(api=KibaApi.model_validate(spec))
    language = PythonLanguageDefinition()
    names = {f'{language.http_method(operation=operation)} {language.endpoint(operation=operation)}': language.operation_name(operation=operation) for operation in renderableApi.operations}
    assert names == {
        'POST /reload-all-data': 'reload_all_data',
        'GET /people': 'list_people',
        'GET /people/{personId:str}': 'get_person',
        'GET /people/email/{email:str}': 'get_person_by_email',
        'GET /people/{personId:str}/profile': 'get_profile_for_person',
        'GET /members/{memberId:str}/cycles': 'list_cycles_for_member',
        'GET /members/{memberId:str}/cycles/{memberCycleId:str}': 'get_cycle_for_member',
        'POST /members/{memberId:str}/cycles': 'create_cycle_for_member',
        'POST /members/{memberId:str}/cycles/{memberCycleId:str}/archive': 'archive_cycle_for_member',
        'POST /members/{memberId:str}/cycles/{memberCycleId:str}/generate-report': 'generate_report_for_member_cycle',
        'GET /members/{memberId:str}/cycles/latest': 'get_latest_cycle_for_member',
        'POST /members/{memberId:str}/cycles/revoke': 'revoke_cycles_for_member',
        'POST /members/{memberId:str}/cycles/create-upload': 'create_upload_for_member_cycles',
        'GET /members/{memberId:str}/cycles/{memberCycleId:str}/post-cycle-updates': 'list_post_cycle_updates_for_member_cycle',
        'GET /member-bookings': 'list_member_bookings',
        'GET /member-bookings/{memberBookingId:str}': 'get_member_booking',
        'GET /members/{memberId:str}/bookings': 'list_bookings_for_member',
        'GET /members/{memberId:str}/bookings/{memberBookingId:str}': 'get_booking_for_member',
        'GET /members/{memberId:str}/bookings/{memberBookingId:str}/notes': 'list_notes_for_member_booking',
        'GET /members/{memberId:str}/booking-notes': 'list_booking_notes_for_member',
        'GET /members/{memberId:str}/chats/{memberChatId:str}/messages': 'list_messages_for_member_chat',
        'POST /threads/{threadId:str}/create-read-url': 'create_read_url_for_thread',
        'GET /threads/latest': 'get_latest_thread',
        'GET /threads/{threadId:str}/messages/{threadMessageId:str}': 'get_message_for_thread',
    }


def test_child_resources_are_named_with_their_parents_but_routed_with_their_own_names(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _generate(
        specYaml="""
resources:
  - singleName: Member
    collectionName: Members
    attributes:
      - name: member-id
        type: String
        isPrimary: true
  - singleName: Chat
    collectionName: Chats
    parentResource: Member
    accessibleFrom:
      - root
    attributes:
      - name: member-chat-id
        type: String
        isPrimary: true
    transitions:
      - action: LIST
  - singleName: Message
    collectionName: Messages
    parentResource: MemberChat
    attributes:
      - name: member-chat-message-id
        type: String
        isPrimary: true
    transitions:
      - action: LIST
  - singleName: Thread
    collectionName: Threads
    attributes:
      - name: thread-id
        type: String
        isPrimary: true
  - singleName: Message
    collectionName: Messages
    parentResource: Thread
    attributes:
      - name: thread-message-id
        type: String
        isPrimary: true
    transitions:
      - action: GET
""",
        outputDirectory=tmp_path,
        monkeypatch=monkeypatch,
    )
    resources = _module('resources')
    calls: dict[str, dict[str, object]] = {}
    client = _client(
        calls=calls,
        returnValues={
            'list_member_chats_v1': [],
            'list_chats_for_member_v1': [resources.MemberChatV1(memberChatId='c1')],
            'list_messages_for_member_chat_v1': [resources.MemberChatMessageV1(memberChatMessageId='x1')],
            'get_message_for_thread_v1': resources.ThreadMessageV1(threadMessageId='y1'),
        },
    )
    responses = [client.get(path).json() for path in ('/member-chats', '/members/m1/chats', '/members/m1/chats/c1/messages', '/threads/t1/messages/y1')]
    assert responses == [{'memberChats': []}, {'memberChats': [{'memberChatId': 'c1'}]}, {'memberChatMessages': [{'memberChatMessageId': 'x1'}]}, {'threadMessage': {'threadMessageId': 'y1'}}]
    assert calls == {
        'list_member_chats_v1': {},
        'list_chats_for_member_v1': {'memberId': 'm1'},
        'list_messages_for_member_chat_v1': {'memberId': 'm1', 'memberChatId': 'c1'},
        'get_message_for_thread_v1': {'threadId': 't1', 'threadMessageId': 'y1'},
    }


def test_nested_resource_types_work_in_any_declaration_order(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _generate(
        specYaml="""
resources:
  - singleName: Order
    collectionName: Orders
    attributes:
      - name: order-id
        type: String
        isPrimary: true
      - name: lines
        type: List
        listValueTypes:
          - OrderLine
      - name: first-line
        type: OrderLine
        isNullable: true
      - name: tags
        type: List
        listValueTypes:
          - String
        isNullable: true
    transitions:
      - action: GET
  - singleName: OrderLine
    collectionName: OrderLines
    attributes:
      - name: name
        type: String
""",
        outputDirectory=tmp_path,
        monkeypatch=monkeypatch,
    )
    resources = _module('resources')
    order = resources.OrderV1(orderId='o1', lines=[{'name': 'a'}], firstLine={'name': 'a'}, tags=None)
    response = _client(calls={}, returnValues={'get_order_v1': order}).get('/orders/o1')
    assert response.json() == {'order': {'orderId': 'o1', 'lines': [{'name': 'a'}], 'firstLine': {'name': 'a'}, 'tags': None}}
    with pytest.raises(pydantic.ValidationError):
        resources.OrderV1(orderId='o1', lines=[], firstLine=None, tags=[None])


def test_create_accepts_request_fields_alongside_settable_attributes(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _generate(
        specYaml="""
resources:
  - singleName: Note
    collectionName: Notes
    attributes:
      - name: note-id
        type: String
        isPrimary: true
      - name: text
        type: String
        isSettable: true
    transitions:
      - action: CREATE
        requestFields:
          - name: should-notify
            type: Boolean
            isRequired: true
          - name: notify-message
            type: String
          - name: is-urgent
            type: Boolean
            defaultValue: false
""",
        outputDirectory=tmp_path,
        monkeypatch=monkeypatch,
    )
    calls: dict[str, dict[str, object]] = {}
    client = _client(calls=calls, returnValues={'create_note_v1': _module('resources').NoteV1(noteId='n1', text='hi')})
    response = client.post('/notes', json={'text': 'hi', 'shouldNotify': True})
    assert response.json() == {'note': {'noteId': 'n1', 'text': 'hi'}}
    assert calls == {'create_note_v1': {'text': 'hi', 'shouldNotify': True, 'notifyMessage': None, 'isUrgent': False}}
    with pytest.raises(BadRequestException, match='shouldNotify: Field required'):
        client.post('/notes', json={'text': 'hi'})


def test_update_accepts_request_fields_alongside_updatable_attributes(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _generate(
        specYaml="""
resources:
  - singleName: Note
    collectionName: Notes
    attributes:
      - name: note-id
        type: String
        isPrimary: true
      - name: text
        type: String
        isUpdatable: true
    transitions:
      - action: UPDATE
        requestFields:
          - name: should-notify
            type: Boolean
            defaultValue: false
""",
        outputDirectory=tmp_path,
        monkeypatch=monkeypatch,
    )
    calls: dict[str, dict[str, object]] = {}
    client = _client(calls=calls, returnValues={'update_note_v1': _module('resources').NoteV1(noteId='n1', text='hi')})
    client.patch('/notes/n1', json={'shouldNotify': True})
    notifyOnlyCall = calls['update_note_v1']
    client.patch('/notes/n1', json={'text': 'hi'})
    assert notifyOnlyCall == {'noteId': 'n1', 'text': UNDEFINED, 'shouldNotify': True}
    assert calls['update_note_v1'] == {'noteId': 'n1', 'text': 'hi', 'shouldNotify': False}


def test_exceptions_with_and_without_fields_round_trip(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _generate(
        specYaml="""
exceptions:
  - name: OrderLockedException
    statusCode: 409
  - name: OrderLimitException
    statusCode: 400
    fields:
      - name: limit
        type: Integer
        isRequired: true
""",
        outputDirectory=tmp_path,
        monkeypatch=monkeypatch,
    )
    exceptions = _module('exceptions')
    lockedException = exceptions.OrderLockedExceptionV1(message='locked')
    limitException = exceptions.OrderLimitExceptionV1(limit=3, message='too many')
    roundTrippedException = exceptions.OrderLimitExceptionV1.from_dict(limitException.to_dict())
    assert (lockedException.statusCode, lockedException.to_dict()['fields']) == (409, {})
    assert limitException.to_dict()['fields'] == {'limit': 3}
    assert (roundTrippedException.limit, roundTrippedException.message) == (3, 'too many')


@pytest.mark.parametrize(
    ('specYaml', 'expectedErrors'),
    [
        pytest.param(
            """
transitions:
  - action: IMPORT
    requestFields:
      - name: class
        type: String
""",
            ['"import" is not a valid Python name', '"class" is not a valid Python name'],
            id='python-keywords',
        ),
        pytest.param(
            """
resources:
  - singleName: Person
    collectionName: People
    attributes:
      - name: person-id
        type: String
        isPrimary: true
      - name: email
        type: String
        isUnique: true
    transitions:
      - action: GET
  - singleName: PersonByEmail
    collectionName: PeopleByEmail
    attributes:
      - name: person-by-email-id
        type: String
        isPrimary: true
    transitions:
      - action: GET
""",
            ['Duplicate operation name get_person_by_email'],
            id='duplicate-operation-names',
        ),
        pytest.param(
            """
resources:
  - singleName: Person
    collectionName: People
    attributes:
      - name: person-id
        type: String
        isPrimary: true
      - name: name
        type: String
        isSettable: true
    transitions:
      - action: CREATE
transitions:
  - action: PEOPLE
""",
            ['Duplicate route: POST /people'],
            id='duplicate-routes',
        ),
        pytest.param(
            """
resources:
  - singleName: Tag
    collectionName: Tags
    attributes:
      - name: label
        type: String
    transitions:
      - action: LIST
      - action: GET
  - singleName: Person
    collectionName: People
    attributes:
      - name: person-id
        type: String
        isPrimary: true
    transitions:
      - action: GET
  - singleName: Profile
    collectionName: Profiles
    parentResource: Person
    attributes:
      - name: person-id
        type: String
        isPrimary: true
      - name: bio
        type: String
        isSettable: true
    transitions:
      - action: CREATE
""",
            ['Transitions with no endpoint: Tag GET, PersonProfile CREATE.'],
            id='transitions-without-endpoints',
        ),
        pytest.param(
            """
resources:
  - singleName: Thing
    collectionName: Things
    attributes:
      - name: thing-id
        type: String
        isPrimary: true
    transitions:
      - action: GET
        method: POST
""",
            ['Only custom transitions can set a method: GET'],
            id='method-on-standard-transition',
        ),
        pytest.param(
            """
resources:
  - singleName: Member
    collectionName: Members
    attributes:
      - name: member-id
        type: String
        isPrimary: true
  - singleName: Note
    collectionName: Notes
    parentResource: Member
    attributes:
      - name: member-note-id
        type: String
        isPrimary: true
    transitions:
      - action: LIST
      - action: GET
  - singleName: Reply
    collectionName: Replies
    parentResource: Note
    attributes:
      - name: reply-id
        type: String
        isPrimary: true
  - singleName: MemberNote
    collectionName: MemberNotes
    attributes:
      - name: member-note-id
        type: String
        isPrimary: true
""",
            ['Duplicate resource name: MemberNote', 'Unknown parent resource Note for Reply'],
            id='child-resource-naming',
        ),
        pytest.param(
            """
resources:
  - singleName: Thing
    collectionName: Things
    attributes:
      - name: thing-id
        type: String
        isPrimary: true
    transitions:
      - action: GET
        isIndirectAction: true
""",
            ['Only custom transitions can be indirect actions: GET'],
            id='indirect-action-on-standard-transition',
        ),
        pytest.param(
            """
resources:
  - singleName: Note
    collectionName: Notes
    attributes:
      - name: note-id
        type: String
        isPrimary: true
      - name: text
        type: String
        isSettable: true
    transitions:
      - action: CREATE
        requestFields:
          - name: text
            type: Integer
""",
            ['Duplicate parameter text on POST /notes'],
            id='create-request-field-duplicates-attribute',
        ),
        pytest.param(
            """
resources:
  - singleName: Note
    collectionName: Notes
    attributes:
      - name: note-id
        type: String
        isPrimary: true
      - name: text
        type: String
        isUpdatable: true
    transitions:
      - action: UPDATE
        requestFields:
          - name: text
            type: Integer
""",
            ['Duplicate parameter text on PATCH /notes/{noteId:str}'],
            id='update-request-field-duplicates-attribute',
        ),
        pytest.param(
            """
resources:
  - singleName: Member
    collectionName: Members
    attributes:
      - name: member-id
        type: String
        isPrimary: true
  - singleName: Note
    collectionName: Notes
    parentResource: Member
    accessibleFrom:
      - Member
    attributes:
      - name: member-note-id
        type: String
        isPrimary: true
    transitions:
      - action: LIST
  - singleName: Thing
    collectionName: Things
    accessibleFrom:
      - root
    attributes:
      - name: thing-id
        type: String
        isPrimary: true
    transitions:
      - action: LIST
""",
            ['MemberNote is already accessible from Member', 'Thing is already accessible from root'],
            id='accessible-from-existing-route',
        ),
        pytest.param(
            """
resources:
  - singleName: Member
    collectionName: Members
    attributes:
      - name: member-id
        type: String
        isPrimary: true
  - singleName: Team
    collectionName: Teams
    attributes:
      - name: team-id
        type: String
        isPrimary: true
  - singleName: Note
    collectionName: Notes
    parentResource: Member
    accessibleFrom:
      - Team
    attributes:
      - name: member-note-id
        type: String
        isPrimary: true
    transitions:
      - action: LIST
""",
            ['MemberNote can only be accessible from root or an ancestor, not Team'],
            id='accessible-from-non-ancestor',
        ),
        pytest.param(
            """
resources:
  - singleName: Member
    collectionName: Members
    attributes:
      - name: member-id
        type: String
        isPrimary: true
  - singleName: Note
    collectionName: Notes
    parentResource: Member
    attributes:
      - name: note-id
        type: String
        isPrimary: true
    transitions:
      - action: LIST
""",
            ['Primary attribute of MemberNote must be member-note-id, found note-id'],
            id='primary-attribute-without-full-name',
        ),
        pytest.param(
            """
resources:
  - singleName: Thing
    collectionName: Things
    attributes:
      - name: thing-id
        type: String
        isPrimary: true
    transitions:
      - action: LIST
        responseType: stream
""",
            ['Only custom transitions can set a responseType: LIST'],
            id='response-type-on-standard-transition',
        ),
        pytest.param(
            """
transitions:
  - action: TAIL
    responseType: stream
  - action: LINK
    responseType: redirect
    responseField:
      name: url
      type: String
  - action: WEBHOOK
    method: GET
    requestFields:
      - name: params
        type: String
        source: query-parameters
""",
            [
                'tail: stream transitions need a responseField',
                'link: redirect transitions cannot have a responseField',
                'webhook: query-parameters field params must be a Mapping of String to String',
            ],
            id='invalid-sources-and-response-types',
        ),
    ],
)
def test_rejects_specs_that_cannot_be_generated(specYaml: str, expectedErrors: list[str], tmp_path: pathlib.Path) -> None:
    with pytest.raises(SemanticValidationException) as raisedException:
        _render(specYaml=specYaml, outputDirectory=tmp_path)
    errorMessage = raisedException.value.message or ''
    for expectedError in expectedErrors:
        assert expectedError in errorMessage


def test_rejects_malformed_versions(tmp_path: pathlib.Path) -> None:
    with pytest.raises(SyntacticValidationException):
        _render(specYaml='version: 1x2x3', outputDirectory=tmp_path)


def test_builds_only_the_service_package_into_the_output_directory(tmp_path: pathlib.Path) -> None:
    outputDirectory = tmp_path / 'out'
    (outputDirectory / 'other_package').mkdir(parents=True)
    (outputDirectory / 'application.py').write_text('app = None\n')
    (outputDirectory / 'other_package' / 'module.py').write_text('value = 1\n')
    changedPaths = _render(specYaml='transitions: []', outputDirectory=tmp_path)
    assert all(path.relative_to(outputDirectory).parts[0] == PACKAGE_NAME for path in changedPaths)
    assert (outputDirectory / PACKAGE_NAME / 'v1' / 'api.py').is_file()
    assert (outputDirectory / 'application.py').read_text() == 'app = None\n'
    assert (outputDirectory / 'other_package' / 'module.py').read_text() == 'value = 1\n'


def test_rebuilds_only_rewrite_changed_files_and_remove_stale_ones(tmp_path: pathlib.Path) -> None:
    specYaml = """
transitions:
  - action: PING
"""
    packageDirectory = tmp_path / 'out' / PACKAGE_NAME
    _render(specYaml=specYaml, outputDirectory=tmp_path)
    (packageDirectory / 'stale.py').write_text('')
    (packageDirectory / '__pycache__').mkdir()
    (packageDirectory / '__pycache__' / 'cached.pyc').write_bytes(b'')
    assert _render(specYaml=specYaml, outputDirectory=tmp_path) == [packageDirectory / 'stale.py']
    assert not (packageDirectory / 'stale.py').exists()
    assert (packageDirectory / '__pycache__' / 'cached.pyc').exists()
    changedPaths = _render(specYaml=f'{specYaml}  - action: PONG\n', outputDirectory=tmp_path)
    assert set(changedPaths) == {packageDirectory / 'v1' / 'api.py', packageDirectory / 'v1' / 'endpoints.py', packageDirectory / 'v1' / 'internal.py'}


REBUILT_EXIT_CODE = 7
WATCH_COMMAND_SCRIPT = f"""
import pathlib
import sys
import time

import yaml

apiPath = pathlib.Path(sys.argv[1]) / 'genie_test_api' / 'v1' / 'api.py'
specPath = pathlib.Path(sys.argv[2])
if 'pong' in apiPath.read_text():
    sys.exit(2)
spec = yaml.safe_load(specPath.read_text())
spec['transitions'].append({{'action': 'PONG'}})
specPath.write_text(yaml.safe_dump(spec))
for _ in range(100):
    if 'pong' in apiPath.read_text():
        sys.exit({REBUILT_EXIT_CODE})
    time.sleep(0.1)
sys.exit(3)
"""


def test_watch_builds_before_running_the_command_rebuilds_while_it_runs_and_returns_its_exit_code(tmp_path: pathlib.Path) -> None:
    specPath = _write_spec(specYaml='transitions:\n  - action: PING\n', directory=tmp_path)
    outputDirectory = tmp_path / 'out'
    returnCode = watch(specPath=specPath, target='python-server', outputDirectoryPath=outputDirectory, command=[sys.executable, '-c', WATCH_COMMAND_SCRIPT, str(outputDirectory), str(specPath)])
    assert returnCode == REBUILT_EXIT_CODE
