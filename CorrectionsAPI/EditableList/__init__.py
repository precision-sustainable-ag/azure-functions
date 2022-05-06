import json
import logging
import os
import sys
import traceback

import azure.functions as func
import mysql.connector
import pandas as pd
import psycopg2
import sqlalchemy
from psycopg2 import sql

from ..SharedFunctions import authenticator


class EditableList:
    def __init__(self, req):
        self.connect_to_shadow_live()

        try:
            req_body = req.get_json()
        except ValueError:
            pass
        else:
            self.token = req_body.get('token')
            self.version = req_body.get('version')

    def authenticate(self):
        authenticated, response = authenticator.authenticate(self.token)
        if not authenticated:
            return False, response
        else:
            return True, response

    def connect_to_shadow_live(self):
        postgres_host = os.environ.get('LIVE_HOST')
        postgres_dbname = os.environ.get('LIVE_SHADOW_DBNAME')
        postgres_user = os.environ.get('LIVE_USER')
        postgres_password = os.environ.get('LIVE_PASSWORD')
        postgres_sslmode = os.environ.get('LIVE_SSLMODE')

        # Make postgres connections
        postgres_con_string = "host={0} user={1} dbname={2} password={3} sslmode={4}".format(
            postgres_host, postgres_user, postgres_dbname, postgres_password, postgres_sslmode)
        # print(postgres_con_string)
        self.shadow_con = psycopg2.connect(postgres_con_string)
        self.shadow_cur = self.shadow_con.cursor()
        self.shadow_con.autocommit = True

        postgres_engine_string = "postgresql://{0}:{1}@{2}/{3}".format(
            postgres_user, postgres_password, postgres_host, postgres_dbname)
        self.shadow_engine = sqlalchemy.create_engine(postgres_engine_string)

        print("connected to shadow live")

    def fetch_editable_list(self):
        editable_list = pd.DataFrame(pd.read_sql(
            "SELECT editable_list, entry_to_iterate, iterator_editable_list, table_names FROM editable_list_by_version WHERE version = '{}'".format(self.version), self.shadow_engine))
        return editable_list


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    try:
        el = EditableList(req)

        authenticated, response = el.authenticate()
        if not authenticated:
            return func.HttpResponse(json.dumps(response), headers={'content-type': 'application/json'}, status_code=400)

        editable_list = el.fetch_editable_list()

        if editable_list.empty:
            return func.HttpResponse(json.dumps({"message": "no version in shadow db"}), headers={'content-type': 'application/json'}, status_code=400)

        return_obj = {
            "editable_list": editable_list.iloc[0].get("editable_list"),
            "entry_to_iterate": editable_list.iloc[0].get("entry_to_iterate"),
            "iterator_editable_list": editable_list.iloc[0].get("iterator_editable_list"),
            "table_names": editable_list.iloc[0].get("table_names"),
        }

        return func.HttpResponse(body=json.dumps(return_obj), headers={'content-type': 'application/json'}, status_code=200)

    except Exception:
        error = traceback.format_exc()
        logging.error(error)
        return func.HttpResponse(error, status_code=400)