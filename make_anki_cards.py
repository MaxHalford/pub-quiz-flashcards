import datetime as dt
import json
import pathlib

cards = pathlib.Path("cards.txt").open("w")
date_urls = json.load(pathlib.Path("the_guardian/date_urls.json").open())

for week in pathlib.Path("the_guardian").glob("*/*/*.json"):
    date = dt.date(*map(int, (part.replace(".json", "") for part in week.parts[-3:])))
    with open(week) as f:
        for question, answer in json.load(f).items():
            cards.write(f"{question}\t{answer}\t{date_urls[date.isoformat()]}\n")
