import datetime
from zoneinfo import ZoneInfo
from abc import ABC
from typing import Any, Iterable, Mapping, MutableMapping, Optional
from urllib.parse import urlparse, parse_qs

import requests
from airbyte_cdk.sources.streams.http.http import HttpStream


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

        This method should return a Mapping (e.g: dict) containing whatever information required to make paginated requests. This dict is passed
        to most other methods in this class to help you form headers, request bodies, query params, etc..

        For example, if the API accepts a 'page' parameter to determine which page of the result to return, and a response from the API contains a
        'page' number, then this method should probably return a dict {'page': response.json()['page'] + 1} to increment the page count by 1.
        The request_params method should then read the input next_page_token and set the 'page' param to next_page_token['page'].

        :param response: the most recent response from the API
        :return If there is another page in the result, a mapping (e.g: dict) containing information needed to query the next page in the response.
                If there are no more pages in the result, return None.
        """

        json_response = response.json()
        response_link = json_response['link']
        parameters_for_next_request = {}
        for i in range(0, len(response_link)):
            if response_link[i]['relation'] == 'next':
                url = response_link[i]['url']
                parsed_url = urlparse(url)
                parameters_for_next_request = parse_qs(parsed_url.query)

        return parameters_for_next_request

    def request_params(
            self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, any] = None, next_page_token: Mapping[str, Any] = None
    ) -> MutableMapping[str, Any]:
        """
        Usually contains common params e.g. pagination size etc.
        """
        return {}

    def parse_response(self, response: requests.Response, **kwargs) -> Iterable[Mapping]:
        """
        TODO: Override this method to define how a response is parsed.
        :return an iterable containing each record in the response
        """
        yield {}


class IncrementalHapiFhirStream(HapiFhirStream, ABC):
    """
    This is the implementation of the incremental stream to read data from the source incrementally
    """
    state_checkpoint_interval = 50

    @property
    def cursor_field(self) -> str:
        """
        Override to return the cursor field used by this stream e.g: an API entity might always use created_at as the cursor field. This is
        usually id or date based. This field's presence tells the framework this in an incremental stream. Required for incremental.
        return str: The name of the cursor field.
        """
        return "lastUpdated"

    def get_updated_state(self, current_stream_state: MutableMapping[str, Any], latest_record: Mapping[str, Any]) -> Mapping[str, Any]:
        """
        Override to determine the latest state after reading the latest record. This typically compared the cursor_field from the latest record and
        the current state and picks the 'most' recent cursor. This is how a stream's state is determined. Required for incremental.
        """
        last_updated_timestamp = 0
        if 'resource' in latest_record:
            latest_record_metadata = latest_record['resource']['meta']
            last_updated_str = latest_record_metadata.get(self.cursor_field)
            date_format = "%Y-%m-%dT%H:%M:%S.%f%z"
            last_updated_timestamp = datetime.datetime.strptime(last_updated_str, date_format).timestamp()
        return {self.cursor_field: max(last_updated_timestamp, current_stream_state.get(self.cursor_field, 0))}


class QuestionnaireResponseStream(IncrementalHapiFhirStream, ABC):

    def path(
            self,
            *,
            stream_state: Mapping[str, Any] = None,
            stream_slice: Mapping[str, Any] = None,
            next_page_token: Mapping[str, Any] = None,
    ) -> str:
        if next_page_token is None:
            return "QuestionnaireResponse/_search"
        else:
            ""

    def parse_response(self, response: requests.Response, **kwargs) -> Iterable[Mapping]:
        response_json = response.json()

        if 'entry' in response_json:
            for questionnaire_response in response_json['entry']:
                yield questionnaire_response
        else:
            pass


class Patient(HapiFhirStream):
    def parse_response(self, response: requests.Response, **kwargs) -> Iterable[Mapping]:
        response_json = response.json()

        for patient_resource in response_json['entry']:
            yield patient_resource

    primary_key = None

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
        params = {}
        if next_page_token is None:
            return {"organization": "10173", "_count": "100"}
        else:
            params.update(next_page_token)
            return params


class HivTestTestedPositive(IncrementalHapiFhirStream, ABC):

    def parse_response(self, response: requests.Response, **kwargs) -> Iterable[Mapping]:
        response_json = response.json()

        if 'entry' in response_json:
            for questionnaire_response in response_json['entry']:
                yield questionnaire_response
        else:
            pass

    primary_key = None

    def path(self, *, stream_state: Mapping[str, Any] = None, stream_slice: Mapping[str, Any] = None,
             next_page_token: Mapping[str, Any] = None) -> str:
        if next_page_token is None:
            return "QuestionnaireResponse/_search"
        else:
            return ""

    def request_params(
            self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, any] = None, next_page_token: Mapping[str, Any] = None
    ) -> MutableMapping[str, Any]:
        params = {}
        if stream_state:
            last_updated_timestamp = stream_state.get(self.cursor_field)
            # Hardcoded ZoneInfo, the FHIR server ZoneInfo to make sure that you have the real time for lastUpdated params
            last_updated = datetime.datetime.fromtimestamp(last_updated_timestamp, ZoneInfo("Africa/Dar_es_Salaam"))
            last_updated_date = last_updated.strftime("%Y-%m-%dT%H:%M:%S.%f")
            last_updated_date_params = {"_lastUpdated": "gt" + last_updated_date}
            print("#################################" + last_updated_date)
            params.update(last_updated_date_params)
        if next_page_token is None:
            questionnaire_params = {"questionnaire": "Questionnaire/art-client-identifier-and-hiv-test"}
            params.update(questionnaire_params)
            return params
        else:
            params.update(next_page_token)
            return params


class CurrentOnArtStream(IncrementalHapiFhirStream, ABC):

    def parse_response(self, response: requests.Response, **kwargs) -> Iterable[Mapping]:
        response_json = response.json()

        if 'entry' in response_json:
            for questionnaire_response in response_json['entry']:
                yield questionnaire_response
        else:
            pass

    primary_key = None

    def path(self, *, stream_state: Mapping[str, Any] = None, stream_slice: Mapping[str, Any] = None,
             next_page_token: Mapping[str, Any] = None) -> str:
        if next_page_token is None:
            return "QuestionnaireResponse/_search"
        else:
            return ""

    def request_params(
            self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, any] = None, next_page_token: Mapping[str, Any] = None
    ) -> MutableMapping[str, Any]:
        params = {}
        if stream_state:
            last_updated_timestamp = stream_state.get(self.cursor_field)
            # Hardcoded ZoneInfo, the FHIR server ZoneInfo to make sure that you have the real time for lastUpdated params
            last_updated = datetime.datetime.fromtimestamp(last_updated_timestamp, ZoneInfo("Africa/Dar_es_Salaam"))
            last_updated_date = last_updated.strftime("%Y-%m-%dT%H:%M:%S.%f")
            last_updated_date_params = {"_lastUpdated": "gt" + last_updated_date}
            print("#################################" + last_updated_date)
            params.update(last_updated_date_params)
        if next_page_token is None:
            questionnaire_params = {"questionnaire": "Questionnaire/art-client-tb-history-and-regimen"}
            params.update(questionnaire_params)
            return params
        else:
            params.update(next_page_token)
            return params


class HtsIndexStream(IncrementalHapiFhirStream, ABC):

    def parse_response(self, response: requests.Response, **kwargs) -> Iterable[Mapping]:
        response_json = response.json()

        if 'entry' in response_json:
            for questionnaire_response in response_json['entry']:
                yield questionnaire_response
        else:
            pass

    primary_key = None

    def path(
            self,
            *,
            stream_state: Mapping[str, Any] = None,
            stream_slice: Mapping[str, Any] = None,
            next_page_token: Mapping[str, Any] = None,
    ) -> str:
        if next_page_token is None:
            return "QuestionnaireResponse/_search"
        else:
            return ""

    def request_params(
            self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, any] = None, next_page_token: Mapping[str, Any] = None
    ) -> MutableMapping[str, Any]:
        params = {}
        if stream_state:
            last_updated_timestamp = stream_state.get(self.cursor_field)
            # Hardcoded ZoneInfo, the FHIR server ZoneInfo to make sure that you have the real time for lastUpdated params
            last_updated = datetime.datetime.fromtimestamp(last_updated_timestamp, ZoneInfo("Africa/Dar_es_Salaam"))
            last_updated_date = last_updated.strftime("%Y-%m-%dT%H:%M:%S.%f")
            last_updated_date_params = {"_lastUpdated": "gt" + last_updated_date}
            print("#################################" + last_updated_date)
            params.update(last_updated_date_params)
        if next_page_token is None:
            questionnaire_params = {"questionnaire": "Questionnaire/contact-and-community-positive-hiv-test-and-next-appointment"}
            params.update(questionnaire_params)
            return params
        else:
            params.update(next_page_token)
            return params


class HtsIndexUntestedStream(IncrementalHapiFhirStream, ABC):

    def parse_response(self, response: requests.Response, **kwargs) -> Iterable[Mapping]:
        response_json = response.json()
        if 'entry' in response_json:
            for questionnaire_response in response_json['entry']:
                yield questionnaire_response
        else:
            pass

    primary_key = None

    def path(
            self,
            *,
            stream_state: Mapping[str, Any] = None,
            stream_slice: Mapping[str, Any] = None,
            next_page_token: Mapping[str, Any] = None,
    ) -> str:
        if next_page_token is None:
            return "QuestionnaireResponse/_search"
        else:
            return ""

    def request_params(
            self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, any] = None, next_page_token: Mapping[str, Any] = None
    ) -> MutableMapping[str, Any]:
        params = {}
        if stream_state:
            last_updated_timestamp = stream_state.get(self.cursor_field)
            # Hardcoded ZoneInfo, the FHIR server ZoneInfo to make sure that you have the real time for lastUpdated params
            last_updated = datetime.datetime.fromtimestamp(last_updated_timestamp, ZoneInfo("Africa/Dar_es_Salaam"))
            last_updated_date = last_updated.strftime("%Y-%m-%dT%H:%M:%S.%f")
            last_updated_date_params = {"_lastUpdated": "gt" + last_updated_date}
            print("#################################" + last_updated_date)
            params.update(last_updated_date_params)
        if next_page_token is None:
            questionnaire_request_param = {"questionnaire": "Questionnaire/art-client-index-case-testing"}
            params.update(questionnaire_request_param)
            return params
        else:
            params.update(next_page_token)
            return params


class PatientIncremental(IncrementalHapiFhirStream, ABC):

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

    primary_key = None

    def parse_response(self, response: requests.Response, **kwargs) -> Iterable[Mapping]:
        response_json = response.json()

        # Check if the response has any entry
        if 'entry' in response_json:
            for patient_resource in response_json['entry']:
                yield patient_resource
        else:
            pass

    def request_params(
            self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, any] = None, next_page_token: Mapping[str, Any] = None
    ) -> MutableMapping[str, Any]:
        params = {}
        if stream_state:
            last_updated_timestamp = stream_state.get(self.cursor_field)
            # Hardcoded ZoneInfo, the FHIR server ZoneInfo to make sure that you have the real time for lastUpdated params
            last_updated = datetime.datetime.fromtimestamp(last_updated_timestamp, ZoneInfo("Africa/Dar_es_Salaam"))
            last_updated_date = last_updated.strftime("%Y-%m-%dT%H:%M:%S.%f")
            last_updated_date_params = {"_lastUpdated": "gt" + last_updated_date}
            print("#################################" + last_updated_date)
            params.update(last_updated_date_params)
        if next_page_token is None:
            organization_count_params = {"organization": "10173", "_count": "100"}
            params.update(organization_count_params)
            return params
        else:
            params.update(next_page_token)
            return params


class PatientDemographicRegistration(IncrementalHapiFhirStream, ABC):

    def path(
            self,
            *,
            stream_state: Mapping[str, Any] = None,
            stream_slice: Mapping[str, Any] = None,
            next_page_token: Mapping[str, Any] = None,
    ) -> str:
        if next_page_token is None:
            return "QuestionnaireResponse/_search"
        else:
            ""

    primary_key = None

    def request_params(
            self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, any] = None, next_page_token: Mapping[str, Any] = None
    ) -> MutableMapping[str, Any]:
        params = {}
        if stream_state:
            last_updated_timestamp = stream_state.get(self.cursor_field)
            # Hardcoded ZoneInfo, the FHIR server ZoneInfo to make sure that you have the real time for lastUpdated params
            last_updated = datetime.datetime.fromtimestamp(last_updated_timestamp, ZoneInfo("Africa/Dar_es_Salaam"))
            last_updated_date = last_updated.strftime("%Y-%m-%dT%H:%M:%S.%f")
            last_updated_date_params = {"_lastUpdated": "gt" + last_updated_date}
            print("#################################" + last_updated_date)
            params.update(last_updated_date_params)
        if next_page_token is None:
            questionnaire_param = {"questionnaire": "Questionnaire/patient-demographic-registration", "_count": "100"}
            params.update(questionnaire_param)
            return params
        else:
            params.update(next_page_token)
            return params

    def parse_response(self, response: requests.Response, **kwargs) -> Iterable[Mapping]:
        response_json = response.json()

        if 'entry' in response_json:
            for questionnaire_response in response_json['entry']:
                yield questionnaire_response
        else:
            pass


class PatientFinishVisit(IncrementalHapiFhirStream, ABC):

    def path(
            self,
            *,
            stream_state: Mapping[str, Any] = None,
            stream_slice: Mapping[str, Any] = None,
            next_page_token: Mapping[str, Any] = None,
    ) -> str:
        if next_page_token is None:
            return "QuestionnaireResponse/_search"
        else:
            ""

    primary_key = None

    def request_params(
            self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, any] = None, next_page_token: Mapping[str, Any] = None
    ) -> MutableMapping[str, Any]:
        params = {}
        if stream_state:
            last_updated_timestamp = stream_state.get(self.cursor_field)
            # Hardcoded ZoneInfo, the FHIR server ZoneInfo to make sure that you have the real time for lastUpdated params
            last_updated = datetime.datetime.fromtimestamp(last_updated_timestamp, ZoneInfo("Africa/Dar_es_Salaam"))
            last_updated_date = last_updated.strftime("%Y-%m-%dT%H:%M:%S.%f")
            last_updated_date_params = {"_lastUpdated": "gt" + last_updated_date}
            print("#################################" + last_updated_date)
            params.update(last_updated_date_params)
        if next_page_token is None:
            questionnaire_param = {"questionnaire": "Questionnaire/patient-finish-visit", "_count": "100"}
            params.update(questionnaire_param)
            return params
        else:
            params.update(next_page_token)
            return params

    def parse_response(self, response: requests.Response, **kwargs) -> Iterable[Mapping]:
        response_json = response.json()

        if 'entry' in response_json:
            for questionnaire_response in response_json['entry']:
                yield questionnaire_response
        else:
            pass


class ExposedInfantHivTestAndResults(QuestionnaireResponseStream, ABC):
    primary_key = None

    def request_params(
            self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, any] = None, next_page_token: Mapping[str, Any] = None
    ) -> MutableMapping[str, Any]:
        params = {}
        if stream_state:
            last_updated_timestamp = stream_state.get(self.cursor_field)
            # Hardcoded ZoneInfo, the FHIR server ZoneInfo to make sure that you have the real time for lastUpdated params
            last_updated = datetime.datetime.fromtimestamp(last_updated_timestamp, ZoneInfo("Africa/Dar_es_Salaam"))
            last_updated_date = last_updated.strftime("%Y-%m-%dT%H:%M:%S.%f")
            last_updated_date_params = {"_lastUpdated": "gt" + last_updated_date}
            print("#################################" + last_updated_date)
            params.update(last_updated_date_params)
        if next_page_token is None:
            questionnaire_param = {"questionnaire": "Questionnaire/exposed-infant-hiv-test-and-results", "_count": "100"}
            params.update(questionnaire_param)
            return params
        else:
            params.update(next_page_token)
            return params


class ExposedInfantMilestoneHivTest(QuestionnaireResponseStream, ABC):
    primary_key = None

    def request_params(
            self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, any] = None, next_page_token: Mapping[str, Any] = None
    ) -> MutableMapping[str, Any]:
        params = {}
        if stream_state:
            last_updated_timestamp = stream_state.get(self.cursor_field)
            # Hardcoded ZoneInfo, the FHIR server ZoneInfo to make sure that you have the real time for lastUpdated params
            last_updated = datetime.datetime.fromtimestamp(last_updated_timestamp, ZoneInfo("Africa/Dar_es_Salaam"))
            last_updated_date = last_updated.strftime("%Y-%m-%dT%H:%M:%S.%f")
            last_updated_date_params = {"_lastUpdated": "gt" + last_updated_date}
            print("#################################" + last_updated_date)
            params.update(last_updated_date_params)
        if next_page_token is None:
            questionnaire_param = {"questionnaire": "Questionnaire/exposed-infant-milestone-hiv-test", "_count": "100"}
            params.update(questionnaire_param)
            return params
        else:
            params.update(next_page_token)
            return params


class PatientVitalsFemaleZeroSixMonths(QuestionnaireResponseStream, ABC):
    primary_key = None

    def request_params(
            self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, any] = None, next_page_token: Mapping[str, Any] = None
    ) -> MutableMapping[str, Any]:
        params = {}
        if stream_state:
            last_updated_timestamp = stream_state.get(self.cursor_field)
            # Hardcoded ZoneInfo, the FHIR server ZoneInfo to make sure that you have the real time for lastUpdated params
            last_updated = datetime.datetime.fromtimestamp(last_updated_timestamp, ZoneInfo("Africa/Dar_es_Salaam"))
            last_updated_date = last_updated.strftime("%Y-%m-%dT%H:%M:%S.%f")
            last_updated_date_params = {"_lastUpdated": "gt" + last_updated_date}
            print("#################################" + last_updated_date)
            params.update(last_updated_date_params)
        if next_page_token is None:
            questionnaire_param = {"questionnaire": "Questionnaire/patient-vitals-female-0-to-6-months", "_count": "100"}
            params.update(questionnaire_param)
            return params
        else:
            params.update(next_page_token)
            return params


class PatientVitalsSixMonthsFifteenYears(QuestionnaireResponseStream, ABC):
    primary_key = None

    def request_params(
            self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, any] = None, next_page_token: Mapping[str, Any] = None
    ) -> MutableMapping[str, Any]:
        params = {}
        if stream_state:
            last_updated_timestamp = stream_state.get(self.cursor_field)
            # Hardcoded ZoneInfo, the FHIR server ZoneInfo to make sure that you have the real time for lastUpdated params
            last_updated = datetime.datetime.fromtimestamp(last_updated_timestamp, ZoneInfo("Africa/Dar_es_Salaam"))
            last_updated_date = last_updated.strftime("%Y-%m-%dT%H:%M:%S.%f")
            last_updated_date_params = {"_lastUpdated": "gt" + last_updated_date}
            print("#################################" + last_updated_date)
            params.update(last_updated_date_params)
        if next_page_token is None:
            questionnaire_param = {"questionnaire": "Questionnaire/patient-vitals-6-months-to-15-years", "_count": "100"}
            params.update(questionnaire_param)
            return params
        else:
            params.update(next_page_token)
            return params
