# ruff: noqa: S101
import datetime
import json
import os
import pathlib
import subprocess
import typing

import pytest

from geniespec.cli import build
from geniespec.genie import SemanticValidationException
from tests.spec import write_spec

TYPESCRIPT_TOOLS_DIRECTORY = pathlib.Path(__file__).parent / 'node_modules'
TYPESCRIPT_CLIENT_SPEC = """
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
        isUpdatable: true
      - name: nickname
        type: String
        isNullable: true
        isSettable: true
        isUpdatable: true
      - name: birth-date
        type: Date
        isSettable: true
      - name: created-date
        type: Datetime
      - name: scores
        type: Mapping
        mappingKeyType: String
        mappingValueTypes:
          - Float
          - 'Null'
      - name: best-friend
        type: Friend
        isNullable: true
        isSettable: true
      - name: tags
        type: List
        listValueTypes:
          - String
    transitions:
      - action: LIST
        requestFields:
          - name: is-active
            type: Boolean
      - action: CREATE
      - action: UPDATE
      - action: DELETE
      - action: CHAT
        operatesOn: individual
        responseType: stream
        requestFields:
          - name: message
            type: String
            isRequired: true
        responseField:
          name: reply
          type: Friend
  - singleName: Friend
    collectionName: Friends
    attributes:
      - name: name
        type: String
      - name: met-date
        type: Datetime
transitions:
  - action: PAYMENT-LINK
    method: GET
    responseType: redirect
    requestFields:
      - name: invoice-no
        type: String
        isRequired: true
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
"""
TYPESCRIPT_CLIENT_SCRIPT = """
import { Requester, RestMethod } from '@kibalabs/core';

import { FriendV1, GenieTestApiV1Client, PersonV1 } from './genie-test-api/v1';

const personObject = {
  personId: 'p/1',
  name: 'Ann',
  nickname: null,
  birthDate: '2000-02-03',
  createdDate: '2024-01-02T03:04:05.000Z',
  scores: { maths: 1.5, art: null },
  bestFriend: { name: 'Bo', metDate: '2023-05-06T07:08:09.000Z' },
  tags: ['x'],
};
const calls: Record<string, unknown>[] = [];
const requester = {
  makeRequest: async (method: RestMethod, url: string, data?: Record<string, unknown>): Promise<{ content: string }> => {
    calls.push({ method, url, data: JSON.parse(JSON.stringify(data ?? null)) });
    const content = method === RestMethod.GET ? { people: [personObject] } : method === RestMethod.DELETE ? {} : { person: personObject };
    return { content: JSON.stringify(content) };
  },
  makeStreamingRequest: async (method: RestMethod, url: string, data: Record<string, unknown> | undefined, parseItem: (obj: Record<string, unknown>) => unknown, onItem: (item: unknown) => void): Promise<void> => {
    calls.push({ method, url, data: JSON.parse(JSON.stringify(data ?? null)) });
    [{ reply: { name: 'Cy', metDate: '2022-01-01T00:00:00.000Z' } }, { reply: { name: 'Di', metDate: '2021-01-01T00:00:00.000Z' } }].forEach((item) => onItem(parseItem(item)));
  },
} as unknown as Requester;

const client = new GenieTestApiV1Client(requester, 'https://api.test/v1');
const people = await client.listPeople({ isActive: false });
await client.listPeople();
await client.createPerson({ name: 'Ann', birthDate: new Date(2000, 1, 3), bestFriend: new FriendV1('Bo', new Date('2023-05-06T07:08:09.000Z')) });
const updatedPerson = await client.updatePerson('p/1', { nickname: null });
await client.deletePerson('p/1');
const replies: FriendV1[] = [];
await client.chatPerson('p/1', { message: 'hi' }, (reply: FriendV1): void => {
  replies.push(reply);
});
const person = people[0];
console.log(JSON.stringify({
  calls,
  person,
  isPersonParsed: person instanceof PersonV1 && person.createdDate instanceof Date && person.bestFriend instanceof FriendV1 && person.bestFriend.metDate instanceof Date,
  updatedNickname: updatedPerson.nickname,
  replies: replies.map((reply: FriendV1): unknown => ({ name: reply.name, isParsed: reply instanceof FriendV1 && reply.metDate instanceof Date })),
  methodNames: Object.keys(client).filter((key: string): boolean => typeof (client as unknown as Record<string, unknown>)[key] === 'function'),
}));
"""


