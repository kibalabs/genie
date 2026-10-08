from __future__ import annotations

import re

from core.exceptions import KibaException
from pydantic import BaseModel

from geniespec.types import ComplexTypes
from geniespec.types import FieldSources
from geniespec.types import ResponseTypes
from geniespec.types import Version


class RenderableString(BaseModel):
    string: list[str]

    def __add__(self, other: RenderableString) -> RenderableString:
        return RenderableString(string=self.string + other.string)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, RenderableString) and self.lowerCaseString == other.lowerCaseString

    def __hash__(self) -> int:
        return hash(frozenset(self.string))

    @property
    def lowerCaseString(self) -> str:  # noqa: N802
        return ''.join([s.lower() for s in self.string])

    @property
    def upperCaseString(self) -> str:  # noqa: N802
        return ''.join([s.upper() for s in self.string])

    @property
    def pascalCaseString(self) -> str:  # noqa: N802
        return ''.join([s.lower().capitalize() for s in self.string])

    @property
    def camelCaseString(self) -> str:  # noqa: N802
        return self.string[0].lower() + ''.join([s.lower().capitalize() for s in self.string[1:]])

    @property
    def snakeCaseString(self) -> str:  # noqa: N802
        return '_'.join([s.lower() for s in self.string])

    @property
    def kebabCaseString(self) -> str:  # noqa: N802
        return '-'.join([s.lower() for s in self.string])

    @property
    def capitalizedKebabCaseString(self) -> str:  # noqa: N802
        return '-'.join([s.capitalize() for s in self.string])

    def join_string(self, separator: str) -> str:
        return separator.join(self.string)

    @property
    def endpointUrlString(self) -> str:  # noqa: N802
        return '/' + '/'.join([s.lower() for s in self.string])

    @classmethod
    def from_pascal_case_string(cls, string: str) -> RenderableString:
        return cls(string=re.sub('([A-Z][a-z]+)', r' \1', re.sub('([A-Z0-9])', r' \1', string)).split())

    @classmethod
    def from_camel_case_string(cls, string: str) -> RenderableString:
        return cls(string=re.sub('([a-z][A-Z]+)', r' \1', re.sub('([A-Z0-9])', r' \1', string)).split())

    @classmethod
    def from_snake_case_string(cls, string: str) -> RenderableString:
        return cls.from_separated_string(string=string, separator='_')

    @classmethod
    def from_kebab_case_string(cls, string: str) -> RenderableString:
        return cls.from_separated_string(string=string, separator='-')

    @classmethod
    def from_upper_case_string(cls, string: str) -> RenderableString:
        return cls(string=[string])

    @classmethod
    def from_lower_case_string(cls, string: str) -> RenderableString:
        return cls(string=[string])

    @classmethod
    def from_separated_string(cls, string: str, separator: str) -> RenderableString:
        return cls(string=string.split(separator))


class RenderableType(BaseModel):
    rawType: str
    isNullable: bool
    isList: bool = False
    className: RenderableString | None = None


class MappingRenderableType(RenderableType):
    keyType: RenderableType
    valueType: RenderableType
    rawType: str = ComplexTypes.MAPPING


class RenderableField(BaseModel):
    name: RenderableString
    fieldType: RenderableType
    defaultValue: str | int | float | bool | None = None


class RenderableAttribute(RenderableField):
    isUnique: bool = False
    isPrimary: bool = False
    isUpdatable: bool = False
    isNullable: bool = False
    isSettable: bool = False
    isAccessibleIndependently: bool = False
    shouldDisableGetEndpoint: bool = False


class RenderableResource(BaseModel):
    singleName: RenderableString
    collectionName: RenderableString
    parentResource: str | None = None
    attributes: list[RenderableAttribute]
    independentAttributes: list[RenderableAttribute] = []
    primaryAttribute: RenderableAttribute | None = None
    accessibleFrom: list[str] = []


class RenderableMethod(BaseModel):
    method: RenderableString


class RenderableEndpointComponent(BaseModel):
    pass


class AttributeEndpointComponent(RenderableEndpointComponent):
    attribute: RenderableAttribute | None
    resource: RenderableResource | None


class ActionEndpointComponent(RenderableEndpointComponent):
    actionName: RenderableString | None


class ResourceEndpointComponent(RenderableEndpointComponent):
    resource: RenderableResource
    attribute: RenderableAttribute | None
    relativeSingleName: RenderableString
    relativeCollectionName: RenderableString


class SingleResourceEndpointComponent(RenderableEndpointComponent):
    resource: RenderableResource
    relativeSingleName: RenderableString


class RenderableEndpoint(BaseModel):
    components: list[RenderableEndpointComponent]

    @property
    def lastComponent(self) -> RenderableEndpointComponent:  # noqa: N802
        if len(self.components) == 0:
            raise KibaException(message=f'RenderableEndpoint with no components found')
        return self.components[-1]

    @property
    def urlParameters(self) -> list[RenderableParameter]:  # noqa: N802
        return [
            RenderableParameter(name=component.attribute.name, fieldType=component.attribute.fieldType, isRequired=True, isDeprecated=False)
            for component in self.components
            if isinstance(component, ResourceEndpointComponent) and component.attribute is not None
        ]


class RenderableParameter(RenderableField):
    maxValue: float | int | bool | str | None = None
    minValue: float | int | bool | str | None = None
    isRequired: bool = False
    isDeprecated: bool = False
    source: str = FieldSources.REQUEST


class RenderableOperation(BaseModel):
    method: RenderableMethod
    endpoint: RenderableEndpoint
    query: list[RenderableParameter] | None
    body: list[RenderableParameter] | None
    responseFields: list[RenderableField] | None
    authentication: str | None
    isIndirectAction: bool = False
    responseType: str = ResponseTypes.JSON

    @property
    def urlParameters(self) -> list[RenderableParameter]:  # noqa: N802
        return self.endpoint.urlParameters

    @property
    def parameters(self) -> list[RenderableParameter]:
        deduplicatedParameters: list[RenderableParameter] = []
        parameterList = self.urlParameters + (self.body if self.body is not None else []) + (self.query if self.query is not None else [])
        for parameter in parameterList:
            if parameter not in deduplicatedParameters:
                deduplicatedParameters.append(parameter)
        deduplicatedParameters.sort(key=lambda deduplicatedParameter: (deduplicatedParameter.isRequired, deduplicatedParameter.defaultValue is None), reverse=True)
        return deduplicatedParameters


class ExceptionRenderableField(RenderableField):
    isRequired: bool = False


class RenderableException(BaseModel):
    name: RenderableString
    message: str | None
    statusCode: int | None
    fields: list[ExceptionRenderableField]


class RenderableApi(BaseModel):
    version: Version
    serviceName: RenderableString
    pythonClientPackageName: str
    typescriptClientPackageName: str
    resources: list[RenderableResource]
    operations: list[RenderableOperation]
    exceptions: list[RenderableException]


class ProcessableResource(BaseModel):
    class IndependentAttributeOccurrence(BaseModel):
        processableResource: ProcessableResource
        attribute: RenderableAttribute

    class Parent(BaseModel):
        processableResource: ProcessableResource
        isOneToOne: bool

    renderableResource: RenderableResource
    parent: Parent | None
    occursAsIndependentAttribute: list[IndependentAttributeOccurrence]


class EndpointContainer(BaseModel):
    individualEndpoints: list[RenderableEndpoint]
    collectionEndpoints: list[RenderableEndpoint]
