import datetime
import json
from zoneinfo import ZoneInfo
from abc import ABC
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional
from urllib.parse import urlparse, parse_qs

import requests
from airbyte_cdk.sources.streams.http.http import HttpStream
from .utils.functions import process_data
from .utils.resources_configs import resources_config

# Basic full refresh stream
class HapiFhirStream(HttpStream, ABC):
    """

    This class represents a stream output by the connector.
    This is an abstract base class meant to contain all the common functionality at the API level e.g: the API base URL,
    pagination strategy, parsing responses etc..

    Each stream should extend this class (or another abstract subclass of it) to specify behavior unique to that stream.

    Typically for REST APIs each stream corresponds to a resource in the API. For example if the API
    contains the endpoints
        - GET fhir/Patient
        - GET fhir/QuestionnaireResponse/hiv-index-testing

    then you should have three classes:
    `class HapiFhirStream(HttpStream, ABC)` which is the current class
    `class Patient(HapiFhirStream)` contains behavior to pull data for patients using fhir/Patient
    `class HivIndexTesting(HapiFhirStream)` contains behavior to pull data for hiv index testing
     questionnaire responses using fhir/QuestionnaireResponse/hiv-index-testing
    """

    def __init__(self, url: str, **kwargs):
        super(HapiFhirStream, self).__init__(**kwargs)
        self._url = url

    @property
    def url_base(self) -> str:
        return self._url

    def next_page_token(self, response: requests.Response) -> Optional[Mapping[str, Any]]:
        """

        This method should return a Mapping (e.g: dict) containing whatever information required to make paginated requests. This dict is
        passed to most other methods in this class to help you form headers, request bodies, query params, etc.

        For example, if the API accepts a 'page' parameter to determine which page of the result to return, and a response from the API
        contains a 'page' number, then this method should probably return a dict {'page': response.json()['page'] + 1} to increment the
        page count by 1.
        The request_params method should then read the input next_page_token and set the 'page' param to next_page_token['page'].

        :param response: the most recent response from the API
        :return If there is another page in the result, a mapping (e.g: dict) containing information needed to query the next page in the
        response. If there are no more pages in the result, return None.
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
        Override to determine the latest state after reading the latest record. This typically compared the cursor_field from the latest
        record and the current state and picks the 'most' recent cursor. This is how a stream's state is determined. Required for
        incremental.
        """
        last_updated_timestamp = 0
        if 'resource' in latest_record:
            latest_record_metadata = latest_record['resource']['meta']
            last_updated_str = latest_record_metadata.get(self.cursor_field)
            date_format = "%Y-%m-%dT%H:%M:%S.%f%z"
            last_updated_timestamp = datetime.datetime.strptime(last_updated_str, date_format).timestamp()
        return {self.cursor_field: max(last_updated_timestamp, current_stream_state.get(self.cursor_field, 0))}


class QuestionnaireResponseStream(IncrementalHapiFhirStream, ABC):
    def __init__(self, url: str, **kwargs):
        super(QuestionnaireResponseStream, self).__init__(url, **kwargs)
        self.resources_config = resources_config
        self.tags_to_remove = self.resources_config.get('otherResource', [])
        self.link_ids_to_keep = self.resources_config.get('questionnaireResponse',{}).get('finish-visit',{})
        
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
                yield process_data(questionnaire_response, self.tags_to_remove, self.link_ids_to_keep)
        else:
            pass


class Patient(HapiFhirStream):
    def __init__(self, url: str, **kwargs):
        super(Patient, self).__init__(url, **kwargs)
        self.resources_config = resources_config
        self.tags_to_remove = self.resources_config.get('patientResource', [])

    def parse_response(self, response: requests.Response, **kwargs) -> Iterable[Mapping]:
        response_json = response.json()

        for patient_resource in response_json['entry']:
            yield process_data(patient_resource, self.tags_to_remove)

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


