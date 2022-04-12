#  Copyright (c) ZenML GmbH 2021. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at:
#
#       https://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
#  or implied. See the License for the specific language governing
#  permissions and limitations under the License.

from datetime import datetime, timedelta

from pipeline import evaluator, importer, mnist_pipeline, normalizer, trainer

from zenml.pipelines import Schedule

if __name__ == "__main__":
    # Run the pipeline
    p = mnist_pipeline(
        importer=importer(),
        normalizer=normalizer(),
        trainer=trainer(),
        evaluator=evaluator(),
    )
    p.run(
        schedule=Schedule(
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(minutes=10),
            interval_second=60,
        )
    )