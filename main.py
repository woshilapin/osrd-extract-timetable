#!/usr/bin/env python

import itertools
from inquirer.questions import json
from termcolor import colored
import collections.abc
import datetime
import inquirer
import os
import requests

gateway_token = os.getenv("GATEWAY_TOKEN")
answers = dict()
answers["url"] = "http://localhost:4000/api"


session = requests.Session()
session.cookies = requests.utils.add_dict_to_cookiejar(
    session.cookies, dict(gateway=gateway_token)
)


def list_projects() -> collections.abc.Generator[tuple[str, str], None, None]:
    page = 1
    page_count = 2
    while page < page_count:
        projects = session.get(f"{answers['url']}/projects?page={page}").json()
        page = projects.get("current")
        page_count = projects.get("page_count")
        for project in projects.get("results"):
            yield (project.get("name"), project.get("id"))
    return


def list_studies(
    project_id: str,
) -> collections.abc.Generator[tuple[str, str], None, None]:
    page = 1
    page_count = 2
    while page < page_count:
        studies = session.get(
            f"{answers['url']}/projects/{project_id}/studies?page={page}"
        ).json()
        page = studies.get("current")
        page_count = studies.get("page_count")
        for study in studies.get("results"):
            yield (study.get("name"), study.get("id"))
    return


def list_scenarios(
    project_id: str,
    study_id: str,
) -> collections.abc.Generator[tuple[str, str], None, None]:
    page = 1
    page_count = 2
    while page < page_count:
        scenarios = session.get(
            f"{answers['url']}/projects/{project_id}/studies/{study_id}/scenarios?page={page}"
        ).json()
        page = scenarios.get("current")
        page_count = scenarios.get("page_count")
        for scenario in scenarios.get("results"):
            yield (scenario.get("name"), scenario.get("id"))
    return


def validate_url(url: str) -> bool:
    try:
        session.get(url)
        return True
    except Exception as e:
        raise inquirer.errors.ValidationError(
            url,
            "Can't connect to the API. Did you set up 'GATEWAY_TOKEN' and 'REQUESTS_CA_BUNDLE'?",
        )


def validate_date(s: str) -> bool:
    try:
        datetime.date.fromisoformat(s)
        return True
    except:
        return False


questions = [
    inquirer.List(
        "url",
        message="Choose from which environment to extract trains",
        choices=[
            ("prd", "https://osrd.reseau.sncf.fr/api"),
            ("rec", "https://rec-osrd.reseau.sncf.fr/api"),
            ("dev", "https://dev-osrd.reseau.sncf.fr/api"),
            ("local", "http://localhost:4000/api"),
        ],
        validate=lambda _, answer: validate_url(answer),
    ),
    inquirer.List(
        "from_timetable_method",
        message="Select the method to find the timetable from which train should be extracted",
        choices=[
            ("From STDCM search environment", "stdcm"),
            ("From a specific scenario", "scenario"),
        ],
    ),
    inquirer.List(
        "from_project",
        message="Select the project where are the trains to extract",
        choices=lambda _: list(list_projects()),
        ignore=lambda answers: answers["from_timetable_method"] != "scenario",
    ),
    inquirer.List(
        "from_study",
        message="Select the study where are the trains to extract",
        choices=lambda answers: list(list_studies(answers["from_project"])),
        ignore=lambda answers: answers["from_timetable_method"] != "scenario",
    ),
    inquirer.List(
        "from_scenario",
        message="Select the scenario where are the trains to extract",
        choices=lambda answers: list(
            list_scenarios(answers["from_project"], answers["from_study"])
        ),
        ignore=lambda answers: answers["from_timetable_method"] != "scenario",
    ),
    inquirer.List(
        "extraction_method",
        message="Select the method to extract trains",
        choices=[("Train names", "from_train_names")],
    ),
    inquirer.Editor(
        "train_names",
        message="List all the train names you want to extract (one per line)",
        ignore=lambda answers: answers["extraction_method"] != "from_train_names",
    ),
    inquirer.Text(
        "extraction_date",
        message="Give the date of the trains to extract (YYYY-MM-DD)",
        validate=lambda _, answer: validate_date(answer),
    ),
    inquirer.List(
        "to_method",
        message="Select what you want to do with those trains",
        choices=[
            ("Create a new scenario", "scenario"),
            ("Export a JSON timetable", "json"),
        ],
    ),
    inquirer.Text(
        "project_name",
        message="Project's name to extract to",
        default=os.environ.get("USER"),
        ignore=lambda answers: answers["to_method"] != "scenario",
    ),
    inquirer.Text(
        "study_name",
        message="Study's name to extract to",
        default="debug",
        ignore=lambda answers: answers["to_method"] != "scenario",
    ),
    inquirer.Text(
        "scenario_name",
        message="Scenario's name to extract to",
        default=datetime.datetime.now().date(),
        ignore=lambda answers: answers["to_method"] != "scenario",
    ),
    inquirer.Path(
        "to_path",
        message="Give the path of the JSON timetable to export",
        path_type=inquirer.Path.FILE,
        ignore=lambda answers: answers["to_method"] != "json",
    ),
]
answers: dict[str, str] = inquirer.prompt(questions)


