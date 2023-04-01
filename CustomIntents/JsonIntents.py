import json
from collections import OrderedDict
from time import perf_counter

import numpy as np


class JsonIntents:
    def __init__(self, json_file_adrees):
        self.json_file_adress = json_file_adrees
        self.json_file = None
        if json_file_adrees.endswith(".json"):
            self.load_json_intents(json_file_adrees)

    def load_json_intents(self, json_file_adress):
        self.json_file = json.loads(open(json_file_adress).read())

    def add_pattern_app(self, tag=None):
        intents = self.json_file
        if tag is None:
            for counter, _ in enumerate(intents["intents"]):
                while True:
                    new_term = input(intents["intents"][counter]["tag"] + " : ")
                    if new_term.upper() == "D":
                        break
                    elif any(str(obj).lower() == new_term.lower() for obj in intents["intents"][counter]["patterns"]):
                        print("it exist ! ")
                    elif new_term.isspace() or new_term == "":
                        print("type a valid intent ! ")
                    else:
                        intents["intents"][counter]["patterns"] = list(intents["intents"][counter]["patterns"]).__add__(
                            [new_term])
                        print("added")
        else:
            tag_counter = 0
            for _ in (intents["intents"]):
                if intents["intents"][tag_counter]["tag"] == tag:
                    break
                else:
                    tag_counter += 1

            while True:
                new_term = input(intents["intents"][tag_counter]["tag"] + " : ")
                if new_term.upper() == "D":
                    break
                elif any(str(obj).lower() == new_term.lower() for obj in intents["intents"][tag_counter]["patterns"]):
                    print("it exist ! ")
                elif new_term.isspace() or new_term == "":
                    print("type a valid intent ! ")
                else:
                    intents["intents"][tag_counter]["patterns"] = list(
                        intents["intents"][tag_counter]["patterns"]).__add__([new_term])
                    print("added")


        with open(self.json_file_adress, "w") as out_file:
            json.dump(intents, out_file)
        print("intents updated ! ")
        self.load_json_intents(self.json_file_adress)

    def delete_duplicate_app(self):
        intents = self.json_file
        for counter, _ in enumerate(intents["intents"]):
            intents["intents"][counter]["patterns"] = list(
                OrderedDict.fromkeys(intents["intents"][counter]["patterns"]))
        with open(self.json_file_adress, "w") as out_file:
            json.dump(intents, out_file)
        self.load_json_intents(self.json_file_adress)

    def add_tag_app(self, tag=None, responses=None):
        json_file = self.json_file
        if tag is None and responses is None:
            new_tag = input("what should the tag say ? ")
            responses = []
            while True:
                new_response = input("add a response for it : (d for done) ")
                if new_response.lower() == "d":
                    break
                else:
                    responses.append(new_response)
        elif tag is None:
            new_tag = input("what should the tag say ? ")
        elif responses is None:
            new_tag = tag
            responses = []
            while True:
                new_response = input("add a response for it : (d for done) ")
                if new_response.lower() == "d":
                    break
                else:
                    responses.append(new_response)
        else:
            new_tag = tag

        json_file["intents"] = list(json_file["intents"]).__add__(
            [{"tag": [new_tag], "patterns": [], "responses": responses}])
        with open(self.json_file_adress, "w") as out_file:
            json.dump(json_file, out_file)
        print("new tag added !")
        self.load_json_intents(self.json_file_adress)