class PatientIncremental(IncrementalHapiFhirStream, ABC):
    
    def __init__(self, url: str, **kwargs):
        super(PatientIncremental, self).__init__(url, **kwargs)
        self.resources_config = resources_config
        self.tags_to_remove = self.resources_config.get('patientResource', [])

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
                yield process_data(patient_resource, self.tags_to_remove)
        else:
            pass

    def request_params(
            self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, any] = None, next_page_token: Mapping[str, Any] = None
    ) -> MutableMapping[str, Any]:
        params = {}
        if stream_state:
            last_updated_timestamp = stream_state.get(self.cursor_field)
            # Hardcoded ZoneInfo, the FHIR server ZoneInfo to make sure that you have the real time for lastUpdated params
            last_updated = datetime.datetime.fromtimestamp(last_updated_timestamp, ZoneInfo("Africa/Blantyre"))
            last_updated_date = last_updated.strftime("%Y-%m-%dT%H:%M:%S.%f")
            last_updated_date_params = {"_lastUpdated": "gt" + last_updated_date}
            print("#################################" + last_updated_date)
            params.update(last_updated_date_params)
        if next_page_token is None:
            active_patient_count_params = {"active": "true", "_count": "100"}
            params.update(active_patient_count_params)
            return params
        else:
            params.update(next_page_token)
            return params
class PatientFinishVisit(QuestionnaireResponseStream, ABC):
    primary_key = None

    def request_params(
            self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, any] = None, next_page_token: Mapping[str, Any] = None
    ) -> MutableMapping[str, Any]:
        params = {}
        if stream_state:
            last_updated_timestamp = stream_state.get(self.cursor_field)
            # Hardcoded ZoneInfo, the FHIR server ZoneInfo to make sure that you have the real time for lastUpdated params
            last_updated = datetime.datetime.fromtimestamp(last_updated_timestamp, ZoneInfo("Africa/Blantyre"))
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


class CarePlansStream(IncrementalHapiFhirStream, ABC):
    def __init__(self, url: str, **kwargs):
        super(IncrementalHapiFhirStream, self).__init__(url, **kwargs)
        self.resources_config = resources_config
        self.tags_to_remove = self.resources_config.get('otherResource', [])

    def path(
            self,
            *,
            stream_state: Mapping[str, Any] = None,
            stream_slice: Mapping[str, Any] = None,
            next_page_token: Mapping[str, Any] = None,
    ) -> str:
        if next_page_token is None:
            return "CarePlan/_search"
        else:
            ""

    def parse_response(self, response: requests.Response, **kwargs) -> Iterable[Mapping]:
        response_json = response.json()

        if 'entry' in response_json:
            for resource in response_json['entry']:
                yield process_data(resource, self.tags_to_remove)
        else:
            pass


class CompletedCarePlans(CarePlansStream, ABC):
    primary_key = None

    def request_params(
            self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, any] = None, next_page_token: Mapping[str, Any] = None
    ) -> MutableMapping[str, Any]:
        params = {}
        if stream_state:
            last_updated_timestamp = stream_state.get(self.cursor_field)
            # Hardcoded ZoneInfo, the FHIR server ZoneInfo to make sure that you have the real time for lastUpdated params
            last_updated = datetime.datetime.fromtimestamp(last_updated_timestamp, ZoneInfo("Africa/Blantyre"))
            last_updated_date = last_updated.strftime("%Y-%m-%dT%H:%M:%S.%f")
            last_updated_date_params = {"_lastUpdated": "gt" + last_updated_date}
            print("#################################" + last_updated_date)
            params.update(last_updated_date_params)
        if next_page_token is None:
            questionnaire_param = {"status": "completed", "_count": "100"}
            params.update(questionnaire_param)
            return params
        else:
            params.update(next_page_token)
            return params


class LocationStream(IncrementalHapiFhirStream, ABC):

    def path(
            self,
            *,
            stream_state: Mapping[str, Any] = None,
            stream_slice: Mapping[str, Any] = None,
            next_page_token: Mapping[str, Any] = None,
    ) -> str:
        if next_page_token is None:
            return "Location/_search"
        else:
            ""

    def parse_response(self, response: requests.Response, **kwargs) -> Iterable[Mapping]:
        response_json = response.json()

        if 'entry' in response_json:
            for location in response_json['entry']:
                yield location
        else:
            pass


class Locations(LocationStream, ABC):
    primary_key = None

    def request_params(
            self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, any] = None, next_page_token: Mapping[str, Any] = None
    ) -> MutableMapping[str, Any]:
        params = {}
        if stream_state:
            last_updated_timestamp = stream_state.get(self.cursor_field)
            # Hardcoded ZoneInfo, the FHIR server ZoneInfo to make sure that you have the real time for lastUpdated params
            last_updated = datetime.datetime.fromtimestamp(last_updated_timestamp, ZoneInfo("Africa/Blantyre"))
            last_updated_date = last_updated.strftime("%Y-%m-%dT%H:%M:%S.%f")
            last_updated_date_params = {"_lastUpdated": "gt" + last_updated_date}
            print("#################################" + last_updated_date)
            params.update(last_updated_date_params)
        if next_page_token is None:
            location_param = {"status": "active", "_count": "100"}
            params.update(location_param)
            return params
        else:
            params.update(next_page_token)
            return params


