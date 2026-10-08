from __future__ import annotations

from typing import ClassVar

import pydantic
from pydantic import BaseModel


class PrimitiveTypes:
    LONG_INTEGER = 'LongInteger'
    INTEGER = 'Integer'
    FLOAT = 'Float'
    DOUBLE = 'Double'
    STRING = 'String'
    BOOLEAN = 'Boolean'
    DATETIME = 'Datetime'
    DATE = 'Date'
    JSON = 'Json'
    ALL: ClassVar[list[str]] = [LONG_INTEGER, INTEGER, FLOAT, DOUBLE, STRING, BOOLEAN, DATETIME, DATE, JSON]


class FieldSources:
    REQUEST = 'request'
    QUERY_PARAMETERS = 'query-parameters'


class ResponseTypes:
    JSON = 'json'
    STREAM = 'stream'
    REDIRECT = 'redirect'


class ComplexTypes:
    MAPPING = 'Mapping'
    ALL: ClassVar[list[str]] = [MAPPING]


class Attribute(BaseModel):
    name: str
    fieldType: str = pydantic.Field(alias='type')
    listValueTypes: list[str] = []
    mappingKeyType: str | None = None
    mappingValueTypes: list[str] = []
    isPrimary: bool = False
    isUnique: bool = False
    shouldDisableGetEndpoint: bool = False
    isUnfilterable: bool = False
    isUpdatable: bool = False
    isNullable: bool = False
    isDeprecated: bool = False
    isSettable: bool = False
    isAccessibleIndependently: bool = False
    defaultValue: str | int | float | bool | None = None


class ResponseField(BaseModel):
    name: str
    fieldType: str = pydantic.Field(alias='type')
    listValueTypes: list[str] = []
    mappingKeyType: str | None = None
    mappingValueTypes: list[str] = []
    isNullable: bool = False
    isList: bool = False


class RequestField(BaseModel):
    name: str
    fieldType: str = pydantic.Field(alias='type')
    listValueTypes: list[str] = []
    mappingKeyType: str | None = None
    mappingValueTypes: list[str] = []
    isRequired: bool = False
    isDeprecated: bool = False
    defaultValue: str | int | float | bool | None = None
    maxValue: str | int | float | None = None
    minValue: str | int | float | None = None
    source: str = FieldSources.REQUEST


class BaseTransition(BaseModel):
    action: str
    method: str | None = None
    responseField: ResponseField | None = None
    requestFields: list[RequestField] = []
    authentication: str | None = None
    responseType: str = ResponseTypes.JSON


class Transition(BaseTransition):
    operatesOn: str | None = None
    isIndirectAction: bool = False


class RootTransition(BaseTransition):
    pass


class Resource(BaseModel):
    singleName: str
    collectionName: str
    parentResource: str | None = None
    attributes: list[Attribute] = []
    transitions: list[Transition] = []
    accessibleFrom: list[str] = []

    @property
    def primaryAttribute(self) -> Attribute | None:  # noqa: N802
        return next(iter([attribute for attribute in self.attributes if attribute.isPrimary]), None)


class ExceptionField(BaseModel):
    name: str
    fieldType: str = pydantic.Field(alias='type')
    listValueTypes: list[str] = []
    isRequired: bool = False
    isNullable: bool = False
    defaultValue: str | int | float | bool | None = None


class ApiException(BaseModel):
    name: str
    message: str | None = None
    extends: str | None = None
    statusCode: int | None = None
    fields: list[ExceptionField] = []


class Version(BaseModel):
    major: str
    minor: str
    patch: str


class KibaApi(BaseModel):
    version: str
    serviceName: str
    pythonClientPackageName: str
    typescriptClientPackageName: str
    resources: list[Resource] = []
    transitions: list[RootTransition] = []
    exceptions: list[ApiException] = []
    defaultAuthentication: str | None = None

    @property
    def versionObject(self) -> Version:  # noqa: N802
        parts = self.version.split('.')
        return Version(major=parts[0], minor=parts[1], patch=parts[2])
