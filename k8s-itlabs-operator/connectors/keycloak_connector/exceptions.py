from validation.exceptions import AnnotationValidatorMissedRequiredException, AnnotationValidatorEmptyValueException, \
    ConnectorError


class KeycloakConnectorError(ConnectorError):
    pass


class KeycloakConnectorApplicationError(KeycloakConnectorError):
    pass


class KeycloakConnectorInfrastructureError(KeycloakConnectorError):
    pass


class KeycloakConnectorCrdDoesNotExist(KeycloakConnectorError):
    pass


class NonExistSecretForKeycloakConnector(KeycloakConnectorError):
    pass


class KeycloakConnectorMissingRequiredAnnotationError(KeycloakConnectorError,
                                                      AnnotationValidatorMissedRequiredException):
    pass


class KeycloakConnectorAnnotationEmptyValueError(KeycloakConnectorError, AnnotationValidatorEmptyValueException):
    pass