class AllCarePlans(CarePlansStream, ABC):
    primary_key = None

    def request_params(
            self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, any] = None, next_page_token: Mapping[str, Any] = None
    ) -> MutableMapping[str, Any]:
        params = {}
        if stream_state:
            last_updated_timestamp = stream_state.get(self.cursor_field)
            # Hardcoded ZoneInfo, the FHIR server ZoneInfo to make sure that you have the real time for lastUpdated params
            last_updated = datetime.datetime.fromtimestamp(last_updated_timestamp, ZoneInfo("Africa/Blantyre"))
            last_updated_date = last_updated.strftime("%Y-%m-%dT%H:%M:%S.%f")
            last_updated_date_params = {"_lastUpdated": "gt" + last_updated_date}
            print("#################################" + last_updated_date)
            params.update(last_updated_date_params)
        if next_page_token is None:
            questionnaire_param = {"_count": "100"}
            params.update(questionnaire_param)
            return params
        else:
            params.update(next_page_token)
            return params


class TaskStream(IncrementalHapiFhirStream, ABC):

    def __init__(self, url: str, **kwargs):
        super(IncrementalHapiFhirStream, self).__init__(url, **kwargs)
        self.resources_config = resources_config
        self.tags_to_remove = self.resources_config.get('otherResource', [])
    
    def path(
            self,
            *,
            stream_state: Mapping[str, Any] = None,
            stream_slice: Mapping[str, Any] = None,
            next_page_token: Mapping[str, Any] = None,
    ) -> str:
        if next_page_token is None:
            return "Task/_search"
        else:
            ""

    def parse_response(self, response: requests.Response, **kwargs) -> Iterable[Mapping]:
        response_json = response.json()

        if 'entry' in response_json:
            for resource in response_json['entry']:
                yield process_data(resource, self.tags_to_remove)
        else:
            pass


class Tasks(TaskStream, ABC):
    primary_key = None

    def request_params(
            self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, any] = None, next_page_token: Mapping[str, Any] = None
    ) -> MutableMapping[str, Any]:
        params = {}
        if stream_state:
            last_updated_timestamp = stream_state.get(self.cursor_field)
            # Hardcoded ZoneInfo, the FHIR server ZoneInfo to make sure that you have the real time for lastUpdated params
            last_updated = datetime.datetime.fromtimestamp(last_updated_timestamp, ZoneInfo("Africa/Blantyre"))
            last_updated_date = last_updated.strftime("%Y-%m-%dT%H:%M:%S.%f")
            last_updated_date_params = {"_lastUpdated": "gt" + last_updated_date}
            print("#################################" + last_updated_date)
            params.update(last_updated_date_params)
        if next_page_token is None:
            tasks_param = {"_count": "500"}
            params.update(tasks_param)
            return params
        else:
            params.update(next_page_token)
            return params


class TracingOutcomeStream(IncrementalHapiFhirStream, ABC):

    def __init__(self, url: str, **kwargs):
        super(IncrementalHapiFhirStream, self).__init__(url, **kwargs)
        self.resources_config = resources_config
        self.tags_to_remove = self.resources_config.get('otherResource', [])

    def path(
            self,
            *,
            stream_state: Mapping[str, Any] = None,
            stream_slice: Mapping[str, Any] = None,
            next_page_token: Mapping[str, Any] = None,
    ) -> str:
        if next_page_token is None:
            return "Observation/_search"
        else:
            ""

    def parse_response(self, response: requests.Response, **kwargs) -> Iterable[Mapping]:
        response_json = response.json()

        if 'entry' in response_json:
            for resource in response_json['entry']:
                yield process_data(resource, self.tags_to_remove)
        else:
            pass


