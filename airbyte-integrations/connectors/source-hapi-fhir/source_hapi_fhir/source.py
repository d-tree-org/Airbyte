#
# Copyright (c) 2022 Airbyte, Inc., all rights reserved.
#


from typing import Any, List, Mapping, Tuple

from airbyte_cdk.sources import AbstractSource
from airbyte_cdk.sources.streams import Stream
from airbyte_cdk.models import SyncMode
from airbyte_cdk.sources.streams.http.auth import TokenAuthenticator
from keycloak import KeycloakOpenID

from .streams import Patient, HivTestTestedPositive, CurrentOnArtStream, HtsIndexStream, HtsIndexUntestedStream

"""
TODO: Most comments in this class are instructive and should be deleted after the source is implemented.

This file provides a stubbed example of how to use the Airbyte CDK to develop both a source connector which supports full refresh or and an
incremental syncs from an HTTP API.

The various TODOs are both implementation hints and steps - fulfilling all the TODOs should be sufficient to implement one basic and one incremental
stream from a source. This pattern is the same one used by Airbyte internally to implement connectors.

The approach here is not authoritative, and devs are free to use their own judgement.

There are additional required TODOs in the files within the integration_tests folder and the spec.yaml file.
"""


# Source
class SourceHapiFhir(AbstractSource):
    def check_connection(self, logger, config) -> Tuple[bool, any]:
        """
        TODO: Implement a connection check to validate that the user-provided config can be used to connect to the underlying API

        See https://github.com/airbytehq/airbyte/blob/master/airbyte-integrations/connectors/source-stripe/source_stripe/source.py#L232
        for an example.

        :param config:  the user-input config object conforming to the connector's spec.yaml
        :param logger:  logger object
        :return Tuple[bool, any]: (True, None) if the input config can be used to connect to the API successfully, (False, error) otherwise.
        """
        try:
            keycloak_openid = KeycloakOpenID(server_url=config["server_url"],
                                             realm_name=config["realm_name"],
                                             client_id=config["client_id"],
                                             client_secret_key=config["client_secret"])
            token = keycloak_openid.token(username=config["username"], password=config["password"])
            auth = TokenAuthenticator(token=token["access_token"])
            patient_stream = Patient(authenticator=auth)
            patient_stream.read_records(sync_mode=SyncMode.full_refresh)
            return True, None
        except Exception as e:
            return False, e

    def streams(self, config: Mapping[str, Any]) -> List[Stream]:
        """
        TODO: Replace the streams below with your own streams.

        :param config: A Mapping of the user input configuration as defined in the connector spec.
        """
        keycloak_openid = KeycloakOpenID(server_url=config["server_url"],
                                         realm_name=config["realm_name"],
                                         client_id=config["client_id"],
                                         client_secret_key=config["client_secret"])

        token = keycloak_openid.token(username=config["username"], password=config["password"])

        auth = TokenAuthenticator(token=token["access_token"])  # Oauth2Authenticator is also available if you need oauth support
        return [Patient(authenticator=auth),
                HivTestTestedPositive(authenticator=auth),
                CurrentOnArtStream(authenticator=auth),
                HtsIndexStream(authenticator=auth),
                HtsIndexUntestedStream(authenticator=auth)]
