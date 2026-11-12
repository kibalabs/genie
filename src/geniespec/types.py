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
    UUID = 'Uuid'
    BIG_INT = 'BigInt'
    BOOLEAN = 'Boolean'
    DATETIME = 'Datetime'
    DATE = 'Date'
    JSON = 'Json'
    ALL: ClassVar[list[str]] = [LONG_INTEGER, INTEGER, FLOAT, DOUBLE, STRING, UUID, BIG_INT, BOOLEAN, DATETIME, DATE, JSON]


class FieldSources:
    REQUEST = 'request'
    QUERY_PARAMETERS = 'query-parameters'


class ResponseTypes:
    JSON = 'json'
    STREAM = 'stream'
    REDIRECT = 'redirect'


class RateLimitKeys:
    USER = 'user'
    IP = 'ip'


class ApiRateLimit(BaseModel):
    name: str
    perMinute: int | None = None
    perFiveMinutes: int | None = None
    perHour: int | None = None
    perDay: int | None = None
    keyBy: str = RateLimitKeys.USER


class ComplexTypes:
    MAPPING = 'Mapping'
    ALL: ClassVar[list[str]] = [MAPPING]


class SpecialTypes:
    LIST = 'List'
    ENUM = 'Enum'
    FILE = 'File'
    NULL = 'Null'


class ApiEnum(BaseModel):
    name: str
    values: list[str]


class ApiOneOf(BaseModel):
    name: str
    discriminator: str
    types: list[str]


class FieldConstraints(BaseModel):
    minValue: int | float | None = None
    maxValue: int | float | None = None
    minLength: int | None = None
    maxLength: int | None = None
    pattern: str | None = None


class Attribute(FieldConstraints):
    name: str
    fieldType: str = pydantic.Field(alias='type')
    listValueTypes: list[str] = []
    mappingKeyType: str | None = None
    mappingValueTypes: list[str] = []
    enumValues: list[str] = []
    isPrimary: bool = False
    isUnique: bool = False
    isUniqueInParent: bool = False
    shouldDisableGetEndpoint: bool = False
    isUnfilterable: bool = False
    isUpdatable: bool = False
    isNullable: bool = False
    isDeprecated: bool = False
    isSettable: bool = False
    isAccessibleIndependently: bool = False
    defaultValue: str | int | float | bool | None = None
    description: str | None = None


class ResponseField(BaseModel):
    name: str
    fieldType: str = pydantic.Field(alias='type')
    listValueTypes: list[str] = []
    mappingKeyType: str | None = None
    mappingValueTypes: list[str] = []
    enumValues: list[str] = []
    isNullable: bool = False
    isList: bool = False
    description: str | None = None


class RequestField(FieldConstraints):
    name: str
    fieldType: str = pydantic.Field(alias='type')
    listValueTypes: list[str] = []
    mappingKeyType: str | None = None
    mappingValueTypes: list[str] = []
    enumValues: list[str] = []
    isRequired: bool = False
    isDeprecated: bool = False
    defaultValue: str | int | float | bool | None = None
    source: str = FieldSources.REQUEST
    description: str | None = None


class TransitionOverrides(BaseModel):
    responseFieldName: str | None = None


class BaseTransition(BaseModel):
    action: str
    method: str | None = None
    responseField: ResponseField | None = None
    requestFields: list[RequestField] = []
    authentication: str | None = None
    rateLimit: str | None = None
    responseType: str = ResponseTypes.JSON
    operationId: str | None = None
    summary: str | None = None
    description: str | None = None
    tags: list[str] = []
    extensions: dict[str, pydantic.JsonValue] = {}
    overrides: TransitionOverrides = TransitionOverrides()


class Transition(BaseTransition):
    operatesOn: str | None = None
    isIndirectAction: bool = False


class RootTransition(BaseTransition):
    pass


class ResourceOverrides(BaseModel):
    shouldPrefixParentName: bool = True


class Resource(BaseModel):
    singleName: str
    collectionName: str
    parentResource: str | None = None
    attributes: list[Attribute] = []
    transitions: list[Transition] = []
    accessibleFrom: list[str] = []
    overrides: ResourceOverrides = ResourceOverrides()

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
    enums: list[ApiEnum] = []
    oneOfs: list[ApiOneOf] = []
    defaultAuthentication: str | None = None
    rateLimits: list[ApiRateLimit] = []
    defaultRateLimit: str | None = None

    @property
    def versionObject(self) -> Version:  # noqa: N802
        parts = self.version.split('.')
        return Version(major=parts[0], minor=parts[1], patch=parts[2])