class TracingOutcomesConducted(TracingOutcomeStream, ABC):
    primary_key = None

    def request_params(
            self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, any] = None, next_page_token: Mapping[str, Any] = None
    ) -> MutableMapping[str, Any]:
        params = {}
        if stream_state:
            last_updated_timestamp = stream_state.get(self.cursor_field)
            # Hardcoded ZoneInfo, the FHIR server ZoneInfo to make sure that you have the real time for lastUpdated params
            last_updated = datetime.datetime.fromtimestamp(last_updated_timestamp, ZoneInfo("Africa/Blantyre"))
            last_updated_date = last_updated.strftime("%Y-%m-%dT%H:%M:%S.%f")
            last_updated_date_params = {"_lastUpdated": "gt" + last_updated_date}
            print("#################################" + last_updated_date)
            params.update(last_updated_date_params)
        if next_page_token is None:
            obs_param = {"code": "tracing-outcome-conducted", "_count": "500"}
            params.update(obs_param)
            return params
        else:
            params.update(next_page_token)
            return params


class TracingOutcomesUnconducted(TracingOutcomeStream, ABC):
    primary_key = None

    def request_params(
            self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, any] = None, next_page_token: Mapping[str, Any] = None
    ) -> MutableMapping[str, Any]:
        params = {}
        if stream_state:
            last_updated_timestamp = stream_state.get(self.cursor_field)
            # Hardcoded ZoneInfo, the FHIR server ZoneInfo to make sure that you have the real time for lastUpdated params
            last_updated = datetime.datetime.fromtimestamp(last_updated_timestamp, ZoneInfo("Africa/Blantyre"))
            last_updated_date = last_updated.strftime("%Y-%m-%dT%H:%M:%S.%f")
            last_updated_date_params = {"_lastUpdated": "gt" + last_updated_date}
            print("#################################" + last_updated_date)
            params.update(last_updated_date_params)
        if next_page_token is None:
            obs_param = {"code": "tracing-outcome-unconducted", "_count": "500"}
            params.update(obs_param)
            return params
        else:
            params.update(next_page_token)
            return params


class AuditEventStream(IncrementalHapiFhirStream, ABC):
    def path(
            self,
            *,
            stream_state: Mapping[str, Any] = None,
            stream_slice: Mapping[str, Any] = None,
            next_page_token: Mapping[str, Any] = None,
    ) -> str:
        if next_page_token is None:
            return "AuditEvent/_search"
        else:
            ""

    def parse_response(self, response: requests.Response, **kwargs) -> Iterable[Mapping]:
        response_json = response.json()

        if 'entry' in response_json:
            for location in response_json['entry']:
                yield location
        else:
            pass


class AuditEvents(AuditEventStream, ABC):
    primary_key = None

    def request_params(
            self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, any] = None, next_page_token: Mapping[str, Any] = None
    ) -> MutableMapping[str, Any]:
        params = {}
        if stream_state:
            last_updated_timestamp = stream_state.get(self.cursor_field)
            # Hardcoded ZoneInfo, the FHIR server ZoneInfo to make sure that you have the real time for lastUpdated params
            last_updated = datetime.datetime.fromtimestamp(last_updated_timestamp, ZoneInfo("Africa/Blantyre"))
            last_updated_date = last_updated.strftime("%Y-%m-%dT%H:%M:%S.%f")
            last_updated_date_params = {"_lastUpdated": "gt" + last_updated_date}
            print("#################################" + last_updated_date)
            params.update(last_updated_date_params)
        if next_page_token is None:
            audit_event_param = {"_count": "500"}
            params.update(audit_event_param)
            return params
        else:
            params.update(next_page_token)
            return params


class Practitioner(IncrementalHapiFhirStream, ABC):
    primary_key = None

    def path(
            self,
            *,
            stream_state: Mapping[str, Any] = None,
            stream_slice: Mapping[str, Any] = None,
            next_page_token: Mapping[str, Any] = None,
    ) -> str:
        if next_page_token is None:
            return "Practitioner/_search"
        else:
            ""

    def parse_response(self, response: requests.Response, **kwargs) -> Iterable[Mapping]:
        response_json = response.json()

        if 'entry' in response_json:
            for location in response_json['entry']:
                yield location
        else:
            pass

    def request_params(self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, any] = None,
                       next_page_token: Mapping[str, Any] = None) -> MutableMapping[str, Any]:
        params = {}
        if stream_state:
            last_updated_timestamp = stream_state.get(self.cursor_field)
            # Hardcoded ZoneInfo, the FHIR server ZoneInfo to make sure that you have the real time for lastUpdated params
            last_updated = datetime.datetime.fromtimestamp(last_updated_timestamp, ZoneInfo("Africa/Blantyre"))
            last_updated_date = last_updated.strftime("%Y-%m-%dT%H:%M:%S.%f")
            last_updated_date_params = {"_lastUpdated": "gt" + last_updated_date}
            print("#################################" + last_updated_date)
            params.update(last_updated_date_params)
        if next_page_token is None:
            practitioner_param = {"active": "true", "_count": "500"}
            params.update(practitioner_param)
            return params
        else:
            params.update(next_page_token)
            return params