def timetable_infra_from_stdcm() -> tuple[str, str]:
    search_environment = session.get(
        f"{answers['url']}/stdcm/search_environment"
    ).json()
    return search_environment.get("timetable_id"), search_environment.get("infra_id")


def timetable_infra_from_scenario(
    project_id: str, study_id: str, scenario_id: str
) -> tuple[str, str]:
    scenario = session.get(
        f"{answers['url']}/projects/{project_id}/studies/{study_id}/scenarios/{scenario_id}"
    ).json()
    return scenario.get("timetable_id"), scenario.get("infra_id")


timetable_id, infra_id = None, None
match answers["from_timetable_method"]:
    case "stdcm":
        timetable_id, infra_id = timetable_infra_from_stdcm()
    case "scenario":
        timetable_id, infra_id = timetable_infra_from_scenario(
            answers["from_project"], answers["from_study"], answers["from_scenario"]
        )

assert timetable_id is not None
assert infra_id is not None
print(
    colored("✨", "yellow"),
    f"Extraction from timetable '{timetable_id}' with infra '{infra_id}'",
)


def extract_from_train_names(
    train_names: list[str],
) -> collections.abc.Generator[dict[str, str], None, None]:
    for train_name in train_names:
        search_body = {
            "object": "trainschedule",
            "query": [
                "and",
                ["=", ["timetable_id"], timetable_id],
                ["=", ["train_name"], train_name.strip()],
            ],
        }
        train_schedules = session.post(
            f"{answers['url']}/search", json=search_body
        ).json()
        print(
            colored("🔎", "blue"),
            f"{len(train_schedules)} found in the timetable",
        )
        extract_date = datetime.date.fromisoformat(answers["extraction_date"])
        train_schedules = [
            train_schedule
            for train_schedule in train_schedules
            if datetime.datetime.fromisoformat(train_schedule.get("start_time")).date()
            == extract_date
        ]
        for train_schedule in train_schedules:
            train_schedule.pop("id")
            train_schedule.pop("timetable_id")
            match train_schedule.get("comfort"):
                case 0:
                    train_schedule.update({"comfort": "STANDARD"})
                case 1:
                    train_schedule.update({"comfort": "AIR_CONDITIONING"})
                case 2:
                    train_schedule.update({"comfort": "HEATING"})
                case _:
                    print(
                        colored("❌", "red"),
                        f"unknown comfort value, ignoring the train '{train_name}'",
                    )
                    continue
            match train_schedule.get("constraint_distribution"):
                case 0:
                    train_schedule.update({"constraint_distribution": "STANDARD"})
                case 1:
                    train_schedule.update({"constraint_distribution": "MARECO"})
                case _:
                    print(
                        colored("❌", "red"),
                        f"unknown constraint_distribution value, ignoring the train '{train_name}'",
                    )
                    continue
            yield train_schedule
    return