def _run_typescript(specYaml: str, script: str, directory: pathlib.Path) -> typing.Any:  # type: ignore[explicit-any]
    outputDirectory = directory / 'out'
    build(specPath=write_spec(specYaml=specYaml, directory=directory), target='typescript-client', outputDirectoryPath=outputDirectory)
    (outputDirectory / 'node_modules').symlink_to(TYPESCRIPT_TOOLS_DIRECTORY, target_is_directory=True)
    (outputDirectory / 'package.json').write_text('{"type": "module"}')
    scriptPath = outputDirectory / 'script.ts'
    scriptPath.write_text(script)
    typeCheck = subprocess.run(  # noqa: S603
        [str(TYPESCRIPT_TOOLS_DIRECTORY / '.bin' / 'tsc'), '--noEmit', '--strict', '--skipLibCheck', '--target', 'ES2022', '--module', 'preserve', '--moduleResolution', 'bundler', str(scriptPath)], capture_output=True, text=True, check=False
    )
    assert typeCheck.returncode == 0, typeCheck.stdout
    result = subprocess.run([str(TYPESCRIPT_TOOLS_DIRECTORY / '.bin' / 'tsx'), str(scriptPath)], capture_output=True, text=True, check=True, cwd=outputDirectory, env={**os.environ, 'TZ': 'UTC'})  # noqa: S603
    return json.loads(result.stdout)


def _parse_datetime(value: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(value)


def test_typescript_client_type_checks_sends_requests_and_parses_responses(tmp_path: pathlib.Path) -> None:
    output = _run_typescript(specYaml=TYPESCRIPT_CLIENT_SPEC, script=TYPESCRIPT_CLIENT_SCRIPT, directory=tmp_path)
    calls = output['calls']
    createdBestFriend = calls[2]['data'].pop('bestFriend')
    assert calls == [
        {'method': 'get', 'url': 'https://api.test/v1/people', 'data': {'isActive': False}},
        {'method': 'get', 'url': 'https://api.test/v1/people', 'data': {}},
        {'method': 'post', 'url': 'https://api.test/v1/people', 'data': {'name': 'Ann', 'birthDate': '2000-02-03'}},
        {'method': 'patch', 'url': 'https://api.test/v1/people/p%2F1', 'data': {'nickname': None}},
        {'method': 'delete', 'url': 'https://api.test/v1/people/p%2F1', 'data': None},
        {'method': 'post', 'url': 'https://api.test/v1/people/p%2F1/chat', 'data': {'message': 'hi'}},
    ]
    assert createdBestFriend['name'] == 'Bo'
    assert _parse_datetime(createdBestFriend['metDate']) == datetime.datetime(2023, 5, 6, 7, 8, 9, tzinfo=datetime.UTC)
    assert output['person'] == {
        'personId': 'p/1',
        'name': 'Ann',
        'nickname': None,
        'birthDate': '2000-02-03T00:00:00.000Z',
        'createdDate': '2024-01-02T03:04:05.000Z',
        'scores': {'maths': 1.5, 'art': None},
        'bestFriend': {'name': 'Bo', 'metDate': '2023-05-06T07:08:09.000Z'},
        'tags': ['x'],
    }
    assert output['isPersonParsed']
    assert output['updatedNickname'] is None
    assert output['replies'] == [{'name': 'Cy', 'isParsed': True}, {'name': 'Di', 'isParsed': True}]
    assert set(output['methodNames']) - {'makeRequest', 'makeStreamingRequest'} == {'listPeople', 'createPerson', 'updatePerson', 'deletePerson', 'chatPerson'}


def test_typescript_client_rejects_names_reserved_in_typescript(tmp_path: pathlib.Path) -> None:
    specYaml = """
resources:
  - singleName: Setting
    collectionName: Settings
    attributes:
      - name: setting-id
        type: String
        isPrimary: true
      - name: default
        type: String
    transitions:
      - action: GET
"""
    build(specPath=write_spec(specYaml=specYaml, directory=tmp_path), target='python-server', outputDirectoryPath=tmp_path / 'python')
    with pytest.raises(SemanticValidationException, match='"default" is not a valid TypeScript name'):
        build(specPath=write_spec(specYaml=specYaml, directory=tmp_path), target='typescript-client', outputDirectoryPath=tmp_path / 'typescript')