class CareTeam(IncrementalHapiFhirStream, ABC):
    primary_key = None

    def path(
            self,
            *,
            stream_state: Mapping[str, Any] = None,
            stream_slice: Mapping[str, Any] = None,
            next_page_token: Mapping[str, Any] = None,
    ) -> str:
        if next_page_token is None:
            return "CareTeam/_search"
        else:
            ""

    def parse_response(self, response: requests.Response, **kwargs) -> Iterable[Mapping]:
        response_json = response.json()

        if 'entry' in response_json:
            for location in response_json['entry']:
                yield location
        else:
            pass

    def request_params(self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, any] = None,
                       next_page_token: Mapping[str, Any] = None) -> MutableMapping[str, Any]:
        params = {}
        if stream_state:
            last_updated_timestamp = stream_state.get(self.cursor_field)
            # Hardcoded ZoneInfo, the FHIR server ZoneInfo to make sure that you have the real time for lastUpdated params
            last_updated = datetime.datetime.fromtimestamp(last_updated_timestamp, ZoneInfo("Africa/Blantyre"))
            last_updated_date = last_updated.strftime("%Y-%m-%dT%H:%M:%S.%f")
            last_updated_date_params = {"_lastUpdated": "gt" + last_updated_date}
            print("#################################" + last_updated_date)
            params.update(last_updated_date_params)
        if next_page_token is None:
            care_team_param = {"status": "active", "_count": "500"}
            params.update(care_team_param)
            return params
        else:
            params.update(next_page_token)
            return params

class Encounter(IncrementalHapiFhirStream, ABC):
    def __init__(self, url: str, **kwargs):
        super(IncrementalHapiFhirStream, self).__init__(url, **kwargs)
        self.resources_config = resources_config
        self.tags_to_remove = self.resources_config.get('otherResource', [])
    primary_key = None

    def path(
            self,
            *,
            stream_state: Mapping[str, Any] = None,
            stream_slice: Mapping[str, Any] = None,
            next_page_token: Mapping[str, Any] = None,
    ) -> str:
        if next_page_token is None:
            return "Encounter/_search"
        else:
            ""

    def parse_response(self, response: requests.Response, **kwargs) -> Iterable[Mapping]:
        response_json = response.json()

        if 'entry' in response_json:
            for resource in response_json['entry']:
                yield process_data(resource, self.tags_to_remove)
        else:
            pass

    def request_params(self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, any] = None,
                       next_page_token: Mapping[str, Any] = None) -> MutableMapping[str, Any]:
        params = {}
        if stream_state:
            last_updated_timestamp = stream_state.get(self.cursor_field)
            # Hardcoded ZoneInfo, the FHIR server ZoneInfo to make sure that you have the real time for lastUpdated params
            last_updated = datetime.datetime.fromtimestamp(last_updated_timestamp, ZoneInfo("Africa/Blantyre"))
            last_updated_date = last_updated.strftime("%Y-%m-%dT%H:%M:%S.%f")
            last_updated_date_params = {"_lastUpdated": "gt" + last_updated_date}
            print("#################################" + last_updated_date)
            params.update(last_updated_date_params)
        if next_page_token is None:
            encounter_param = {"status": "finished", "_count": "500"}
            params.update(encounter_param)
            return params
        else:
            params.update(next_page_token)
            return params

