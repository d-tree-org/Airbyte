from abc import ABC
from typing import Any, Iterable, List, Mapping, MutableMapping, Optional, Tuple, Union
from airbyte_cdk.sources.streams.http.http import HttpStream
from urllib.parse import urlparse, parse_qs
import requests


# Basic full refresh stream
class HapiFhirStream(HttpStream, ABC):
    """
    TODO remove this comment

    This class represents a stream output by the connector.
    This is an abstract base class meant to contain all the common functionality at the API level e.g: the API base URL, pagination strategy,
    parsing responses etc..

    Each stream should extend this class (or another abstract subclass of it) to specify behavior unique to that stream.

    Typically for REST APIs each stream corresponds to a resource in the API. For example if the API
    contains the endpoints
        - GET v1/customers
        - GET v1/employees

    then you should have three classes:
    `class HapiFhirStream(HttpStream, ABC)` which is the current class
    `class Customers(HapiFhirStream)` contains behavior to pull data for customers using v1/customers
    `class Employees(HapiFhirStream)` contains behavior to pull data for employees using v1/employees

    If some streams implement incremental sync, it is typical to create another class
    `class IncrementalHapiFhirStream((HapiFhirStream), ABC)` then have concrete stream implementations extend it. An example
    is provided below.

    See the reference docs for the full list of configurable options.
    """
    url_base = "https://fhir-dev.d-tree.org/fhir/"

    def next_page_token(self, response: requests.Response) -> Optional[Mapping[str, Any]]:
        """
        TODO: Override this method to define a pagination strategy. If you will not be using pagination, no action is required - just return None.

        This method should return a Mapping (e.g: dict) containing whatever information required to make paginated requests. This dict is passed
        to most other methods in this class to help you form headers, request bodies, query params, etc..

        For example, if the API accepts a 'page' parameter to determine which page of the result to return, and a response from the API contains a
        'page' number, then this method should probably return a dict {'page': response.json()['page'] + 1} to increment the page count by 1.
        The request_params method should then read the input next_page_token and set the 'page' param to next_page_token['page'].

        :param response: the most recent response from the API
        :return If there is another page in the result, a mapping (e.g: dict) containing information needed to query the next page in the response.
                If there are no more pages in the result, return None.
        """
        return None

    def request_params(
            self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, any] = None, next_page_token: Mapping[str, Any] = None
    ) -> MutableMapping[str, Any]:
        """
        TODO: Override this method to define any query parameters to be set. Remove this method if you don't need to define request params.
        Usually contains common params e.g. pagination size etc.
        """
        return {}

    def parse_response(self, response: requests.Response, **kwargs) -> Iterable[Mapping]:
        """
        TODO: Override this method to define how a response is parsed.
        :return an iterable containing each record in the response
        """
        yield {}


class Patient(HapiFhirStream):
    def parse_response(self, response: requests.Response, **kwargs) -> Iterable[Mapping]:
        return [response.json()]

    primary_key = None

    def next_page_token(self, response: requests.Response) -> Optional[Mapping[str, Any]]:
        json_response = response.json()
        response_link = json_response['link']
        parameters_for_next_request = {}
        for i in range(0, len(response_link)):
            if response_link[i]['relation'] == 'next':
                url = response_link[i]['url']
                parsed_url = urlparse(url)
                parameters_for_next_request = parse_qs(parsed_url.query)

        return parameters_for_next_request

    def path(
            self,
            *,
            stream_state: Mapping[str, Any] = None,
            stream_slice: Mapping[str, Any] = None,
            next_page_token: Mapping[str, Any] = None,
    ) -> str:
        if next_page_token is None:
            return "Patient/_search"
        else:
            return ""

    def request_params(
            self,
            stream_state: Mapping[str, Any],
            stream_slice: Mapping[str, Any] = None,
            next_page_token: Mapping[str, Any] = None,
    ) -> MutableMapping[str, Any]:
        if next_page_token is None:
            return {"organization": "10173"}
        else:
            pagination_params = next_page_token
            return pagination_params


class HivTestTestedPositive(HapiFhirStream):

    def parse_response(self, response: requests.Response, **kwargs) -> Iterable[Mapping]:
        return [response.json()]

    primary_key = None

    def next_page_token(self, response: requests.Response) -> Optional[Mapping[str, Any]]:
        json_response = response.json()
        response_link = json_response['link']
        parameters_for_next_request = {}
        for i in range(0, len(response_link)):
            if response_link[i]['relation'] == 'next':
                url = response_link[i]['url']
                parsed_url = urlparse(url)
                parameters_for_next_request = parse_qs(parsed_url.query)
        return parameters_for_next_request

    def path(self, *, stream_state: Mapping[str, Any] = None, stream_slice: Mapping[str, Any] = None,
             next_page_token: Mapping[str, Any] = None) -> str:
        if next_page_token is None:
            return "QuestionnaireResponse/_search"
        else:
            return ""

    def request_params(
            self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, any] = None, next_page_token: Mapping[str, Any] = None
    ) -> MutableMapping[str, Any]:
        if next_page_token is None:
            return {"questionnaire": "Questionnaire/art-client-identifier-and-hiv-test"}
        else:
            return next_page_token


class CurrentOnArtStream(HapiFhirStream):

    def parse_response(self, response: requests.Response, **kwargs) -> Iterable[Mapping]:
        return [response.json()]

    primary_key = None

    def next_page_token(self, response: requests.Response) -> Optional[Mapping[str, Any]]:
        json_response = response.json()
        response_link = json_response['link']
        parameters_for_next_request = {}
        for i in range(0, len(response_link)):
            if response_link[i]['relation'] == 'next':
                url = response_link[i]['url']
                parsed_url = urlparse(url)
                parameters_for_next_request = parse_qs(parsed_url.query)
        return parameters_for_next_request

    def path(self, *, stream_state: Mapping[str, Any] = None, stream_slice: Mapping[str, Any] = None,
             next_page_token: Mapping[str, Any] = None) -> str:
        if next_page_token is None:
            return "QuestionnaireResponse/_search"
        else:
            return ""

    def request_params(
            self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, any] = None, next_page_token: Mapping[str, Any] = None
    ) -> MutableMapping[str, Any]:
        if next_page_token is None:
            return {"questionnaire": "Questionnaire/art-client-tb-history-and-regimen"}
        else:
            return next_page_token