match answers["extraction_method"]:
    case "from_train_names":
        train_schedules = extract_from_train_names(answers["train_names"].splitlines())


def create_project(project_name: str) -> tuple[str, dict[str, str]]:
    search_body = {"object": "project", "query": ["=", ["name"], project_name]}
    projects = session.post(f"{answers['url']}/search", json=search_body).json()
    if len(projects) > 0:
        project = projects[0]
        print(
            colored("🔎", "blue"),
            f"Project '{project_name}' already exists",
        )
    else:
        project_body = {
            "budget": 0,
            "description": "",
            "funders": "",
            "image": None,
            "name": project_name,
            "objectives": "",
            "tags": [],
        }
        project = session.post(f"{answers['url']}/projects", json=project_body).json()
        print(
            colored("💾", "green"),
            f"Project '{project_name}' created",
        )

    project_id = project.get("id")
    return project_id, project


def create_study(project_id: str, study_name: str) -> tuple[str, dict[str, str]]:
    search_body = {
        "object": "study",
        "query": [
            "and",
            ["=", ["project_id"], project_id],
            ["search", ["name"], study_name],
        ],
    }
    studies = session.post(f"{answers['url']}/search", json=search_body).json()
    if len(studies) > 0:
        study = studies[0]
        print(
            colored("🔎", "blue"),
            f"Study '{study_name}' already exists",
        )
    else:
        study_body = {
            "actual_end_date": None,
            "budget": 0,
            "business_code": "",
            "description": "",
            "expected_end_date": None,
            "name": study_name,
            "service_code": "",
            "start_date": None,
            "state": "started",
            "study_type": "",
            "tags": [],
        }
        study = session.post(
            f"{answers['url']}/projects/{project_id}/studies",
            json=study_body,
        ).json()
        print(
            colored("💾", "green"),
            f"Study '{study_name}' created",
        )

    study_id = study.get("id")
    return study_id, study


def create_scenario(
    project_id: str, study_id: str, scenario_name: str
) -> tuple[str, dict[str, str]]:
    timetable = session.post(f"{answers['url']}/timetable").json()
    new_timetable_id = timetable.get("timetable_id")
    scenario_body = {
        "description": "",
        "electrical_profile_set_id": 2,
        "infra_id": infra_id,
        "name": scenario_name,
        "tags": [],
        "timetable_id": new_timetable_id,
    }
    scenario = session.post(
        f"{answers['url']}/projects/{project_id}/studies/{study_id}/scenarios",
        json=scenario_body,
    ).json()
    print(
        colored("💾", "green"),
        f"Scenario '{scenario_name}' created",
    )

    scenario_id = scenario.get("id")
    return scenario_id, scenario


def to_scenario(train_schedules: list[dict[str, str]]):
    to_project_name = answers["project_name"]
    to_study_name = answers["study_name"]
    to_scenario_name = answers["scenario_name"]

    project_id, _ = create_project(to_project_name)
    study_id, _ = create_study(project_id, to_study_name)
    _, scenario = create_scenario(project_id, study_id, to_scenario_name)
    timetable_id = scenario["timetable_id"]

    created = session.post(
        f"{answers['url']}/timetable/{timetable_id}/train_schedules",
        json=train_schedules,
    ).json()
    print(
        colored("📤", "green"),
        f"{len(created)} train schedules exported to the new timetable",
    )


def to_json(train_schedules: list[dict[str, str]]):
    path = answers["to_path"]
    with open(path, "w") as f:
        json.dump({"train_schedules": train_schedules, "paced_trains": []}, f)


train_schedules = list(train_schedules)
match answers["to_method"]:
    case "scenario":
        to_scenario(train_schedules)
    case "json":
        to_json(train_schedules)