class OrganizationAffiliation(IncrementalHapiFhirStream, ABC):
    primary_key = None

    def path(
            self,
            *,
            stream_state: Mapping[str, Any] = None,
            stream_slice: Mapping[str, Any] = None,
            next_page_token: Mapping[str, Any] = None,
    ) -> str:
        if next_page_token is None:
            return "OrganizationAffiliation/_search"
        else:
            ""

    def parse_response(self, response: requests.Response, **kwargs) -> Iterable[Mapping]:
        response_json = response.json()

        if 'entry' in response_json:
            for resource in response_json['entry']:
                yield resource
        else:
            pass

    def request_params(self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, any] = None,
                       next_page_token: Mapping[str, Any] = None) -> MutableMapping[str, Any]:
        params = {}
        if stream_state:
            last_updated_timestamp = stream_state.get(self.cursor_field)
            # Hardcoded ZoneInfo, the FHIR server ZoneInfo to make sure that you have the real time for lastUpdated params
            last_updated = datetime.datetime.fromtimestamp(last_updated_timestamp, ZoneInfo("Africa/Blantyre"))
            last_updated_date = last_updated.strftime("%Y-%m-%dT%H:%M:%S.%f")
            last_updated_date_params = {"_lastUpdated": "gt" + last_updated_date}
            print("#################################" + last_updated_date)
            params.update(last_updated_date_params)
        if next_page_token is None:
            organization_affiliation_param = {"active": "true", "_count": "500"}
            params.update(organization_affiliation_param)
            return params
        else:
            params.update(next_page_token)
            return params
        
class Conditions(IncrementalHapiFhirStream, ABC):
    def __init__(self, url: str, **kwargs):
        super(IncrementalHapiFhirStream, self).__init__(url, **kwargs)
        self.resources_config = resources_config
        self.tags_to_remove = self.resources_config.get('otherResource', [])

    primary_key = None

    def path(
            self,
            *,
            stream_state: Mapping[str, Any] = None,
            stream_slice: Mapping[str, Any] = None,
            next_page_token: Mapping[str, Any] = None,
    ) -> str:
        if next_page_token is None:
            return "Condition/_search"
        else:
            ""

    def parse_response(self, response: requests.Response, **kwargs) -> Iterable[Mapping]:
        response_json = response.json()

        if 'entry' in response_json:
            for resource in response_json['entry']:
                yield process_data(resource, self.tags_to_remove)
        else:
            pass

    def request_params(self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, any] = None,
                       next_page_token: Mapping[str, Any] = None) -> MutableMapping[str, Any]:
        params = {}
        if stream_state:
            last_updated_timestamp = stream_state.get(self.cursor_field)
            # Hardcoded ZoneInfo, the FHIR server ZoneInfo to make sure that you have the real time for lastUpdated params
            last_updated = datetime.datetime.fromtimestamp(last_updated_timestamp, ZoneInfo("Africa/Blantyre"))
            last_updated_date = last_updated.strftime("%Y-%m-%dT%H:%M:%S.%f")
            last_updated_date_params = {"_lastUpdated": "gt" + last_updated_date}
            print("#################################" + last_updated_date)
            params.update(last_updated_date_params)
        if next_page_token is None:
            query_param = {"clinical-status": "active", "_count": "500"}
            params.update(query_param)
            return params
        else:
            params.update(next_page_token)
            return params
        
class VitalsDisclosed(IncrementalHapiFhirStream, ABC):
    def __init__(self, url: str, **kwargs):
        super(IncrementalHapiFhirStream, self).__init__(url, **kwargs)
        self.resources_config = resources_config
        self.tags_to_remove = self.resources_config.get('otherResource', [])

    primary_key = None

    def path(
            self,
            *,
            stream_state: Mapping[str, Any] = None,
            stream_slice: Mapping[str, Any] = None,
            next_page_token: Mapping[str, Any] = None,
    ) -> str:
        if next_page_token is None:
            return "Observation/_search"
        else:
            ""

    def parse_response(self, response: requests.Response, **kwargs) -> Iterable[Mapping]:
        response_json = response.json()

        if 'entry' in response_json:
            for resource in response_json['entry']:
                yield process_data(resource, self.tags_to_remove)
        else:
            pass

    def request_params(self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, any] = None,
                       next_page_token: Mapping[str, Any] = None) -> MutableMapping[str, Any]:
        params = {}
        if stream_state:
            last_updated_timestamp = stream_state.get(self.cursor_field)
            # Hardcoded ZoneInfo, the FHIR server ZoneInfo to make sure that you have the real time for lastUpdated params
            last_updated = datetime.datetime.fromtimestamp(last_updated_timestamp, ZoneInfo("Africa/Blantyre"))
            last_updated_date = last_updated.strftime("%Y-%m-%dT%H:%M:%S.%f")
            last_updated_date_params = {"_lastUpdated": "gt" + last_updated_date}
            print("#################################" + last_updated_date)
            params.update(last_updated_date_params)
        if next_page_token is None:
            query_param = {"code": "vitals-disclose", "_count": "500"}
            params.update(query_param)
            return params
        else:
            params.update(next_page_token)
            return params