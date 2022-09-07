#
# Copyright (c) 2022 Airbyte, Inc., all rights reserved.
#


import sys

from airbyte_cdk.entrypoint import launch
from source_hapi_fhir import SourceHapiFhir

if __name__ == "__main__":
    source = SourceHapiFhir()
    launch(source, sys.argv[1:])
