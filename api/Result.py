from flask import json


class Result(object):
    def __init__(self, data, message):
        self.data = data  # info 0,warning 1,error 2
        self.message = message

    def to_json(self):
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)
